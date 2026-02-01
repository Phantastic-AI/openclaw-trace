# Signal Classification Evaluation — Research Brief

**Experiment:** Evaluating OpenClaw's automated `kind_v2` classifier  
**Date:** 2026-02-01  
**Author:** HAL (OpenClaw Agent)

---

## Tracing

| System | Reference |
|--------|-----------|
| **Weave** | [019c1b4b-b35b-743f-8a8a-0978de1bc367](https://wandb.ai/ninjaa-self/openclaw-trace-experiments/r/call/019c1b4b-b35b-743f-8a8a-0978de1bc367) |
| **Redis** | `signal_eval:experiment:1769984536` |

---

## Summary

**Overall Accuracy: 45%** (9/20 correct)

The automated classifier performs moderately on `ux_friction` (the dominant class) but struggles with smaller classes, particularly confusing `process_tooling` with `ux_friction`.

---

## Methodology

1. **Stratified sample:** 20 rollups from 121 total, ensuring class representation
2. **Blind classification:** Claude (sonnet-4) independently classified each signal without seeing the automated label
3. **Comparison:** Built confusion matrix, computed per-class precision/recall/F1

### Sample Distribution
```
ux_friction:           13
proactive_opportunity:  3
defect:                 2
process_tooling:        2
```

---

## Results

### Per-Class Metrics

| Class | Precision | Recall | F1 | Interpretation |
|-------|-----------|--------|-----|----------------|
| **ux_friction** | 0.78 | 0.54 | **0.64** | Best performer — high precision but misses some true positives |
| proactive_opportunity | 0.50 | 0.33 | 0.40 | Moderate — confused with user_delight and capability_gap |
| defect | 0.25 | 0.50 | 0.33 | Low precision — Claude thinks more things are defects |
| **process_tooling** | 0.00 | 0.00 | **0.00** | Complete failure — all misclassified as ux_friction |
| user_delight | N/A | N/A | N/A | No samples |
| capability_gap | N/A | N/A | N/A | No samples |
| reliability_perf | N/A | N/A | N/A | No samples |

### Confusion Matrix

```
                   Claude Classification
                 ux_fric  proact  defect  proc_t  user_d  capab   reliab
Auto  ux_friction     7       1       3       2       0       0       0
      proactive       0       1       0       0       1       1       0
      defect          0       0       1       1       0       0       0
      process_tool    2       0       0       0       0       0       0
```

---

## Key Findings

### 1. `process_tooling` → `ux_friction` confusion (100% error rate)

Both `process_tooling` samples were classified as `ux_friction` by Claude.

**Example:**
- Auto: `process_tooling`
- Claude: `ux_friction`
- Summary: "System instructs to read HEARTBEAT.md and follow it strictly"

**Root cause:** The boundary between "tooling issue" and "UX issue" is fuzzy. If a tooling problem causes user friction, is it process_tooling or ux_friction?

**Recommendation:** Clarify taxonomy or merge these classes.

### 2. `ux_friction` over-classification

Claude classified 11/20 samples as `ux_friction` vs. 13 in the ground truth. High precision (0.78) but moderate recall (0.54).

**Pattern:** When in doubt, the classifier defaults to `ux_friction` because it's the catch-all for "something annoying happened."

### 3. `defect` under-precision

Precision only 25% — Claude labels things as `defect` that the automated classifier calls other things.

**Example:**
- Auto: `ux_friction` 
- Claude: `defect`
- Summary: "System repeatedly reports 'Cron (error)'"

**Root cause:** "Cron (error)" literally contains the word "error" so Claude assumes it's a defect. The automated classifier looks at impact (user frustration) rather than symptom (error message).

---

## Recommendations

### Short-term (improve classifier)

1. **Merge `process_tooling` into `ux_friction`** — the distinction isn't meaningful in practice
2. **Add keyword features** — signals containing "error" should weight toward `defect`
3. **Increase training data** for minority classes

### Medium-term (improve taxonomy)

1. **Redefine classes** around user impact rather than technical symptom:
   - `friction` (user annoyed)
   - `blocker` (user can't proceed)
   - `delight` (user happy)
   - `opportunity` (agent could do better)

2. **Multi-label classification** — many signals are both `ux_friction` AND `defect`

### Long-term (improve pipeline)

1. **Human-in-the-loop labeling** — build gold standard dataset
2. **Active learning** — prioritize uncertain samples for human review
3. **Confidence scores** — classifier should output uncertainty

---

## Limitations

- **Small sample size** (n=20) — results may not generalize
- **Silver standard** — Claude labels are not human ground truth
- **Class imbalance** — 65% of samples are `ux_friction`
- **Single session source** — signals may not represent full distribution

---

## Artifacts

| Artifact | Location |
|----------|----------|
| Experiment script | `run_experiment.py` |
| Results JSON | `results_v2.json` |
| Data description | `input_files/data_description.md` |
| Weave trace | [019c1b4b...](https://wandb.ai/ninjaa-self/openclaw-trace-experiments/r/call/019c1b4b-b35b-743f-8a8a-0978de1bc367) |
| Redis key | `signal_eval:experiment:1769984536` |

---

## Conclusion

The OpenClaw signal classifier achieves **45% accuracy** against Claude's independent judgments. Performance is acceptable for `ux_friction` (F1=0.64) but poor for other classes. The main issue is **class boundary ambiguity** — particularly between `process_tooling` and `ux_friction`.

**Actionable next step:** Simplify the taxonomy and retrain with clearer class definitions.
