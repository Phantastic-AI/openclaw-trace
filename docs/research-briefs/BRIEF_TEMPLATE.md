# Research Brief Template (v2)

Origin: <Phorge ticket URL>

## Definition of Done
ACCEPT IF: YAML header complete (no "Unknown") + decision statement + evidence with data source links + RCA (confidence + tests) + >=2 options with owners + experiment design (if applicable) + explicit recommendation + next-step owner + safety check.

---

## 0) Header

```yaml
---
ticket: T####
title: "<title>"
owners: [@dri, @reviewer]
created: YYYY-MM-DD
version: v1
code_sha: ""        # commit SHA for relevant code
data_sha: ""        # dataset/session snapshot hash
decision: "Act | Experiment | Defer"
---
```

## 1) Problem + target outcome
- **Problem (observable):**
  - <bullet 1>
  - <bullet 2>
- **User / business impact (1-2 bullets):**
  - <who is affected, how badly>
- **Outcome metrics (quantitative, 1-3):**
  - <metric 1>
- **Non-goals / out of scope (1-3):**
  - <non-goal 1> (use "None" if truly none — never "Unknown")

## 2) Evidence snapshot
- **Quantitative data (3-8 bullets max):**
  - <counts, deltas, rates, top examples>
  - **Data source:** <script path, SQL query, or notebook link>
- **Qualitative examples (2-5 bullets):**
  - <what happens, when, to whom — with quotes if available>
- **Repro steps (if applicable, 2-6 bullets):**
  - <step 1>
- **Links:** <dashboards, logs, prior incidents, code pointers>

## 3) Root Cause Analysis (RCA)
- **Suspected root cause(s) (1-3, falsifiable):**
  - <cause 1>
- **Contributing factors (2-6):**
  - <factor 1>
- **Assumptions (falsifiable, 1-3):**
  - <assumption 1>
- **Evidence mapping (per cause):**
  - **Evidence FOR:** <1-3 bullets>
  - **Evidence AGAINST / gaps:** <1-3 bullets>
- **Confidence (per cause):** High | Medium | Low
- **Validation tests (1-5):**
  - <change/measure → expected if true → expected if false>

## 3b) Experiment Design (only if Next Step = Experiment)
- **Hypothesis:** If <change>, then <expected outcome>
- **Treatment(s) vs Control(s):**
  - Treatment: <what changes>
  - Control: <baseline>
- **Sample size / runtime stop-rule:** <n sessions, n days, or stopping criterion>
- **Evaluation metrics & statistical test:** <metric + test (e.g., paired t-test, bootstrap CI)>
- **Logging plan:** <what gets logged, where, schema>
- **Reproducibility:**
  - [ ] One-command repro: `make reproduce-T####` or equivalent
  - [ ] Random seeds fixed
  - [ ] Requirements locked
  - [ ] Config committed

## 4) Options (competing paths)
- **Option A (Act):** <change + expected impact>
  - Impact: High | Med | Low
  - Cost/complexity: High | Med | Low
  - Risk + rollback/containment: <note>
  - Dependencies / blockers: <note>
  - Owner: <@handle>
  - Time-to-signal: fast | medium | slow
- **Option B (Experiment):** <what to test>
  - Impact: High | Med | Low
  - Cost/complexity: High | Med | Low
  - Risk + rollback/containment: <note>
  - Dependencies / blockers: <note>
  - Owner: <@handle>
  - Time-to-signal: fast | medium | slow
- **Option C (Defer):** <dependency/unknown>
  - Impact: High | Med | Low
  - Cost/complexity: High | Med | Low
  - Risk + rollback/containment: <note>
  - Dependencies / blockers: <note>
  - Owner: <@handle>
  - Time-to-signal: fast | medium | slow

## 5) Recommendation (single choice)
- **Pick one:** Act | Experiment | Defer
- **Rationale (3-6 bullets max):**
  - <bullet 1>
- **Solution type:** Code patch | Config change | AGENTS.md update | Lobster workflow | Skill update | Hybrid
- **Roll-out strategy:** <flag-guard, % ramp, direct deploy, `.lobster` file for reuse>
- **Plan (next 1-3 actions):**
  - <action + owner>
- **Stop conditions (reversal triggers):**
  - <trigger 1>

## 6) Background & Prior Work (optional)
- <3-4 bullets linking to earlier tickets, briefs, or papers>

## 7) Safety & Compliance
- **Privacy impact:** <PII exposure? Redaction needed?>
- **Model/prompt safety:** <any prompt injection, alignment, or red-team concerns?>
- **Data governance:** <who can access artifacts? retention policy?>

## 8) Appendix & Artifacts (optional)
- Log extracts, diagrams, experiment notebooks
- Minimal trace snippet or timeline only if it adds new information

---

## Length guidance
- Target 400-900 words, hard cap 2 pages.
- No section >12 bullets; no bullet longer than 2 lines.

## Filename convention
- `docs/research-briefs/T####-<slug>/brief-v1.md`
- Artifacts: `docs/research-briefs/T####-<slug>/artifacts/`
