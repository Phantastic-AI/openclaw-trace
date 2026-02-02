#!/usr/bin/env python3
"""
Signal Validity Experiment v2 — Fully Reproducible

Research Question:
    When the OpenClaw signal miner says "there's an issue", is there actually one?

Usage:
    # Install dependencies
    pip install anthropic

    # Set API key
    export ANTHROPIC_API_KEY="sk-ant-..."

    # Run experiment
    python signal_validity_v2.py

    # Or run with custom parameters
    python signal_validity_v2.py --samples 30 --output results.json

Data Paths:
    - Rollups: /home/debian/clawd/home/tmp/rollup_latest120_v2_snapshot.json
    - Sessions: /home/debian/clawd/home/tmp/sessions_latest_120_20260201_024756/

Output:
    - Console: Summary statistics
    - JSON: Full results with per-signal details
"""

import argparse
import json
import os
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ============================================================================
# CONFIGURATION
# ============================================================================

# Data paths (update these if data moves)
ROLLUP_PATH = "/home/debian/clawd/home/tmp/rollup_latest120_v2_snapshot.json"
SESSIONS_DIR = "/home/debian/clawd/home/tmp/sessions_latest_120_20260201_024756"

# Problem classes to evaluate (signals we expect to be "issues")
PROBLEM_CLASSES = [
    "ux_friction",
    "defect", 
    "process_tooling",
    "reliability_perf",
    "capability_gap"
]

# Model for evaluation
EVAL_MODEL = "claude-sonnet-4-20250514"

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class SignalValidation:
    """Result of validating a single signal."""
    fingerprint_id: str
    signal_class: str
    canonical_summary: str
    session_context: str  # Raw evidence from sessions
    is_real_issue: bool   # Claude's judgment
    confidence: str       # high/medium/low
    reasoning: str        # Explanation
    severity: str         # none/low/medium/high
    eval_timestamp: str   # When evaluation ran


@dataclass
class ExperimentResults:
    """Full experiment results."""
    experiment_id: str
    timestamp: str
    n_samples: int
    precision: float
    real_issues: int
    false_positives: int
    by_class: dict
    severity_distribution: dict
    validations: list


# ============================================================================
# DATA LOADING
# ============================================================================

def load_rollups(path: str = ROLLUP_PATH) -> list[dict]:
    """Load signal rollups from JSON file."""
    print(f"Loading rollups from: {path}")
    with open(path) as f:
        data = json.load(f)
    rollups = data.get("rollups", [])
    print(f"  Loaded {len(rollups)} rollups")
    return rollups


def get_signal_class(rollup: dict) -> str:
    """Get the primary class of a rollup based on kind_v2_counts."""
    counts = rollup.get("kind_v2_counts", {})
    if not counts:
        return "unknown"
    return max(counts, key=counts.get)


def filter_problem_signals(rollups: list[dict]) -> list[dict]:
    """Filter rollups to only problem classes."""
    filtered = [r for r in rollups if get_signal_class(r) in PROBLEM_CLASSES]
    print(f"  Filtered to {len(filtered)} problem signals")
    return filtered


# ============================================================================
# CONTEXT RETRIEVAL
# ============================================================================

def get_session_context(rollup: dict, sessions_dir: str = SESSIONS_DIR, 
                        max_events: int = 50, max_chars: int = 3000) -> str:
    """
    Retrieve raw session context for a signal.
    
    This is the "evidence" we show to the evaluator — actual conversation
    snippets from the sessions where this signal was detected.
    """
    # Get session IDs referenced by this rollup
    session_ids = set()
    for sig in rollup.get("signals", []):
        sid = sig.get("session_id", "")
        if sid:
            session_ids.add(sid)
    
    if not session_ids:
        return "[No session IDs found in rollup]"
    
    context_snippets = []
    sessions_dir_path = Path(sessions_dir)
    
    # Find matching session files
    for sf in sessions_dir_path.glob("*.jsonl"):
        try:
            with open(sf) as f:
                first_line = f.readline()
                header = json.loads(first_line)
                
                if header.get("id") not in session_ids:
                    continue
                
                # Read events from this session
                f.seek(0)
                lines = f.readlines()[:max_events]
                
                for line in lines:
                    try:
                        event = json.loads(line)
                        msg = event.get("message", {})
                        role = msg.get("role", "")
                        content = msg.get("content", [])
                        
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text = block.get("text", "")[:500]
                                    if text and role:
                                        context_snippets.append(f"[{role}]: {text}")
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue
    
    if not context_snippets:
        # Fallback: use signal summaries from the rollup
        for sig in rollup.get("signals", [])[:5]:
            summary = sig.get("summary", "")
            if summary:
                context_snippets.append(f"[signal]: {summary}")
    
    # Join and truncate
    full_context = "\n---\n".join(context_snippets[:15])
    return full_context[:max_chars]


# ============================================================================
# VALIDATION LOGIC
# ============================================================================

def validate_signal(rollup: dict, client) -> SignalValidation:
    """
    Have Claude evaluate whether a signal represents a real issue.
    
    This is the core of the experiment: we show Claude the signal summary
    and raw session context, and ask it to judge whether this is a real
    problem or a false positive.
    """
    signal_class = get_signal_class(rollup)
    summary = rollup.get("canonical_summary", "")
    context = get_session_context(rollup)
    
    prompt = f"""You are auditing an AI agent's self-improvement system.

The system detected a potential issue from analyzing session logs:

**Signal Class:** {signal_class}
**Signal Summary:** {summary}

**Raw Session Context (evidence):**
{context}

---

## Your Task

Determine: **Is this actually a problem that needs fixing?**

Consider:
1. Is this a real issue that would frustrate a user or indicate a bug?
2. Or is this a false positive (normal behavior misclassified as a problem)?
3. If it's real, how severe is it?

## Response Format (JSON only)

{{
  "is_real_issue": true or false,
  "confidence": "high" or "medium" or "low",
  "reasoning": "1-2 sentence explanation of your judgment",
  "severity": "none" or "low" or "medium" or "high"
}}
"""

    try:
        response = client.messages.create(
            model=EVAL_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text.strip()
        
        # Parse JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        result = json.loads(text)
        
        return SignalValidation(
            fingerprint_id=rollup.get("fingerprint_id", ""),
            signal_class=signal_class,
            canonical_summary=summary,
            session_context=context[:500] + "..." if len(context) > 500 else context,
            is_real_issue=result.get("is_real_issue", False),
            confidence=result.get("confidence", "low"),
            reasoning=result.get("reasoning", ""),
            severity=result.get("severity", "none"),
            eval_timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        return SignalValidation(
            fingerprint_id=rollup.get("fingerprint_id", ""),
            signal_class=signal_class,
            canonical_summary=summary,
            session_context=context[:500] + "..." if len(context) > 500 else context,
            is_real_issue=False,
            confidence="none",
            reasoning=f"Evaluation error: {e}",
            severity="none",
            eval_timestamp=datetime.now(timezone.utc).isoformat()
        )


# ============================================================================
# EXPERIMENT RUNNER
# ============================================================================

def run_experiment(n_samples: int = 20, seed: Optional[int] = None) -> ExperimentResults:
    """
    Run the full signal validity experiment.
    
    1. Load rollups
    2. Filter to problem signals
    3. Sample N signals
    4. Validate each with Claude
    5. Compute metrics
    """
    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        print("Set it with: export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)
    
    from anthropic import Anthropic
    client = Anthropic()
    
    # Set random seed for reproducibility
    if seed is not None:
        random.seed(seed)
        print(f"Random seed: {seed}")
    
    experiment_id = f"validity_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print("\n" + "="*70)
    print("SIGNAL VALIDITY EXPERIMENT")
    print("Question: When the system says 'there's an issue', is there actually one?")
    print("="*70)
    
    # Load and filter data
    rollups = load_rollups()
    problem_rollups = filter_problem_signals(rollups)
    
    # Sample
    actual_samples = min(n_samples, len(problem_rollups))
    samples = random.sample(problem_rollups, actual_samples)
    print(f"\nSampled {actual_samples} signals for evaluation")
    
    # Show class distribution in sample
    class_dist = defaultdict(int)
    for s in samples:
        class_dist[get_signal_class(s)] += 1
    print(f"Sample distribution: {dict(class_dist)}")
    
    # Validate each signal
    print(f"\nValidating signals with {EVAL_MODEL}...")
    print("-" * 70)
    
    validations = []
    for i, rollup in enumerate(samples):
        summary_preview = rollup.get("canonical_summary", "")[:50]
        print(f"[{i+1}/{actual_samples}] {summary_preview}...")
        
        result = validate_signal(rollup, client)
        validations.append(result)
        
        status = "✓ REAL" if result.is_real_issue else "✗ FALSE POS"
        print(f"  → {status} ({result.confidence})")
        
        # Rate limiting
        time.sleep(0.5)
    
    # Compute metrics
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    
    real_issues = sum(1 for v in validations if v.is_real_issue)
    false_positives = len(validations) - real_issues
    precision = real_issues / len(validations) if validations else 0
    
    print(f"\n**Signal Precision: {precision:.1%}**")
    print(f"  Real issues:     {real_issues}/{len(validations)}")
    print(f"  False positives: {false_positives}/{len(validations)}")
    
    # Per-class metrics
    by_class = defaultdict(lambda: {"real": 0, "false": 0, "total": 0})
    for v in validations:
        by_class[v.signal_class]["total"] += 1
        if v.is_real_issue:
            by_class[v.signal_class]["real"] += 1
        else:
            by_class[v.signal_class]["false"] += 1
    
    print("\nPer-class precision:")
    for cls, counts in sorted(by_class.items()):
        pct = counts["real"] / counts["total"] if counts["total"] else 0
        print(f"  {cls}: {pct:.0%} ({counts['real']}/{counts['total']})")
    
    # Severity distribution
    severity_dist = defaultdict(int)
    for v in validations:
        if v.is_real_issue:
            severity_dist[v.severity] += 1
    
    print("\nSeverity of real issues:")
    for sev in ["high", "medium", "low"]:
        if sev in severity_dist:
            print(f"  {sev}: {severity_dist[sev]}")
    
    # Build results object
    results = ExperimentResults(
        experiment_id=experiment_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        n_samples=len(validations),
        precision=precision,
        real_issues=real_issues,
        false_positives=false_positives,
        by_class={k: dict(v) for k, v in by_class.items()},
        severity_distribution=dict(severity_dist),
        validations=[asdict(v) for v in validations]
    )
    
    return results


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Signal Validity Experiment: Evaluate if detected signals are real issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--samples", "-n", type=int, default=20,
        help="Number of signals to sample (default: 20)"
    )
    parser.add_argument(
        "--seed", "-s", type=int, default=None,
        help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Output JSON file path (default: signal_validity_results_<timestamp>.json)"
    )
    
    args = parser.parse_args()
    
    # Run experiment
    results = run_experiment(n_samples=args.samples, seed=args.seed)
    
    # Save results
    if args.output:
        output_path = args.output
    else:
        output_path = f"signal_validity_results_{results.experiment_id}.json"
    
    with open(output_path, "w") as f:
        json.dump(asdict(results), f, indent=2)
    
    print(f"\nResults saved to: {output_path}")
    
    return results


if __name__ == "__main__":
    main()
