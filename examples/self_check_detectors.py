from __future__ import annotations

import sys
from pathlib import Path

from rlm_session_analyzer.transcript import load_transcript, detect_failures, detect_tool_calls


def main() -> int:
    p = Path(__file__).parent / "synthetic_nested_tool_events.jsonl"
    tr = load_transcript(p)

    tools = detect_tool_calls(tr.events)
    fails = detect_failures(tr.events)

    assert any(t.get("toolName") == "read" and t.get("status") == "error" for t in tools), tools
    assert any(t.get("toolName") == "bash" and t.get("exitCode") == 2 for t in tools), tools

    assert any(f.get("kind") == "tool_error" and f.get("toolName") == "read" for f in fails), fails
    assert any(f.get("kind") == "tool_error" and f.get("toolName") == "bash" and f.get("exitCode") == 2 for f in fails), fails
    assert any(f.get("kind") == "pattern" for f in fails), fails

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
