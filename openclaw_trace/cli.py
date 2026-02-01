from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .llm_client import NoLLMClient, OpenAICompatClient
from .recursive_driver import DriverConfig, RecursiveAnalyzer
from .transcript import load_transcript


def _build_llm(kind: str) -> object:
    if kind == "openai":
        try:
            return OpenAICompatClient()
        except Exception:
            # If API env is missing/misconfigured, fall back to a deterministic stub.
            return NoLLMClient()
    return NoLLMClient()


def _cmd_analyze(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(
        prog="openclaw-trace analyze",
        description="RLM-inspired analyzer for a single OpenClaw/Clawdbot session transcript (jsonl).",
    )
    ap.add_argument("transcriptPath", help="Path to a session transcript .jsonl")
    ap.add_argument("--objective", default="Reconstruct phases/branches/failures while creating a research paper.")
    ap.add_argument("--max-events", type=int, default=None, help="Load only first N events (debug)")
    ap.add_argument("--max-iters", type=int, default=6)
    ap.add_argument("--program", type=str, default=None, help="Path to a Python program to run instead of calling an LLM")
    ap.add_argument("--out", type=str, default="-", help="Output JSON path (default: stdout)")
    ap.add_argument("--llm", choices=["openai", "none"], default="openai")
    ap.add_argument("--temperature", type=float, default=0.0)

    args = ap.parse_args(argv)

    transcript = load_transcript(args.transcriptPath, max_events=args.max_events)
    llm = _build_llm(args.llm)

    cfg = DriverConfig(max_iters=args.max_iters)
    analyzer = RecursiveAnalyzer(transcript=transcript, llm=llm, cfg=cfg)

    program_text = None
    if args.program:
        program_text = Path(args.program).read_text(encoding="utf-8")

    result = analyzer.run(objective=args.objective, program=program_text, temperature=args.temperature)

    out_obj = {
        "mode": "analyze",
        "transcriptPath": str(Path(args.transcriptPath).resolve()),
        "events": transcript.n,
        "objective": args.objective,
        "result": result,
    }

    s = json.dumps(out_obj, indent=2, ensure_ascii=False)
    if args.out == "-":
        print(s)
    else:
        Path(args.out).write_text(s, encoding="utf-8")


def _cmd_mine_ideas(argv: list[str]) -> None:
    from .mine_ideas import DEFAULT_KEYWORDS, MineIdeasConfig, mine_ideas, render_markdown

    ap = argparse.ArgumentParser(
        prog="openclaw-trace mine-ideas",
        description="Crawl many session jsonl files and mine frontier experiment ideas.",
    )
    ap.add_argument(
        "--sessions-dir",
        default="/home/debian/.clawdbot/agents/main/sessions",
        help="Directory containing session .jsonl files",
    )
    ap.add_argument(
        "--include",
        action="append",
        default=["*.jsonl", "**/*.jsonl"],
        help="Glob(s) relative to sessions-dir to include (repeatable)",
    )
    ap.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Glob(s) relative to sessions-dir to exclude (repeatable)",
    )
    ap.add_argument("--max-sessions", type=int, default=None)
    ap.add_argument("--max-matches-per-session", type=int, default=40)
    ap.add_argument("--max-snippet-chars", type=int, default=800)
    ap.add_argument("--dry-run", action="store_true", help="Only scan traces + write candidate segments (no LLM)")
    ap.add_argument("--llm", choices=["openai", "none"], default="openai")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument(
        "--keywords",
        type=str,
        default=",".join(DEFAULT_KEYWORDS),
        help="Comma-separated keywords to seed deterministic candidate mining",
    )
    ap.add_argument(
        "--out-json",
        type=str,
        default="out_mine_ideas.json",
        help="Output JSON path",
    )
    ap.add_argument(
        "--out-md",
        type=str,
        default="out_mine_ideas.md",
        help="Output Markdown report path",
    )

    args = ap.parse_args(argv)

    kw = [k.strip() for k in (args.keywords or "").split(",") if k.strip()]

    llm = NoLLMClient() if (args.llm == "none" or args.dry_run) else _build_llm(args.llm)

    cfg = MineIdeasConfig(
        sessions_dir=Path(args.sessions_dir),
        include=args.include or [],
        exclude=args.exclude or [],
        max_sessions=args.max_sessions,
        max_matches_per_session=args.max_matches_per_session,
        max_snippet_chars=args.max_snippet_chars,
        use_llm=not args.dry_run and args.llm != "none",
        temperature=args.temperature,
    )

    report = mine_ideas(llm=llm, cfg=cfg, keywords=kw)

    # Always print a tiny sanity line so it's obvious what we scanned.
    try:
        matched = len(report.get("results", []))
    except Exception:
        matched = "?"
    print(f"[openclaw-trace] mine-ideas: sessionsDir={cfg.sessions_dir} matched={matched}", file=sys.stderr)

    Path(args.out_json).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    Path(args.out_md).write_text(render_markdown(report), encoding="utf-8")


def _cmd_mine_signals(argv: list[str]) -> None:
    from .mine_signals import MineSignalsConfig, mine_signals

    ap = argparse.ArgumentParser(
        prog="openclaw-trace mine-signals",
        description="Crawl many session jsonl files and mine self-improvement signals.",
    )
    ap.add_argument(
        "--sessions-dir",
        default="/home/debian/.clawdbot/agents/main/sessions",
        help="Directory containing session .jsonl files",
    )
    ap.add_argument(
        "--include",
        action="append",
        default=["*.jsonl", "**/*.jsonl"],
        help="Glob(s) relative to sessions-dir to include (repeatable)",
    )
    ap.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Glob(s) relative to sessions-dir to exclude (repeatable)",
    )
    ap.add_argument("--max-sessions", type=int, default=None)
    ap.add_argument("--chunk-events", type=int, default=20)
    ap.add_argument("--chunk-overlap", type=int, default=4)
    ap.add_argument("--max-text-chars", type=int, default=800)
    ap.add_argument("--max-items-per-chunk", type=int, default=10)
    ap.add_argument("--max-evidence-per-item", type=int, default=2)
    ap.add_argument("--max-summary-chars", type=int, default=120)
    ap.add_argument("--max-quote-chars", type=int, default=200)
    ap.add_argument("--llm", choices=["openai", "none"], default="openai")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument(
        "--out-jsonl",
        type=str,
        default="out_signals.jsonl",
        help="Output JSONL path",
    )
    ap.add_argument(
        "--out-json",
        type=str,
        default="out_signals.json",
        help="Output summary JSON path",
    )

    args = ap.parse_args(argv)

    llm = NoLLMClient() if args.llm == "none" else _build_llm(args.llm)

    cfg = MineSignalsConfig(
        sessions_dir=Path(args.sessions_dir),
        include=args.include or [],
        exclude=args.exclude or [],
        max_sessions=args.max_sessions,
        chunk_events=args.chunk_events,
        chunk_overlap=args.chunk_overlap,
        max_text_chars=args.max_text_chars,
        max_items_per_chunk=args.max_items_per_chunk,
        max_evidence_per_item=args.max_evidence_per_item,
        max_summary_chars=args.max_summary_chars,
        max_quote_chars=args.max_quote_chars,
        use_llm=args.llm != "none",
        temperature=args.temperature,
    )

    summary, items = mine_signals(llm=llm, cfg=cfg)

    # Always print a tiny sanity line so it's obvious what we scanned.
    print(
        f"[openclaw-trace] mine-signals: sessionsDir={cfg.sessions_dir} items={summary['counts']['items']}",
        file=sys.stderr,
    )

    Path(args.out_jsonl).write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in items) + ("\n" if items else ""),
        encoding="utf-8",
    )
    Path(args.out_json).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")


def _cmd_rollup_signals(argv: list[str]) -> None:
    from .rollup_signals import RollupConfig, load_items, rollup_signals

    ap = argparse.ArgumentParser(
        prog="openclaw-trace rollup-signals",
        description="Roll up mined signals into ranked clusters.",
    )
    ap.add_argument("--in-jsonl", required=True, help="Input signals JSONL path")
    ap.add_argument("--out-json", default="rollup.json", help="Output rollup JSON path")
    ap.add_argument("--out-md", default="rollup.md", help="Output rollup Markdown path")
    ap.add_argument("--max-samples", type=int, default=3)
    ap.add_argument("--max-tags", type=int, default=8)

    args = ap.parse_args(argv)

    items = load_items(Path(args.in_jsonl))
    summary, rollups = rollup_signals(items=items, cfg=RollupConfig(max_samples=args.max_samples, max_tags=args.max_tags))

    out = {
        "summary": summary,
        "rollups": rollups,
    }
    Path(args.out_json).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    lines: list[str] = []
    lines.append("# Rollup summary")
    lines.append("")
    lines.append(f"- items: {summary['counts']['items']}")
    lines.append(f"- groups: {summary['counts']['groups']}")
    lines.append(f"- tiers: {summary['tiers']}")
    lines.append("")

    for r in rollups[:50]:
        lines.append(f"## Tier {r['tier']} score={r['score']:.2f}")
        lines.append("")
        lines.append(f"- summary: {r['canonical_summary']}")
        lines.append(f"- kinds: {r['kind_counts']}")
        lines.append(f"- max_severity: {r['max_severity']}")
        lines.append(f"- tags_top: {r['tags_top']}")
        lines.append(f"- samples: {len(r['sample_refs'])}")
        lines.append("")

    Path(args.out_md).write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> None:
    # Single, explicit CLI surface (no legacy aliases or implicit dispatch).
    # Use:
    # - `openclaw-trace analyze ...`
    # - `openclaw-trace mine-ideas ...`
    # - `openclaw-trace mine-signals ...`
    # - `openclaw-trace rollup-signals ...`
    ap = argparse.ArgumentParser(prog="openclaw-trace")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("analyze", help="Analyze a single transcript")
    sub.add_parser("mine-ideas", help="Mine frontier experiment ideas from many traces")
    sub.add_parser("mine-signals", help="Mine self-improvement signals from many traces")
    sub.add_parser("rollup-signals", help="Roll up mined signals into ranked clusters")

    ns, _rest = ap.parse_known_args(sys.argv[1:2])

    if ns.cmd == "analyze":
        _cmd_analyze(sys.argv[2:])
    elif ns.cmd == "mine-ideas":
        _cmd_mine_ideas(sys.argv[2:])
    elif ns.cmd == "mine-signals":
        _cmd_mine_signals(sys.argv[2:])
    elif ns.cmd == "rollup-signals":
        _cmd_rollup_signals(sys.argv[2:])
    else:
        ap.print_help()
        raise SystemExit(2)


if __name__ == "__main__":
    main()
