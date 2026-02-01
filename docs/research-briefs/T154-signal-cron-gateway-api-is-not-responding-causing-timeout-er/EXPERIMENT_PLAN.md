# Experiment Plan: T154 Cron Gateway Timeout

## Hypothesis

The `cron.list` 30s timeout is caused by **lock contention** in the CronService. When a long-running job is executing (holding the lock via `locked()`), all other cron operations—including `list()`—must wait for the promise chain to resolve.

### Why this is likely:
1. `locked.ts` uses promise chaining: all operations on the same store path are serialized
2. `executeJob()` can run arbitrary agent turns (potentially minutes)
3. `list()` requires the lock to read from the store
4. A 30s timeout exactly matches a job that hangs or runs slowly

### Alternative hypotheses:
- File I/O blocking (less likely—store is cached after first load)
- Gateway HTTP layer issue (possible but would affect all endpoints)
- Memory pressure causing GC pauses (would see other symptoms)

---

## Experiment Design

### Phase 1: Instrumentation (baseline measurement)

**Goal:** Measure actual latency distribution of `cron.list` under normal conditions.

**Method:**
1. Add Weave tracing to cron operations:
   ```python
   @weave.op
   def cron_list_latency_test(n_calls: int) -> dict:
       # Call cron.list n times, record latencies
       pass
   ```

2. Redis for state:
   - Store latency samples: `LPUSH cron:list:latencies <ms>`
   - Track lock contention: `INCR cron:lock:contention` when wait > threshold

3. Baseline metrics:
   - P50, P95, P99 latency for `cron.list`
   - Lock wait time distribution
   - Correlation with running jobs

**Expected output:** Baseline latency distribution showing normal case is <100ms.

### Phase 2: Reproduce the timeout

**Goal:** Confirm lock contention causes the timeout.

**Method:**
1. Create a synthetic long-running cron job (30s+ execution)
2. While job is running, call `cron.list` from another session
3. Measure: does `list()` timeout?

**Test script:**
```bash
# Terminal 1: Start long job
clawdbot cron run <job-id> --force  # Job that takes 30+ seconds

# Terminal 2: Attempt list (should timeout)
time clawdbot cron list
```

**Expected output:** `cron.list` blocks until job completes, causing timeout.

### Phase 3: Fix options

#### Option A: Non-blocking reads (recommended)
Modify `list()` to read from cache without acquiring the write lock.

```typescript
// New read path - no lock needed for list()
export async function list(state: CronServiceState, opts?: { includeDisabled?: boolean }) {
  // Read directly from cache if available (no lock)
  if (state.store) {
    const includeDisabled = opts?.includeDisabled === true;
    const jobs = state.store.jobs.filter((j) => includeDisabled || j.enabled);
    return jobs.sort((a, b) => (a.state.nextRunAtMs ?? 0) - (b.state.nextRunAtMs ?? 0));
  }
  // Fall back to locked load only if cache is empty
  return await locked(state, async () => {
    await ensureLoaded(state);
    const includeDisabled = opts?.includeDisabled === true;
    const jobs = (state.store?.jobs ?? []).filter((j) => includeDisabled || j.enabled);
    return jobs.sort((a, b) => (a.state.nextRunAtMs ?? 0) - (b.state.nextRunAtMs ?? 0));
  });
}
```

**Trade-off:** Slightly stale data (job might have just finished) but no blocking.

#### Option B: Read-write lock separation
Replace promise-chain lock with proper RWLock (readers don't block readers).

**Trade-off:** More complex, but cleaner semantics.

#### Option C: Lock timeout with early return
Add timeout to lock acquisition, return cached/stale data if lock not acquired in 5s.

**Trade-off:** Explicit staleness signal, more defensive.

### Phase 4: Verify fix

**Method:**
1. Apply Option A fix
2. Re-run Phase 2 reproduction test
3. `cron.list` should return immediately even during long job execution

**Metrics (with Weave):**
- `cron.list` P99 latency before fix: Expected >30000ms during job execution
- `cron.list` P99 latency after fix: Expected <100ms always
- Delta: 99%+ improvement in worst case

---

## Implementation Steps

1. **Create branch:** `t154-cron-list-nonblocking`

2. **Add instrumentation:**
   - Weave tracing on `cronHandlers['cron.list']`
   - Redis latency logging

3. **Run baseline:**
   ```bash
   python experiments/t154_baseline.py --n-calls 100 --output baseline.json
   ```

4. **Run reproduction:**
   ```bash
   python experiments/t154_reproduce.py --job-duration 45 --output reproduce.json
   ```

5. **Apply fix:** Modify `ops.ts` per Option A

6. **Run verification:**
   ```bash
   python experiments/t154_verify.py --job-duration 45 --output verify.json
   ```

7. **Generate report:** Compare before/after metrics

---

## Success Criteria

| Metric | Before | After | Pass? |
|--------|--------|-------|-------|
| `cron.list` P99 during idle | <100ms | <100ms | ✅ |
| `cron.list` P99 during job execution | 30000ms+ (timeout) | <100ms | ✅ |
| Data staleness | N/A | <1s | ✅ |

---

## Artifacts

- `/experiments/t154_baseline.py` — Baseline latency measurement
- `/experiments/t154_reproduce.py` — Reproduction test
- `/experiments/t154_verify.py` — Verification after fix
- Weave project: `ninjaa-self/openclaw-trace-experiments`
- Redis keys: `cron:list:latencies`, `cron:lock:contention`

---

## Timeline

| Step | Duration |
|------|----------|
| Instrumentation | 30 min |
| Baseline run | 10 min |
| Reproduction | 15 min |
| Fix implementation | 30 min |
| Verification | 15 min |
| Report write-up | 20 min |
| **Total** | **~2 hours** |
