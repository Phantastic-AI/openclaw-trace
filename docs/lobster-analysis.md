# Lobster as a Solution Type for OpenClaw Trace Research Briefs

*Reviewed by Oracle (o3) — corrections applied.*

## What is Lobster?

[openclaw/lobster](https://github.com/openclaw/lobster) (480⭐) is a local-first workflow shell for OpenClaw. It runs YAML/JSON workflow files with:
- **Sequential steps**: each step runs a shell command (`/bin/sh -lc`), captures stdout/JSON output
- **Step references**: `$step_id.json`, `$step_id.stdout`, `$step_id.approved` — pipe data between steps (string substitution, not structural)
- **Approval gates**: steps with `approval: true` pause for human review, return a `resumeToken` for async resume
- **Args/env**: parameterized workflows with `${arg_name}` substitution (works in commands, env, cwd)
- **Conditions**: `when:` supports only `true`/`false`/`$step.approved`/`$step.skipped` — NOT arbitrary expressions or JSON lookups
- **State persistence**: resume tokens saved to disk via `writeStateJson`, workflows are resumable with `--resume <token>`
- **Resumability**: `workflows.run --resume <token>` picks up where it left off

**Important limitations:**
- No parallelism (sequential only)
- No built-in retry/timeout (must be emulated with multiple steps)
- Non-zero exit code aborts the entire workflow (no `on_error`/`continue_on_error`)
- No scheduling built-in (needs external cron/runner)
- Arbitrary shell execution — needs code-review/security practices
- TS-typed API, but no runtime type enforcement on step outputs

## Workflow File Format

```yaml
name: "optimized-heartbeat-check"
description: "Read HEARTBEAT.md only if hash changed since last check"
args:
  path:
    default: "/home/debian/clawd/HEARTBEAT.md"
    description: "Path to HEARTBEAT.md"
steps:
  - id: last_hash
    command: "lobster state.get heartbeat_hash 2>/dev/null || echo ''"
  - id: current_hash
    command: "sha256sum ${path} | cut -d' ' -f1"
  - id: compare_and_read
    command: |
      LAST=$(echo '$last_hash.stdout' | tr -d '[:space:]')
      CURR=$(echo '$current_hash.stdout' | tr -d '[:space:]')
      if [ "$LAST" = "$CURR" ]; then
        echo '{"changed": false, "action": "HEARTBEAT_OK"}'
      else
        cat ${path}
        lobster state.set heartbeat_hash "$CURR"
      fi
```

## Solution Categories for Research Briefs

### 1. **Lobster Workflow** — Best for:
- **Multi-step orchestration**: mine→rollup→brief pipeline as one workflow
- **Approval gates**: human-in-the-loop for destructive ops (git push, ticket close, deploy)
- **Caching/dedup**: use `state.get`/`state.set` to cache expensive operations
- **Conditional execution**: skip steps based on prior step's `approved`/`skipped` status
- **Cross-tool coordination**: combine gh, curl, phorge CLI in sequential steps
- **Retry logic** (emulated): multiple steps with condition checks, not built-in

### 2. **Code Patch** — Bug fixes, algorithm changes, new features
### 3. **Config Change** — AGENTS.md/SOUL.md/openclaw.json tweaks
### 4. **Skill Update** — New or improved OpenClaw skills
### 5. **Hybrid** — Lobster workflow + code patch

## What Lobster CANNOT Solve
- **LLM behavior changes**: prompt engineering, model selection — needs config changes
- **Deep algorithmic issues**: clustering quality, embedding similarity — needs code patches
- **Real-time in-session behavior**: Lobster runs as a separate process, not inline
- **Memory/context window issues**: fundamental model limitations
- **Parallel execution**: no fan-out/fan-in support
- **Complex conditional logic**: `when:` only supports `approved`/`skipped` checks
- **Error recovery**: any non-zero exit aborts the workflow

## Portability for MoltPod Customers
Lobster workflows are portable with caveats:
- ✅ YAML files, no compilation
- ✅ Args make them parameterizable (`--args-json '{"path": "/their/path"}'`)
- ✅ Local-first state (no shared server needed)
- ✅ Approval gates work in both interactive and tool mode (resumeToken for async)
- ⚠️ State files may contain paths/secrets — clean before sharing
- ⚠️ Scheduling is external (needs cron/OpenClaw cron, not built into Lobster)
- ⚠️ Arbitrary shell execution — review workflows before running untrusted ones

## Lobster Workflow Checklist (for brief authors)
When recommending a Lobster workflow solution:
- [ ] Filename ends with `.lobster.yaml`
- [ ] Contains `args:` section with sensible defaults
- [ ] Includes approval step for any destructive action
- [ ] Tested locally with `lobster workflows.run <file> --args-json '...'`
- [ ] Condition expressions use only `$step.approved` or `$step.skipped`
- [ ] Complex logic lives in shell commands, not `when:` expressions

## Engine Improvement Opportunities
If product work is in scope:
- Extend `evaluateCondition` for JSONPath/jq predicates (`$step.json.changed`)
- Add `retry:` and `timeout:` at step level
- Add `on_error: skip|continue|abort`
- Add `version:` field to WorkflowFile schema
- Document security practices for `.lobster.yaml` files
