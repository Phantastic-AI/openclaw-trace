from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .llm_client import LLMClient, NoLLMClient
from .redaction import contains_pii, drop_pii_lines, redact_pii, truncate_snippet
from .transcript import Transcript, load_transcript


Json = dict[str, Any]


DEFAULT_KEYWORDS = [
    "idea",
    "experiment",
    "paper",
    "evaluate",
    "evaluation",
    "benchmark",
    "ablation",
    "failure",
    "failed",
    "timeout",
    "timed out",
    "hallucination",
    "rlm",
    "agent",
    "tool",
    "trace",
    "prompt",
    "dataset",
]


@dataclass
class MineIdeasConfig:
    sessions_dir: Path
    include: list[str]
    exclude: list[str]
    max_sessions: int | None = None
    max_matches_per_session: int = 40
    window_before: int = 4
    window_after: int = 6
    max_snippet_chars: int = 800
    use_llm: bool = True
    temperature: float = 0.0
    scrub_output: bool = True


def _iter_session_files(cfg: MineIdeasConfig) -> list[Path]:
    if not cfg.sessions_dir.exists():
        raise FileNotFoundError(f"sessions dir not found: {cfg.sessions_dir}")

    candidates = [p for p in cfg.sessions_dir.rglob("*.jsonl") if p.is_file()]

    def ok(p: Path) -> bool:
        rel = str(p.relative_to(cfg.sessions_dir))
        if cfg.include and not any(fnmatch.fnmatch(rel, pat) for pat in cfg.include):
            return False
        if cfg.exclude and any(fnmatch.fnmatch(rel, pat) for pat in cfg.exclude):
            return False
        return True

    out = [p for p in candidates if ok(p)]
    out.sort()
    if cfg.max_sessions is not None:
        out = out[: cfg.max_sessions]
    return out


def _event_text(ev: Json) -> str:
    """Best-effort text extraction for mining.

    This intentionally avoids returning huge dumps.
    """
    # Newer Clawdbot shape nests messages.
    m = ev.get("message")
    if isinstance(m, dict):
        role = m.get("role")
        content = m.get("content")
        parts: list[str] = []
        if isinstance(role, str) and role:
            parts.append(f"role={role}")
        if isinstance(content, str):
            if content.strip():
                parts.append(content)
        elif isinstance(content, list):
            # OpenAI content parts
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    t = item.get("text", "")
                    if t.strip():
                        parts.append(t)
                elif isinstance(item, str) and item.strip():
                    parts.append(item)
        # tool result preview
        if not parts:
            for k in ("toolName", "details", "input"):
                v = m.get(k)
                if v is None:
                    continue
                try:
                    parts.append(json.dumps({k: v}, ensure_ascii=False)[:800])
                except Exception:
                    parts.append(str(v)[:800])
        return "\n".join(parts).strip()

    # Fallback: older events may store content at top-level.
    for k in ("content", "text", "error", "stderr", "stdout"):
        v = ev.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    # Last resort: a short JSON dump.
    try:
        return json.dumps(ev, ensure_ascii=False)[:1200]
    except Exception:
        return str(ev)[:1200]


def _segment_synopsis(transcript: Transcript, hit_index: int, cfg: MineIdeasConfig) -> str:
    start = max(0, hit_index - cfg.window_before)
    end = min(transcript.n, hit_index + cfg.window_after)
    lines: list[str] = []
    for i in range(start, end):
        ev = transcript.event(i)
        t = _event_text(ev)
        if not t:
            continue
        # Never include huge raw snippets.
        t = truncate_snippet(t, max_chars=cfg.max_snippet_chars)
        lines.append(f"[{i}] {t}")

    synopsis = "\n".join(lines)
    # NOTE (per ninjaa): do not aggressively pre-scrub before synthesis.
    # This tool is intended for one-time internal runs where idea quality matters.
    # We still enforce snippet truncation to avoid dumping long raw logs.
    synopsis = truncate_snippet(synopsis, max_chars=cfg.max_snippet_chars)
    return synopsis


def _keyword_regex(keywords: Iterable[str]) -> re.Pattern[str]:
    # Build a single regex; escape pieces and allow word boundaries when plausible.
    alts = []
    for kw in keywords:
        kw = kw.strip()
        if not kw:
            continue
        alts.append(re.escape(kw))
    if not alts:
        alts = [re.escape("idea")]
    pat = r"(?:" + "|".join(alts) + r")"
    return re.compile(pat, re.I)


def _llm_prompt_for_idea(synopsis: str) -> tuple[str, str]:
    system = (
        "You propose frontier AI research experiments from a scrubbed transcript synopsis. "
        "The synopsis is already redacted; do not try to infer or reconstruct any private details. "
        "Return ONLY strict JSON with keys: title, hypothesis, method, metrics, synthetic_dataset, why_frontier. "
        "Each value must be a concise string."
    )
    user = (
        "Given this transcript synopsis, propose ONE compelling frontier experiment. "
        "Focus on concrete, testable hypotheses and measurable metrics.\n\n"
        "SYNOPSIS (REDACTED):\n" + synopsis
    )
    return system, user


def _safe_json_from_llm(text: str) -> Json | None:
    # Attempt to extract the first JSON object from the response.
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    return obj


def _sanitize_obj_strings(obj: Any) -> Any:
    """Final safety scrub: if any string contains PII patterns, replace with [REDACTED]."""
    if isinstance(obj, str):
        if contains_pii(obj):
            return "[REDACTED]"
        return obj
    if isinstance(obj, list):
        return [_sanitize_obj_strings(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _sanitize_obj_strings(v) for k, v in obj.items()}
    return obj


def mine_ideas(*, llm: LLMClient | None, cfg: MineIdeasConfig, keywords: list[str] | None = None) -> Json:
    kw = keywords or DEFAULT_KEYWORDS
    pat = _keyword_regex(kw)

    files = _iter_session_files(cfg)

    sessions_out: list[Json] = []
    synthetic_dataset_ideas: list[str] = []

    if llm is None:
        llm = NoLLMClient()

    for p in files:
        transcript = load_transcript(p)

        hits = transcript.search(pat, limit=cfg.max_matches_per_session)
        if not hits:
            continue

        rel = None
        try:
            rel = str(p.relative_to(cfg.sessions_dir))
        except Exception:
            rel = p.name

        session_rec: Json = {
            "session": rel,
            "events": transcript.n,
            "matches": [],
            "ideas": [],
        }

        # Deduplicate nearby hits.
        seen: set[int] = set()
        for idx, _ev in hits:
            if any(abs(idx - s) <= 2 for s in seen):
                continue
            seen.add(idx)
            synopsis = _segment_synopsis(transcript, idx, cfg)

            match_rec = {"index": idx, "synopsis": synopsis}
            session_rec["matches"].append(match_rec)

            if cfg.use_llm and not isinstance(llm, NoLLMClient):
                system, user = _llm_prompt_for_idea(synopsis)
                resp = llm.complete(system=system, user=user, temperature=cfg.temperature)
                idea = _safe_json_from_llm(resp.text) or {
                    "title": "(unparsed)",
                    "hypothesis": "(unparsed)",
                    "method": resp.text[:800],
                    "metrics": "(unparsed)",
                    "synthetic_dataset": "(unparsed)",
                    "why_frontier": "(unparsed)",
                }

                # Optional output scrub (default off): redact any PII-ish strings in outputs.
                if cfg.scrub_output:
                    idea = _sanitize_obj_strings(idea)
                session_rec["ideas"].append(idea)

                sdi = idea.get("synthetic_dataset")
                if isinstance(sdi, str) and sdi and sdi != "[REDACTED]":
                    synthetic_dataset_ideas.append(sdi)

        if session_rec["matches"]:
            sessions_out.append(session_rec)

    out: Json = {
        "mode": "mine-ideas",
        "sessionsDir": str(cfg.sessions_dir),
        "include": cfg.include,
        "exclude": cfg.exclude,
        "keywords": kw,
        "snippets": {"max_snippet_chars": cfg.max_snippet_chars},
        "scrubOutput": cfg.scrub_output,
        "results": sessions_out,
        "synthetic_dataset_ideas": synthetic_dataset_ideas,
    }
    return _sanitize_obj_strings(out) if cfg.scrub_output else out


def render_markdown(report: Json, *, scrub_output: bool | None = None) -> str:
    lines: list[str] = []
    lines.append("# openclaw-trace mine-ideas report")
    lines.append("")
    lines.append(f"- sessionsDir: `{report.get('sessionsDir')}`")
    lines.append(f"- sessionsMatched: `{len(report.get('results', []))}`")
    lines.append("")

    for sess in report.get("results", []):
        if not isinstance(sess, dict):
            continue
        lines.append(f"## Session: `{sess.get('session')}`")
        lines.append("")

        matches = sess.get("matches")
        if isinstance(matches, list) and matches:
            lines.append("### Candidate segments")
            for m in matches:
                if not isinstance(m, dict):
                    continue
                syn = m.get("synopsis")
                idx = m.get("index")
                lines.append(f"- index {idx}:\n\n```\n{syn}\n```\n")

        ideas = sess.get("ideas")
        if isinstance(ideas, list) and ideas:
            lines.append("### Proposed experiment ideas")
            for idea in ideas:
                if not isinstance(idea, dict):
                    continue
                title = idea.get("title", "(untitled)")
                lines.append(f"#### {title}")
                for k, label in [
                    ("hypothesis", "Hypothesis"),
                    ("method", "Method"),
                    ("metrics", "Metrics"),
                    ("synthetic_dataset", "Synthetic dataset"),
                    ("why_frontier", "Why it's frontier"),
                ]:
                    v = idea.get(k)
                    if isinstance(v, str) and v:
                        lines.append(f"- **{label}:** {v}")
                lines.append("")

    sdi = report.get("synthetic_dataset_ideas")
    lines.append("# Synthetic dataset ideas")
    lines.append("")
    if isinstance(sdi, list) and sdi:
        for x in sdi[:200]:
            if isinstance(x, str) and x:
                lines.append(f"- {x}")
    else:
        lines.append("(none)")
    lines.append("")

    md = "\n".join(lines)

    do_scrub = report.get("scrubOutput") if scrub_output is None else scrub_output
    if do_scrub:
        # Redact common patterns, then drop any remaining lines matching PII patterns.
        md = redact_pii(md)
        md2, dropped = drop_pii_lines(md)
        if dropped:
            md2 += f"\n\n> NOTE: Dropped {dropped} line(s) during final PII validation.\n"
        return md2

    return md
