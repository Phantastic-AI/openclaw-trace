#!/usr/bin/env python3
"""
Signal Validity Experiment

Research Question: When the signal miner says "there's an issue", 
                   is there actually an issue?

This is ground truth validation:
1. Take signals classified as problems (ux_friction, defect, etc.)
2. Go back to the raw session evidence
3. Have Claude judge: "Is this actually a problem, or false positive?"

Metrics:
- True Positive Rate: signals that are real issues
- False Positive Rate: signals that aren't actually issues
"""

import json
import os
import random
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path

from anthropic import Anthropic

# Load API key
env_file = Path('/home/debian/clawd/home/Workspace/Denario/.env')
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key, val = line.split('=', 1)
            os.environ[key] = val.strip('"').strip("'")


ROLLUP_PATH = "/home/debian/clawd/home/tmp/rollup_latest120_v2_snapshot.json"
SESSIONS_DIR = "/home/debian/clawd/home/tmp/sessions_latest_120_20260201_024756"


@dataclass
class ValidityResult:
    fingerprint_id: str
    signal_class: str
    canonical_summary: str
    session_context: str
    is_real_issue: bool  # Claude's judgment
    confidence: str
    reasoning: str
    severity_if_real: str  # none/low/medium/high


def load_rollups() -> list[dict]:
    with open(ROLLUP_PATH) as f:
        data = json.load(f)
    return data.get("rollups", [])


def get_signal_class(rollup: dict) -> str:
    counts = rollup.get("kind_v2_counts", {})
    if not counts:
        return "unknown"
    return max(counts, key=counts.get)


def get_session_context(rollup: dict) -> str:
    """Get raw session context for a signal."""
    # Get session IDs from the rollup
    session_ids = set()
    for sig in rollup.get("signals", []):
        sid = sig.get("session_id", "")
        if sid:
            session_ids.add(sid)
    
    context_snippets = []
    
    # Find matching session files and extract relevant content
    for sf in Path(SESSIONS_DIR).glob("*.jsonl"):
        with open(sf) as f:
            first_line = f.readline()
            try:
                header = json.loads(first_line)
                if header.get("id") in session_ids:
                    # Read a sample of the session
                    f.seek(0)
                    lines = f.readlines()[:50]  # First 50 events
                    
                    for line in lines:
                        try:
                            event = json.loads(line)
                            msg = event.get("message", {})
                            content = msg.get("content", [])
                            role = msg.get("role", "")
                            
                            if isinstance(content, list):
                                for block in content:
                                    if isinstance(block, dict) and block.get("type") == "text":
                                        text = block.get("text", "")[:500]
                                        if text:
                                            context_snippets.append(f"[{role}]: {text}")
                        except:
                            continue
            except:
                continue
    
    if not context_snippets:
        # Fallback: use the signal summaries
        for sig in rollup.get("signals", [])[:3]:
            context_snippets.append(sig.get("summary", ""))
    
    return "\n---\n".join(context_snippets[:10])[:3000]


def validate_signal(rollup: dict) -> ValidityResult:
    """Have Claude judge if a signal is a real issue."""
    
    signal_class = get_signal_class(rollup)
    summary = rollup.get("canonical_summary", "")
    context = get_session_context(rollup)
    
    client = Anthropic()
    
    prompt = f"""You are auditing an AI agent's self-improvement system. 

The system detected a "signal" (potential issue) from analyzing session logs:

**Signal Class:** {signal_class}
**Signal Summary:** {summary}

**Raw Session Context:**
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
  "is_real_issue": true/false,
  "confidence": "high/medium/low",
  "reasoning": "1-2 sentence explanation",
  "severity_if_real": "none/low/medium/high"
}}
"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        result = json.loads(text)
        
        return ValidityResult(
            fingerprint_id=rollup.get("fingerprint_id", ""),
            signal_class=signal_class,
            canonical_summary=summary,
            session_context=context[:500],
            is_real_issue=result.get("is_real_issue", False),
            confidence=result.get("confidence", "low"),
            reasoning=result.get("reasoning", ""),
            severity_if_real=result.get("severity_if_real", "none")
        )
    except Exception as e:
        return ValidityResult(
            fingerprint_id=rollup.get("fingerprint_id", ""),
            signal_class=signal_class,
            canonical_summary=summary,
            session_context=context[:500],
            is_real_issue=False,
            confidence="none",
            reasoning=f"Error: {e}",
            severity_if_real="none"
        )


def run_experiment(n_samples: int = 20):
    """Run the validity experiment."""
    
    print("="*60)
    print("SIGNAL VALIDITY EXPERIMENT")
    print("Is there actually an issue when the system says there is?")
    print("="*60)
    
    rollups = load_rollups()
    
    # Filter to "problem" signals only
    problem_classes = ["ux_friction", "defect", "process_tooling", "reliability_perf", "capability_gap"]
    problem_rollups = [r for r in rollups if get_signal_class(r) in problem_classes]
    
    print(f"\nTotal rollups: {len(rollups)}")
    print(f"Problem signals: {len(problem_rollups)}")
    
    # Sample
    samples = random.sample(problem_rollups, min(n_samples, len(problem_rollups)))
    print(f"Sampled: {len(samples)}")
    
    # Validate each
    results = []
    for i, rollup in enumerate(samples):
        print(f"\n[{i+1}/{len(samples)}] Validating: {rollup.get('canonical_summary', '')[:50]}...")
        
        result = validate_signal(rollup)
        results.append(result)
        
        status = "✓ REAL" if result.is_real_issue else "✗ FALSE POS"
        print(f"  → {status} ({result.confidence}): {result.reasoning[:60]}")
        
        time.sleep(0.5)
    
    # Compute metrics
    real_issues = sum(1 for r in results if r.is_real_issue)
    false_positives = len(results) - real_issues
    
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    
    precision = real_issues / len(results) if results else 0
    print(f"\n**Signal Precision: {precision:.1%}**")
    print(f"  Real issues: {real_issues}/{len(results)}")
    print(f"  False positives: {false_positives}/{len(results)}")
    
    # By class
    by_class = defaultdict(lambda: {"real": 0, "false": 0})
    for r in results:
        if r.is_real_issue:
            by_class[r.signal_class]["real"] += 1
        else:
            by_class[r.signal_class]["false"] += 1
    
    print("\nBy class:")
    for cls, counts in by_class.items():
        total = counts["real"] + counts["false"]
        pct = counts["real"] / total if total else 0
        print(f"  {cls}: {pct:.0%} real ({counts['real']}/{total})")
    
    # Severity distribution
    print("\nSeverity of real issues:")
    severity_counts = defaultdict(int)
    for r in results:
        if r.is_real_issue:
            severity_counts[r.severity_if_real] += 1
    for sev, count in sorted(severity_counts.items()):
        print(f"  {sev}: {count}")
    
    # Save results
    output = {
        "n_samples": len(results),
        "precision": precision,
        "real_issues": real_issues,
        "false_positives": false_positives,
        "by_class": dict(by_class),
        "results": [asdict(r) for r in results]
    }
    
    out_path = Path(__file__).parent / "signal_validity_results.json"
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nResults saved to {out_path}")
    
    return output


if __name__ == "__main__":
    run_experiment(20)
