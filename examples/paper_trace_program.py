# Deterministic analysis program for claw-trace (formerly rlm-analyze)
# Expects helper functions: search(), window(), detect_tool_calls(), detect_failures(), summarize_span(), N

# search() returns list[dict] with at least: {index, preview, keys, _line_no}

def idxs(matches):
    return [m["index"] for m in matches if isinstance(m, dict) and "index" in m]

# Key markers for "paper creation" in the trace
markers = {
    "paper_request": idxs(search("Write an arXiv paper", limit=50)),
    "paper_tex": idxs(search("paper.tex", limit=50)),
    "paper_pdf": idxs(search("paper.pdf", limit=50)),
    "pdflatex": idxs(search("pdflatex", limit=50)),
    "latex": idxs(search("LaTeX", limit=50)),
    "denario": idxs(search("Denario", limit=50)),
    "compiled": idxs(search("compiled", limit=50)),
}

all_hits = sorted(set(sum(markers.values(), [])))

start0 = 0
endN = N - 1

# If we found no hits, just summarize the beginning.
if not all_hits:
    PHASES = [
        {"phase": "Session (no explicit paper markers)", "start": 0, "end": min(N - 1, 800), "summary": summarize_span(0, min(N - 1, 800))}
    ]
    FINAL = "No explicit paper-writing markers (paper.tex/pdflatex/arXiv) were found in the scanned portion of the trace."
else:
    # Define phases around first request, generation, compilation, and aftermath.
    first = all_hits[0]
    last = all_hits[-1]

    def clamp(a, b):
        a = max(0, a)
        b = min(N - 1, b)
        return a, b

    # Heuristic windows
    p0s, p0e = clamp(first - 80, first + 120)
    p1s, p1e = clamp(first + 121, min(last, first + 900))
    p2s, p2e = clamp(p1e + 1, min(last + 120, p1e + 900))
    p3s, p3e = clamp(p2e + 1, min(N - 1, p2e + 900))

    PHASES = []
    PHASES.append({
        "phase": "Trigger / ask for paper",
        "start": p0s,
        "end": p0e,
        "summary": summarize_span(p0s, p0e),
        "markers": {k: [i for i in v if p0s <= i <= p0e] for k, v in markers.items()},
        "failures": detect_failures(p0s, p0e),
    })
    PHASES.append({
        "phase": "Generation / iteration",
        "start": p1s,
        "end": p1e,
        "summary": summarize_span(p1s, p1e),
        "markers": {k: [i for i in v if p1s <= i <= p1e] for k, v in markers.items()},
        "failures": detect_failures(p1s, p1e),
    })
    PHASES.append({
        "phase": "Compile / artifact",
        "start": p2s,
        "end": p2e,
        "summary": summarize_span(p2s, p2e),
        "markers": {k: [i for i in v if p2s <= i <= p2e] for k, v in markers.items()},
        "failures": detect_failures(p2s, p2e),
    })
    PHASES.append({
        "phase": "Aftermath / follow-ups",
        "start": p3s,
        "end": p3e,
        "summary": summarize_span(p3s, p3e),
        "markers": {k: [i for i in v if p3s <= i <= p3e] for k, v in markers.items()},
        "failures": detect_failures(p3s, p3e),
    })

    # Pull a few concrete snippets to ground the narrative
    snippet_idxs = sorted(set(markers["paper_request"][:2] + markers["paper_tex"][:2] + markers["paper_pdf"][:2]))
    snippets = []
    for i in snippet_idxs:
        w = window(i, min(N, i + 3), fields=["type", "message", "content", "tool", "tool_name", "status", "error", "timestamp", "_line_no"])  # a tiny window for context
        if w:
            snippets.append({"index": i, "events": w})

    FINAL = (
        "Paper-creation trajectory (heuristic)\n"
        f"- Total events scanned: {N}\n"
        f"- First paper marker at index {first}, last at {last}\n\n"
        "Markers found:\n"
        + "\n".join([f"- {k}: {len(v)} hits" for k, v in markers.items()])
        + "\n\n"
        "Phase summaries:\n"
        + "\n".join([f"- {p['phase']}: [{p['start']}..{p['end']}]" for p in PHASES])
        + "\n\n"
        "Grounding snippets (first occurrences):\n"
        + "\n".join([f"- idx {s['index']}: {str(s['events'][0])[:240]}" for s in snippets if s.get('events')])
    )
