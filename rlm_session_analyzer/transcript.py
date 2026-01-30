from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional


Json = dict[str, Any]


# --- Transcript loading and indexing ---

def _iter_jsonl(path: Path) -> Iterator[Json]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception as e:
                # Keep going; represent parse failures as events so failure detection can surface it.
                yield {
                    "_parse_error": str(e),
                    "_raw": line[:2000],
                    "_line_no": line_no,
                }
                continue
            if isinstance(obj, dict):
                obj.setdefault("_line_no", line_no)
                yield obj
            else:
                yield {"_non_dict": True, "value": obj, "_line_no": line_no}


@dataclass
class Transcript:
    """In-memory representation of a jsonl transcript.

    This is intentionally simple: a list of event dicts plus a few helpers that operate
    over indices (0-based). The core RLM-style pattern is: keep this `context` object
    *outside* the model prompt and provide helper functions that reveal only relevant
    slices/search results.
    """

    path: Path
    events: list[Json]

    @property
    def n(self) -> int:
        return len(self.events)

    def event(self, i: int) -> Json:
        return self.events[i]

    def window(self, start: int, end: int, *, fields: Optional[list[str]] = None) -> list[Json]:
        start = max(0, start)
        end = min(self.n, end)
        if start >= end:
            return []
        span = self.events[start:end]
        if fields is None:
            return span
        out: list[Json] = []
        for ev in span:
            out.append({k: ev.get(k) for k in fields if k in ev} | {"_line_no": ev.get("_line_no")})
        return out

    def search(
        self,
        query: str | re.Pattern[str],
        *,
        fields: Optional[list[str]] = None,
        limit: int = 50,
        start: int = 0,
    ) -> list[tuple[int, Json]]:
        """Return [(index,event), ...] where query matches in selected fields or JSON dump."""
        if isinstance(query, str):
            pat = re.compile(re.escape(query), re.IGNORECASE)
        else:
            pat = query
        matches: list[tuple[int, Json]] = []
        for i in range(max(0, start), self.n):
            ev = self.events[i]
            if fields:
                hay = "\n".join(str(ev.get(k, "")) for k in fields)
            else:
                # JSON dump can be expensive; keep it small.
                hay = json.dumps(ev, ensure_ascii=False)[:20000]
            if pat.search(hay):
                matches.append((i, ev))
                if len(matches) >= limit:
                    break
        return matches


def load_transcript(path: str | Path, *, max_events: Optional[int] = None) -> Transcript:
    p = Path(path)
    events: list[Json] = []
    for ev in _iter_jsonl(p):
        events.append(ev)
        if max_events is not None and len(events) >= max_events:
            break
    return Transcript(path=p, events=events)


# --- Higher-level detectors ---


def _msg(ev: Json) -> Json | None:
    """Return nested message dict for Clawdbot transcripts, if present."""
    m = ev.get("message")
    return m if isinstance(m, dict) else None


def _content_text(v: Any) -> str:
    """Extract human-readable text from a content field.

    Handles:
    - "string"
    - [{"type":"text","text":"..."}, ...]
    - arbitrary dicts/lists (best-effort JSON)
    """
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        parts: list[str] = []
        for item in v:
            if isinstance(item, str):
                if item:
                    parts.append(item)
                continue
            if isinstance(item, dict):
                # common OpenAI-ish content part
                t = item.get("text")
                if isinstance(t, str) and t:
                    parts.append(t)
                    continue
                # fallback
                try:
                    parts.append(json.dumps(item, ensure_ascii=False)[:2000])
                except Exception:
                    parts.append(str(item)[:2000])
                continue
            parts.append(str(item)[:2000])
        return "\n".join(p for p in parts if p)
    if isinstance(v, dict):
        # Sometimes the tool result is stored as {status, tool, error, ...}
        for k in ("text", "error", "stderr", "stdout", "output"):
            t = v.get(k)
            if isinstance(t, str) and t:
                return t
        try:
            return json.dumps(v, ensure_ascii=False)[:4000]
        except Exception:
            return str(v)[:4000]
    return str(v)[:4000]


def detect_tool_calls(events: list[Json]) -> list[dict[str, Any]]:
    """Heuristic extractor for tool calls in Clawdbot-ish transcripts.

    Supports both historical shapes (top-level tool fields) and the newer Clawdbot
    session-jsonl shape where tool results are nested under ev["message"] with:
      role=toolResult, toolName, toolCallId, details={status, exitCode, error, ...},
      content=[{type:"text", text:"..."}]

    Output records include: index, toolName, toolCallId, status/exitCode, error.
    """
    out: list[dict[str, Any]] = []

    for idx, ev in enumerate(events):
        m = _msg(ev)

        tool_name: str | None = None
        tool_call_id: str | None = None
        details: dict[str, Any] | None = None

        # Newer nested tool result shape.
        if m and isinstance(m, dict) and m.get("role") == "toolResult":
            tn = m.get("toolName")
            if isinstance(tn, str) and tn:
                tool_name = tn
            tcid = m.get("toolCallId")
            if isinstance(tcid, str) and tcid:
                tool_call_id = tcid
            det = m.get("details")
            details = det if isinstance(det, dict) else None

        # Older top-level shapes.
        if not tool_name:
            tn = ev.get("tool") or ev.get("tool_name")
            if isinstance(tn, str) and tn:
                tool_name = tn
        if not tool_name:
            # Some logs store as type='tool_call'
            if ev.get("type") in {"tool_call", "tool"} and ev.get("name"):
                tool_name = str(ev.get("name"))

        if not tool_name:
            continue

        rec: dict[str, Any] = {
            "index": idx,
            "_line_no": ev.get("_line_no"),
            "toolName": tool_name,
        }
        if tool_call_id:
            rec["toolCallId"] = tool_call_id

        # Extract action if present (commonly for browser/tool namespaces).
        inp = None
        if m and isinstance(m, dict):
            inp = m.get("input")
        if inp is None:
            inp = ev.get("input") or ev.get("arguments")
        if isinstance(inp, dict) and "action" in inp:
            rec["action"] = inp.get("action")

        # Status/exitCode/error from nested details or top-level.
        if details:
            if "status" in details:
                rec["status"] = details.get("status")
            if "exitCode" in details:
                rec["exitCode"] = details.get("exitCode")
            if details.get("error"):
                rec["error"] = str(details.get("error"))[:2000]
        if "status" in ev and "status" not in rec:
            rec["status"] = ev.get("status")
        if "exitCode" in ev and "exitCode" not in rec:
            rec["exitCode"] = ev.get("exitCode")
        if ev.get("error") and "error" not in rec:
            rec["error"] = str(ev.get("error"))[:2000]

        # Optional: include a short preview from content.
        preview_src = None
        if m and isinstance(m, dict):
            preview_src = m.get("content")
        if preview_src is None:
            preview_src = ev.get("content")
        preview = _content_text(preview_src).strip()
        if preview:
            rec["preview"] = preview[:300]

        out.append(rec)

    return out


_FAILURE_PATTERNS = [
    re.compile(r"\b(traceback|exception|error|failed|failure|timeout|timed out|permission denied)\b", re.I),
    re.compile(r"\b(oom|out of memory|sigkill|killed)\b", re.I),
]


def detect_failures(events: list[Json], *, limit: int = 200) -> list[dict[str, Any]]:
    """Heuristic failure detector (errors, tool failures, stack traces)."""
    out: list[dict[str, Any]] = []

    for idx, ev in enumerate(events):
        line_no = ev.get("_line_no")

        # Explicit JSONL parse errors.
        if ev.get("_parse_error"):
            out.append({"index": idx, "kind": "parse_error", "detail": ev.get("_parse_error"), "_line_no": line_no})
            if len(out) >= limit:
                break
            continue

        # Tool-result failures nested under message.details.
        m = _msg(ev)
        if m and isinstance(m, dict) and m.get("role") == "toolResult":
            details = m.get("details") if isinstance(m.get("details"), dict) else {}
            status = details.get("status")
            exit_code = details.get("exitCode")
            err = details.get("error")
            if status == "error" or (isinstance(exit_code, int) and exit_code != 0) or err:
                out.append(
                    {
                        "index": idx,
                        "kind": "tool_error",
                        "toolName": m.get("toolName"),
                        "status": status,
                        "exitCode": exit_code,
                        "detail": (str(err) if err else _content_text(m.get("content")))[:2000],
                        "_line_no": line_no,
                    }
                )
                if len(out) >= limit:
                    break
                continue

        # Top-level error fields.
        if ev.get("error"):
            out.append({"index": idx, "kind": "error_field", "detail": str(ev.get("error"))[:2000], "_line_no": line_no})
            if len(out) >= limit:
                break
            continue

        # Scan text-ish content (including nested message.content arrays).
        texts: list[str] = []
        # top-level candidates
        for k in ("content", "text", "output", "stderr", "stdout"):
            t = _content_text(ev.get(k)).strip()
            if t:
                texts.append(t)
        # nested candidates
        if m and isinstance(m, dict):
            t = _content_text(m.get("content")).strip()
            if t:
                texts.append(t)
            # sometimes details carries a big aggregated string
            det = m.get("details")
            if isinstance(det, dict):
                for k in ("aggregated", "stderr", "stdout", "error"):
                    dt = _content_text(det.get(k)).strip()
                    if dt:
                        texts.append(dt)

        if not texts:
            continue

        hay = "\n".join(texts)
        if any(p.search(hay) for p in _FAILURE_PATTERNS):
            out.append({"index": idx, "kind": "pattern", "detail": hay[:2000], "_line_no": line_no})
            if len(out) >= limit:
                break

    return out
