#!/usr/bin/env python3
"""
Extract detailed workflow examples from session traces.
"""

import json
from pathlib import Path
from collections import defaultdict

SESSIONS_DIR = "/home/debian/clawd/home/tmp/sessions_latest_120_20260201_024756"


def extract_tool_sequences_with_args(session_path: str) -> list[dict]:
    """Extract tool calls with arguments."""
    tools = []
    with open(session_path) as f:
        for line in f:
            try:
                event = json.loads(line.strip())
                msg = event.get("message", {})
                content = msg.get("content", [])
                
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "toolCall":
                            name = block.get("name", "unknown")
                            args = block.get("arguments", {})
                            
                            # Extract key info based on tool type
                            summary = summarize_tool(name, args)
                            
                            tools.append({
                                "name": name,
                                "summary": summary,
                                "timestamp": event.get("timestamp", "")
                            })
            except:
                continue
    return tools


def summarize_tool(name: str, args: dict) -> str:
    """Create a short summary of what the tool does."""
    if name in ("bash", "exec", "Bash"):
        cmd = args.get("command", "")[:80]
        return f"`{cmd}`"
    elif name == "read" or name == "Read":
        path = args.get("path", args.get("file_path", ""))
        return f"read: {path}"
    elif name == "write" or name == "Write":
        path = args.get("path", args.get("file_path", ""))
        return f"write: {path}"
    elif name == "edit" or name == "Edit":
        path = args.get("path", args.get("file_path", ""))
        return f"edit: {path}"
    elif name == "memory_search":
        query = args.get("query", "")[:50]
        return f"memory: '{query}'"
    elif name == "cron":
        action = args.get("action", "")
        return f"cron.{action}"
    elif name == "message":
        action = args.get("action", "")
        to = args.get("to", args.get("target", ""))[:30]
        return f"message.{action} → {to}"
    elif name == "gateway":
        action = args.get("action", "")
        return f"gateway.{action}"
    elif name == "process":
        action = args.get("action", "")
        return f"process.{action}"
    else:
        return name


def find_workflow_examples():
    """Find concrete examples of each workflow pattern."""
    
    # Patterns we're interested in
    patterns_of_interest = [
        ("memory_search", "bash"),  # recall-then-execute
        ("read", "bash"),           # file-driven
        ("write", "exec"),          # script-gen
        ("exec", "read", "edit"),   # debug loop
        ("cron",),                  # scheduling
    ]
    
    examples = defaultdict(list)
    
    session_files = list(Path(SESSIONS_DIR).glob("*.jsonl"))
    
    for sf in session_files:
        tools = extract_tool_sequences_with_args(str(sf))
        if len(tools) < 2:
            continue
        
        # Look for patterns
        tool_names = [t["name"].lower() for t in tools]
        
        # memory_search → bash
        for i, name in enumerate(tool_names):
            if name == "memory_search" and i + 1 < len(tool_names):
                if tool_names[i + 1] in ("bash", "exec"):
                    examples["recall-then-execute"].append({
                        "session": sf.name,
                        "sequence": [tools[i], tools[i+1]]
                    })
        
        # read → bash
        for i, name in enumerate(tool_names):
            if name == "read" and i + 1 < len(tool_names):
                if tool_names[i + 1] in ("bash", "exec"):
                    examples["file-driven-cli"].append({
                        "session": sf.name,
                        "sequence": [tools[i], tools[i+1]]
                    })
        
        # cron operations
        for i, name in enumerate(tool_names):
            if name == "cron":
                examples["scheduling"].append({
                    "session": sf.name,
                    "tool": tools[i]
                })
    
    # Print examples
    print("="*70)
    print("WORKFLOW EXAMPLES")
    print("="*70)
    
    for pattern_name, pattern_examples in examples.items():
        print(f"\n### {pattern_name.upper()} ({len(pattern_examples)} instances)")
        for ex in pattern_examples[:5]:  # Show first 5
            if "sequence" in ex:
                seq_str = " → ".join(t["summary"] for t in ex["sequence"])
                print(f"  • {seq_str}")
            else:
                print(f"  • {ex['tool']['summary']}")
    
    return examples


if __name__ == "__main__":
    examples = find_workflow_examples()
