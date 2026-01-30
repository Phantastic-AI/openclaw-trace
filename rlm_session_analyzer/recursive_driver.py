from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .llm_client import LLMClient, LLMResponse
from .safe_exec import SafeExecResult, safe_exec
from .transcript import Transcript, detect_failures, detect_tool_calls


SYSTEM_PROMPT = """You are an analysis agent generating **raw Python code** to analyze a large session transcript.

Constraints:
- Output **RAW PYTHON ONLY** (no Markdown fences, no ``` blocks).
- You CANNOT import modules or access filesystem/network.
- You MUST use provided helper functions: search, window, detect_tool_calls, detect_failures, summarize_span.
- Keep outputs concise.

Helper shapes:
- search(query, ...) -> list[dict] hits, each hit has at least: {"index": int, "preview": str, "keys": [...], "_line_no": int|None}
  - To get indices: [h["index"] for h in hits]
- window(start,end,...) -> list[dict] events (a small slice)

You MUST set:
- FINAL: a non-empty string
You MAY set:
- PHASES: list[dict] with fields like {phase, start, end, summary, notes}

The driver will execute your code in a restricted environment.
"""


@dataclass
class DriverConfig:
    max_iters: int = 6
    max_window_events: int = 120
    max_search_hits: int = 30


class RecursiveAnalyzer:
    def __init__(
        self,
        *,
        transcript: Transcript,
        llm: LLMClient,
        cfg: DriverConfig | None = None,
    ):
        self.transcript = transcript
        self.llm = llm
        self.cfg = cfg or DriverConfig()

        # State accumulated outside the prompt
        self.notes: list[str] = []
        self.produced_code: list[str] = []

    # --- helper functions exposed to generated code ---
    def _search(self, query: str, fields: list[str] | None = None, limit: int | None = None, start: int = 0):
        lim = limit or self.cfg.max_search_hits
        hits = self.transcript.search(query, fields=fields, limit=lim, start=start)
        # Return a condensed structure so generated code doesn't accidentally drag huge dicts into outputs.
        def _extract_preview(ev: dict[str, Any]) -> str:
            # Newer transcripts store payload under ev["message"], often with content=[{type:"text", text:"..."}]
            m = ev.get("message")
            if isinstance(m, dict):
                c = m.get("content")
                if isinstance(c, list):
                    parts = []
                    for it in c:
                        if isinstance(it, dict) and isinstance(it.get("text"), str):
                            parts.append(it.get("text"))
                        elif isinstance(it, str):
                            parts.append(it)
                    if parts:
                        return "\n".join(parts)
                if isinstance(c, str) and c:
                    return c
                # fallback for nested message
                if isinstance(m.get("text"), str) and m.get("text"):
                    return m.get("text")
            # Older shapes
            for k in ("content", "text"):
                if isinstance(ev.get(k), str) and ev.get(k):
                    return ev.get(k)
            return str(ev)

        return [
            {
                "index": i,
                "_line_no": ev.get("_line_no"),
                "keys": sorted(list(ev.keys()))[:40],
                "preview": _extract_preview(ev)[:500],
            }
            for i, ev in hits
        ]

    def _window(self, start: int, end: int, fields: list[str] | None = None):
        # hard limit
        if end - start > self.cfg.max_window_events:
            end = start + self.cfg.max_window_events
        span = self.transcript.window(start, end, fields=fields)
        # compact any huge strings
        compacted: list[dict[str, Any]] = []
        for ev in span:
            cev: dict[str, Any] = {}
            for k, v in ev.items():
                if isinstance(v, str) and len(v) > 1200:
                    cev[k] = v[:1200] + "…"
                else:
                    cev[k] = v
            compacted.append(cev)
        return compacted

    def _detect_tool_calls(self, start: int = 0, end: int | None = None):
        end = self.transcript.n if end is None else end
        return detect_tool_calls(self.transcript.events[start:end])

    def _detect_failures(self, start: int = 0, end: int | None = None, limit: int = 200):
        end = self.transcript.n if end is None else end
        return detect_failures(self.transcript.events[start:end], limit=limit)

    def _summarize_span(self, start: int, end: int) -> str:
        # lightweight deterministic summary to reduce token pressure; not LLM-based.
        span = self._window(start, end, fields=["type", "role", "tool", "tool_name", "content", "message", "error", "status", "_line_no"])
        tool_count = sum(1 for ev in span if ev.get("tool") or ev.get("tool_name"))
        err_count = sum(1 for ev in span if ev.get("error"))
        # Pull a few representative messages (including nested message.content parts)
        def _extract_text(ev: dict[str, Any]) -> str:
            m = ev.get("message")
            if isinstance(m, dict):
                c = m.get("content")
                if isinstance(c, list):
                    parts = []
                    for it in c:
                        if isinstance(it, dict) and isinstance(it.get("text"), str):
                            parts.append(it.get("text"))
                        elif isinstance(it, str):
                            parts.append(it)
                    if parts:
                        return "\n".join(parts)
                if isinstance(c, str) and c:
                    return c
                # sometimes tool errors live in details.error
                det = m.get("details")
                if isinstance(det, dict) and isinstance(det.get("error"), str) and det.get("error"):
                    return det.get("error")
            for k in ("content", "message", "text"):
                if isinstance(ev.get(k), str) and ev.get(k):
                    return ev.get(k)
            return ""

        msgs = []
        for ev in span:
            t = _extract_text(ev)
            if isinstance(t, str) and t.strip():
                msgs.append(t.strip().replace("\n", " ")[:160])
            if len(msgs) >= 6:
                break
        return (
            f"Span [{start},{end}) events={len(span)} tool_calls={tool_count} errors={err_count}\n"
            + "Examples:\n- "
            + "\n- ".join(msgs)
        )

    def _env(self) -> dict[str, Any]:
        return {
            "search": self._search,
            "window": self._window,
            "detect_tool_calls": self._detect_tool_calls,
            "detect_failures": self._detect_failures,
            "summarize_span": self._summarize_span,
            "N": self.transcript.n,
        }

    def run(self, *, objective: str, program: str | None = None, temperature: float = 0.0) -> dict[str, Any]:
        """Iteratively request code from an LLM and execute it until FINAL is produced."""

        if program is not None:
            res = safe_exec(program, env=self._env())
            return self._result_from_exec(res)

        last_error: str | None = None
        for it in range(1, self.cfg.max_iters + 1):
            user_prompt = self._build_user_prompt(objective=objective, iteration=it, last_error=last_error)
            resp: LLMResponse = self.llm.complete(system=SYSTEM_PROMPT, user=user_prompt, temperature=temperature)
            code = resp.text.strip()
            self.produced_code.append(code)
            try:
                res = safe_exec(code, env=self._env())
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                continue

            out = self._result_from_exec(res)
            if out.get("FINAL"):
                out["_iterations"] = it
                out["_last_error"] = last_error
                out["_code"] = code
                return out

            last_error = "Program ran but did not set FINAL"

        return {
            "FINAL": "Failed to produce FINAL within max iterations.",
            "PHASES": [],
            "_iterations": self.cfg.max_iters,
            "_last_error": last_error,
            "_code": self.produced_code[-1] if self.produced_code else None,
        }

    def _result_from_exec(self, res: SafeExecResult) -> dict[str, Any]:
        merged = dict(res.globals)
        merged.update(res.locals)
        final = merged.get("FINAL")
        phases = merged.get("PHASES")
        return {
            "FINAL": final,
            "PHASES": phases,
        }

    def _build_user_prompt(self, *, objective: str, iteration: int, last_error: str | None) -> str:
        # Keep prompt small. We do NOT embed the transcript.
        header = {
            "objective": objective,
            "iteration": iteration,
            "transcript_events": self.transcript.n,
            "available_helpers": ["search", "window", "detect_tool_calls", "detect_failures", "summarize_span"],
        }
        if last_error:
            header["last_error"] = last_error
        return (
            "You must write Python code that uses helpers to reconstruct phases/branches/failures.\n"
            "Set FINAL to a narrative summary and PHASES to structured phases.\n"
            "\n"
            f"STATE:\n{json.dumps(header, indent=2)}\n\n"
            "Tips:\n"
            "- Start by locating where the user asked to create a research paper (search for 'research paper', 'paper', 'abstract', 'introduction').\n"
            "- Then map major phases: planning, data gathering, writing sections, citations, formatting, tooling, failures/retries, final deliverable.\n"
            "- Use detect_failures() and detect_tool_calls() for structure.\n"
        )
