from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .llm_client import NoLLMClient, OpenAICompatClient
from .recursive_driver import DriverConfig, RecursiveAnalyzer
from .transcript import load_transcript


def main_deprecated() -> None:
    """Backwards-compatible entrypoint for the old `rlm-analyze` script name."""
    print(
        "DEPRECATED: `rlm-analyze` has been renamed to `claw-trace`. "
        "Please update your scripts.\n",
        file=sys.stderr,
    )
    main()


def _build_llm(kind: str) -> object:
    if kind == "openai":
        try:
            return OpenAICompatClient()
        except Exception:
            return NoLLMClient()
    return NoLLMClient()


def _cmd_analyze(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(
        prog="claw-trace analyze",
        description="RLM-style analyzer for a single Clawdbot session transcript (jsonl).",
    )
    ap.add_argument("transcriptPath", help="Path to a Clawdbot session transcript .jsonl")
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
        prog="claw-trace mine-ideas",
        description="Crawl many Clawdbot session jsonl files and mine frontier experiment ideas (PII-safe).",
    )
    ap.add_argument(
        "--sessions-dir",
        default="/home/debian/.clawdbot/agents/main/sessions",
        help="Directory containing Clawdbot session .jsonl files",
    )
    ap.add_argument(
        "--include",
        action="append",
        default=["**/*.jsonl"],
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
    ap.add_argument("--no-llm", action="store_true", help="Only do deterministic candidate extraction + synopses")
    ap.add_argument(
        "--scrub-output",
        action="store_true",
        help="(Optional) scrub PII-ish patterns from JSON/Markdown outputs and drop offending lines. Default: off.",
    )
    ap.add_argument(
        "--no-scrub",
        action="store_true",
        help="Alias for default behavior (do not scrub outputs).",
    )
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

    llm = NoLLMClient() if (args.llm == "none" or args.no_llm) else _build_llm(args.llm)

    scrub_output = bool(args.scrub_output) and not bool(args.no_scrub)

    cfg = MineIdeasConfig(
        sessions_dir=Path(args.sessions_dir),
        include=args.include or [],
        exclude=args.exclude or [],
        max_sessions=args.max_sessions,
        max_matches_per_session=args.max_matches_per_session,
        max_snippet_chars=args.max_snippet_chars,
        use_llm=not args.no_llm and args.llm != "none",
        temperature=args.temperature,
        scrub_output=scrub_output,
    )

    report = mine_ideas(llm=llm, cfg=cfg, keywords=kw)
    Path(args.out_json).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    Path(args.out_md).write_text(render_markdown(report, scrub_output=scrub_output), encoding="utf-8")


def main() -> None:
    # Backwards-compatible behavior:
    # - `claw-trace <transcriptPath> [flags]` -> analyze
    # New subcommands:
    # - `claw-trace analyze ...`
    # - `claw-trace mine-ideas ...`
    if len(sys.argv) >= 2 and sys.argv[1] not in {"analyze", "mine-ideas", "mine_ideas", "-h", "--help"}:
        _cmd_analyze(sys.argv[1:])
        return

    ap = argparse.ArgumentParser(prog="claw-trace")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("analyze", help="Analyze a single transcript (existing functionality)")
    sub.add_parser("mine-ideas", help="Mine research experiment ideas from many sessions (PII-safe)")

    ns, rest = ap.parse_known_args(sys.argv[1:2])

    if ns.cmd == "analyze":
        _cmd_analyze(sys.argv[2:])
    elif ns.cmd == "mine-ideas":
        _cmd_mine_ideas(sys.argv[2:])
    else:
        ap.print_help()
        raise SystemExit(2)


if __name__ == "__main__":
    main()
