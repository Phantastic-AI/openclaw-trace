#!/usr/bin/env python3
"""
T154 Cron Gateway Timeout Experiment

Hypothesis: cron.list timeouts are caused by lock contention when jobs are executing.
This script measures latency and reproduces the issue.

Traces: https://wandb.ai/ninjaa-self/openclaw-trace-experiments/weave
"""

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

# Weave integration
WEAVE_AVAILABLE = False
weave = None

def setup_weave():
    global WEAVE_AVAILABLE, weave
    api_key = os.environ.get('WANDB_API_KEY')
    if not api_key:
        print("[WARN] WANDB_API_KEY not set, Weave tracing disabled", file=sys.stderr)
        return False
    
    try:
        import weave as _weave
        weave = _weave
        weave.init('ninjaa-self/openclaw-trace-experiments')
        WEAVE_AVAILABLE = True
        print("[OK] Weave initialized: https://wandb.ai/ninjaa-self/openclaw-trace-experiments/weave")
        return True
    except Exception as e:
        print(f"[WARN] Weave init failed: {e}", file=sys.stderr)
        return False


@dataclass
class LatencyResult:
    call_id: int
    start_ts: float
    end_ts: float
    latency_ms: float
    success: bool
    error: Optional[str] = None
    jobs_count: Optional[int] = None


CLAWDBOT_CMD = ["node", "/home/debian/clawdbot/dist/entry.js"]


def call_cron_list_raw() -> tuple[bool, Optional[int], Optional[str], float]:
    """Call cron.list via gateway and measure latency (raw, no tracing)."""
    start = time.time()
    try:
        result = subprocess.run(
            CLAWDBOT_CMD + ["cron", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=35
        )
        latency = (time.time() - start) * 1000
        
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                jobs = data.get('jobs', [])
                return True, len(jobs), None, latency
            except json.JSONDecodeError:
                return True, None, None, latency
        else:
            return False, None, result.stderr.strip()[:200], latency
            
    except subprocess.TimeoutExpired:
        latency = (time.time() - start) * 1000
        return False, None, "TIMEOUT after 35s", latency
    except Exception as e:
        latency = (time.time() - start) * 1000
        return False, None, str(e)[:200], latency


def call_cron_list() -> dict:
    """Traced wrapper for cron.list call."""
    success, jobs_count, error, latency_ms = call_cron_list_raw()
    return {
        "success": success,
        "jobs_count": jobs_count,
        "error": error,
        "latency_ms": latency_ms
    }


def run_baseline_inner(n_calls: int) -> list[dict]:
    """Run baseline latency measurements (inner logic)."""
    results = []
    
    for i in range(n_calls):
        start_ts = time.time()
        call_result = call_cron_list()
        end_ts = time.time()
        
        result = {
            "call_id": i,
            "start_ts": start_ts,
            "end_ts": end_ts,
            **call_result
        }
        results.append(result)
        
        status = "✓" if call_result["success"] else "✗"
        print(f"  [{i+1}/{n_calls}] {status} {call_result['latency_ms']:.1f}ms (jobs={call_result['jobs_count']})")
        
        time.sleep(0.5)
    
    return results


def analyze_results(results: list[dict], label: str) -> dict:
    """Compute statistics from results."""
    latencies = [r["latency_ms"] for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    
    if not latencies:
        return {
            "label": label,
            "n_calls": len(results),
            "n_success": 0,
            "n_failures": len(failures),
            "p50_ms": None,
            "p95_ms": None,
            "p99_ms": None,
            "max_ms": None,
            "timeouts": len([f for f in failures if f.get("error") and "TIMEOUT" in f["error"]])
        }
    
    latencies.sort()
    n = len(latencies)
    
    return {
        "label": label,
        "n_calls": len(results),
        "n_success": n,
        "n_failures": len(failures),
        "p50_ms": latencies[int(n * 0.5)] if n > 0 else None,
        "p95_ms": latencies[int(n * 0.95)] if n > 0 else None,
        "p99_ms": latencies[int(n * 0.99)] if n > 0 else None,
        "max_ms": max(latencies) if latencies else None,
        "min_ms": min(latencies) if latencies else None,
        "mean_ms": sum(latencies) / n if n > 0 else None,
        "timeouts": len([f for f in failures if f.get("error") and "TIMEOUT" in f["error"]])
    }


def print_stats(stats: dict):
    """Pretty print statistics."""
    print(f"\n--- {stats['label']} ---")
    print(f"  Calls: {stats['n_success']}/{stats['n_calls']} success")
    if stats['n_failures'] > 0:
        print(f"  Failures: {stats['n_failures']} (timeouts: {stats['timeouts']})")
    if stats['p50_ms']:
        print(f"  P50: {stats['p50_ms']:.1f}ms")
        print(f"  P95: {stats['p95_ms']:.1f}ms")
        print(f"  P99: {stats['p99_ms']:.1f}ms")
        print(f"  Max: {stats['max_ms']:.1f}ms")


def run_experiment(phase: str, n_calls: int) -> dict:
    """
    Run the T154 cron timeout experiment.
    
    This function is traced by Weave when available.
    """
    print(f"\n=== {phase.upper()}: {n_calls} calls to cron.list ===\n")
    
    results = run_baseline_inner(n_calls)
    stats = analyze_results(results, phase)
    print_stats(stats)
    
    return {
        "experiment": "t154_cron_timeout",
        "phase": phase,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "results": results
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="T154 Cron Timeout Experiment")
    parser.add_argument("--phase", choices=["baseline", "stress", "full"], default="baseline")
    parser.add_argument("--n-calls", type=int, default=10)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()
    
    print("=" * 60)
    print("T154 CRON TIMEOUT EXPERIMENT")
    print("=" * 60)
    print(f"Phase: {args.phase}")
    print(f"Calls: {args.n_calls}")
    
    # Initialize Weave
    weave_ok = setup_weave()
    print(f"Weave: {'enabled' if weave_ok else 'disabled'}")
    print("=" * 60)
    
    # If Weave is available, wrap the experiment function
    if WEAVE_AVAILABLE and weave:
        # Create traced version of our experiment
        traced_experiment = weave.op(run_experiment)
        output = traced_experiment(args.phase, args.n_calls)
    else:
        output = run_experiment(args.phase, args.n_calls)
    
    # Save output
    if args.output:
        Path(args.output).write_text(json.dumps(output, indent=2))
        print(f"\n[OK] Results saved to {args.output}")
    
    if WEAVE_AVAILABLE:
        print(f"\n[OK] Traces: https://wandb.ai/ninjaa-self/openclaw-trace-experiments/weave")
    
    return output


if __name__ == "__main__":
    main()
