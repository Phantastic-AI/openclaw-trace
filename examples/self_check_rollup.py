from __future__ import annotations

import json
from pathlib import Path

import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from openclaw_trace.rollup_signals import RollupConfig, load_items, rollup_signals


def main() -> None:
    items = load_items(root / "examples" / "synthetic_signals.jsonl")
    summary, rollups = rollup_signals(items=items, cfg=RollupConfig(max_samples=2, max_tags=5))

    assert summary["counts"]["items"] == 4, "expected 4 items"
    assert summary["counts"]["groups"] == 3, "expected 3 groups"

    top = rollups[0]
    assert top["count_items"] == 2, "expected duplicate group count 2"
    assert top["tier"] == 1, "expected tier 1 for incident/high severity"

    print("OK")


if __name__ == "__main__":
    main()
