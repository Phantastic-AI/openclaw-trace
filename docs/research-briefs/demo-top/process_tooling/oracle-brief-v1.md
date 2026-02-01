Now I have all the evidence needed to write the revised brief. Let me create the revised version that removes all unsupported claims.

# Research Brief (v1)

**Origin:** Demo://rollup

---

## 0) Header

- **Ticket:** Demo — HEARTBEAT.md handling improvement (Demo://rollup)
- **Owner (DRI):** Unknown
- **Date / version:** Unknown
- **Decision needed:** Should we investigate how the system handles HEARTBEAT.md when no tasks need attention?
- **Proposed next step:** Investigate current behavior when HEARTBEAT.md is missing, empty, or contains no actionable tasks.

---

## 1) Problem + target outcome

**Problem (observable):**
- Improvement suggestion: "System should better handle dependency on HEARTBEAT.md and avoid repeated error messages if no tasks need attention" (source: rollup canonical_summary)
- Spec states: "Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. If nothing needs attention, reply HEARTBEAT_OK" (source: context.md evidence quote)
- Specific failure mode unknown — no log excerpts or error messages provided in evidence

**Success metrics:**
- Unknown — requires investigation to define measurable criteria

**Non-goals / out of scope:**
- Redesigning HEARTBEAT.md file format
- Adding retry/backoff logic for file-read operations

---

## 2) Evidence snapshot

**Current behavior:**
- Per spec: "Read HEARTBEAT.md if it exists (workspace context). Follow it strictly."
- Per spec: "If nothing needs attention, reply HEARTBEAT_OK."
- Improvement suggestion indicates system should "avoid repeated error messages if no tasks need attention" (exact error text unknown)

**Data points:**
- Count: 1 item across 1 session (source: rollup summary)
- Severity: low (source: rollup summary)
- Tier: 1, reasons: incident (source: rollup summary)
- Score: 3.69 (source: rollup summary)
- Kind: process_tooling (source: kind_v2_counts)
- Tags: process (1), incident (1) (source: tags_top)

**Repro steps:**
- Unknown — no reproduction steps documented

**Links:** docs/research-briefs/demo-top/process_tooling/context.md

---

## 3) Root Cause Analysis (RCA)

**Suspected root cause(s):**
- Unknown — no code, logs, or detailed error information available to determine root cause

**Contributing factors:**
- Unknown — insufficient evidence to identify contributing factors

**Confidence:**
- Unable to assess — no evidence available for root cause determination

**Validation tests:**
- Unknown — specific tests cannot be defined without understanding current failure mode

---

## 4) Options

**Option A (Investigate):** Gather additional evidence by examining logs, code, and actual system behavior when HEARTBEAT.md is missing or contains no tasks.
- Impact: Unknown
- Cost/complexity: Unknown
- Risk: Low — investigation only

**Option B (Defer):** Wait for additional incident data; current evidence is 1 session, low severity.
- Impact: Unknown — log noise may persist if issue is systemic
- Cost/complexity: None
- Risk: Unknown

---

## 5) Recommendation

- **Pick one:** Investigate
- **Rationale:**
  - Root cause unknown — no logs, error messages, or code paths identified
  - Single session with low severity; additional evidence needed before implementation
  - Cannot define solution without understanding actual failure mode

**Plan (next actions):**
- Gather logs or error messages related to HEARTBEAT.md handling — Owner: Unknown
- Identify code path that handles HEARTBEAT.md — Owner: Unknown
- Define concrete failure scenarios based on investigation findings — Owner: Unknown

**Stop conditions:**
- Investigation reveals no actual issue — close without code change
- Investigation reveals specific failure mode — proceed to define solution

---

## 6) Appendix

**Spec excerpt (verbatim from context.md):**
> Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK.

**Signal identifiers:**
- Fingerprint: fp1:6880fa3c815d2b5255a11923cc1ae4353e6a6124538ac0c9a87c4c35ee70b63e
- Signature: sig1:174bf78a4d6c0016bce2e061d844eab80dd775a205c8181df9fa7a3a13b278de
- Item ID: sha256:7dec3514af1a2707384d15a89a7597d11d130a2a8693e3d5528d07f3da5f2cba

---

## Acceptance checklist

- ⚠️ **Ticket link:** Demo://rollup (placeholder, not a valid URL)
- ✅ **Decision statement:** Present — "Should we investigate how the system handles HEARTBEAT.md when no tasks need attention?"
- ✅ **Evidence:** Rollup data present with fingerprint, counts, severity, score, and spec excerpt
- ⚠️ **RCA:** Cannot complete — insufficient evidence for root cause analysis
- ✅ **>=2 options:** Two options provided (Investigate, Defer)
- ✅ **Recommendation:** Investigate, with rationale
- ⚠️ **Next-step owner:** Listed as "Unknown"

**VERDICT:** Incomplete — This brief requires investigation to gather additional evidence before a complete analysis can be performed. Key gaps: no log excerpts, no error message text, no code references, no owner assigned.