from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .embedding_client import openai_embeddings

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


def _normalize_vec(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 0:
        return vec
    return [v / norm for v in vec]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


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


def fingerprint_v1(kind_v2: str, canonical_summary: str, tags_top: list[tuple[str, int]]) -> tuple[str, str]:
    tokens = _tokens(canonical_summary)
    gram_core = " ".join(_bigrams(tokens)[:6])
    tag_core = ",".join(t[:32].lower() for t, _n in tags_top[:5])
    fp_text = f"{kind_v2}|{gram_core}|{tag_core}"
    return fp_text, f"fp1:{_hash(fp_text)}"


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

    if kind == "proactive_opportunity":
        return "proactive_opportunity", "kind:proactive_opportunity"

    if kind == "user_delight":
        return "user_delight", "kind:user_delight"

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


def _embedding_text(rollup: Json) -> str:
    summary = (rollup.get("canonical_summary") or "").strip()
    tags = [t for t, _n in (rollup.get("tags_top") or []) if isinstance(t, str)]
    kind_counts = rollup.get("kind_v2_counts") or {}
    kind_top = []
    if isinstance(kind_counts, dict):
        kind_top = [k for k, _v in sorted(kind_counts.items(), key=lambda kv: -kv[1])[:2]]
    parts = []
    if summary:
        parts.append(summary)
    if tags:
        parts.append("Tags: " + ", ".join(tags[:6]))
    if kind_top:
        parts.append("Kinds: " + ", ".join(kind_top))
    return "\n".join(parts).strip()


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


@dataclass
class MergeConfig:
    enabled: bool = False
    method: str = "jaccard"
    auto_jaccard: float = 0.62
    llm_jaccard: float = 0.5
    max_pairs_per_block: int = 5000
    use_llm: bool = False
    embed_model: str | None = None
    embed_similarity: float = 0.88
    embed_llm_similarity: float = 0.8
    embed_k: int = 8


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return inter / union


def _safe_json(text: str) -> Json | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _llm_merge_decision(llm: Any, a: Json, b: Json) -> bool:
    system = (
        "Decide if two issue summaries describe the same underlying issue. "
        "Return ONLY JSON: {\"decision\":\"merge|separate\",\"confidence\":0.0}. "
        "Be conservative: merge only if clearly the same."
    )
    payload = {
        "a": {
            "summary": a.get("canonical_summary"),
            "kind_v2": a.get("kind_v2_counts"),
            "tags_top": a.get("tags_top"),
        },
        "b": {
            "summary": b.get("canonical_summary"),
            "kind_v2": b.get("kind_v2_counts"),
            "tags_top": b.get("tags_top"),
        },
    }
    resp = llm.complete(system=system, user=json.dumps(payload, ensure_ascii=False), temperature=0.0)
    obj = _safe_json(resp.text) or {}
    decision = (obj.get("decision") or "").lower()
    conf = obj.get("confidence")
    if decision == "merge" and isinstance(conf, (int, float)) and conf >= 0.7:
        return True
    return False


def _load_sqlite_vec(conn: sqlite3.Connection):
    try:
        import sqlite_vec  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on optional package
        raise RuntimeError("sqlite-vec is not installed. Install it with: pip install sqlite-vec") from exc
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    if not hasattr(sqlite_vec, "serialize"):
        raise RuntimeError("sqlite-vec missing serialize() helper; upgrade the package")
    return sqlite_vec


def _merge_groups(rollups: list[Json], groups: dict[int, list[Json]]) -> list[Json]:
    merged: list[Json] = []
    for members in groups.values():
        if len(members) == 1:
            merged.append(members[0])
            continue

        count_items = sum(m.get("count_items", 0) for m in members)
        count_sessions = sum(m.get("count_sessions", 0) for m in members)
        kind_counts = Counter()
        kind_v2_counts = Counter()
        tag_counts = Counter()
        max_sev = "unknown"
        max_sev_rank = -1
        sentiment_counts = Counter()
        merged_from = []

        for m in members:
            merged_from.append(m.get("signature_id"))
            kind_counts.update(m.get("kind_counts") or {})
            kind_v2_counts.update(m.get("kind_v2_counts") or {})
            tag_counts.update({k: v for k, v in (m.get("tags_top") or [])})
            sev = m.get("max_severity") or "unknown"
            rank = _severity_rank(sev)
            if rank > max_sev_rank:
                max_sev_rank = rank
                max_sev = sev
            sentiment_counts.update([m.get("sentiment") or "neutral"])

        canonical = max(members, key=lambda m: m.get("count_items", 0))
        tier, tier_reasons = _tier_for_group(max_sev, tag_counts, kind_counts)
        score = _score_group(count_items=count_items, max_sev=max_sev, tag_counts=tag_counts, kind_counts=kind_counts)
        tags_top = tag_counts.most_common(8)
        kind_v2_primary = kind_v2_counts.most_common(1)[0][0] if kind_v2_counts else "ux_friction"
        fp_text, fp_id = fingerprint_v1(kind_v2_primary, canonical.get("canonical_summary", ""), tags_top)

        merged.append(
            {
                **canonical,
                "count_items": count_items,
                "count_sessions": count_sessions,
                "kind_counts": dict(kind_counts),
                "kind_v2_counts": dict(kind_v2_counts),
                "max_severity": max_sev,
                "tier": tier,
                "tier_reasons": tier_reasons,
                "score": score,
                "tags_top": tags_top,
                "fingerprint_id": fp_id,
                "fingerprint_text": _redact(fp_text),
                "sentiment": sentiment_counts.most_common(1)[0][0] if sentiment_counts else "neutral",
                "merged_from": merged_from,
            }
        )

    merged.sort(key=lambda r: (r.get("tier", 9), -float(r.get("score", 0))))
    return merged


def _merge_rollups_jaccard(rollups: list[Json], cfg: MergeConfig, llm: Any | None) -> list[Json]:
    if not rollups:
        return rollups

    # Block by primary kind_v2 for now (cheap; avoids O(n^2) across everything).
    blocks: dict[str, list[int]] = defaultdict(list)
    for idx, r in enumerate(rollups):
        kind_v2_primary = max(r.get("kind_v2_counts", {"ux_friction": 1}), key=r.get("kind_v2_counts", {"ux_friction": 1}).get)
        blocks[kind_v2_primary].append(idx)

    parent = list(range(len(rollups)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for kind_v2, idxs in blocks.items():
        if len(idxs) < 2:
            continue
        pairs = 0
        for i, idx in enumerate(idxs):
            a = rollups[idx]
            tokens_a = set(_tokens(a.get("canonical_summary", "")))
            for j in range(i + 1, len(idxs)):
                pairs += 1
                if pairs > cfg.max_pairs_per_block:
                    break
                b = rollups[idxs[j]]
                tokens_b = set(_tokens(b.get("canonical_summary", "")))
                sim = _jaccard(tokens_a, tokens_b)
                if sim >= cfg.auto_jaccard:
                    union(idx, idxs[j])
                elif cfg.use_llm and llm is not None and sim >= cfg.llm_jaccard:
                    if _llm_merge_decision(llm, a, b):
                        union(idx, idxs[j])
            if pairs > cfg.max_pairs_per_block:
                break

    groups: dict[int, list[Json]] = defaultdict(list)
    for idx, r in enumerate(rollups):
        groups[find(idx)].append(r)

    return _merge_groups(rollups, groups)


def _merge_rollups_embeddings(rollups: list[Json], cfg: MergeConfig, llm: Any | None) -> list[Json]:
    if not rollups:
        return rollups

    texts = [_embedding_text(r) for r in rollups]
    embeddings = openai_embeddings(texts, model=cfg.embed_model)
    if len(embeddings) != len(rollups):
        raise RuntimeError("Embedding response size mismatch")

    normed = [_normalize_vec(v) for v in embeddings]
    dim = len(normed[0]) if normed else 0
    if dim == 0:
        return rollups

    conn = sqlite3.connect(":memory:")
    sqlite_vec = _load_sqlite_vec(conn)
    conn.execute(f"CREATE VIRTUAL TABLE rollup_vecs USING vec0(embedding float[{dim}]);")
    for idx, vec in enumerate(normed):
        conn.execute("INSERT INTO rollup_vecs(rowid, embedding) VALUES (?, ?)", (idx + 1, sqlite_vec.serialize(vec)))
    conn.commit()

    blocks: dict[str, list[int]] = defaultdict(list)
    block_of: dict[int, str] = {}
    for idx, r in enumerate(rollups):
        kind_v2_primary = max(r.get("kind_v2_counts", {"ux_friction": 1}), key=r.get("kind_v2_counts", {"ux_friction": 1}).get)
        blocks[kind_v2_primary].append(idx)
        block_of[idx] = kind_v2_primary

    parent = list(range(len(rollups)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for kind_v2, idxs in blocks.items():
        if len(idxs) < 2:
            continue
        k = min(max(cfg.embed_k, 1) + 1, len(idxs))
        pairs = 0
        for idx in idxs:
            vec = normed[idx]
            rows = conn.execute(
                "SELECT rowid, distance FROM rollup_vecs WHERE embedding MATCH ? AND k = ?",
                (sqlite_vec.serialize(vec), k),
            ).fetchall()
            for rowid, _dist in rows:
                j = rowid - 1
                if j <= idx:
                    continue
                if block_of.get(j) != kind_v2:
                    continue
                pairs += 1
                if pairs > cfg.max_pairs_per_block:
                    break
                sim = _dot(vec, normed[j])
                if sim >= cfg.embed_similarity:
                    union(idx, j)
                elif cfg.use_llm and llm is not None and sim >= cfg.embed_llm_similarity:
                    if _llm_merge_decision(llm, rollups[idx], rollups[j]):
                        union(idx, j)
            if pairs > cfg.max_pairs_per_block:
                break

    groups: dict[int, list[Json]] = defaultdict(list)
    for idx, r in enumerate(rollups):
        groups[find(idx)].append(r)

    return _merge_groups(rollups, groups)


def rollup_signals(*, items: list[Json], cfg: RollupConfig, merge_cfg: MergeConfig | None = None, llm: Any | None = None) -> tuple[Json, list[Json]]:
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
        tags_top = tag_counts.most_common(cfg.max_tags)
        kind_v2_primary = kind_v2_counts.most_common(1)[0][0] if kind_v2_counts else "ux_friction"
        fp_text, fp_id = fingerprint_v1(kind_v2_primary, canonical_summary, tags_top)

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
                "tags_top": tags_top,
                "canonical_summary": canonical_summary,
                "fingerprint_id": fp_id,
                "fingerprint_text": _redact(fp_text),
                "sample_refs": samples,
                "sentiment": Counter(_sentiment(g) for g in group).most_common(1)[0][0] if group else "neutral",
                "kind_v2_reason_top": kind_v2_reasons.most_common(2),
            }
        )

    rollups.sort(key=lambda r: (r.get("tier", 9), -float(r.get("score", 0))))

    if merge_cfg and merge_cfg.enabled:
        if merge_cfg.method == "embeddings":
            rollups = _merge_rollups_embeddings(rollups, merge_cfg, llm)
        else:
            rollups = _merge_rollups_jaccard(rollups, merge_cfg, llm)

    summary = {
        "counts": {
            "items": len(items),
            "groups": len(rollups),
        },
        "tiers": Counter(str(r["tier"]) for r in rollups),
    }
    summary["tiers"] = dict(summary["tiers"])
    if merge_cfg and merge_cfg.enabled:
        summary["merge"] = {
            "method": merge_cfg.method,
            "auto_jaccard": merge_cfg.auto_jaccard,
            "llm_jaccard": merge_cfg.llm_jaccard,
            "embed_similarity": merge_cfg.embed_similarity,
            "embed_llm_similarity": merge_cfg.embed_llm_similarity,
            "embed_k": merge_cfg.embed_k,
            "embed_model": merge_cfg.embed_model,
        }
    return summary, rollups


def load_items(path: Path) -> list[Json]:
    items: list[Json] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items
