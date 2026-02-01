#!/usr/bin/env python3
"""
T154 Cron Gateway Timeout Experiment

Hypothesis: cron.list timeouts are caused by lock contention when jobs are executing.
This script measures latency and reproduces the issue.
"""

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# Weave integration
try:
    import weave
    WEAVE_AVAILABLE = True
except ImportError:
    WEAVE_AVAILABLE = False
    print("[WARN] weave not installed, tracing disabled", file=sys.stderr)

# Redis integration  
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("[WARN] redis not installed, will skip Redis logging", file=sys.stderr)


@dataclass
class LatencyResult:
    call_id: int
    start_ts: float
    end_ts: float
    latency_ms: float
    success: bool
    error: Optional[str] = None
    jobs_count: Optional[int] = None


def init_weave():
    if WEAVE_AVAILABLE:
        api_key = os.environ.get('WANDB_API_KEY')
        if not api_key:
            print("[WARN] WANDB_API_KEY not set, Weave tracing disabled", file=sys.stderr)
            return False
        try:
            weave.init('ninjaa-self/openclaw-trace-experiments')
            print("[OK] Weave initialized")
            return True
        except Exception as e:
            print(f"[WARN] Weave init failed: {e}", file=sys.stderr)
            return False
    return False


def get_redis():
    if not REDIS_AVAILABLE:
        return None
    try:
        # Try local Redis first, then cloud
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        return r
    except:
        return None


CLAWDBOT_CMD = ["node", "/home/debian/clawdbot/dist/entry.js"]

def call_cron_list() -> tuple[bool, Optional[int], Optional[str], float]:
    """Call cron.list via gateway and measure latency."""
    start = time.time()
    try:
        result = subprocess.run(
            CLAWDBOT_CMD + ["cron", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=35  # Just over the 30s gateway timeout
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


def run_baseline(n_calls: int = 20) -> list[LatencyResult]:
    """Run baseline latency measurements."""
    print(f"\n=== BASELINE: {n_calls} calls to cron.list ===\n")
    results = []
    
    for i in range(n_calls):
        start_ts = time.time()
        success, jobs_count, error, latency_ms = call_cron_list()
        end_ts = time.time()
        
        result = LatencyResult(
            call_id=i,
            start_ts=start_ts,
            end_ts=end_ts,
            latency_ms=latency_ms,
            success=success,
            error=error,
            jobs_count=jobs_count
        )
        results.append(result)
        
        status = "✓" if success else "✗"
        print(f"  [{i+1}/{n_calls}] {status} {latency_ms:.1f}ms (jobs={jobs_count})")
        
        # Small delay between calls
        time.sleep(0.5)
    
    return results


def analyze_results(results: list[LatencyResult], label: str) -> dict:
    """Compute statistics from results."""
    latencies = [r.latency_ms for r in results if r.success]
    failures = [r for r in results if not r.success]
    
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
            "timeouts": len([f for f in failures if f.error and "TIMEOUT" in f.error])
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
        "timeouts": len([f for f in failures if f.error and "TIMEOUT" in f.error])
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


def log_to_redis(r, results: list[LatencyResult], label: str):
    """Log results to Redis for persistence."""
    if not r:
        return
    
    key = f"t154:experiment:{label}:{int(time.time())}"
    data = {
        "label": label,
        "timestamp": datetime.utcnow().isoformat(),
        "results": [asdict(r) for r in results]
    }
    r.set(key, json.dumps(data), ex=86400 * 7)  # 7 day TTL
    
    # Also push individual latencies for easy analysis
    for result in results:
        if result.success:
            r.lpush(f"t154:latencies:{label}", result.latency_ms)
    r.ltrim(f"t154:latencies:{label}", 0, 999)  # Keep last 1000
    
    print(f"[Redis] Logged to {key}")


def weave_traced_experiment(func):
    """Decorator to trace with Weave if available."""
    if WEAVE_AVAILABLE:
        return weave.op(func)
    return func


@weave_traced_experiment
def run_experiment_phase(phase: str, n_calls: int) -> dict:
    """Run a single experiment phase with tracing."""
    results = run_baseline(n_calls)
    stats = analyze_results(results, phase)
    return {
        "phase": phase,
        "stats": stats,
        "results": [asdict(r) for r in results]
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="T154 Cron Timeout Experiment")
    parser.add_argument("--phase", choices=["baseline", "stress", "full"], default="baseline")
    parser.add_argument("--n-calls", type=int, default=20)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()
    
    print("=" * 60)
    print("T154 CRON TIMEOUT EXPERIMENT")
    print("=" * 60)
    print(f"Phase: {args.phase}")
    print(f"Calls: {args.n_calls}")
    print(f"Weave: {'enabled' if WEAVE_AVAILABLE else 'disabled'}")
    print(f"Redis: {'enabled' if REDIS_AVAILABLE else 'disabled'}")
    print("=" * 60)
    
    init_weave()
    r = get_redis()
    
    if args.phase == "baseline":
        results = run_baseline(args.n_calls)
        stats = analyze_results(results, "baseline")
        print_stats(stats)
        log_to_redis(r, results, "baseline")
        
        output = {
            "experiment": "t154_cron_timeout",
            "phase": "baseline",
            "timestamp": datetime.utcnow().isoformat(),
            "stats": stats,
            "results": [asdict(r) for r in results]
        }
        
    elif args.phase == "full":
        # Full experiment: baseline, then stress test
        print("\n>>> Phase 1: Baseline")
        baseline_results = run_baseline(args.n_calls)
        baseline_stats = analyze_results(baseline_results, "baseline")
        print_stats(baseline_stats)
        log_to_redis(r, baseline_results, "baseline")
        
        output = {
            "experiment": "t154_cron_timeout",
            "phase": "full",
            "timestamp": datetime.utcnow().isoformat(),
            "baseline": {
                "stats": baseline_stats,
                "results": [asdict(r) for r in baseline_results]
            }
        }
    
    else:
        output = {"error": f"Unknown phase: {args.phase}"}
    
    # Save output
    if args.output:
        Path(args.output).write_text(json.dumps(output, indent=2))
        print(f"\n[OK] Results saved to {args.output}")
    else:
        print(f"\n[Results JSON]\n{json.dumps(output, indent=2)}")
    
    return output


if __name__ == "__main__":
    main()
