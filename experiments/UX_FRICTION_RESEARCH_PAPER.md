# UX Friction: Cron Error Spam — Research Paper

**Origin:** Demo://rollup (ux_friction)  
**Date:** 2026-02-01  
**Author:** HAL (OpenClaw Agent)

---

## Tracing & Persistence

| System | Status | Reference |
|--------|--------|-----------|
| **Weave** | ✅ Verified | [019c1b36-dadf-7425-91bf-b8e77316351b](https://wandb.ai/ninjaa-self/openclaw-trace-experiments/r/call/019c1b36-dadf-7425-91bf-b8e77316351b) |
| **Redis** | ✅ Verified | `ux_friction:analysis:*`, `ux_friction:total_analyses` |

---

## Abstract

"Cron (error)" messages appear repeatedly in sessions with **successful content**, causing the assistant to spam users with repeated prompts. Analysis of 3001 session events reveals **1430 cron messages labeled as "error"**, of which **72% (1029) contain successful response content**. Root cause: the cron system marks jobs as "error" when **delivery fails** (e.g., missing recipient), even when the job itself produced valid output.

---

## 1. Problem Statement

**Symptom:**
- Multiple "Cron (error)" messages fire in rapid succession
- Messages contain successful content (drafts, suggestions)
- Assistant treats each as "needs attention" → spam cascade

**Impact:**
- User receives 10+ nearly identical prompts asking for clarification
- Session becomes unusable until cron spam stops
- Trust erosion ("why is HAL broken?")

---

## 2. Evidence (Quantified)

### 2.1 Session Analysis

```
Session: 0001_31e89d3b-7e8b-40d6-9ec1-61a5722a4000.jsonl
Total events: 3001
Cron events: 1433 (47.8% of session)
```

### 2.2 Error Classification

| Metric | Value |
|--------|-------|
| Labeled as "error" | 1430 (99.8%) |
| **False errors** (success content) | **1029 (72%)** |
| Rapid-fire (<10s gap) | 857 (60%) |
| Min gap between cron events | 646ms |
| Mean gap | 18,317ms |

### 2.3 Sample False Errors

```
[77] ✗ FALSE ERROR: "Cron (error): Ready to draft..."
[79] ✓ TRUE ERROR: "Cron (error): I couldn't..."

Content analysis: "draft", "suggest", "here", "got it", "noted" → SUCCESS indicators
```

### 2.4 Redis Persistence

```bash
$ redis-cli get ux_friction:total_analyses
"1"
$ redis-cli get ux_friction:false_error_sessions
"1"
```

---

## 3. Root Cause Analysis

### 3.1 Code Path

**File:** `src/cron/service/timer.ts` (lines 115-118)

```typescript
const statusPrefix = status === "ok" ? prefix : `${prefix} (${status})`;
state.deps.enqueueSystemEvent(`${statusPrefix}: ${body}`, { agentId: job.agentId });
```

**File:** `src/cron/isolated-agent/run.ts` (lines 378-386)

```typescript
if (!resolvedDelivery.to) {
  const reason = resolvedDelivery.error?.message ?? "Cron delivery requires a recipient (--to).";
  if (!bestEffortDeliver) {
    return {
      status: "error",      // ← ERROR even though output is valid
      summary,
      outputText,           // ← Valid output included!
      error: reason,
    };
  }
}
```

### 3.2 Failure Mode

1. Cron job runs → produces valid output (summary + outputText)
2. Delivery fails (no `--to` recipient configured)
3. Status set to "error" despite valid output
4. Posted to main session as "Cron (error): [valid content]"
5. HEARTBEAT instruction appended → assistant treats as actionable
6. Assistant responds with clarification request
7. Next cron fires → repeat

### 3.3 Contributing Factors

| Factor | Evidence |
|--------|----------|
| Missing `--to` recipient | Error message: "Cron delivery requires a recipient" |
| HEARTBEAT appended to errors | "Read HEARTBEAT.md if it exists..." in error messages |
| Rapid job scheduling | 857 events <10s apart |
| No deduplication | Same content repeated with slight variations |

---

## 4. Solution Options

### Option A: Separate delivery failure from job failure (Recommended)

**Change:** When job produces valid output but delivery fails, mark as `status: "ok"` with a delivery warning.

```typescript
if (!resolvedDelivery.to) {
  const reason = resolvedDelivery.error?.message ?? "Delivery skipped: no recipient.";
  return {
    status: "ok",  // Job succeeded, delivery didn't
    summary: `${summary}\n\n⚠️ ${reason}`,
    outputText,
  };
}
```

**Trade-offs:**
- ✅ False errors eliminated
- ✅ Valid output still posted
- ⚠️ Delivery failure less visible (but it's in the message)

### Option B: Don't append HEARTBEAT to error messages

**Change:** Skip HEARTBEAT instruction for error-status posts.

```typescript
const statusPrefix = status === "ok" ? prefix : `${prefix} (${status})`;
const heartbeat = status === "ok" ? heartbeatSuffix : "";  // Skip on error
state.deps.enqueueSystemEvent(`${statusPrefix}: ${body}${heartbeat}`, ...);
```

**Trade-offs:**
- ✅ Reduces spam (assistant won't treat as actionable)
- ⚠️ Actual errors might need attention but won't trigger

### Option C: Rate-limit cron posts to main

**Change:** Deduplicate or throttle cron messages within a time window.

```typescript
const lastPost = state.lastPostToMain[job.id];
if (lastPost && nowMs - lastPost < 30_000) {
  return;  // Skip if posted within 30s
}
```

**Trade-offs:**
- ✅ Eliminates rapid-fire spam
- ⚠️ May miss legitimate rapid updates

---

## 5. Recommendation

**Implement Option A (separate delivery failure from job failure).**

**Rationale:**
- 72% of "errors" are false positives
- Job output is valid and useful
- Delivery failure is a config issue, not a job failure
- Preserves user visibility into what the job produced

**Also consider:**
- Option C (rate-limiting) as a defense-in-depth measure
- Option B if error messages should never trigger HEARTBEAT

---

## 6. Implementation

**File:** `src/cron/isolated-agent/run.ts`

```diff
 if (!resolvedDelivery.to) {
   const reason =
     resolvedDelivery.error?.message ?? "Cron delivery requires a recipient (--to).";
   if (!bestEffortDeliver) {
     return {
-      status: "error",
+      status: "ok",
       summary,
       outputText,
-      error: reason,
+      error: undefined,
+      deliveryWarning: reason,  // New field for visibility
     };
   }
```

**Additional:** Update `timer.ts` to include delivery warning in post body if present.

---

## 7. Artifacts

| Artifact | Location |
|----------|----------|
| Experiment script | `experiments/ux_friction_cron_spam.py` |
| Analysis data | `experiments/ux_friction_analysis.json` |
| Weave trace | [019c1b36...](https://wandb.ai/ninjaa-self/openclaw-trace-experiments/r/call/019c1b36-dadf-7425-91bf-b8e77316351b) |
| Redis keys | `ux_friction:*` |

---

## 8. References

- Signal: `fp1:3d13a00f23c7165d5d2f9382972dd02dddfdbf9d6009b6cd9ea657fa618eb18b`
- Session: `0001_31e89d3b-7e8b-40d6-9ec1-61a5722a4000.jsonl`
- Timer code: `src/cron/service/timer.ts`
- Isolated agent: `src/cron/isolated-agent/run.ts`
