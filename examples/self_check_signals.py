from __future__ import annotations

from pathlib import Path

from openclaw_trace.llm_client import NoLLMClient
from openclaw_trace.mine_signals import MineSignalsConfig, mine_signals


def main() -> None:
    sessions_dir = Path(__file__).resolve().parent
    cfg = MineSignalsConfig(
        sessions_dir=sessions_dir,
        include=["synthetic_signals.jsonl"],
        exclude=[],
        max_sessions=1,
        use_llm=False,
    )

    summary, items = mine_signals(llm=NoLLMClient(), cfg=cfg)

    assert summary["counts"]["sessions_scanned"] == 1
    assert items, "expected at least one mined signal"

    kinds = {item["kind"] for item in items}
    assert "error" in kinds, "expected error signal"
    assert "user_frustration" in kinds, "expected user_frustration signal"

    for item in items:
        assert len(item["summary"]) <= cfg.max_summary_chars
        assert len(item["evidence"]) <= cfg.max_evidence_per_item

    print("OK")


if __name__ == "__main__":
    main()
