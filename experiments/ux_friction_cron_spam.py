#!/usr/bin/env python3
"""
UX Friction Experiment: Cron Error Spam

Problem: "Cron (error)" messages appear repeatedly with successful content,
         causing assistant to spam user with repeated prompts.

Hypothesis:
  1. Multiple cron jobs fire in rapid succession
  2. "(error)" label is incorrectly applied to successful responses
  3. Retry mechanism may be re-executing jobs

Traces: Weave + Redis
"""

import json
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Weave integration
WEAVE_AVAILABLE = False
weave = None

# Redis integration
REDIS_AVAILABLE = False
redis_client = None


def setup_weave():
    global WEAVE_AVAILABLE, weave
    api_key = os.environ.get('WANDB_API_KEY')
    if not api_key:
        print("[WARN] WANDB_API_KEY not set", file=sys.stderr)
        return False
    try:
        import weave as _weave
        weave = _weave
        weave.init('ninjaa-self/openclaw-trace-experiments')
        WEAVE_AVAILABLE = True
        print("[OK] Weave: https://wandb.ai/ninjaa-self/openclaw-trace-experiments/weave")
        return True
    except Exception as e:
        print(f"[WARN] Weave init failed: {e}", file=sys.stderr)
        return False


def setup_redis():
    global REDIS_AVAILABLE, redis_client
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        redis_client = r
        REDIS_AVAILABLE = True
        print("[OK] Redis: localhost:6379")
        return True
    except Exception as e:
        print(f"[WARN] Redis not available: {e}", file=sys.stderr)
        return False


@dataclass
class CronEvent:
    """A cron-related event from session logs."""
    index: int
    timestamp: str
    role: str
    is_cron: bool
    is_error: bool
    content_preview: str
    content_length: int
    time_since_last_cron_ms: Optional[float] = None


def parse_session_file(path: str) -> list[dict]:
    """Parse a JSONL session file."""
    events = []
    with open(path, 'r') as f:
        for i, line in enumerate(f):
            try:
                data = json.loads(line)
                if data.get('type') == 'message':
                    msg = data.get('message', {})
                    content = msg.get('content', [])
                    text = ''
                    for c in content:
                        if c.get('type') == 'text':
                            text = c.get('text', '')
                            break
                    events.append({
                        'index': i,
                        'timestamp': data.get('timestamp'),
                        'role': msg.get('role'),
                        'text': text,
                        'model': msg.get('model'),
                    })
            except json.JSONDecodeError:
                continue
    return events


def extract_cron_events(events: list[dict]) -> list[CronEvent]:
    """Extract and analyze cron-related events."""
    cron_pattern = re.compile(r'Cron \((error|ok|run)\):', re.IGNORECASE)
    cron_events = []
    last_cron_ts = None
    
    for e in events:
        text = e.get('text', '')
        match = cron_pattern.search(text)
        
        if match or 'Cron' in text:
            is_error = 'error' in text.lower() and 'Cron' in text
            
            # Calculate time since last cron
            ts = e.get('timestamp')
            time_since_last = None
            if ts and last_cron_ts:
                try:
                    t1 = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    t0 = datetime.fromisoformat(last_cron_ts.replace('Z', '+00:00'))
                    time_since_last = (t1 - t0).total_seconds() * 1000
                except:
                    pass
            
            cron_events.append(CronEvent(
                index=e['index'],
                timestamp=ts,
                role=e['role'],
                is_cron=True,
                is_error=is_error,
                content_preview=text[:100],
                content_length=len(text),
                time_since_last_cron_ms=time_since_last
            ))
            
            if ts:
                last_cron_ts = ts
    
    return cron_events


def analyze_spam_patterns(cron_events: list[CronEvent]) -> dict:
    """Analyze cron event patterns for spam detection."""
    if not cron_events:
        return {"error": "No cron events found"}
    
    # Time gaps between consecutive cron events
    gaps = [e.time_since_last_cron_ms for e in cron_events if e.time_since_last_cron_ms is not None]
    
    # Count errors vs successful
    error_count = sum(1 for e in cron_events if e.is_error)
    user_cron_count = sum(1 for e in cron_events if e.role == 'user')
    
    # Find rapid-fire sequences (< 10 seconds apart)
    rapid_fire = [g for g in gaps if g < 10000]
    
    # Analyze content - are "error" messages actually errors?
    error_with_content = []
    for e in cron_events:
        if e.is_error:
            # Check if content looks like a successful response
            preview = e.content_preview.lower()
            has_draft = any(word in preview for word in ['draft', 'suggest', 'here', 'got it', 'noted'])
            error_with_content.append({
                'index': e.index,
                'has_successful_content': has_draft,
                'preview': e.content_preview[:50]
            })
    
    return {
        "total_cron_events": len(cron_events),
        "error_labeled": error_count,
        "user_role_cron": user_cron_count,
        "rapid_fire_count": len(rapid_fire),
        "gap_min_ms": min(gaps) if gaps else None,
        "gap_max_ms": max(gaps) if gaps else None,
        "gap_mean_ms": sum(gaps) / len(gaps) if gaps else None,
        "false_errors": sum(1 for e in error_with_content if e['has_successful_content']),
        "error_samples": error_with_content[:5]
    }


def redis_log_analysis(analysis: dict, session_id: str):
    """Log analysis results to Redis."""
    if not REDIS_AVAILABLE or not redis_client:
        return
    try:
        ts = int(time.time())
        key = f"ux_friction:analysis:{session_id}:{ts}"
        redis_client.set(key, json.dumps(analysis), ex=86400 * 7)
        
        # Track metrics
        redis_client.incr("ux_friction:total_analyses")
        if analysis.get("rapid_fire_count", 0) > 0:
            redis_client.incr("ux_friction:rapid_fire_sessions")
        if analysis.get("false_errors", 0) > 0:
            redis_client.incr("ux_friction:false_error_sessions")
        
        print(f"[OK] Redis: saved to {key}")
    except Exception as e:
        print(f"[WARN] Redis log failed: {e}", file=sys.stderr)


def run_experiment(session_path: str) -> dict:
    """Run the UX friction analysis experiment."""
    print(f"\n=== UX FRICTION EXPERIMENT ===")
    print(f"Session: {session_path}\n")
    
    # Parse session
    events = parse_session_file(session_path)
    print(f"Total events: {len(events)}")
    
    # Extract cron events
    cron_events = extract_cron_events(events)
    print(f"Cron events: {len(cron_events)}")
    
    # Analyze patterns
    analysis = analyze_spam_patterns(cron_events)
    
    # Print findings
    print(f"\n--- Analysis ---")
    print(f"  Total cron events: {analysis['total_cron_events']}")
    print(f"  Labeled as 'error': {analysis['error_labeled']}")
    print(f"  False errors (success content): {analysis['false_errors']}")
    print(f"  Rapid-fire (<10s gap): {analysis['rapid_fire_count']}")
    if analysis['gap_min_ms']:
        print(f"  Gap range: {analysis['gap_min_ms']:.0f}ms - {analysis['gap_max_ms']:.0f}ms")
        print(f"  Gap mean: {analysis['gap_mean_ms']:.0f}ms")
    
    if analysis.get('error_samples'):
        print(f"\n--- Error Samples ---")
        for s in analysis['error_samples'][:3]:
            status = "✗ FALSE" if s['has_successful_content'] else "✓ TRUE"
            print(f"  [{s['index']}] {status}: {s['preview']}...")
    
    # Log to Redis
    session_id = Path(session_path).stem
    redis_log_analysis(analysis, session_id)
    
    return {
        "experiment": "ux_friction_cron_spam",
        "session_path": session_path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_count": len(events),
        "cron_event_count": len(cron_events),
        "analysis": analysis,
        "cron_events": [asdict(e) for e in cron_events[:20]]  # First 20 for debugging
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="UX Friction Cron Spam Experiment")
    parser.add_argument("--session", type=str, required=True, help="Path to session JSONL file")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()
    
    print("=" * 60)
    print("UX FRICTION: CRON ERROR SPAM EXPERIMENT")
    print("=" * 60)
    
    weave_ok = setup_weave()
    redis_ok = setup_redis()
    print(f"Weave: {'enabled' if weave_ok else 'disabled'}")
    print(f"Redis: {'enabled' if redis_ok else 'disabled'}")
    print("=" * 60)
    
    # Run experiment (traced if Weave available)
    if WEAVE_AVAILABLE and weave:
        traced_run = weave.op(run_experiment)
        output = traced_run(args.session)
    else:
        output = run_experiment(args.session)
    
    if args.output:
        Path(args.output).write_text(json.dumps(output, indent=2))
        print(f"\n[OK] Results saved to {args.output}")
    
    if WEAVE_AVAILABLE:
        print(f"\n[OK] Traces: https://wandb.ai/ninjaa-self/openclaw-trace-experiments/weave")
    
    return output


if __name__ == "__main__":
    main()
