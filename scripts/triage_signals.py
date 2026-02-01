#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1, "unknown": 0}

EMAIL_RE = re.compile(r"[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://\\S+")
TOKEN_RE = re.compile(r"\\b(sk-[A-Za-z0-9_-]{8,}|xox[baprs]-\\S{6,}|ghp_\\S{6,}|AKIA\\S{8,})\\b")
LONGHEX_RE = re.compile(r"\\b[0-9a-fA-F]{16,}\\b")
PATH_RE = re.compile(r"/(?:home|Users|var|etc|opt|srv)/[^\\s]*")


def _redact(text: str) -> str:
    text = EMAIL_RE.sub("[email]", text)
    text = URL_RE.sub("[url]", text)
    text = TOKEN_RE.sub("[token]", text)
    text = LONGHEX_RE.sub("[id]", text)
    text = PATH_RE.sub("[path]", text)
    return text


def _tier(item: dict) -> tuple[int, list[str]]:
    tags = set(item.get("tags") or [])
    severity = (item.get("severity") or "unknown").lower()
    kind = (item.get("kind") or "").lower()
    reasons: list[str] = []
    if "incident" in tags or severity in {"critical", "high"}:
        if "incident" in tags:
            reasons.append("incident")
        if severity in {"critical", "high"}:
            reasons.append(f"severity:{severity}")
        return 1, reasons
    if kind in {"error", "user_frustration"} or severity == "medium":
        if kind in {"error", "user_frustration"}:
            reasons.append(f"kind:{kind}")
        if severity == "medium":
            reasons.append("severity:medium")
        return 2, reasons
    return 3, ["default"]


def _score(item: dict) -> float:
    severity = (item.get("severity") or "unknown").lower()
    sev = SEVERITY_WEIGHT.get(severity, 0)
    tags = set(item.get("tags") or [])
    kind = (item.get("kind") or "").lower()
    score = float(sev)
    if "incident" in tags:
        score += 2.0
    if kind == "error":
        score += 0.3
    if kind == "user_frustration":
        score += 0.2
    return score


def main() -> None:
    ap = argparse.ArgumentParser(description="Lightweight triage for mined signals (pre-rollup).")
    ap.add_argument("--in-jsonl", required=True, help="Input signals JSONL")
    ap.add_argument("--out-jsonl", default="triage_signals.jsonl")
    ap.add_argument("--out-json", default="triage_summary.json")
    ap.add_argument("--out-md", default="triage_summary.md")
    ap.add_argument("--max-items-per-tier", type=int, default=10)
    args = ap.parse_args()

    items = [json.loads(line) for line in Path(args.in_jsonl).read_text().splitlines() if line.strip()]
    for item in items:
        tier, reasons = _tier(item)
        item["tier"] = tier
        item["tier_reasons"] = reasons
        item["triage_score"] = _score(item)

    Path(args.out_jsonl).write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in items) + ("\n" if items else ""),
        encoding="utf-8",
    )

    counts = {
        "items": len(items),
        "tiers": Counter(str(it["tier"]) for it in items),
        "kinds": Counter(it.get("kind", "?") for it in items),
        "severities": Counter(it.get("severity", "?") for it in items),
        "top_tags": Counter(t for it in items for t in (it.get("tags") or [])).most_common(15),
    }
    Path(args.out_json).write_text(json.dumps(counts, indent=2, ensure_ascii=False), encoding="utf-8")

    by_tier: dict[int, list[dict]] = {1: [], 2: [], 3: []}
    for item in items:
        by_tier[item["tier"]].append(item)
    for tier in by_tier:
        by_tier[tier].sort(key=lambda it: it.get("triage_score", 0), reverse=True)

    lines: list[str] = []
    lines.append("# Triage summary (pre-rollup)")
    lines.append("")
    lines.append(f"- items: {counts['items']}")
    lines.append(f"- tiers: {dict(counts['tiers'])}")
    lines.append(f"- kinds: {dict(counts['kinds'])}")
    lines.append(f"- severities: {dict(counts['severities'])}")
    lines.append("")

    for tier in (1, 2, 3):
        lines.append(f"## Tier {tier} (top {args.max_items_per_tier})")
        lines.append("")
        for item in by_tier[tier][: args.max_items_per_tier]:
            summary = _redact(item.get("summary", ""))
            tags = ",".join(item.get("tags") or [])
            lines.append(
                f"- [{item.get('kind')}] sev={item.get('severity')} score={item.get('triage_score'):.2f} "
                f"tags={tags} id={item.get('item_id')} summary={summary}"
            )
        lines.append("")

    Path(args.out_md).write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
