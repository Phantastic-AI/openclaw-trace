# Example analyzer program (runs with --llm none --program examples/paper_program.py)

hits = search("research paper", limit=10)
if not hits:
    hits = search("paper", limit=10)

failures = detect_failures(limit=50)
tools = detect_tool_calls()

PHASES = [
    {
        "name": "High-level signals",
        "paper_mentions": hits,
        "failure_count": len(failures),
        "tool_call_count": len(tools),
    }
]

FINAL = (
    "Heuristic summary (no LLM): "
    f"found {len(hits)} mentions of 'research paper/paper', "
    f"{len(tools)} tool calls, and {len(failures)} potential failures. "
    "Re-run with OPENAI_API_KEY for a narrative phase reconstruction."
)
