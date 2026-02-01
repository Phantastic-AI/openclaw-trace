#!/usr/bin/env bash
set -euo pipefail

if [ -f "$HOME/.profile" ]; then
  # shellcheck disable=SC1090
  source "$HOME/.profile"
fi

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "OPENAI_API_KEY is not set. Aborting." >&2
  exit 2
fi

SESSIONS_DIR="${SESSIONS_DIR:-/home/debian/.clawdbot/agents/main/sessions}"
INCLUDE_GLOB="${INCLUDE_GLOB:-**/*.jsonl}"
MAX_SESSIONS="${MAX_SESSIONS:-120}"
OUT_ROOT="${OUT_ROOT:-/home/debian/clawd/home/tmp}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${OUT_ROOT}/daily_${STAMP}"

MERGE_SIMILAR="${MERGE_SIMILAR:-1}"
MERGE_LLM="${MERGE_LLM:-1}"
TICKET_CREATE="${TICKET_CREATE:-0}"

mkdir -p "$OUT_DIR"

MINE_JSONL="$OUT_DIR/out_signals.jsonl"
MINE_JSON="$OUT_DIR/out_signals.json"
ROLLUP_JSON="$OUT_DIR/rollup.json"
ROLLUP_MD="$OUT_DIR/rollup.md"
TICKET_IR="$OUT_DIR/ticket_ir.jsonl"

python -m openclaw_trace.cli mine-signals \
  --sessions-dir "$SESSIONS_DIR" \
  --include "$INCLUDE_GLOB" \
  --max-sessions "$MAX_SESSIONS" \
  --out-jsonl "$MINE_JSONL" \
  --out-json "$MINE_JSON" \
  >"$OUT_DIR/mine_signals.log" 2>&1

ROLLUP_ARGS=(--in-jsonl "$MINE_JSONL" --out-json "$ROLLUP_JSON" --out-md "$ROLLUP_MD")
if [ "$MERGE_SIMILAR" = "1" ]; then
  ROLLUP_ARGS+=(--merge-similar)
fi
if [ "$MERGE_LLM" = "1" ]; then
  ROLLUP_ARGS+=(--merge-llm --llm openai)
fi

python -m openclaw_trace.cli rollup-signals "${ROLLUP_ARGS[@]}" \
  >"$OUT_DIR/rollup.log" 2>&1

python scripts/export_ticket_ir.py \
  --in-json "$ROLLUP_JSON" \
  --out-jsonl "$TICKET_IR" \
  >"$OUT_DIR/ticket_ir.log" 2>&1

if [ "$TICKET_CREATE" = "1" ]; then
  python scripts/ticket_rollup.py \
    --in-json "$ROLLUP_JSON" \
    >"$OUT_DIR/ticket_rollup.log" 2>&1
fi

echo "[daily-pipeline] out_dir=$OUT_DIR"
