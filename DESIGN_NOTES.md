# Design notes: mapping this prototype to a fuller RLM

This repo is a minimal, self-contained recursive-LLM loop.

## What we implemented

- **Context stays out of prompt**: transcript is parsed into `Transcript.events` and never embedded wholesale.
- **Narrow tool surface**: generated code can only call helper functions: `search`, `window`, `detect_tool_calls`, `detect_failures`, `summarize_span`.
- **Constrained execution**: `safe_exec.py` blocks imports and some dangerous syntax.
- **Iterative loop**: `RecursiveAnalyzer.run()` calls an LLM for code, executes, retries with error feedback.

## How this corresponds to `alexzhang13/rlm`

If you later adopt a full RLM framework, a likely mapping is:

- `Transcript` -> an **external state store** / `Context` object in the controller.
- helper functions -> **tool registry** entries (with structured schemas + serialization)
- `RecursiveAnalyzer` -> **controller loop** with:
  - planner step (choose which tool to call / which span to inspect)
  - executor step (tool call)
  - summarizer step (update scratchpad / memory)
  - finalizer step (produce report)

In a mature RLM, the model typically emits *tool calls* rather than Python code. This prototype uses Python code because it’s the smallest end-to-end loop.

## Scaling improvements

1. **Transcript backend**
   - Replace `events: list[dict]` with an on-disk index:
     - offsets per line
     - mmap file
     - load windows lazily
   - Add optional precomputed inverted index for `search()`.

2. **More robust schema support**
   - Add adapters for known transcript shapes (Clawdbot versions, different providers).

3. **Caching**
   - Cache search results/windows/summaries keyed by (query, start, end).
   - Cache LLM responses per prompt hash.

4. **Policy/safety**
   - Use `RestrictedPython` for stronger sandboxing.
   - Enforce runtime quotas (CPU time, instruction count, output size).

5. **Better phase/branch reconstruction**
   - Track threads/conversations by `threadId`, `replyTo`, or tool session ids.
   - Build a DAG of "intent" nodes (planning/writing/revise) and "execution" nodes (tool calls).

## Why "code only" is OK here

- It lets the model write small analysis routines without adding a big planning layer.
- The surface area is constrained by the helpers.
- The driver can iteratively refine based on runtime errors.

If you migrate to tool-call RLM, keep the helper function interfaces; only swap the LLM output format.
