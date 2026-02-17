# Research Brief Template (v1)

Origin: Demo://rollup

## 0) Header
- **Ticket:** Unknown - Signal (demo): HTTP Conduit calls with api.token are consistently broken for search/read methods (Demo://rollup)
- **Owner (DRI):** Unknown
- **Date / version:** 2026-02-01, v1
- **Decision needed:** Decide whether the primary issue is the reported Conduit api.token failure or the Cron (error) behavior in the rollup context.
- **Proposed next step:** Experiment

## 1) Problem + target outcome
- **Problem (observable):** Ticket summary reports HTTP Conduit calls with api.token are consistently broken for search/read methods.
- **Problem (observable):** Rollup context shows repeated "Cron (error)" log messages during normal reminder interactions.
- **Success metrics (1-3):** Unknown
- **Non-goals / out of scope (1-3):** Unknown

## 2) Evidence snapshot
- **Current behavior (2-5 bullets):** System emits "Cron (error)" messages that describe memory lookup results and reminder context.
- **Current behavior (2-5 bullets):** Assistant continues normal reminder prompts (channels, tone, options) after each Cron (error) message.
- **Current behavior (2-5 bullets):** The pattern appears in session_id sha256:b237572fe9c550c77d2b894ec4b4c65c56d18286b591ef10fab9192729007949.
- **Current behavior (2-5 bullets):** The snippets show timestamps from 2026-01-31 19:28:52 to 19:30:06 UTC.
- **Data points (3-8 bullets max):** count_items 5; count_sessions 3; kind_v2_counts shows 5 defects.
- **Data points (3-8 bullets max):** tier 1 with reasons ['incident']; max_severity low; score 5.091759469228054.
- **Data points (3-8 bullets max):** tags_top: incident 5, error 4, cron 1, reminder 1.
- **Data points (3-8 bullets max):** fingerprint_id fp1:547b740ca3c56f4bcd483714f7564cf67dc7452e1eef7446916a109bfdd8c2fd; signature_id sig1:146c0f5f9c83ea0b3acef459cc9524aaaf425390513256964061366683de4464.
- **Data points (3-8 bullets max):** Example evidence indices include 403, 405, 419, 421, 627, 629 in the rollup.
- **Repro steps (if applicable, 2-6 bullets):** Unknown
- **Links:** docs/research-briefs/demo-top/defect/context.md; session_file 0001_31e89d3b-7e8b-40d6-9ec1-61a5722a4000.jsonl

## 3) Root Cause Analysis (RCA)
- **Suspected root cause(s) (1-3, falsifiable):** Unknown
- **Contributing factors (2-6):** Unknown
- **Evidence mapping (per cause) - Evidence FOR:** Unknown
- **Evidence mapping (per cause) - Evidence AGAINST / gaps:** Unknown
- **Confidence (per cause):** Low
- **Validation tests (1-5):** Attempt HTTP Conduit `search` and `read` with `api.token` as described in the ticket -> failures reproduce consistently -> calls succeed or fail inconsistently.
- **Validation tests (1-5):** Replay the reminder flow from session_file 0001_31e89d3b-7e8b-40d6-9ec1-61a5722a4000.jsonl -> Cron (error) messages appear during normal prompts -> no Cron (error) messages.
- **Validation tests (1-5):** Check memory lookup outcome for the reminder context -> empty memory aligns with Cron (error) text -> memory present but Cron (error) still emitted.
- **Validation tests (1-5):** Search other sessions for Cron (error) without user-visible failures -> many false positives -> Cron (error) only appears with real failures.

## 4) Options (competing paths)
- **Option A (Act):** Reclassify or suppress Cron (error) logging during reminder interactions to reduce incident noise.
- **Option A Impact:** Med
- **Option A Cost/complexity:** Low
- **Option A Risk + rollback/containment:** Risk of hiding true errors; rollback by restoring original logging.
- **Option A Time-to-signal:** fast
- **Option B (Experiment):** Validate the api.token failure claim and the Cron (error) signal via targeted repro and session inspection.
- **Option B Impact:** Med
- **Option B Cost/complexity:** Med
- **Option B Risk + rollback/containment:** Low risk; purely investigative.
- **Option B Time-to-signal:** fast
- **Option C (Defer):** Wait for more sessions or higher severity signals before acting.
- **Option C Impact:** Low
- **Option C Cost/complexity:** Low
- **Option C Risk + rollback/containment:** Ongoing noise and missed real defect.
- **Option C Time-to-signal:** slow

## 5) Recommendation (single choice)
- **Pick one:** Experiment
- **Rationale (3-6 bullets max):** Evidence shows Cron (error) messages during normal reminder prompts with no explicit failure in the snippet.
- **Rationale (3-6 bullets max):** The ticket summary claims Conduit api.token failures, but the provided context does not show those errors.
- **Rationale (3-6 bullets max):** Severity is low and volume is limited (5 items, 3 sessions), so validate before acting.
- **Rationale (3-6 bullets max):** There are concrete timestamps and a session_file to use for targeted replay.
- **Plan (next 1-3 actions):** Reproduce HTTP Conduit `search`/`read` with `api.token` as described in the ticket -> owner Unknown.
- **Plan (next 1-3 actions):** Replay the reminder interaction from session_file 0001_31e89d3b-7e8b-40d6-9ec1-61a5722a4000.jsonl to confirm Cron (error) triggers -> owner Unknown.
- **Plan (next 1-3 actions):** Decide whether to reclassify or suppress Cron (error) for this flow based on results -> owner Unknown.
- **Stop conditions (reversal triggers):** If api.token failures are confirmed and repeatable, pivot to that fix path.
- **Stop conditions (reversal triggers):** If Cron (error) is expected logging with no underlying failure, close or downgrade the signal.

## 6) Appendix (optional)
- Minimal timeline: 2026-01-31 19:28:52 to 19:30:06 UTC shows repeated Cron (error) messages while the assistant asks for reminder details.

---

## Acceptance checklist (one line)
ACCEPT IF: ticket link + decision statement + evidence + RCA (confidence + tests) + >=2 options + explicit recommendation + next-step owner.