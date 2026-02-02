# Incident: Truncated Evidence in Signal Evaluation

**Date:** 2026-02-02  
**Severity:** Medium  
**Status:** Resolved  
**Phorge:** Pending wiki upload

## Summary

Signal classification/validity experiments were running with **zero session context** due to a data format mismatch. This caused Claude to make judgments based only on truncated summaries (~50 chars) instead of full evidence (~2000 chars).

## Root Cause

The rollup JSON contains `sample_refs[].session_id` as **SHA256 hashes**:

```json
"session_id": "sha256:b237572fe9c550c77d2b894ec4b4c65c56d18286b591ef10fab9192729007949"
```

But session files are named with UUIDs:
```
0001_31e89d3b-7e8b-40d6-9ec1-61a5722a4000.jsonl
```

The matching logic looked for UUID in filename, found nothing, returned empty context.

## Impact

| Experiment | Before (truncated) | After (full evidence) |
|------------|-------------------|----------------------|
| Validity | 75% precision | **100% precision** |
| Classification | 45% accuracy | 55% accuracy |

The 75% → 100% precision jump shows the evaluator was severely handicapped by missing context.

## Fix

Use `out_signals_latest120_v2.jsonl` which contains `evidence[].quote` — actual conversation snippets:

```python
def get_session_context(rollup, raw_signals, max_chars=3000):
    # Fuzzy match by summary words
    for summary, signals in raw_signals.items():
        if len(canonical_words & summary_words) >= 3:
            for sig in signals[:3]:
                for ev in sig.get("evidence", []):
                    evidence_snippets.append(f"[{ev['role']}]: {ev['quote']}")
```

## Lessons Learned

1. **Always verify data flows end-to-end** — check that context is actually populated
2. **Log context length** — `print(f"Context length: {len(context)} chars")` immediately revealed the bug
3. **Don't trust ID formats** — hashes ≠ UUIDs, verify the actual values

## Artifacts

- Fixed scripts: `experiments/signal_validity_v2.py`, `experiments/signal_classification_v2.py`
- Commits: `575a115`, `ddce902`
