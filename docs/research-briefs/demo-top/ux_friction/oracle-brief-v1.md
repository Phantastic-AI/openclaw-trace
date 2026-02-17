# Research Brief Template (v1)

Origin: `Demo://rollup`

## 0) Header
- **Ticket:** Unknown - Signal (demo): System repeatedly issues 'Cron (error)' messages indicating potential issues with task handling or state management. (`Demo://rollup`)
- **Owner (DRI):** Unknown
- **Date / version:** Unknown, v1
- **Decision needed:** Decide how to address recurring 'Cron (error)' messages tied to task handling/state management.
- **Proposed next step:** Experiment

## 1) Problem + target outcome
- **Problem (observable):**
  - System repeatedly issues 'Cron (error)' messages indicating potential issues with task handling or state management.
  - Multiple 'Cron (error)' entries appear in a single session with differing acknowledgements (e.g., "Got it", "Noted", "I checked memory...").
- **Success metrics (1-3):**
  - Unknown
- **Non-goals / out of scope (1-3):**
  - Unknown

## 2) Evidence snapshot
- **Current behavior (2-5 bullets):**
  - In one session (count_sessions: 1), 'Cron (error)' messages appear repeatedly around 19:17-19:25 UTC on 2026-01-31.
  - The assistant responds with "Reminder needs attention" prompts after each 'Cron (error)' system line in the trace snippets.
  - The rollup is tagged as incident/error with medium max severity.
- **Data points (3-8 bullets max):**
  - count_items: 2; count_sessions: 1
  - max_severity: medium; tier: 1 (reasons=['incident'])
  - score: 5.098612288668109
  - kind_v2_counts: {'ux_friction': 2}
  - tags_top: [['error', 2], ['incident', 2]]
  - fingerprint_id: `fp1:3d13a00f23c7165d5d2f9382972dd02dddfdbf9d6009b6cd9ea657fa618eb18b`
  - signature_id: `sig1:4fcf1ed4230f6a331d9284ac845d4aa5477499b5ab1105536fa88f06f361df96`
- **Repro steps (if applicable, 2-6 bullets):**
  - Unknown
- **Links:** `Demo://rollup`, `docs/research-briefs/demo-top/ux_friction/context.md`, `0001_31e89d3b-7e8b-40d6-9ec1-61a5722a4000.jsonl`

## 3) Root Cause Analysis (RCA)
- **Suspected root cause(s) (1-3, falsifiable):**
  - Cron subsystem error path is triggered during task handling/state management, producing 'Cron (error)' messages.
- **Contributing factors (2-6):**
  - Multiple 'Cron (error)' events occur in a single session within minutes.
  - Message bodies vary ("Got it", "Noted", "I checked memory..."), suggesting inconsistent handling or retries.
- **Evidence mapping (per cause):**
  - **Evidence FOR:** canonical_summary cites repeated 'Cron (error)' messages and task/state issues; sample items show multiple timestamps in the same session.
  - **Evidence AGAINST / gaps:** no stack traces or code pointers; only one session in evidence; no explicit repro steps.
- **Confidence (per cause):** Low
- **Validation tests (1-5):**
  - Inspect `0001_31e89d3b-7e8b-40d6-9ec1-61a5722a4000.jsonl` around indices 273-365 to confirm trigger sequence for each 'Cron (error)'.
  - Verify whether a `HEARTBEAT.md` file existed during the session and whether the cron handler attempted to read it.
  - Attempt a controlled replay of the same system prompts; if 'Cron (error)' repeats, the issue is reproducible; if not, it is transient.
  - Review `Demo://rollup` for missing metadata (DRI, success metrics, non-goals, repro steps, brief date) and update sections if present.

## 4) Options (competing paths)
- **Option A (Act):** Fix cron handling during task/state processing to prevent 'Cron (error)' emissions and correctly follow HEARTBEAT instructions.
  - Impact: Med
  - Cost/complexity: Med
  - Risk + rollback/containment: Potential behavior change in cron handling; guard with feature flag if available.
  - Time-to-signal: medium
- **Option B (Experiment):** Instrument cron error path and replay the session to isolate triggers and classify the error type.
  - Impact: Med
  - Cost/complexity: Low
  - Risk + rollback/containment: Low risk; logging can be removed after diagnosis.
  - Time-to-signal: fast
- **Option C (Defer):** Wait for more sessions or higher severity signals before acting.
  - Impact: Low
  - Cost/complexity: Low
  - Risk + rollback/containment: Risk of continued UX friction; no rollback needed.
  - Time-to-signal: slow

## 5) Recommendation (single choice)
- **Pick one:** Experiment
- **Rationale (3-6 bullets max):**
  - Evidence is limited to 2 items and 1 session, so scope is unclear.
  - Error messages vary in content, indicating the trigger is not well understood.
  - No repro steps or code pointers exist, so instrumentation/replay is the fastest path to clarity.
- **Plan (next 1-3 actions):**
  - Inspect the session file around the indexed spans to map trigger -> response (Owner: Unknown).
  - Add minimal logging around the cron error path or capture extra trace context on the next run (Owner: Unknown).
  - Update the ticket with findings and define success metrics/scope (Owner: Unknown).
- **Stop conditions (reversal triggers):**
  - If inspection shows the messages are synthetic/test artifacts, stop and reclassify.
  - If a single clear defect is identified, switch to Act.

## 6) Appendix (optional)
- 2026-01-31 19:17:37 and 19:17:51 UTC: 'Cron (error)' with "Got it."
- 2026-01-31 19:24:50 UTC: 'Cron (error)' with "Noted."
- 2026-01-31 19:25:43 UTC: 'Cron (error)' message notes no extra memory/context beyond the reminder.

---

## Acceptance checklist (one line)
ACCEPT IF: ticket link + decision statement + evidence + RCA (confidence + tests) + >=2 options + explicit recommendation + next-step owner.