#!/usr/bin/env python3
"""
Workflow Extraction Experiment

Goal: Find repeating tool-call sequences in session traces 
      → candidate skill definitions

Approach:
1. Parse sessions for tool call sequences
2. Find frequent n-grams (tool patterns)
3. Cluster similar workflows
4. Output skill candidates
"""

import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Generator

SESSIONS_DIR = "/home/debian/clawd/home/tmp/sessions_latest_120_20260201_024756"


def extract_tool_calls(session_path: str) -> list[dict]:
    """Extract tool calls from a session file."""
    tools = []
    with open(session_path) as f:
        for line in f:
            try:
                event = json.loads(line.strip())
                msg = event.get("message", {})
                content = msg.get("content", [])
                
                # Look for toolCall blocks (Clawdbot format)
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "toolCall":
                            tools.append({
                                "name": block.get("name", "unknown"),
                                "input": block.get("arguments", {}),
                                "id": block.get("id", ""),
                                "timestamp": event.get("timestamp", "")
                            })
            except:
                continue
    return tools


def get_tool_sequence(session_path: str) -> list[str]:
    """Get ordered list of tool names from a session."""
    tools = extract_tool_calls(session_path)
    return [t["name"] for t in tools]


def find_ngrams(sequence: list[str], n: int) -> list[tuple]:
    """Extract n-grams from a sequence."""
    return [tuple(sequence[i:i+n]) for i in range(len(sequence) - n + 1)]


def analyze_workflows(sessions_dir: str, min_n: int = 2, max_n: int = 5):
    """Analyze tool sequences for patterns."""
    
    all_sequences = []
    session_files = list(Path(sessions_dir).glob("*.jsonl"))
    
    print(f"Analyzing {len(session_files)} sessions...")
    
    for sf in session_files:
        seq = get_tool_sequence(str(sf))
        if len(seq) >= 2:
            all_sequences.append(seq)
    
    print(f"Found {len(all_sequences)} sessions with tool calls")
    
    # Count n-grams
    ngram_counts = defaultdict(Counter)
    
    for seq in all_sequences:
        for n in range(min_n, max_n + 1):
            for ngram in find_ngrams(seq, n):
                ngram_counts[n][ngram] += 1
    
    # Find frequent patterns
    print("\n" + "="*60)
    print("FREQUENT TOOL PATTERNS (potential skills)")
    print("="*60)
    
    for n in range(min_n, max_n + 1):
        top_patterns = ngram_counts[n].most_common(10)
        meaningful = [(p, c) for p, c in top_patterns if c >= 2]
        
        if meaningful:
            print(f"\n### {n}-tool sequences (count >= 2)")
            for pattern, count in meaningful:
                print(f"  [{count:2d}x] {' → '.join(pattern)}")
    
    # Identify skill candidates
    print("\n" + "="*60)
    print("SKILL CANDIDATES")
    print("="*60)
    
    # Look for INTERESTING patterns (not just same-tool chains)
    def is_interesting(pattern):
        """A pattern is interesting if it has 2+ distinct tools."""
        return len(set(pattern)) >= 2
    
    candidates = []
    for n in range(2, max_n + 1):
        for pattern, count in ngram_counts[n].most_common(50):
            if count >= 3 and is_interesting(pattern):
                candidates.append({
                    "pattern": list(pattern),
                    "count": count,
                    "length": n
                })
    
    # Deduplicate (remove subpatterns if superpattern exists)
    filtered = []
    for c in sorted(candidates, key=lambda x: -x["length"]):
        is_sub = False
        for existing in filtered:
            if all(t in existing["pattern"] for t in c["pattern"]):
                is_sub = True
                break
        if not is_sub:
            filtered.append(c)
    
    for i, c in enumerate(filtered[:15], 1):
        print(f"\n{i}. **{' → '.join(c['pattern'])}** ({c['count']}x)")
        
        # Suggest skill name
        tool_names = c["pattern"]
        if "memory_search" in tool_names:
            print("   → Skill type: Memory/recall workflow")
        elif "Bash" in tool_names or "exec" in tool_names:
            print("   → Skill type: CLI/automation workflow")
        elif "browser" in tool_names:
            print("   → Skill type: Web automation workflow")
        elif "message" in tool_names:
            print("   → Skill type: Communication workflow")
        elif "cron" in tool_names:
            print("   → Skill type: Scheduling workflow")
        elif "Read" in tool_names and "Write" in tool_names:
            print("   → Skill type: File processing workflow")
    
    # Convert tuple keys to strings for JSON
    ngram_json = {}
    for n in range(min_n, max_n+1):
        ngram_json[n] = {" → ".join(k): v for k, v in ngram_counts[n].most_common(20)}
    
    return {
        "session_count": len(all_sequences),
        "ngram_counts": ngram_json,
        "candidates": filtered[:15]
    }


if __name__ == "__main__":
    results = analyze_workflows(SESSIONS_DIR)
    
    # Save results
    out_path = "/home/debian/clawd/home/rlm-session-analyzer/experiments/workflow_patterns.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")
