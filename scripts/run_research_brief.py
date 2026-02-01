#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

DEFAULT_TEMPLATE = Path(__file__).resolve().parents[1] / "docs" / "research-briefs" / "BRIEF_TEMPLATE.md"
PHORGE_URL = "https://hub.phantastic.ai"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:60] or "brief"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _fetch_ticket(ticket_id: int) -> dict[str, str]:
    payload = {"constraints": {"ids": [ticket_id]}, "limit": 1}
    cmd = [
        "sudo",
        "/srv/phorge/phorge/bin/conduit",
        "call",
        "--local",
        "--method",
        "maniphest.search",
        "--as",
        "admin",
        "--input",
        "-",
    ]
    proc = subprocess.run(cmd, input=json.dumps(payload), text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "Failed to fetch ticket")
    data = json.loads(proc.stdout)
    items = data.get("result", {}).get("data", [])
    if not items:
        raise RuntimeError(f"Ticket T{ticket_id} not found")
    fields = items[0]["fields"]
    return {
        "title": fields.get("name") or f"T{ticket_id}",
        "description": fields.get("description", {}).get("raw") or "",
        "url": f"{PHORGE_URL}/T{ticket_id}",
    }


def _read_context(paths: list[Path], max_chars: int) -> str:
    if not paths:
        return ""
    parts: list[str] = []
    used = 0
    for path in paths:
        text = _read_text(path)
        remaining = max_chars - used
        if remaining <= 0:
            break
        if len(text) > remaining:
            text = text[:remaining] + "\n...[truncated]\n"
        parts.append(f"## CONTEXT: {path}\n{text}")
        used += len(text)
    return "\n\n".join(parts)


def _build_prompt(*, template: str, ticket: dict[str, str] | None, context: str) -> str:
    system_context = (
        "You are writing a research brief for a recursive self-improvement system. "
        "Some issues are objective bugs/patches, some are subjective opportunities to delight, "
        "and some have multiple valid answers that require research/experiments. "
        "Follow the template exactly. Output markdown only. Keep it concise. "
        "If information is missing, write 'Unknown' and add a validation test."
    )

    ticket_block = ""
    if ticket:
        ticket_block = (
            f"Ticket: {ticket.get('title','')}\n"
            f"URL: {ticket.get('url','')}\n"
            f"Description:\n{ticket.get('description','')}\n"
        )

    return (
        f"{system_context}\n\n"
        f"{ticket_block}\n"
        f"{context}\n\n"
        "TEMPLATE (fill in all sections):\n\n"
        f"{template}\n"
    )


def _run_claude(prompt: str, model: str) -> str:
    cmd = [
        "claude",
        "-p",
        "--print",
        "--output-format",
        "text",
        "--permission-mode",
        "dontAsk",
        "--model",
        model,
        prompt,
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "Claude CLI failed")
    return proc.stdout


def _run_codex_critic(brief: str, model: str) -> str:
    prompt = (
        "Review this research brief for gaps, weak evidence, and missing RCA validation tests. "
        "Return concise bullets with concrete fixes.\n\n"
        f"{brief}\n"
    )
    cmd = ["codex", "exec", "-c", f'model="{model}"', prompt]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "Codex exec failed")
    return proc.stdout


def main() -> None:
    ap = argparse.ArgumentParser(description="Headless research-brief runner (Claude Code + optional Codex critic)")
    ap.add_argument("--ticket-id", type=int, default=None, help="Phorge ticket ID (e.g., 145)")
    ap.add_argument("--ticket-url", type=str, default=None, help="Phorge ticket URL (overrides ticket-id URL)")
    ap.add_argument("--context", action="append", default=[], help="Context file(s) to include (repeatable)")
    ap.add_argument("--template", type=str, default=str(DEFAULT_TEMPLATE), help="Template path")
    ap.add_argument("--out", type=str, default=None, help="Output brief path")
    ap.add_argument("--max-context-chars", type=int, default=12000)
    ap.add_argument("--model", type=str, default=os.environ.get("CLAUDE_MODEL", "sonnet"))
    ap.add_argument("--critic", action="store_true", help="Run Codex critic and write a review file")
    ap.add_argument("--critic-model", type=str, default=os.environ.get("CODEX_MODEL", "gpt-5.2-codex"))
    ap.add_argument("--dry-run", action="store_true", help="Print prompt and exit")

    args = ap.parse_args()

    ticket: Optional[dict[str, str]] = None
    if args.ticket_id:
        try:
            ticket = _fetch_ticket(args.ticket_id)
        except Exception as exc:
            print(f"[brief-runner] WARN: {exc}", file=sys.stderr)
    if ticket and args.ticket_url:
        ticket["url"] = args.ticket_url
    elif args.ticket_url and not ticket:
        ticket = {"title": f"T{args.ticket_id or ''}", "description": "", "url": args.ticket_url}

    template_text = _read_text(Path(args.template))
    context_text = _read_context([Path(p) for p in args.context], args.max_context_chars)
    prompt = _build_prompt(template=template_text, ticket=ticket, context=context_text)

    if args.dry_run:
        print(prompt)
        return

    brief = _run_claude(prompt, args.model)

    out_path: Path
    if args.out:
        out_path = Path(args.out)
    else:
        if not ticket:
            raise SystemExit("Provide --out when --ticket-id/--ticket-url is not set")
        slug = _slugify(ticket.get("title", "brief"))
        out_path = Path("docs") / "research-briefs" / f"T{args.ticket_id}-{slug}" / "oracle-brief-v1.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(brief, encoding="utf-8")
    print(f"[brief-runner] wrote {out_path}")

    if args.critic:
        review = _run_codex_critic(brief, args.critic_model)
        review_path = out_path.with_name(out_path.stem + ".codex-review.md")
        review_path.write_text(review, encoding="utf-8")
        print(f"[brief-runner] wrote {review_path}")


if __name__ == "__main__":
    main()
