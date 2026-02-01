from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

Json = dict[str, Any]

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "unknown": 0}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://\S+")
TOKEN_RE = re.compile(r"\b(sk-[A-Za-z0-9_-]{8,}|xox[baprs]-\S{6,}|ghp_\S{6,}|AKIA\S{8,})\b")
LONGHEX_RE = re.compile(r"\b[0-9a-fA-F]{16,}\b")
PATH_RE = re.compile(r"/(?:home|Users|var|etc|opt|srv)/[^\s]*")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "by",
    "is",
    "are",
    "was",
    "were",
    "be",
    "this",
    "that",
    "it",
    "as",
    "at",
    "from",
    "into",
    "we",
    "you",
    "they",
    "i",
    "our",
    "your",
    "their",
}


def _redact(text: str) -> str:
    text = EMAIL_RE.sub("[email]", text)
    text = URL_RE.sub("[url]", text)
    text = TOKEN_RE.sub("[token]", text)
    text = LONGHEX_RE.sub("[id]", text)
    text = PATH_RE.sub("[path]", text)
    text = IP_RE.sub("[ip]", text)
    text = PHONE_RE.sub("[phone]", text)
    text = CARD_RE.sub("[fin_id]", text)
    return text


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokens(text: str) -> list[str]:
    tokens = [t for t in _normalize(text).split() if t and t not in STOPWORDS]
    if not tokens:
        tokens = _normalize(text).split()
    return tokens


def _bigrams(tokens: list[str]) -> list[str]:
    if len(tokens) < 2:
        return tokens
    return ["_".join(tokens[i : i + 2]) for i in range(len(tokens) - 1)]


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def signature_v1(item: Json) -> tuple[str, str]:
    kind = (item.get("kind") or "unknown").strip().lower()
    summary = item.get("summary") or ""
    tags = sorted(t for t in (item.get("tags") or []) if isinstance(t, str))
    tokens = _tokens(summary)
    grams = _bigrams(tokens)
    gram_core = " ".join(grams[:6])
    tag_core = ",".join(t[:32].lower() for t in tags[:5])
    sig_text = f"{kind}|{gram_core}|{tag_core}"
    return sig_text, f"sig1:{_hash(sig_text)}"


def _severity_rank(sev: str) -> int:
    return SEVERITY_ORDER.get((sev or "unknown").lower(), 0)


def _tier_for_group(max_sev: str, tag_counts: Counter, kind_counts: Counter) -> tuple[int, list[str]]:
    reasons: list[str] = []
    if tag_counts.get("incident", 0) > 0 or _severity_rank(max_sev) >= SEVERITY_ORDER["high"]:
        if tag_counts.get("incident", 0) > 0:
            reasons.append("incident")
        if _severity_rank(max_sev) >= SEVERITY_ORDER["high"]:
            reasons.append(f"severity:{max_sev}")
        return 1, reasons
    if kind_counts.get("error", 0) > 0 or kind_counts.get("user_frustration", 0) > 0 or _severity_rank(max_sev) == SEVERITY_ORDER["medium"]:
        if kind_counts.get("error", 0) > 0:
            reasons.append("kind:error")
        if kind_counts.get("user_frustration", 0) > 0:
            reasons.append("kind:user_frustration")
        if _severity_rank(max_sev) == SEVERITY_ORDER["medium"]:
            reasons.append("severity:medium")
        return 2, reasons
    return 3, ["default"]


def _score_group(*, count_items: int, max_sev: str, tag_counts: Counter, kind_counts: Counter) -> float:
    sev = _severity_rank(max_sev)
    score = math.log1p(count_items) + sev
    if tag_counts.get("incident", 0) > 0:
        score += 2.0
    if kind_counts.get("error", 0) > 0:
        score += 0.3
    if kind_counts.get("user_frustration", 0) > 0:
        score += 0.2
    return score


def _classify_kind_v2(item: Json) -> tuple[str, str]:
    kind = (item.get("kind") or "").lower()
    summary = (item.get("summary") or "").lower()
    tags = set(t.lower() for t in (item.get("tags") or []) if isinstance(t, str))

    def has(*terms: str) -> bool:
        return any(t in summary for t in terms)

    if kind == "error":
        if has("timeout", "timed out", "rate limit", "usage limit", "quota", "latency", "slow", "flaky", "unavailable", "connection refused"):
            return "reliability_perf", "error:reliability_perf"
        return "defect", "error:defect"

    if kind == "user_frustration":
        return "ux_friction", "user_frustration:ux_friction"

    if kind in {"improvement_suggestion", "experiment_suggestion"}:
        if has("eval", "evaluation", "benchmark", "ablation", "experiment"):
            return "process_tooling", "suggestion:process_tooling"
        if has("tool", "integration", "feature", "capability", "missing"):
            return "capability_gap", "suggestion:capability_gap"
        if has("clarity", "confus", "ux", "format", "explain", "prompt"):
            return "ux_friction", "suggestion:ux_friction"
        if has("timeout", "latency", "slow", "rate limit"):
            return "reliability_perf", "suggestion:reliability_perf"
        if has("privacy", "pii", "safety", "policy", "refusal"):
            return "safety_compliance", "suggestion:safety_compliance"
        if "process" in tags or has("triage", "rollup", "pipeline", "logging", "metrics"):
            return "process_tooling", "suggestion:process_tooling"
        return "ux_friction", "suggestion:ux_friction"

    if "process" in tags or has("triage", "rollup", "pipeline", "logging", "metrics"):
        return "process_tooling", "other:process_tooling"

    return "ux_friction", "other:ux_friction"


def _sentiment(item: Json) -> str:
    summary = (item.get("summary") or "").lower()
    if (item.get("kind") or "").lower() == "user_frustration":
        return "frustrated"
    if any(k in summary for k in ("frustrat", "confus", "annoy", "upset", "not what i meant")):
        return "frustrated"
    return "neutral"


@dataclass
class RollupConfig:
    max_samples: int = 3
    max_tags: int = 8


def rollup_signals(*, items: list[Json], cfg: RollupConfig) -> tuple[Json, list[Json]]:
    grouped: dict[str, list[Json]] = defaultdict(list)
    sig_texts: dict[str, str] = {}
    for item in items:
        sig_text, sig_id = signature_v1(item)
        sig_texts[sig_id] = sig_text
        grouped[sig_id].append(item)

    rollups: list[Json] = []
    for sig_id, group in grouped.items():
        count_items = len(group)
        sessions = {g.get("session_id") for g in group if g.get("session_id")}
        count_sessions = len(sessions)

        kind_counts = Counter((g.get("kind") or "unknown") for g in group)
        kind_v2_counts = Counter()
        kind_v2_reasons = Counter()
        tag_counts = Counter(t for g in group for t in (g.get("tags") or []) if isinstance(t, str))
        max_sev = "unknown"
        max_sev_rank = -1
        for g in group:
            sev = (g.get("severity") or "unknown").lower()
            rank = _severity_rank(sev)
            if rank > max_sev_rank:
                max_sev_rank = rank
                max_sev = sev
            kind_v2, reason = _classify_kind_v2(g)
            kind_v2_counts[kind_v2] += 1
            kind_v2_reasons[reason] += 1

        summaries = [_redact(g.get("summary") or "") for g in group if g.get("summary")]
        summary_counts = Counter(summaries)
        canonical_summary = summary_counts.most_common(1)[0][0] if summary_counts else ""

        tier, tier_reasons = _tier_for_group(max_sev, tag_counts, kind_counts)
        score = _score_group(count_items=count_items, max_sev=max_sev, tag_counts=tag_counts, kind_counts=kind_counts)

        samples: list[Json] = []
        for g in group[: cfg.max_samples]:
            samples.append(
                {
                    "item_id": g.get("item_id"),
                    "session_id": g.get("session_id"),
                    "span": g.get("span"),
                    "source": g.get("source"),
                }
            )

        rollups.append(
            {
                "signature_id": sig_id,
                "signature_text": _redact(sig_texts.get(sig_id, "")),
                "count_items": count_items,
                "count_sessions": count_sessions,
                "kind_counts": dict(kind_counts),
                "kind_v2_counts": dict(kind_v2_counts),
                "max_severity": max_sev,
                "tier": tier,
                "tier_reasons": tier_reasons,
                "score": score,
                "tags_top": tag_counts.most_common(cfg.max_tags),
                "canonical_summary": canonical_summary,
                "sample_refs": samples,
                "sentiment": Counter(_sentiment(g) for g in group).most_common(1)[0][0] if group else "neutral",
                "kind_v2_reason_top": kind_v2_reasons.most_common(2),
            }
        )

    rollups.sort(key=lambda r: (r.get("tier", 9), -float(r.get("score", 0))))

    summary = {
        "counts": {
            "items": len(items),
            "groups": len(rollups),
        },
        "tiers": Counter(str(r["tier"]) for r in rollups),
    }
    summary["tiers"] = dict(summary["tiers"])
    return summary, rollups


def load_items(path: Path) -> list[Json]:
    items: list[Json] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items
