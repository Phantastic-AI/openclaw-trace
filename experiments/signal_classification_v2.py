#!/usr/bin/env python3
"""
Signal Classification Experiment v2 — With Full Session Context

Research Question: How accurate is the automated kind_v2 classification?

Key improvement over v1: Includes raw session context, not just truncated summary.

Usage:
    python signal_classification_v2.py --samples 20 --seed 42

Output:
    - Console: Confusion matrix, precision/recall/F1
    - JSON: Full results
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

# ============================================================================
# CONFIGURATION
# ============================================================================

ROLLUP_PATH = "/home/debian/clawd/home/tmp/rollup_latest120_v2_snapshot.json"
RAW_SIGNALS_PATH = "/home/debian/clawd/home/tmp/out_signals_latest120_v2.jsonl"
SESSIONS_DIR = "/home/debian/clawd/home/tmp/sessions_latest_120_20260201_024756"
EVAL_MODEL = "claude-sonnet-4-20250514"

CLASSES = [
    "ux_friction",
    "proactive_opportunity", 
    "defect",
    "process_tooling",
    "user_delight",
    "capability_gap",
    "reliability_perf"
]

CLASS_DESCRIPTIONS = {
    "ux_friction": "User experience issues, confusing interactions, spam, repeated questions, annoyance",
    "proactive_opportunity": "Chances for the agent to be more helpful proactively without being asked",
    "defect": "Bugs, errors, failures, crashes, things that are broken and shouldn't happen",
    "process_tooling": "Issues with tools, workflows, infrastructure, configuration, external services",
    "user_delight": "Positive interactions, appreciation, compliments, things working well",
    "capability_gap": "Missing features or abilities the agent should have but doesn't",
    "reliability_perf": "Performance, reliability, timeouts, availability, speed issues"
}

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ClassificationResult:
    fingerprint_id: str
    signal_class_auto: str      # Automated classification
    signal_class_claude: str    # Claude's classification
    canonical_summary: str      # Short summary
    session_context: str        # Full evidence (truncated for storage)
    confidence: str
    reasoning: str
    match: bool


# ============================================================================
# DATA LOADING & CONTEXT RETRIEVAL
# ============================================================================

def load_rollups(path: str = ROLLUP_PATH) -> list[dict]:
    with open(path) as f:
        return json.load(f).get("rollups", [])


def load_raw_signals(path: str = RAW_SIGNALS_PATH) -> dict:
    """
    Load raw signals and index by fingerprint for quick lookup.
    Raw signals have actual evidence quotes from the sessions.
    """
    signals_by_fingerprint = defaultdict(list)
    
    with open(path) as f:
        for line in f:
            try:
                sig = json.loads(line.strip())
                # We need to match to rollups somehow
                # Store by summary for fuzzy matching
                summary = sig.get("summary", "")
                signals_by_fingerprint[summary].append(sig)
            except:
                continue
    
    return signals_by_fingerprint


def get_automated_class(rollup: dict) -> str:
    counts = rollup.get("kind_v2_counts", {})
    return max(counts, key=counts.get) if counts else "unknown"


def get_session_context(rollup: dict, raw_signals: dict, max_chars: int = 4000) -> str:
    """
    Retrieve evidence from raw signals — actual quotes from sessions.
    
    The raw_signals dict is indexed by summary for fuzzy matching.
    Each raw signal has an 'evidence' array with quotes.
    """
    canonical = rollup.get("canonical_summary", "")
    
    evidence_snippets = []
    
    # Try to find matching raw signals by looking for similar summaries
    for summary, signals in raw_signals.items():
        # Check if this summary is related to our rollup
        # (Simple check: if words overlap significantly)
        canonical_words = set(canonical.lower().split())
        summary_words = set(summary.lower().split())
        
        if len(canonical_words & summary_words) >= 3:  # At least 3 words in common
            for sig in signals[:3]:  # Up to 3 signals per summary
                # Extract evidence quotes
                for ev in sig.get("evidence", []):
                    quote = ev.get("quote", "")
                    role = ev.get("role", "")
                    if quote:
                        evidence_snippets.append(f"[{role}]: {quote}")
                
                # Also include the signal's own summary
                evidence_snippets.append(f"[signal]: {summary}")
    
    if not evidence_snippets:
        # Fallback: just use the canonical summary repeated
        return f"[canonical]: {canonical}"
    
    # Deduplicate and join
    seen = set()
    unique = []
    for snip in evidence_snippets:
        if snip not in seen:
            seen.add(snip)
            unique.append(snip)
    
    return "\n---\n".join(unique[:15])[:max_chars]


def stratified_sample(rollups: list[dict], n_total: int = 20) -> list[dict]:
    """Sample ensuring representation from each class."""
    by_class = defaultdict(list)
    for r in rollups:
        by_class[get_automated_class(r)].append(r)
    
    samples = []
    total = sum(len(v) for v in by_class.values())
    remaining = n_total
    
    for cls in CLASSES:
        if cls in by_class and by_class[cls] and remaining > 0:
            proportion = len(by_class[cls]) / total
            n = max(1, min(len(by_class[cls]), int(n_total * proportion) + 1, remaining))
            samples.extend(random.sample(by_class[cls], n))
            remaining -= n
    
    random.shuffle(samples)
    return samples[:n_total]


# ============================================================================
# CLASSIFICATION
# ============================================================================

def classify_with_claude(summary: str, context: str, client) -> dict:
    """
    Have Claude classify the signal using BOTH summary AND full context.
    """
    class_list = "\n".join([f"- **{cls}**: {desc}" for cls, desc in CLASS_DESCRIPTIONS.items()])
    
    prompt = f"""You are evaluating a signal extracted from an AI agent's session logs.
Your task is to classify it into exactly ONE of these categories:

{class_list}

---

## Signal to classify

**Summary:** {summary}

**Session Evidence (raw conversation):**
{context}

---

## Instructions

1. Read BOTH the summary AND the raw session evidence carefully
2. The session evidence shows what actually happened — use it to understand the context
3. Choose the SINGLE most appropriate category
4. If the evidence contradicts the summary, trust the evidence

## Response Format (JSON only)

{{
  "class": "<one of: {', '.join(CLASSES)}>",
  "confidence": "<high|medium|low>",
  "reasoning": "<1-2 sentence explanation>"
}}
"""

    try:
        response = client.messages.create(
            model=EVAL_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        return json.loads(text)
    except Exception as e:
        return {"class": "unknown", "confidence": "none", "reasoning": f"Error: {e}"}


# ============================================================================
# METRICS
# ============================================================================

def compute_metrics(results: list[ClassificationResult]) -> dict:
    confusion = defaultdict(lambda: defaultdict(int))
    for r in results:
        confusion[r.signal_class_auto][r.signal_class_claude] += 1
    
    metrics = {}
    for cls in CLASSES:
        tp = confusion[cls][cls]
        fp = sum(confusion[other][cls] for other in CLASSES if other != cls)
        fn = sum(confusion[cls][other] for other in CLASSES if other != cls)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        metrics[cls] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3)
        }
    
    correct = sum(1 for r in results if r.match)
    
    return {
        "accuracy": round(correct / len(results), 3) if results else 0,
        "n_samples": len(results),
        "n_correct": correct,
        "per_class": metrics,
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()}
    }


# ============================================================================
# EXPERIMENT
# ============================================================================

def run_experiment(n_samples: int = 20, seed: int = None):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)
    
    from anthropic import Anthropic
    client = Anthropic()
    
    if seed is not None:
        random.seed(seed)
        print(f"Random seed: {seed}")
    
    print("\n" + "="*70)
    print("SIGNAL CLASSIFICATION EXPERIMENT v2 (with full context)")
    print("="*70)
    
    rollups = load_rollups()
    print(f"Loaded {len(rollups)} rollups")
    
    raw_signals = load_raw_signals()
    print(f"Loaded raw signals with {len(raw_signals)} unique summaries")
    
    samples = stratified_sample(rollups, n_samples)
    print(f"Sampled {len(samples)} signals")
    
    # Show distribution
    dist = defaultdict(int)
    for s in samples:
        dist[get_automated_class(s)] += 1
    print(f"Distribution: {dict(dist)}")
    
    print(f"\nClassifying with {EVAL_MODEL}...")
    print("-" * 70)
    
    results = []
    for i, rollup in enumerate(samples):
        auto_class = get_automated_class(rollup)
        summary = rollup.get("canonical_summary", "")
        context = get_session_context(rollup, raw_signals)
        
        print(f"[{i+1}/{len(samples)}] {summary[:50]}...")
        print(f"  Context length: {len(context)} chars")
        
        result = classify_with_claude(summary, context, client)
        claude_class = result.get("class", "unknown")
        
        classification = ClassificationResult(
            fingerprint_id=rollup.get("fingerprint_id", ""),
            signal_class_auto=auto_class,
            signal_class_claude=claude_class,
            canonical_summary=summary,
            session_context=context[:1000] + "..." if len(context) > 1000 else context,
            confidence=result.get("confidence", ""),
            reasoning=result.get("reasoning", ""),
            match=(auto_class == claude_class)
        )
        results.append(classification)
        
        status = "✓" if classification.match else "✗"
        print(f"  {status} auto={auto_class}, claude={claude_class}")
        
        time.sleep(0.5)
    
    # Metrics
    metrics = compute_metrics(results)
    
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    
    print(f"\n**Accuracy: {metrics['accuracy']:.1%}** ({metrics['n_correct']}/{metrics['n_samples']})")
    
    print(f"\nPer-Class Metrics:")
    print(f"{'Class':<25} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print("-" * 55)
    for cls in CLASSES:
        m = metrics['per_class'].get(cls, {})
        if m.get('tp', 0) + m.get('fp', 0) + m.get('fn', 0) > 0:
            print(f"{cls:<25} {m.get('precision', 0):>10.2f} {m.get('recall', 0):>10.2f} {m.get('f1', 0):>10.2f}")
    
    return {
        "experiment": "signal_classification_v2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_samples": len(samples),
        "metrics": metrics,
        "results": [asdict(r) for r in results]
    }


def main():
    parser = argparse.ArgumentParser(description="Signal Classification v2 (with full context)")
    parser.add_argument("--samples", "-n", type=int, default=20)
    parser.add_argument("--seed", "-s", type=int, default=None)
    parser.add_argument("--output", "-o", type=str, default=None)
    args = parser.parse_args()
    
    output = run_experiment(n_samples=args.samples, seed=args.seed)
    
    out_path = args.output or f"signal_classification_v2_results.json"
    Path(out_path).write_text(json.dumps(output, indent=2))
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
