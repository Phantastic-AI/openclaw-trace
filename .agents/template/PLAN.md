# Skeleton of a Good ExecPlan
_A living design & execution record for this agent / feature._

This document must be **self-contained**: a new contributor can execute end-to-end without other docs.
Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.
Define all non-obvious terms and avoid "as discussed elsewhere" references.

---

## Metadata
- **Owner:** <name or team>
- **Created:** <YYYY-MM-DD>
- **Last Updated:** <YYYY-MM-DD>
- **Agent / Module:** <path or name>
- **Related Plans:** <links to sibling .agents plans or PRs>
- **Plan Policy (if applicable):** <repo-root path to PLANS.md> (this plan must comply)

---

## <Short, action-oriented description>
Describe the intended capability or fix in one sentence:  
"What new behavior or improvement will exist when this plan is complete?"
Include (briefly) the observable success condition (what "done" looks like).

---

## Purpose / Big Picture
Explain what the user or system gains and how it's observable.  
State the measurable or visible outcome - e.g., "users can now ask multi-turn clarifications within 2s latency."
Prefer user-visible behavior and concrete observables over internal implementation goals.

---

## Context and Orientation
Summarize the current state of the system:
- Where this fits (sub-agent, API, or service)
- Key files / modules (with full paths)
- Known limitations or previous attempts
- Define any domain terms or internal jargon  
- Interfaces & dependencies: public APIs touched/added (names + signatures), services/libraries involved, and why
Do **not** assume reader context from other plans.

---

## Plan of Work
Describe the concrete edits and steps:
1. File /Module - change description.
2. Expected effect or validation test.
3. Rollout or verification step.  
Keep prose tight but explicit enough that another engineer could resume work.
For each step, also include:
- Concrete steps: exact commands to run (with working directory) + short expected output
- Validation & acceptance: specific inputs/outputs; tests that fail-before and pass-after
- Idempotence & recovery: safe retry/rollback/cleanup guidance for risky steps
- Artifacts: what proof to capture (diff snippet, log line, benchmark result) and where to paste/link it

---

## Progress
Track all steps with checkboxes and timestamps.

- [x] (2025-10-01 13:00 Z) Implemented streaming API stub.  
- [ ] Add async callback handler for `on_message`.  
- [ ] Write integration tests (completed: 2/6; remaining: 4).  

Use UTC timestamps to visualize progress rate.  
Always keep this list current - it's the "truth" for status.
Every stopping point must be reflected here (split partially completed tasks into "done" vs "remaining").

---

## Surprises & Discoveries
Note any unexpected findings, side effects, optimizations, or new questions.

- Observation: SSE buffering disabled improved latency by 0.8 s.  
- Evidence: measured across 10 requests on staging.

---

## Decision Log
Every material decision should be logged:

- **Decision:** Switch to `asyncio.Queue` for handoff events.  
- **Rationale:** Cleaner coroutine management vs. manual locks.  
- **Date/Author:** 2025-10-05 - A.Advani  

---

## Outcomes & Retrospective
At milestones or completion, capture:
- What succeeded / failed.
- Measured impact vs. intended purpose.
- Lessons for next iteration.

---

## Risks / Open Questions
(Optional but often included)
- What assumptions could fail?
- What metrics or user tests will verify success?
- Recovery/rollback: what to do if deployment/test/command fails; how to return to a clean state

---

## Next Steps / Handoff Notes
(Optional)
List what's left for another contributor or phase.  
Include links to PRs, issues, or future plans.

---
