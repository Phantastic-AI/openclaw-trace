#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

Json = dict[str, Any]


def _format_rollup_block(r: Json) -> str:
    tags = ", ".join(f"{k}:{v}" for k, v in r.get("tags_top", []))
    samples = r.get("sample_refs") or []
    sample_lines = []
    for s in samples:
        sample_lines.append(
            f"- item_id={s.get('item_id')} session_id={s.get('session_id')} span={s.get('span')} source={s.get('source')}"
        )
    sample_text = "\n".join(sample_lines) if sample_lines else "(none)"
    return (
        f"Fingerprint: {r.get('fingerprint_id')}\n"
        f"Canonical summary: {r.get('canonical_summary')}\n"
        f"kind_v2: {r.get('kind_v2_counts')}\n"
        f"max_severity: {r.get('max_severity')}\n"
        f"tier: {r.get('tier')} reasons={r.get('tier_reasons')}\n"
        f"score: {r.get('score')}\n"
        f"count_items: {r.get('count_items')} count_sessions: {r.get('count_sessions')}\n"
        f"tags_top: {tags}\n"
        f"samples:\n{sample_text}\n"
    )


def _should_emit(r: Json, min_tier: int, min_sessions: int, min_items: int) -> bool:
    tier = int(r.get("tier") or 9)
    if tier > min_tier:
        return False
    if r.get("max_severity") == "critical":
        return True
    if r.get("count_sessions", 0) >= min_sessions:
        return True
    if r.get("count_items", 0) >= min_items:
        return True
    return False


def _ticket_ir(r: Json) -> Json:
    title = f"Signal: {r.get('canonical_summary')}"
    return {
        "schema_version": 1,
        "fingerprint_id": r.get("fingerprint_id"),
        "title": title,
        "body": _format_rollup_block(r),
        "priority": 80,
        "kind_v2_primary": max(r.get("kind_v2_counts", {"ux_friction": 1}), key=r.get("kind_v2_counts", {"ux_friction": 1}).get),
        "kind_v2_counts": r.get("kind_v2_counts"),
        "max_severity": r.get("max_severity"),
        "tier": r.get("tier"),
        "score": r.get("score"),
        "count_items": r.get("count_items"),
        "count_sessions": r.get("count_sessions"),
        "tags_top": r.get("tags_top"),
        "canonical_summary": r.get("canonical_summary"),
        "sample_refs": r.get("sample_refs"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Export a ticket-IR JSONL from rollup outputs.")
    ap.add_argument("--in-json", required=True, help="Rollup JSON path")
    ap.add_argument("--out-jsonl", default="ticket_ir.jsonl")
    ap.add_argument("--out-json", default=None, help="Optional summary JSON")
    ap.add_argument("--only-ticketable", action="store_true", help="Apply min-tier/min-session/min-item thresholds")
    ap.add_argument("--min-tier", type=int, default=3, help="Only consider tiers <= this value")
    ap.add_argument("--min-sessions", type=int, default=1)
    ap.add_argument("--min-items", type=int, default=1)
    args = ap.parse_args()

    rollup = json.loads(Path(args.in_json).read_text())
    rollups = rollup.get("rollups", [])

    tickets: list[Json] = []
    for r in rollups:
        if args.only_ticketable and not _should_emit(r, args.min_tier, args.min_sessions, args.min_items):
            continue
        tickets.append(_ticket_ir(r))

    Path(args.out_jsonl).write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in tickets) + ("\n" if tickets else ""),
        encoding="utf-8",
    )

    if args.out_json:
        summary = {
            "tickets": len(tickets),
            "tiers": Counter(str(t.get("tier")) for t in tickets),
            "kind_v2_primary": Counter(t.get("kind_v2_primary") for t in tickets),
        }
        summary["tiers"] = dict(summary["tiers"])
        summary["kind_v2_primary"] = dict(summary["kind_v2_primary"])
        Path(args.out_json).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[ticket-ir] wrote {args.out_jsonl} items={len(tickets)}")


if __name__ == "__main__":
    main()
