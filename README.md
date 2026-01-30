# rlm-session-analyzer (minimal)

> **NOTE (AI-GENERATED, UNREVIEWED):** This repository was produced largely/entirely by LLMs as a quick prototype. It is **not** a polished codebase. Expect rough edges, inconsistent style, missing tests, and potential bugs/security issues. Use at your own risk.

A minimal **RLM-style** (recursive tool-using loop) analyzer for **Clawdbot** session transcripts saved as **JSONL**.

Goal: given a gigantic session trace, reconstruct **phases / branches / failures** during a task such as *"creating a research paper"*.

This project intentionally follows the "recursive-llm" pattern:
- The transcript is loaded into a Python object (`Transcript.events`) **outside the model prompt**.
- The model only sees *small slices* via helper functions like `search()` and `window()`.
- The model returns **Python code only**.
- The driver executes that code in a constrained environment, expecting `FINAL` and optionally `PHASES`.

## Install

```bash
cd /home/debian/clawd/home/rlm-session-analyzer
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

## Run (with an OpenAI-compatible API)

Set API credentials:

```bash
export OPENAI_API_KEY="..."
# optional
export OPENAI_MODEL="gpt-4.1-mini"
export OPENAI_BASE_URL="https://api.openai.com/v1"
```

Run analysis (single transcript):

```bash
claw-trace analyze /path/to/session.jsonl \
  --objective "Reconstruct phases/branches/failures of creating a research paper" \
  --out analysis.json
```

Legacy (still supported):

```bash
claw-trace /path/to/session.jsonl --out analysis.json
```

Backwards-compatible alias (deprecated):

```bash
rlm-analyze /path/to/session.jsonl --out analysis.json
```

The output is JSON with a top-level `result` containing:
- `FINAL`: narrative summary
- `PHASES`: structured phase list (if produced)

## Mine research ideas across many sessions (PII-safe)

This mode crawls a directory of session `.jsonl` files, performs a lightweight deterministic keyword scan using `Transcript.search()`, builds short synopses for each candidate segment, and (optionally) asks an OpenAI-compatible LLM to propose **frontier AI research experiment ideas**.

Per ninjaa’s plan: for internal one-time runs we **do not aggressively pre-scrub** content before synthesis (idea quality > maximal privacy), but we still:
- truncate snippets (never emit long raw logs)
- optionally scrub outputs with `--scrub-output` (default: off)

Example invocation:

```bash
claw-trace mine-ideas \
  --sessions-dir /home/debian/.clawdbot/agents/main/sessions \
  --include "**/*.jsonl" \
  --exclude "**/node_modules/**" \
  --max-sessions 200 \
  --no-llm \
  --out-json out_mine_ideas.json \
  --out-md out_mine_ideas.md

# Optional: scrub outputs (JSON + Markdown) for PII-ish patterns
claw-trace mine-ideas \
  --sessions-dir /home/debian/.clawdbot/agents/main/sessions \
  --include "**/*.jsonl" \
  --max-sessions 200 \
  --scrub-output \
  --out-json out_mine_ideas_scrubbed.json \
  --out-md out_mine_ideas_scrubbed.md
```

To enable LLM idea generation, omit `--no-llm` and set `OPENAI_API_KEY`.

## Run (no API key)

If `OPENAI_API_KEY` is missing, the tool falls back to a deterministic stub.

You can still use it by supplying your own analysis program:

```bash
claw-trace analyze /path/to/session.jsonl --llm none --program examples/paper_program.py
```

## Writing a custom analyzer program

The executed program **cannot import** or access filesystem/network. You are expected to use these helpers:

- `search(query, fields=None, limit=..., start=0) -> list[dict]`
- `window(start, end, fields=None) -> list[dict]`
- `detect_tool_calls(start=0, end=None) -> list[dict]`
- `detect_failures(start=0, end=None, limit=200) -> list[dict]`
- `summarize_span(start, end) -> str`
- `N` total number of events

Your program should set:

- `FINAL: str` (required)
- `PHASES: list[dict]` (optional)

See `examples/paper_program.py`.

## Notes / Limitations

- The sandbox (`safe_exec.py`) is a *best-effort guardrail*, not a perfect security boundary.
- `detect_tool_calls` / `detect_failures` are heuristic; different transcript schemas may require tweaks.
- For extremely large transcripts, this loads everything into memory. If that’s a problem, the next step is an on-disk index + lazy windows.

## Design notes (future mapping to alexzhang13/rlm)

See `DESIGN_NOTES.md` for how to scale this into a fuller RLM workflow (planner/controller + tool registry + caching).
