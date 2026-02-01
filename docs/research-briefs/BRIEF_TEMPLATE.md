# Research Brief Template (v1)

Origin: <Phorge ticket URL>

## 0) Header
- **Ticket:** T#### - <title> (link)
- **Owner (DRI):** <name/handle>
- **Date / version:** YYYY-MM-DD, v1
- **Decision needed:** <one sentence>
- **Proposed next step:** Act | Experiment | Defer

## 1) Problem + target outcome
- **Problem (observable):**
  - <bullet 1>
  - <bullet 2>
- **Success metrics (1-3):**
  - <metric 1>
- **Non-goals / out of scope (1-3):**
  - <non-goal 1>

## 2) Evidence snapshot
- **Current behavior (2-5 bullets):**
  - <what happens, when, to whom>
- **Data points (3-8 bullets max):**
  - <counts, deltas, rates, top examples>
- **Repro steps (if applicable, 2-6 bullets):**
  - <step 1>
- **Links:** <dashboards, logs, prior incidents, code pointers>

## 3) Root Cause Analysis (RCA)
- **Suspected root cause(s) (1-3, falsifiable):**
  - <cause 1>
- **Contributing factors (2-6):**
  - <factor 1>
- **Evidence mapping (per cause):**
  - **Evidence FOR:** <1-3 bullets>
  - **Evidence AGAINST / gaps:** <1-3 bullets>
- **Confidence (per cause):** High | Medium | Low
- **Validation tests (1-5):**
  - <change/measure -> expected if true -> expected if false>

## 4) Options (competing paths)
- **Option A (Act):** <change + expected impact>
  - Impact: High | Med | Low
  - Cost/complexity: High | Med | Low
  - Risk + rollback/containment: <note>
  - Time-to-signal: fast | medium | slow
- **Option B (Experiment):** <what to test>
  - Impact: High | Med | Low
  - Cost/complexity: High | Med | Low
  - Risk + rollback/containment: <note>
  - Time-to-signal: fast | medium | slow
- **Option C (Defer):** <dependency/unknown>
  - Impact: High | Med | Low
  - Cost/complexity: High | Med | Low
  - Risk + rollback/containment: <note>
  - Time-to-signal: fast | medium | slow

## 5) Recommendation (single choice)
- **Pick one:** Act | Experiment | Defer
- **Rationale (3-6 bullets max):**
  - <bullet 1>
- **Plan (next 1-3 actions):**
  - <action + owner>
- **Stop conditions (reversal triggers):**
  - <trigger 1>

## 6) Appendix (optional)
- Minimal trace snippet or tiny timeline only if it adds new information.

---

## Acceptance checklist (one line)
ACCEPT IF: ticket link + decision statement + evidence + RCA (confidence + tests) + >=2 options + explicit recommendation + next-step owner.

## Length guidance
- Target 400-900 words, hard cap 2 pages.
- No section >12 bullets; no bullet longer than 2 lines.

## Filename convention
- docs/research-briefs/T####-<slug>/oracle-brief-v1.md
