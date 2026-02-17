#!/usr/bin/env python3
"""
Claude JSONL Session → Readable Transcript

Usage:
    python claude_transcript.py <session.jsonl> [--output transcript.md]
    python claude_transcript.py <session.jsonl> --format html
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path


def parse_timestamp(ts: str) -> str:
    """Convert ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return ts


def extract_text_content(message: dict) -> str:
    """Extract text from message content (handles arrays and strings)."""
    content = message.get('content', '')
    
    if isinstance(content, str):
        return content
    
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get('type') == 'text':
                    parts.append(block.get('text', ''))
                elif block.get('type') == 'tool_use':
                    tool = block.get('name', 'unknown')
                    parts.append(f"[Tool: {tool}]")
                elif block.get('type') == 'tool_result':
                    parts.append("[Tool Result]")
            elif isinstance(block, str):
                parts.append(block)
        return '\n'.join(parts)
    
    return str(content)


def parse_session(jsonl_path: Path) -> list[dict]:
    """Parse JSONL file into list of turns."""
    turns = []
    
    with open(jsonl_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            entry_type = entry.get('type')
            if entry_type not in ('user', 'assistant'):
                continue
            
            message = entry.get('message', {})
            role = message.get('role', entry_type)
            timestamp = entry.get('timestamp', '')
            content = extract_text_content(message)
            
            # Skip empty content or tool-only assistant turns
            stripped = content.strip()
            if not stripped:
                continue
            if stripped in ('[Tool Result]',):
                continue
            # Skip if only contains [Tool: X] markers
            if stripped.startswith('[Tool:') and '\n' not in stripped:
                continue
            
            turns.append({
                'role': role.upper(),
                'timestamp': parse_timestamp(timestamp),
                'content': content.strip(),
            })
    
    return turns


def format_markdown(turns: list[dict]) -> str:
    """Format turns as markdown transcript."""
    lines = ["# Session Transcript\n"]
    
    for turn in turns:
        lines.append(f"## {turn['role']} [{turn['timestamp']}]\n")
        lines.append(turn['content'])
        lines.append("\n")
    
    return '\n'.join(lines)


def format_html(turns: list[dict]) -> str:
    """Format turns as HTML transcript."""
    html = ['<!DOCTYPE html><html><head><style>']
    html.append('''
        body { font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .turn { margin: 20px 0; padding: 15px; border-radius: 8px; }
        .user { background: #e3f2fd; border-left: 4px solid #1976d2; }
        .assistant { background: #f3e5f5; border-left: 4px solid #7b1fa2; }
        .role { font-weight: bold; margin-bottom: 8px; }
        .timestamp { color: #666; font-size: 0.85em; margin-left: 10px; }
        .content { white-space: pre-wrap; }
    ''')
    html.append('</style></head><body>')
    html.append('<h1>Session Transcript</h1>')
    
    for turn in turns:
        role_class = turn['role'].lower()
        html.append(f'<div class="turn {role_class}">')
        html.append(f'<div class="role">{turn["role"]}<span class="timestamp">{turn["timestamp"]}</span></div>')
        html.append(f'<div class="content">{turn["content"]}</div>')
        html.append('</div>')
    
    html.append('</body></html>')
    return '\n'.join(html)


def main():
    parser = argparse.ArgumentParser(description='Convert Claude JSONL session to readable transcript')
    parser.add_argument('input', help='Input JSONL file')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')
    parser.add_argument('--format', '-f', choices=['md', 'html'], default='md', help='Output format')
    
    args = parser.parse_args()
    
    jsonl_path = Path(args.input)
    if not jsonl_path.exists():
        print(f"Error: {jsonl_path} not found", file=sys.stderr)
        sys.exit(1)
    
    turns = parse_session(jsonl_path)
    
    if args.format == 'html':
        output = format_html(turns)
    else:
        output = format_markdown(turns)
    
    if args.output:
        Path(args.output).write_text(output)
        print(f"Wrote {len(turns)} turns to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == '__main__':
    main()
