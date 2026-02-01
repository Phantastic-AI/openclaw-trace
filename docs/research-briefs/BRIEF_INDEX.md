# Research Brief Index

**Updated:** 2026-02-01 22:15 UTC  
**Weave Project:** [ninjaa-self/openclaw-trace-experiments](https://wandb.ai/ninjaa-self/openclaw-trace-experiments/weave)

---

## Completed Experiments

| ID | Brief | Finding | Fix | Weave Trace | Status |
|----|-------|---------|-----|-------------|--------|
| **T154** | reliability_perf (cron timeout) | Lock contention in CronService blocks reads during job execution | Non-blocking cache reads for `list()` + `status()` | [019c1b21...](https://wandb.ai/ninjaa-self/openclaw-trace-experiments/r/call/019c1b21-ab4b-70d9-94df-dabe71ccc165) | ✅ Fix built, awaiting deploy |
| **UX-01** | ux_friction (cron error spam) | 72% of "Cron (error)" messages contain successful content (false errors) | Separate delivery failure from job failure | [019c1b36...](https://wandb.ai/ninjaa-self/openclaw-trace-experiments/r/call/019c1b36-dadf-7425-91bf-b8e77316351b) | ✅ Analysis complete, fix proposed |
| **EVAL-01** | Signal Classification | Classifier accuracy 45%; process_tooling/ux_friction boundary fuzzy | Merge classes, add keyword features | [019c1b4b...](https://wandb.ai/ninjaa-self/openclaw-trace-experiments/r/call/019c1b4b-b35b-743f-8a8a-0978de1bc367) | ✅ Denario experiment complete |
| **VALID-01** | Signal Validity | **75% precision** — defect 100%, ux_friction 69% | Improve context retrieval for validation | N/A | ✅ Ground truth validated |

---

## Pending Briefs

| Category | Brief | Problem | Recommended Action | Denario-Compatible? |
|----------|-------|---------|-------------------|---------------------|
| **process_tooling** | HEARTBEAT.md handling | System emits cron errors, assistant ignores HEARTBEAT_OK flow | Implement guard + suppress repeats | ❌ Quick fix |
| **defect** | HTTP Conduit broken | Conduit calls with api.token fail for search/read methods | Debug + fix HTTP layer | ❌ Bug fix |
| **capability_gap** | Unnecessary tool calls | Assistant calls tools when HEARTBEAT.md unchanged | Cache HEARTBEAT.md state | ❌ Optimization |
| **reliability_perf** | ChatGPT usage limits | User hits pro plan limits → errors, no response | Analyze usage patterns, predict limits | ✅ **Denario candidate** |
| **proactive_opportunity** | (unclear) | TBD | TBD | ❓ |
| **user_delight** | Positive feedback | User appreciates hybrid draft format | Document as best practice | ❌ No experiment |

---

## Denario-Compatible Experiments

For **AI-for-Science** style research (Denario pipeline), the best candidates are:

### 1. **Usage Pattern Analysis** (reliability_perf)
- **Data:** Token usage across sessions, model distributions, cost patterns
- **Question:** Can we predict when a user will hit rate limits?
- **Method:** Time-series analysis, anomaly detection
- **Output:** Prediction model + usage dashboard

### 2. **Signal Classification Quality** (meta-experiment)
- **Data:** Mined signals, brief classifications, false positive rates
- **Question:** How accurate is the signal mining pipeline?
- **Method:** Compare automated classifications to human labels
- **Output:** Precision/recall metrics, confusion matrix

### 3. **Agent Behavior Patterns** (new)
- **Data:** Session traces, tool call sequences, response patterns
- **Question:** What patterns predict successful vs failed interactions?
- **Method:** Sequence mining, clustering
- **Output:** Behavioral taxonomy, success predictors

---

## Artifacts

| Type | Location |
|------|----------|
| T154 Paper | `experiments/T154_RESEARCH_PAPER.md` |
| UX Friction Paper | `experiments/UX_FRICTION_RESEARCH_PAPER.md` |
| T154 Baseline | `experiments/t154_baseline_v4.json` |
| UX Friction Analysis | `experiments/ux_friction_analysis.json` |
| Redis Keys | `t154:*`, `ux_friction:*` |

---

## Next Actions

1. **Deploy T154 fix** (gateway restart after demos)
2. **Implement UX-01 fix** (delivery failure → ok status)
3. **Run Denario experiment** on usage patterns or signal classification
