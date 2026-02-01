# Architecture (openclaw-trace)

```
                +------------------------------+
                |  Session JSONL (traces)      |
                |  /home/.../sessions/*.jsonl  |
                +---------------+--------------+
                                |
                                v
                       +--------+--------+
                       |   mine-signals  |
                       |  (LLM + rules)  |
                       +--------+--------+
                                |
                       JSONL items w/ evidence
                                |
                                v
                       +--------+--------+
                       |  rollup-signals |
                       |  cluster + rank |
                       +--------+--------+
                                |
                +---------------+-----------------+
                |                                 |
                v                                 v
        +-------+--------+                 +------+-------+
        |  ticket IR     |                 |  Phorge      |
        |  JSONL export  |                 |  tickets     |
        +-------+--------+                 +------+-------+
                |                                 |
                +---------------+-----------------+
                                |
                                v
                       +--------+--------+
                       | research briefs |
                       | actor-critic    |
                       | (Claude+Codex)  |
                       +--------+--------+
                                |
                                v
                       +--------+--------+
                       | experiments     |
                       | + fixes         |
                       +--------+--------+
                                |
                                v
                       +--------+--------+
                       | metrics / evals |
                       +--------+--------+
                                |
                                v
                       (new traces feed back in)
```

Notes:
- Evidence-first: items include exact quotes + indices; rollups drop verbatim quotes.
- PII: redaction stub in miner; rollups redact summaries and avoid raw evidence.
- Fingerprints: stable IDs used to update/merge tickets over time.
