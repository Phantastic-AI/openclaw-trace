# openclaw-trace — mined idea examples (for oracle review)

This document is a small, concrete set of **(trace snippet → mined idea)** examples to evaluate whether the `openclaw-trace mine-ideas` pipeline is a good candidate for further investment.

Repo: https://github.com/Phantastic-AI/openclaw-trace

## How the pipeline works (current)
- Scan session JSONL traces in a directory.
- Choose candidate events using cheap heuristics:
  - keyword hits in extracted event text
  - tool failures (`message.role==toolResult` with `details.status==error` or nonzero `exitCode`)
- Build a small synopsis window around each hit (truncated).
- Ask an LLM to propose a frontier experiment as strict JSON:
  - `title, hypothesis, method, metrics, synthetic_dataset, why_frontier`

## Example 1
- session: `001020c6-a3a1-40e0-9d9c-17acafdcc6d6.jsonl`
- hit: tool-ish / skill content around the cron reminder + subsequent toolResult content

Mined idea (LLM output):
```json
{
  "title": "Evaluating Low Thinking Level AI Models in Task-Oriented Report Enrichment",
  "hypothesis": "AI models operating at a low thinking level can effectively enrich structured reports with minimal human intervention.",
  "method": "Deploy the 'claude-opus-4-5' model configured at low thinking level to automatically enrich Lucas reports; compare enriched reports against human-annotated benchmarks.",
  "metrics": "Enrichment accuracy, relevance score, time to completion, and human satisfaction ratings."
}
```

## Example 2
- session: `00592138-f3fe-434c-9cb7-151a8cc8e464.jsonl`

Mined idea (LLM output):
```json
{
  "title": "Evaluating Low Thinking Level Impact on Complex Reasoning Tasks in Claude-Opus-4-5",
  "hypothesis": "Setting the AI's thinking level to 'low' reduces its performance on complex reasoning tasks compared to higher thinking levels.",
  "method": "Run Claude-Opus-4-5 on a benchmark suite of complex reasoning problems twice: once with thinking level set to 'low' and once with 'high'. Compare accuracy and reasoning coherence.",
  "metrics": "Accuracy percentage on reasoning tasks, coherence score from human evaluators, response time per query."
}
```

## Notes / caveats surfaced by ninjaa
- Conversations contain *many* ideas; current pipeline returns **one idea per candidate hit**, which may be the wrong unit.
- Prefer a next step of **clustering + dedupe + rank** across all candidate idea snippets.
- Keep CLI and naming minimal (Unix philosophy); avoid brittle knobs.
