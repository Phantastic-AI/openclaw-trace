# Research Brief Template (v1)

Origin: Demo://rollup

## 0) Header
- **Ticket:** Unknown - Assistant should avoid unnecessary tool calls when HEARTBEAT.md content is unchanged. (Demo://rollup)
- **Owner (DRI):** Unknown
- **Date / version:** Unknown, v1
- **Decision needed:** Should we prevent repeated HEARTBEAT.md reads when content is unchanged in-session?
- **Proposed next step:** Act

## 1) Problem + target outcome
- **Problem (observable):**
  - Repeated user prompts to read HEARTBEAT.md trigger repeated `read` tool calls in one session.
  - The tool results are identical, yet the assistant still re-reads and replies `HEARTBEAT_OK`.
- **Success metrics (1-3):**
  - No redundant `read` tool calls when HEARTBEAT.md content is unchanged between prompts.
- **Non-goals / out of scope (1-3):**
  - Unknown

## 2) Evidence snapshot
- **Current behavior (2-5 bullets):**
  - 2026-01-31 04:13:32Z: assistant calls `read` on `/home/debian/clawd/HEARTBEAT.md` then replies `HEARTBEAT_OK`.
  - 2026-01-31 04:43:31Z and 05:13:30Z: repeated prompt triggers new `read` tool calls; tool output is the same guidance text.
  - HEARTBEAT guidance states: only report items that are truly new or changed.
- **Data points (3-8 bullets max):**
  - count_items: 1; count_sessions: 1.
  - max_severity: low; tier: 3.
  - score: 1.6931471805599454.
  - kind_v2_counts: {'capability_gap': 1}.
  - tags_top: [['heartbeat', 1], ['efficiency', 1]].
  - fingerprint_id: fp1:e85ba8a875a7b882ae93e626d391fe5df09433f07fba30623fe0ec391cca15f8.
  - signature_id: sig1:83416aeb1e984b1b073bec91accd02889f5a57f83cf8343c4c0ad7bcffd07e27.
- **Repro steps (if applicable, 2-6 bullets):**
  - User: “Read HEARTBEAT.md if it exists... If nothing needs attention, reply HEARTBEAT_OK.”
  - Assistant calls `read` and replies `HEARTBEAT_OK`.
  - User repeats the same instruction; assistant calls `read` again even though output is identical.
- **Links:** Demo://rollup; docs/research-briefs/demo-top/capability_gap/context.md

## 3) Root Cause Analysis (RCA)
- **Suspected root cause(s) (1-3, falsifiable):**
  - No change detection or caching for HEARTBEAT.md; the assistant re-reads on each prompt.
- **Contributing factors (2-6):**
  - The prompt explicitly instructs the assistant to read the file each time.
  - The identical tool output suggests unchanged content, but no suppression occurs.
- **Evidence mapping (per cause):**
  - **Evidence FOR:** repeated `read` tool calls with identical HEARTBEAT content; repeated `HEARTBEAT_OK` replies.
  - **Evidence AGAINST / gaps:** no code-level evidence of missing caching; no explicit policy stating caching is required.
- **Confidence (per cause):** Low
- **Validation tests (1-5):**
  - Inspect HEARTBEAT handling logic -> if true, no caching/change check exists -> if false, caching exists but is not triggered.
  - Replay the prompt sequence with unchanged HEARTBEAT.md -> if true, `read` is called each time -> if false, `read` is skipped after first read.
  - Check Demo://rollup for ticket ID, DRI, and date -> if found, replace Unknown -> if not, keep Unknown.
  - Look for explicit success metrics or non-goals in ticket/context -> if found, replace Unknown -> if not, keep generic metric.

## 4) Options (competing paths)
- **Option A (Act):** Add change detection or memoization for HEARTBEAT.md reads within a session.
  - Impact: Med
  - Cost/complexity: Low
  - Risk + rollback/containment: risk of stale guidance; mitigate by re-reading on detected change.
  - Time-to-signal: fast
- **Option B (Experiment):** Gate `read` calls behind a simple heuristic and compare redundant reads.
  - Impact: Med
  - Cost/complexity: Med
  - Risk + rollback/containment: potential missed updates; keep a simple toggle for rollback.
  - Time-to-signal: medium
- **Option C (Defer):** Wait for more signals or higher severity before acting.
  - Impact: Low
  - Cost/complexity: Low
  - Risk + rollback/containment: continued inefficiency; no rollback needed.
  - Time-to-signal: slow

## 5) Recommendation (single choice)
- **Pick one:** Act
- **Rationale (3-6 bullets max):**
  - The behavior is repeatable in the trace and conflicts with “only report new or changed.”
  - The issue is low severity but affects efficiency and tool usage.
  - A small change can eliminate redundant reads without changing user-facing output.
- **Plan (next 1-3 actions):**
  - Implement a change-detection guard for HEARTBEAT.md reads (Owner: Unknown).
  - Add a test that repeats the prompt without changing the file and asserts no extra `read` call (Owner: Unknown).
  - Update the ticket with results and observed impact (Owner: Unknown).
- **Stop conditions (reversal triggers):**
  - Any missed updates or incorrect `HEARTBEAT_OK` responses after a real HEARTBEAT change.

## 6) Appendix (optional)
- 2026-01-31 04:43:31Z: assistant issues a second `read` for `/home/debian/clawd/HEARTBEAT.md` with identical tool output.

---

## Acceptance checklist (one line)
ACCEPT IF: ticket link + decision statement + evidence + RCA (confidence + tests) + >=2 options + explicit recommendation + next-step owner.

## Length guidance
- Target 400-900 words, hard cap 2 pages.
- No section >12 bullets; no bullet longer than 2 lines.

## Filename convention
- docs/research-briefs/T####-<slug>/oracle-brief-v1.md