# Frontend Spec (literate)

Goal: a **readable, explorable dashboard** that shows the self-improvement loop end‑to‑end: signals → rollups → tickets → research briefs → experiments → fixes.

## Primary users

- **Operator**: wants a quick snapshot, top risks, and what to do next.
- **Research lead**: wants to inspect evidence, compare hypotheses, and run experiments.
- **Demo viewer**: wants to understand the loop in <60 seconds.

## Top‑level information architecture

```
[Home]
  ├─ Overview (daily loop)
  ├─ Signals (raw items)
  ├─ Rollups (clusters)
  ├─ Tickets (Phorge / IR)
  ├─ Research Briefs
  └─ Experiments / Fixes
```

## Napkin UI sketches (ASCII)

### Home / Overview

```
+--------------------------------------------------------------+
| openclaw-agi  |  last run: 2026-02-01  |  status: healthy    |
+--------------------------------------------------------------+
|  Loop Health                                                      |
|  [Signals mined] [Rollups] [Tickets] [Briefs] [Experiments]   |
|     537               461       32         8          3       |
+--------------------------------------------------------------+
|  Top 5 Today (by score)                                        |
|  1) Usage limits causing failures (tier1)   [open] [brief]    |
|  2) Phorge API invalid session                [open] [brief]  |
|  3) ...                                                          |
+--------------------------------------------------------------+
|  Loop Narrative (one paragraph)                               |
|  "The system hit rate-limit failures..."                     |
+--------------------------------------------------------------+
```

### Rollups

```
+----------------------+  +------------------------------------+
| Filters              |  | Rollup list                         |
| kind_v2  [x]         |  |  [tier1] Usage limits ...   score 9 |
| tier     [1][2][3]   |  |  [tier2] Phorge invalid ... score 7 |
| tags     [incident]  |  |  [tier3] UX confusion ...  score 4  |
+----------------------+  +------------------------------------+
| Selected rollup:                                        [CTA] |
|  fingerprint: fp1:...                                        |
|  canonical summary                                            |
|  evidence links → (session, span)                             |
|  suggested next step: brief / ticket / experiment             |
+--------------------------------------------------------------+
```

### Ticket detail

```
+--------------------------------------------------------------+
| Ticket T123  | status: Open | fingerprint: fp1:...           |
+--------------------------------------------------------------+
| Canonical summary                                              |
| Context blocks (rollup evidence, top tags, affected sessions) |
| Linked research briefs → experiments → fixes                   |
+--------------------------------------------------------------+
```

## User journeys

### 1) Demo viewer (60‑second flow)
1. Land on **Home** and read the one‑paragraph loop narrative.
2. Click **Top 5 Today** → see a rollup detail.
3. Click **Research Brief** → scan hypothesis + RCA.
4. Click **Experiment** → see result and next action.

### 2) Operator (daily triage)
1. Open **Rollups** with tier=1/2 filters.
2. Sort by score, skim evidence, click “Create/Update Ticket.”
3. Assign top 3 to **Research Briefs**.
4. Mark daily run as done.

### 3) Research lead (deep dive)
1. Open **Research Briefs** list.
2. Compare competing hypotheses + experiments.
3. Link results back to tickets.
4. Recommend fix or change of direction.

## Data sources and integration

- `out_signals.jsonl` → raw signals
- `rollup.json` → cluster summaries + fingerprints
- `ticket_ir.jsonl` → portable ticket format
- Phorge API → ticket status + comments
- Research briefs directory → markdown

## Interaction & UX notes

- **Literate tone**: short narrations next to charts; minimal jargon.
- **Evidence-first**: every rollup must link back to raw spans.
- **Privacy**: avoid showing verbatim long quotes; show redacted snippets.
- **Drill‑down**: every card has a 1‑click path to context.

## Minimal MVP screens

- Home / Overview
- Rollups list + detail
- Ticket detail (Phorge or IR)
- Research Brief viewer

## Stretch ideas

- “Loop Health Score” time‑series
- Automatic daily email summary
- Compare pre/post‑fix rollup metrics
