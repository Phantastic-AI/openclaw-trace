#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

Json = dict[str, Any]
PHORGE_URL = "https://hub.phantastic.ai"

FP_RE = re.compile(r"(fp1:[0-9a-f]{64})")


def _conduit_call(method: str, payload: Json) -> Json:
    cmd = [
        "sudo",
        "/srv/phorge/phorge/bin/conduit",
        "call",
        "--local",
        "--method",
        method,
        "--as",
        "admin",
        "--input",
        "-",
    ]
    proc = subprocess.run(cmd, input=json.dumps(payload), text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"Conduit call failed: {method}")
    return json.loads(proc.stdout)


def _maniphest_search(limit: int) -> list[Json]:
    payload = {"constraints": {}, "limit": min(limit, 100)}
    data = _conduit_call("maniphest.search", payload)
    return data.get("result", {}).get("data", [])


def _scan_existing_fingerprints(limit: int) -> dict[str, Json]:
    tasks = _maniphest_search(limit)
    found: dict[str, Json] = {}
    for t in tasks:
        fields = t.get("fields", {})
        text = (fields.get("name") or "") + "\n" + (fields.get("description", {}).get("raw") or "")
        for fp in FP_RE.findall(text):
            found[fp] = {
                "id": t.get("id"),
                "phid": t.get("phid"),
                "name": fields.get("name"),
                "url": f"{PHORGE_URL}/T{t.get('id')}",
            }
    return found


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


def _format_item(item: Json) -> str:
    if item.get("schema_version") == 1 and "body" in item:
        return str(item.get("body") or "")
    return _format_rollup_block(item)


def _should_create(r: Json, min_tier: int, min_sessions: int, min_items: int) -> bool:
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


def _create_task(r: Json) -> str:
    title = r.get("title") or f"Signal: {r.get('canonical_summary')}"
    description = _format_item(r)
    payload = {"title": title, "description": description, "priority": r.get("priority", 80)}
    data = _conduit_call("maniphest.createtask", payload)
    return data.get("result", {}).get("uri") or ""


def _comment_task(task_id: int, comment: str) -> None:
    payload = {"objectIdentifier": str(task_id), "transactions": [{"type": "comment", "value": comment}]}
    _conduit_call("maniphest.edit", payload)


def main() -> None:
    ap = argparse.ArgumentParser(description="Create/update Phorge tickets from rollup outputs.")
    ap.add_argument("--in-json", help="Rollup JSON path")
    ap.add_argument("--in-jsonl", help="Ticket IR JSONL path")
    ap.add_argument("--scan-limit", type=int, default=300, help="How many recent tasks to scan for fingerprints")
    ap.add_argument("--min-tier", type=int, default=1, help="Only consider tiers <= this value")
    ap.add_argument("--min-sessions", type=int, default=3)
    ap.add_argument("--min-items", type=int, default=10)
    ap.add_argument("--max-create", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true", help="Print actions only (no Phorge edits)")
    args = ap.parse_args()

    if not args.in_json and not args.in_jsonl:
        raise SystemExit("Provide --in-json (rollup) or --in-jsonl (ticket IR)")

    if args.in_jsonl:
        rollups = [
            json.loads(line)
            for line in Path(args.in_jsonl).read_text().splitlines()
            if line.strip()
        ]
    else:
        rollup = json.loads(Path(args.in_json).read_text())
        rollups = rollup.get("rollups", [])

    existing = _scan_existing_fingerprints(args.scan_limit)
    created = 0
    updates = 0

    for r in rollups:
        fp = r.get("fingerprint_id") or ""
        if not fp:
            continue
        if fp in existing:
            task = existing[fp]
            updates += 1
            if args.dry_run:
                print(f"[update] {task['url']} fp={fp}")
                continue
            _comment_task(task["id"], "Rollup update:\n\n" + _format_item(r))
            continue

        if created >= args.max_create:
            continue
        if not _should_create(r, args.min_tier, args.min_sessions, args.min_items):
            continue

        created += 1
        if args.dry_run:
            print(f"[create] {r.get('canonical_summary')} fp={fp}")
            continue
        uri = _create_task(r)
        if uri:
            print(f"[created] {uri} fp={fp}")

    print(f"[ticket-rollup] updates={updates} created={created} scanned={len(existing)}")


if __name__ == "__main__":
    main()
