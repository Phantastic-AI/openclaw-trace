# Research Brief Template (v1)

Origin: Demo://rollup

## 0) Header
- **Ticket:** Unknown - Signal (demo): System should better handle dependency on HEARTBEAT.md and avoid repeated error messages if no tasks need attention. (Demo://rollup)
- **Owner (DRI):** Unknown
- **Date / version:** 2026-02-01, v1
- **Decision needed:** Decide whether to implement handling for HEARTBEAT.md and suppress repeated Cron error messages when no tasks need attention.
- **Proposed next step:** Act

## 1) Problem + target outcome
- **Problem (observable):**
  - System emits a Cron error instructing to read HEARTBEAT.md and reply HEARTBEAT_OK when nothing needs attention.
  - Assistant responds with unrelated “Reminder needs attention” prompts and the error message repeats.
- **Success metrics (1-3):**
  - Unknown
- **Non-goals / out of scope (1-3):**
  - Unknown

## 2) Evidence snapshot
- **Current behavior (2-5 bullets):**
  - Cron error message says to read HEARTBEAT.md if it exists and reply HEARTBEAT_OK if nothing needs attention.
  - Assistant responds with “Reminder needs attention” prompts instead of the HEARTBEAT_OK flow.
  - The same dependency chain error is emitted again in the same session.
- **Data points (3-8 bullets max):**
  - tier: 1 (reasons include “incident”)
  - max_severity: low
  - score: 3.6931471805599454
  - count_items: 1
  - count_sessions: 1
  - tags_top: process (1), incident (1)
- **Repro steps (if applicable, 2-6 bullets):**
  - Unknown
- **Links:** Demo://rollup; docs/research-briefs/demo-top/process_tooling/context.md

## 3) Root Cause Analysis (RCA)
- **Suspected root cause(s) (1-3, falsifiable):**
  - Missing or ineffective gating that enforces “read HEARTBEAT.md → reply HEARTBEAT_OK if nothing needs attention.”
  - No suppression for repeated Cron error messages within the same session.
- **Contributing factors (2-6):**
  - Cron error is triggered after a failed memory lookup for prior notes.
  - Assistant replies with a reminder prompt rather than acknowledging the HEARTBEAT.md instruction.
  - Unknown whether HEARTBEAT.md exists or what it contains during the session.
- **Evidence mapping (per cause):**
  - **Evidence FOR:** Cron error explicitly instructs the HEARTBEAT.md behavior; assistant reply does not follow it; the error repeats.
  - **Evidence AGAINST / gaps:** No code pointers or logs; HEARTBEAT.md presence and contents not shown.
- **Confidence (per cause):** Low
- **Validation tests (1-5):**
  - Run a replay where HEARTBEAT.md is absent and no tasks need attention → expect a single HEARTBEAT_OK response if true; repeated error prompts if false.
  - Run a replay where HEARTBEAT.md exists with no tasks → expect HEARTBEAT_OK without reminder prompts if true; reminders if false.
  - Confirm DRI in task system → expect a named owner if true; remains Unknown if false.
  - Define success metrics with stakeholders → expect 1–3 measurable criteria if true; still Unknown if false.
  - Capture repro steps from a controlled session → expect consistent steps if true; still Unknown if false.

## 4) Options (competing paths)
- **Option A (Act):** Enforce HEARTBEAT.md handling and suppress repeated Cron errors when no tasks need attention.
  - Impact: Med
  - Cost/complexity: Low
  - Risk + rollback/containment: Risk of suppressing legitimate errors; rollback by disabling suppression.
  - Time-to-signal: fast
- **Option B (Experiment):** Add instrumentation and run a controlled replay to quantify error repetition and compliance with HEARTBEAT.md.
  - Impact: Med
  - Cost/complexity: Low
  - Risk + rollback/containment: Low risk; remove instrumentation if noisy.
  - Time-to-signal: medium
- **Option C (Defer):** Wait for more incidents before changing behavior.
  - Impact: Low
  - Cost/complexity: Low
  - Risk + rollback/containment: Continued repeated errors; no rollback needed.
  - Time-to-signal: slow

## 5) Recommendation (single choice)
- **Pick one:** Act
- **Rationale (3-6 bullets max):**
  - Evidence shows explicit HEARTBEAT.md instruction is not followed.
  - Repeated error message occurs in the same session.
  - Proposed change is low cost and directly targets the observed behavior.
- **Plan (next 1-3 actions):**
  - Implement a guard to read HEARTBEAT.md if it exists and reply HEARTBEAT_OK when nothing needs attention (Owner: Unknown).
  - Add suppression for repeated Cron error messages in a single session (Owner: Unknown).
  - Add a replay-based regression check for the HEARTBEAT_OK path (Owner: Unknown).
- **Stop conditions (reversal triggers):**
  - Legitimate reminder flows are suppressed or tasks in HEARTBEAT.md are skipped.

## 6) Appendix (optional)
- 2026-01-31: Cron error instructs HEARTBEAT.md handling; assistant replies with reminder prompt; Cron error repeats.

---

## Acceptance checklist (one line)
ACCEPT IF: ticket link + decision statement + evidence + RCA (confidence + tests) + >=2 options + explicit recommendation + next-step owner.