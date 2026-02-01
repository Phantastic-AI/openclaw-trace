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
DEFAULT_BRIEFS_DIR = Path(__file__).resolve().parents[1] / "docs" / "research-briefs"
PHORGE_URL = "https://hub.phantastic.ai"

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "by",
    "is",
    "are",
    "was",
    "were",
    "be",
    "this",
    "that",
    "it",
    "as",
    "at",
    "from",
    "into",
    "we",
    "you",
    "they",
    "i",
    "our",
    "your",
    "their",
}


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


def _extract_keywords(text: str, limit: int = 12) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9_]{4,}", text.lower())
    seen: set[str] = set()
    out: list[str] = []
    for w in words:
        if w in STOPWORDS or w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= limit:
            break
    return out


def _find_related_briefs(ticket: dict[str, str], root: Path, limit: int, max_chars: int) -> str:
    if not root.exists():
        return ""
    keywords = _extract_keywords(f"{ticket.get('title','')} {ticket.get('description','')}")
    if not keywords:
        return ""
    scored: list[tuple[int, Path]] = []
    for path in root.rglob("*.md"):
        try:
            text = _read_text(path).lower()
        except Exception:
            continue
        score = sum(1 for k in keywords if k in text)
        if score > 0:
            scored.append((score, path))
    if not scored:
        return ""
    scored.sort(key=lambda x: x[0], reverse=True)
    top_paths = [p for _score, p in scored[:limit]]
    related = _read_context(top_paths, max_chars)
    if not related:
        return ""
    return "## RELATED BRIEFS\n\n" + related


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


def _split_template(template_text: str) -> tuple[list[str], list[dict[str, str]]]:
    lines = template_text.splitlines()
    preamble: list[str] = []
    sections: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    body_lines: list[str] = []
    for line in lines:
        if line.startswith("## "):
            if current is not None:
                current["body"] = "\n".join(body_lines).rstrip()
                sections.append(current)
            current = {"heading": line.strip(), "body": ""}
            body_lines = []
            continue
        if current is None:
            preamble.append(line)
        else:
            body_lines.append(line)
    if current is not None:
        current["body"] = "\n".join(body_lines).rstrip()
        sections.append(current)
    return preamble, sections


def _render_preamble(preamble_lines: list[str], ticket: dict[str, str] | None) -> str:
    out: list[str] = []
    origin = ticket.get("url") if ticket else "Unknown"
    for line in preamble_lines:
        if line.startswith("# "):
            out.append("# Research Brief (v1)")
            continue
        if line.strip().lower().startswith("origin:"):
            out.append(f"Origin: {origin}")
            continue
        out.append(line)
    return "\n".join(out).strip()


def _build_section_prompt(
    *,
    section_heading: str,
    section_body: str,
    ticket: dict[str, str] | None,
    context: str,
    brief_so_far: str,
) -> str:
    system_context = (
        "You are writing a research brief for a recursive self-improvement system. "
        "Some issues are objective bugs/patches, some are subjective opportunities to delight, "
        "and some have multiple valid answers that require research/experiments. "
        "Fill only the requested section. Output markdown only. Keep it concise. "
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
        "BRIEF SO FAR:\n"
        f"{brief_so_far}\n\n"
        "SECTION TEMPLATE (fill only this section):\n"
        f"{section_heading}\n{section_body}\n\n"
        "Output ONLY this section (heading + filled bullets), nothing else.\n"
    )


def _build_section_revision_prompt(*, section_text: str, critic_notes: str) -> str:
    return (
        "Revise the section using the critic notes. Output ONLY the revised section.\n\n"
        f"CRITIC NOTES:\n{critic_notes}\n\n"
        f"SECTION:\n{section_text}\n"
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


def _run_codex_section_critic(section_text: str, model: str) -> str:
    prompt = (
        "Critique this single research-brief section for missing evidence, gaps, or vague claims. "
        "Return concise bullets with concrete fixes. If it is solid, return 'OK'.\n\n"
        f"{section_text}\n"
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
    ap.add_argument("--related-briefs-dir", type=str, default=str(DEFAULT_BRIEFS_DIR))
    ap.add_argument("--related-briefs-limit", type=int, default=3)
    ap.add_argument("--related-briefs-max-chars", type=int, default=3000)
    ap.add_argument("--no-related-briefs", action="store_true", help="Skip local related-briefs lookup")
    ap.add_argument("--model", type=str, default=os.environ.get("CLAUDE_MODEL", "sonnet"))
    ap.add_argument("--critic", action="store_true", help="Run Codex critic and write a review file")
    ap.add_argument("--actor-critic", action="store_true", help="Generate per-section with Codex critique/rewrite")
    ap.add_argument("--evidence-first", action="store_true", help="Draft Evidence snapshot first and use it as context")
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
    related_text = ""
    if ticket and not args.no_related_briefs:
        related_text = _find_related_briefs(
            ticket,
            Path(args.related_briefs_dir),
            args.related_briefs_limit,
            args.related_briefs_max_chars,
        )
    combined_context = "\n\n".join(part for part in [context_text, related_text] if part)
    if args.actor_critic:
        if not args.evidence_first:
            # Default to evidence-first in actor-critic mode if not specified.
            args.evidence_first = True
        preamble_lines, sections = _split_template(template_text)
        preamble = _render_preamble(preamble_lines, ticket)
        brief_parts: list[str] = [preamble] if preamble else []
        generated_sections: dict[int, str] = {}

        def _generate_section(section_heading: str, section_body: str, brief_so_far: str) -> str:
            section_prompt = _build_section_prompt(
                section_heading=section_heading,
                section_body=section_body,
                ticket=ticket,
                context=combined_context,
                brief_so_far=brief_so_far,
            )
            if args.dry_run:
                print(section_prompt)
                raise SystemExit(0)
            draft = _run_claude(section_prompt, args.model).strip()
            critic = _run_codex_section_critic(draft, args.critic_model).strip()
            if critic.lower() != "ok":
                draft = _run_claude(_build_section_revision_prompt(section_text=draft, critic_notes=critic), args.model).strip()
            return draft

        if args.evidence_first:
            for idx, section in enumerate(sections):
                if section["heading"].startswith("## 2) Evidence snapshot"):
                    evidence_text = _generate_section(section["heading"], section["body"], "\n\n".join(brief_parts).strip())
                    generated_sections[idx] = evidence_text
                    brief_parts.append(evidence_text)
                    break

        for idx, section in enumerate(sections):
            if idx in generated_sections:
                continue
            draft = _generate_section(section["heading"], section["body"], "\n\n".join(brief_parts).strip())
            generated_sections[idx] = draft
            brief_parts.append(draft)

        ordered_sections = [generated_sections[idx] for idx in range(len(sections)) if idx in generated_sections]
        brief = "\n\n".join([part for part in brief_parts[:1] if part] + ordered_sections)
    else:
        prompt = _build_prompt(template=template_text, ticket=ticket, context=combined_context)
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
