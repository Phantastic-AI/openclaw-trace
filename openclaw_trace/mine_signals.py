from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from .llm_client import LLMClient, NoLLMClient, OpenAICompatClient
from .transcript import Transcript, load_transcript

Json = dict[str, Any]


ALLOWED_KINDS = {
    "error",
    "user_frustration",
    "improvement_suggestion",
    "experiment_suggestion",
    "proactive_opportunity",
    "user_delight",
    "other",
}

ALLOWED_SEVERITIES = {"low", "medium", "high", "critical", "unknown"}


@dataclass
class MineSignalsConfig:
    sessions_dir: Path
    include: list[str]
    exclude: list[str]
    max_sessions: int | None = None
    chunk_events: int = 20
    chunk_overlap: int = 4
    max_text_chars: int = 800
    max_items_per_chunk: int = 10
    max_evidence_per_item: int = 2
    max_summary_chars: int = 120
    max_quote_chars: int = 200
    use_llm: bool = True
    temperature: float = 0.0


@dataclass
class EventView:
    i: int
    ts: Optional[str]
    role: str
    tool: Optional[str]
    status: Optional[str]
    error_code: Optional[str]
    text: str
    text_truncated: bool
    raw_shape: Optional[str]

    def to_prompt_dict(self) -> Json:
        return {
            "i": self.i,
            "ts": self.ts,
            "role": self.role,
            "tool": self.tool,
            "status": self.status,
            "error_code": self.error_code,
            "text": self.text,
            "text_truncated": self.text_truncated,
            "raw_shape": self.raw_shape,
        }


def redact_text(text: str) -> str:
    """PII redaction stub (no-op in v1)."""
    return text


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    text = text.strip()
    if max_chars <= 0:
        return "", bool(text)
    if len(text) <= max_chars:
        return text, False
    return text[: max_chars - 3].rstrip() + "...", True


_SALIENT_RE = re.compile(
    r"\b(traceback|exception|error|failed|failure|timeout|timed out|not found|invalid|permission denied|exit code|stack trace)\b",
    re.I,
)


def _digest_text(text: str, max_chars: int) -> tuple[str, bool]:
    text = text.strip()
    if len(text) <= max_chars:
        return text, False

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    salient: list[str] = []
    for ln in lines:
        if _SALIENT_RE.search(ln):
            salient.append(ln)

    chosen: list[str] = []
    if lines:
        chosen.append(lines[0])
        if len(lines) > 1:
            chosen.append(lines[-1])

    for ln in salient:
        if ln not in chosen:
            chosen.append(ln)

    digest = "\n".join(chosen).strip()
    digest, truncated = _truncate(digest, max_chars)
    if truncated:
        # Fallback: head+tail when digest still too large or empty.
        half = max_chars // 2
        head = text[:half].rstrip()
        tail = text[-half:].lstrip() if half > 0 else ""
        combined = (head + "\n...\n" + tail).strip()
        combined, truncated2 = _truncate(combined, max_chars)
        return combined, truncated2

    return digest, True


def _msg(ev: Json) -> Json | None:
    m = ev.get("message")
    return m if isinstance(m, dict) else None


def _content_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        parts: list[str] = []
        for item in v:
            if isinstance(item, str):
                if item:
                    parts.append(item)
                continue
            if isinstance(item, dict):
                t = item.get("text")
                if isinstance(t, str) and t:
                    parts.append(t)
                    continue
                try:
                    parts.append(json.dumps(item, ensure_ascii=False)[:2000])
                except Exception:
                    parts.append(str(item)[:2000])
                continue
            parts.append(str(item)[:2000])
        return "\n".join(p for p in parts if p)
    if isinstance(v, dict):
        for k in ("text", "error", "stderr", "stdout", "output"):
            t = v.get(k)
            if isinstance(t, str) and t:
                return t
        try:
            return json.dumps(v, ensure_ascii=False)[:4000]
        except Exception:
            return str(v)[:4000]
    return str(v)[:4000]


def _iter_session_files(cfg: MineSignalsConfig) -> list[Path]:
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


def _is_metadata_event(ev: Json) -> bool:
    if _msg(ev):
        return False
    t = ev.get("type")
    if isinstance(t, str) and t in {"session", "heartbeat", "meta", "metadata"}:
        return True
    return False


def _event_role(ev: Json) -> str:
    if ev.get("_parse_error"):
        return "parse_error"
    m = _msg(ev)
    if m and isinstance(m.get("role"), str):
        return m.get("role")
    role = ev.get("role")
    if isinstance(role, str):
        return role
    return "other"


def _event_tool(ev: Json) -> Optional[str]:
    m = _msg(ev)
    if m and isinstance(m.get("toolName"), str):
        return m.get("toolName")
    for k in ("tool", "tool_name", "toolName", "name"):
        v = ev.get(k)
        if isinstance(v, str) and v:
            return v
    return None


def _event_status(ev: Json) -> Optional[str]:
    m = _msg(ev)
    if m and isinstance(m.get("details"), dict):
        status = m.get("details", {}).get("status")
        if isinstance(status, str):
            return status
    status = ev.get("status")
    return status if isinstance(status, str) else None


def _event_error_code(ev: Json) -> Optional[str]:
    m = _msg(ev)
    details = m.get("details") if m and isinstance(m.get("details"), dict) else {}

    for k in ("error_code", "errorCode", "code"):
        v = details.get(k) if isinstance(details, dict) else None
        if isinstance(v, str) and v:
            return v

    for k in ("error_code", "errorCode", "code"):
        v = ev.get(k)
        if isinstance(v, str) and v:
            return v

    exit_code = None
    if isinstance(details, dict):
        exit_code = details.get("exitCode")
    if exit_code is None:
        exit_code = ev.get("exitCode")
    if isinstance(exit_code, int) and exit_code != 0:
        return f"EXIT_{exit_code}"

    return None


def _event_text_digest(ev: Json, role: str, tool: Optional[str], max_chars: int) -> tuple[str, bool, Optional[str]]:
    m = _msg(ev)
    raw_shape = None
    parts: list[str] = []

    if role == "parse_error":
        raw_shape = "_parse_error"
        parts.append(str(ev.get("_parse_error", "")))
        raw = "\n".join(p for p in parts if p)
        raw = redact_text(raw)
        return _digest_text(raw, max_chars) + (raw_shape,)  # type: ignore[return-value]

    if m and isinstance(m, dict):
        if role in {"user", "assistant", "system"}:
            raw_shape = "message.content"
            parts.append(_content_text(m.get("content")))
        elif role == "toolResult":
            raw_shape = "message.details+content"
            details = m.get("details") if isinstance(m.get("details"), dict) else {}
            if tool:
                parts.append(f"tool={tool}")
            if isinstance(details, dict):
                status = details.get("status")
                if isinstance(status, str):
                    parts.append(f"status={status}")
                exit_code = details.get("exitCode")
                if isinstance(exit_code, int):
                    parts.append(f"exitCode={exit_code}")
                err = details.get("error")
                if err:
                    parts.append(f"error={err}")
                for k in ("stderr", "stdout", "aggregated"):
                    v = details.get(k)
                    if isinstance(v, str) and v:
                        parts.append(v)
            parts.append(_content_text(m.get("content")))
        elif role == "toolCall":
            raw_shape = "message.input"
            parts.append(_content_text(m.get("input")))
            parts.append(_content_text(m.get("content")))
        else:
            raw_shape = "message.content"
            parts.append(_content_text(m.get("content")))

    if not parts:
        raw_shape = raw_shape or "event"
        for k in ("content", "text", "error", "stderr", "stdout"):
            v = ev.get(k)
            if isinstance(v, str) and v:
                parts.append(v)

    raw = "\n".join(p for p in parts if p).strip()
    raw = redact_text(raw)
    if not raw:
        return "", False, raw_shape

    digest, truncated = _digest_text(raw, max_chars)
    return digest, truncated, raw_shape


def _build_event_views(transcript: Transcript, cfg: MineSignalsConfig) -> list[EventView]:
    views: list[EventView] = []
    for i in range(transcript.n):
        ev = transcript.event(i)
        if _is_metadata_event(ev):
            continue
        role = _event_role(ev)
        tool = _event_tool(ev)
        status = _event_status(ev)
        error_code = _event_error_code(ev)
        ts = ev.get("timestamp") if isinstance(ev.get("timestamp"), str) else None
        text, truncated, raw_shape = _event_text_digest(ev, role, tool, cfg.max_text_chars)
        if not text and role == "other":
            # Skip empty non-message events.
            continue
        views.append(
            EventView(
                i=i,
                ts=ts,
                role=role,
                tool=tool,
                status=status,
                error_code=error_code,
                text=text,
                text_truncated=truncated,
                raw_shape=raw_shape,
            )
        )
    return views


def _should_extend_boundary(prev: EventView, nxt: EventView) -> bool:
    if prev.role == "toolCall" and nxt.role == "toolResult":
        return True
    if prev.role == "toolResult" and nxt.role == "assistant":
        return True
    if prev.role == "user" and nxt.role == "assistant":
        return True
    return False


def _chunk_event_views(views: list[EventView], cfg: MineSignalsConfig) -> list[dict[str, Any]]:
    if not views or cfg.chunk_events <= 0:
        return []

    overlap = max(0, min(cfg.chunk_overlap, cfg.chunk_events - 1))
    step = max(1, cfg.chunk_events - overlap)

    chunks: list[dict[str, Any]] = []
    start = 0
    chunk_idx = 0
    n = len(views)

    while start < n:
        end = min(n, start + cfg.chunk_events)
        if end < n:
            prev = views[end - 1]
            nxt = views[end]
            if _should_extend_boundary(prev, nxt):
                end = min(n, end + 1)

        chunk_views = views[start:end]
        if not chunk_views:
            break
        chunks.append(
            {
                "chunk_id": f"chunk:{chunk_idx}",
                "start_i": chunk_views[0].i,
                "end_i": chunk_views[-1].i,
                "views": chunk_views,
            }
        )
        chunk_idx += 1

        if end >= n:
            break
        start = max(0, end - overlap)
        if start < 0:
            start = 0
        if start >= n:
            break
        if start == end:
            start = end + step

    return chunks


def _llm_prompt(chunk: dict[str, Any], cfg: MineSignalsConfig) -> tuple[str, str]:
    system = (
        "You are a trace-mining classifier. Extract self-improvement signals from events. "
        "Return ONLY strict JSON: {\"items\": [...]} with no extra text. "
        "Kinds: error, user_frustration, improvement_suggestion, experiment_suggestion, proactive_opportunity, user_delight, other. "
        "proactive_opportunity = new proactive action the system should do; user_delight = opportunity to wow/delight. "
        "If user mentions an incident report, add tag 'incident'. "
        "Evidence quotes must be exact substrings of events[].text. "
        "Do not include PII; text is already redacted."
    )

    constraints = {
        "max_items_per_chunk": cfg.max_items_per_chunk,
        "max_evidence_per_item": cfg.max_evidence_per_item,
        "max_summary_chars": cfg.max_summary_chars,
        "max_quote_chars": cfg.max_quote_chars,
        "allowed_kinds": sorted(ALLOWED_KINDS),
        "allowed_severities": sorted(ALLOWED_SEVERITIES),
    }

    schema = {
        "items": [
            {
                "kind": "error",
                "summary": "one line <= 120 chars",
                "severity": "low|medium|high|critical|unknown",
                "confidence": 0.0,
                "tags": ["string"],
                "evidence": [
                    {
                        "event_i": 0,
                        "role": "user|assistant|toolResult|toolCall|system|other",
                        "field_path": "text",
                        "quote": "exact substring from events[i].text",
                    }
                ],
                "proposed_fix": {
                    "fix_type": "prompt|code|process|dependency|eval|other",
                    "description": "concise fix",
                },
            }
        ]
    }

    payload = {
        "chunk_id": chunk.get("chunk_id"),
        "constraints": constraints,
        "schema": schema,
        "events": [v.to_prompt_dict() for v in chunk.get("views", [])],
    }

    user = json.dumps(payload, ensure_ascii=False, indent=2)
    return system, user


def _safe_json_from_llm(text: str) -> Json | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _hash_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _normalize_tag(tag: Any) -> Optional[str]:
    if not isinstance(tag, str):
        return None
    t = tag.strip().lower()
    if not t:
        return None
    if len(t) > 64:
        t = t[:64]
    return t


def _quote_within(text: str, quote: str, max_chars: int) -> Optional[str]:
    quote = quote.strip()
    if not quote:
        return None
    if len(quote) > max_chars:
        quote = quote[:max_chars].rstrip()
    if quote and quote in text:
        return quote
    return None


def _validate_item(
    item: Json,
    event_map: dict[int, EventView],
    cfg: MineSignalsConfig,
    session_id: str,
    file_hint: str,
    chunk_id: str,
) -> Optional[Json]:
    if not isinstance(item, dict):
        return None

    kind = item.get("kind")
    if not isinstance(kind, str):
        return None
    kind = kind.strip()
    if kind not in ALLOWED_KINDS:
        return None

    summary = item.get("summary")
    if not isinstance(summary, str):
        return None
    summary = summary.strip()
    if not summary:
        return None
    summary, _ = _truncate(summary, cfg.max_summary_chars)

    evidence = item.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return None

    evidence = evidence[: cfg.max_evidence_per_item]
    validated_evidence: list[Json] = []
    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        event_i = ev.get("event_i")
        if not isinstance(event_i, int):
            continue
        view = event_map.get(event_i)
        if view is None:
            continue
        quote = ev.get("quote")
        if not isinstance(quote, str):
            continue
        quote = _quote_within(view.text, quote, cfg.max_quote_chars)
        if not quote:
            continue
        role = ev.get("role")
        if not isinstance(role, str):
            role = view.role
        field_path = ev.get("field_path")
        if not isinstance(field_path, str):
            field_path = "text"
        validated_evidence.append(
            {
                "event_i": event_i,
                "role": role,
                "field_path": field_path,
                "quote": quote,
            }
        )

    if not validated_evidence:
        return None

    severity = item.get("severity")
    if not isinstance(severity, str):
        severity = "unknown"
    severity = severity.lower().strip()
    if severity not in ALLOWED_SEVERITIES:
        severity = "unknown"

    confidence = item.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = 0.5
    confidence = float(confidence)
    if confidence < 0.0 or confidence > 1.0:
        confidence = 0.5

    tags_in = item.get("tags")
    tags: list[str] = []
    if isinstance(tags_in, list):
        for t in tags_in:
            nt = _normalize_tag(t)
            if nt:
                tags.append(nt)

    # Add incident tag if mentioned.
    if "incident" in summary.lower() or any("incident" in ev.get("quote", "").lower() for ev in validated_evidence):
        if "incident" not in tags:
            tags.append("incident")

    proposed_fix = item.get("proposed_fix")
    if not isinstance(proposed_fix, dict):
        proposed_fix = None
    else:
        desc = proposed_fix.get("description")
        if not isinstance(desc, str) or not desc.strip():
            proposed_fix = None

    span_start = min(ev["event_i"] for ev in validated_evidence)
    span_end = max(ev["event_i"] for ev in validated_evidence)

    dedupe_seed = json.dumps(
        {
            "session_id": session_id,
            "kind": kind,
            "summary": summary,
            "quotes": [ev["quote"] for ev in validated_evidence],
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    item_id = f"sha256:{_hash_str(dedupe_seed)}"

    return {
        "schema_version": 1,
        "item_id": item_id,
        "session_id": session_id,
        "source": {"file_hint": file_hint, "chunk_id": chunk_id},
        "kind": kind,
        "summary": summary,
        "severity": severity,
        "confidence": confidence,
        "tags": tags,
        "span": {"start_i": span_start, "end_i": span_end},
        "evidence": validated_evidence,
        "proposed_fix": proposed_fix,
    }


def _heuristic_extract(chunk: dict[str, Any], cfg: MineSignalsConfig) -> list[Json]:
    views: list[EventView] = chunk.get("views", [])
    items: list[Json] = []

    frustration_re = re.compile(r"\b(confus(ed|ing)|frustrat(ed|ing)|dont understand|do not understand|wtf|not what i meant)\b", re.I)
    improve_re = re.compile(r"\b(we should|should we|suggest|improve|fix|add|change|avoid)\b", re.I)
    experiment_re = re.compile(r"\b(experiment|ablation|benchmark|eval|evaluation|hypothesis)\b", re.I)
    opportunity_re = re.compile(
        r"\b(reach out|outreach|share|publish|demo|hackathon|community|partner(ship)?|collab(orate)?|announce|publicize)\b",
        re.I,
    )
    delight_re = re.compile(r"\b(delight|wow|surprise|magical|polish|lovely|make it feel)\b", re.I)

    for view in views:
        text = view.text
        if not text:
            continue

        if view.role == "toolResult":
            if (view.status and view.status.lower() == "error") or (view.error_code and view.error_code.startswith("EXIT_")):
                items.append(
                    {
                        "kind": "error",
                        "summary": _truncate(text.splitlines()[0], cfg.max_summary_chars)[0],
                        "severity": "medium",
                        "confidence": 0.4,
                        "tags": [f"tool:{view.tool}"] if view.tool else [],
                        "evidence": [
                            {
                                "event_i": view.i,
                                "role": view.role,
                                "field_path": "text",
                                "quote": _truncate(text, cfg.max_quote_chars)[0],
                            }
                        ],
                    }
                )
                continue

        if view.role == "user" and frustration_re.search(text):
            items.append(
                {
                    "kind": "user_frustration",
                    "summary": _truncate(text.splitlines()[0], cfg.max_summary_chars)[0],
                    "severity": "medium",
                    "confidence": 0.4,
                    "tags": ["frustration"],
                    "evidence": [
                        {
                            "event_i": view.i,
                            "role": view.role,
                            "field_path": "text",
                            "quote": _truncate(text, cfg.max_quote_chars)[0],
                        }
                    ],
                }
            )
            continue

        if experiment_re.search(text):
            items.append(
                {
                    "kind": "experiment_suggestion",
                    "summary": _truncate(text.splitlines()[0], cfg.max_summary_chars)[0],
                    "severity": "low",
                    "confidence": 0.3,
                    "tags": ["experiment"],
                    "evidence": [
                        {
                            "event_i": view.i,
                            "role": view.role,
                            "field_path": "text",
                            "quote": _truncate(text, cfg.max_quote_chars)[0],
                        }
                    ],
                }
            )
            continue

        if opportunity_re.search(text):
            items.append(
                {
                    "kind": "proactive_opportunity",
                    "summary": _truncate(text.splitlines()[0], cfg.max_summary_chars)[0],
                    "severity": "low",
                    "confidence": 0.3,
                    "tags": ["opportunity"],
                    "evidence": [
                        {
                            "event_i": view.i,
                            "role": view.role,
                            "field_path": "text",
                            "quote": _truncate(text, cfg.max_quote_chars)[0],
                        }
                    ],
                }
            )
            continue

        if delight_re.search(text):
            items.append(
                {
                    "kind": "user_delight",
                    "summary": _truncate(text.splitlines()[0], cfg.max_summary_chars)[0],
                    "severity": "low",
                    "confidence": 0.3,
                    "tags": ["delight"],
                    "evidence": [
                        {
                            "event_i": view.i,
                            "role": view.role,
                            "field_path": "text",
                            "quote": _truncate(text, cfg.max_quote_chars)[0],
                        }
                    ],
                }
            )
            continue

        if improve_re.search(text):
            items.append(
                {
                    "kind": "improvement_suggestion",
                    "summary": _truncate(text.splitlines()[0], cfg.max_summary_chars)[0],
                    "severity": "low",
                    "confidence": 0.3,
                    "tags": ["suggestion"],
                    "evidence": [
                        {
                            "event_i": view.i,
                            "role": view.role,
                            "field_path": "text",
                            "quote": _truncate(text, cfg.max_quote_chars)[0],
                        }
                    ],
                }
            )

        if len(items) >= cfg.max_items_per_chunk:
            break

    return items[: cfg.max_items_per_chunk]


def mine_signals(*, llm: LLMClient | None, cfg: MineSignalsConfig) -> tuple[Json, list[Json]]:
    files = _iter_session_files(cfg)
    items_out: list[Json] = []
    sessions_with_items = 0

    if llm is None:
        llm = NoLLMClient()

    for p in files:
        transcript = load_transcript(p)
        views = _build_event_views(transcript, cfg)
        chunks = _chunk_event_views(views, cfg)
        if not chunks:
            continue

        try:
            rel = str(p.relative_to(cfg.sessions_dir))
        except Exception:
            rel = p.name

        session_id = f"sha256:{_hash_str(rel)}"
        file_hint = f"sha256:{_hash_str(rel)}"

        session_items: list[Json] = []

        for chunk in chunks:
            event_map = {v.i: v for v in chunk.get("views", [])}
            chunk_id = chunk.get("chunk_id", "chunk:0")

            if cfg.use_llm and not isinstance(llm, NoLLMClient):
                system, user = _llm_prompt(chunk, cfg)
                resp = llm.complete(system=system, user=user, temperature=cfg.temperature)
                payload = _safe_json_from_llm(resp.text) or {}
                raw_items = payload.get("items") if isinstance(payload, dict) else []
                if not isinstance(raw_items, list):
                    raw_items = []
            else:
                raw_items = _heuristic_extract(chunk, cfg)

            validated: list[Json] = []
            for item in raw_items:
                vi = _validate_item(
                    item,
                    event_map,
                    cfg,
                    session_id=session_id,
                    file_hint=file_hint,
                    chunk_id=f"{session_id}/{chunk_id}",
                )
                if vi:
                    validated.append(vi)

            if validated:
                validated = sorted(validated, key=lambda x: x.get("confidence", 0.0), reverse=True)
                validated = validated[: cfg.max_items_per_chunk]
                session_items.extend(validated)

        if session_items:
            sessions_with_items += 1
            items_out.extend(session_items)

    summary = {
        "mode": "mine-signals",
        "sessionsDir": str(cfg.sessions_dir),
        "include": cfg.include,
        "exclude": cfg.exclude,
        "chunk": {"events": cfg.chunk_events, "overlap": cfg.chunk_overlap},
        "limits": {
            "max_text_chars": cfg.max_text_chars,
            "max_items_per_chunk": cfg.max_items_per_chunk,
            "max_evidence_per_item": cfg.max_evidence_per_item,
            "max_summary_chars": cfg.max_summary_chars,
            "max_quote_chars": cfg.max_quote_chars,
        },
        "llm": {
            "enabled": cfg.use_llm and not isinstance(llm, NoLLMClient),
            "model": llm.model if isinstance(llm, OpenAICompatClient) else None,
        },
        "counts": {
            "sessions_scanned": len(files),
            "sessions_with_items": sessions_with_items,
            "items": len(items_out),
        },
    }

    return summary, items_out
