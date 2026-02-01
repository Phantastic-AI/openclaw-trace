# AGENTS.md

Instructions for AI coding agents (Codex, Claude Code, etc.) working on **openclaw-agi**.

---

## Current Work

**Main ticket:** [T151](https://hub.phantastic.ai/T151) — RLM self-improvement: multi‑phase workflow (signals → tickets → research → experiments → fixes)

**Oracle guidance:** The first comment on T145 contains detailed design guidance from the Oracle (GPT-5.2-Pro). Read it before starting — it's substantial but important.

**Subtasks:** Create subtasks under T145 for discrete pieces of work. Use `parent` transaction:
```bash
cat > /home/debian/clawd/home/tmp/subtask.json <<'JSON'
{"title":"Implement chunking strategy","description":"Per Oracle guidance...","priority":80,"parent":"T145"}
JSON
sudo /srv/phorge/phorge/bin/conduit call --local --method maniphest.createtask --as admin --input /home/debian/clawd/home/tmp/subtask.json
```

**Exec plans (ergonomic default):**
- Template: `.agents/template/PLAN.md` (local copy)
- Primary: post the plan in the Phorge task (description or comment) and keep it updated there
- Optional: keep a local working copy in `/home/debian/clawd/home/tmp/plan-<task-id>.md` if drafting; do not rely on `.agents/**` for status

**Project:** `#hal-self-improvement` — https://hub.phantastic.ai/tag/hal-self-improvement/

---

## VPS Environment

| What | Path |
|------|------|
| **Workspace root** | `/home/debian/clawd/` |
| **Project repos** | `/home/debian/clawd/home/Workspace/` |
| **Phorge skill** | `/home/debian/clawd/skills/phorge/` |
| **Socratic tutor skill** | `/home/debian/clawdbot/skills/socratic-tutor/SKILL.md` |

---

## Task Management: Phorge

Use **Phorge** (not local `.agents/` or beads) for task tracking.

### CLI (local conduit)

```bash
# Search task
printf '{"constraints":{"ids":[145]},"limit":1}' \
  | sudo /srv/phorge/phorge/bin/conduit call --local --method maniphest.search --as admin --input -

# Create task
cat > /home/debian/clawd/home/tmp/task.json <<'JSON'
{"title":"My task","description":"Details here","priority":80}
JSON
sudo /srv/phorge/phorge/bin/conduit call --local --method maniphest.createtask --as admin --input /home/debian/clawd/home/tmp/task.json

# Edit task (e.g., close it)
cat > /home/debian/clawd/home/tmp/edit.json <<'JSON'
{"objectIdentifier":"145","transactions":[{"type":"status","value":"resolved"}]}
JSON
sudo /srv/phorge/phorge/bin/conduit call --local --method maniphest.edit --as admin --input /home/debian/clawd/home/tmp/edit.json
```

### Wiki (Phriction)

```bash
# Search wiki (note: no leading slash in path)
printf '{"constraints":{"ancestorPaths":["people/"]},"limit":5}' \
  | sudo /srv/phorge/phorge/bin/conduit call --local --method phriction.document.search --as admin --input -

# Create wiki page (parent must exist)
cat > /home/debian/clawd/home/tmp/wiki.json <<'JSON'
{"slug":"hal/my-page","title":"My Page","content":"Content here"}
JSON
sudo /srv/phorge/phorge/bin/conduit call --local --method phriction.create --as admin --input /home/debian/clawd/home/tmp/wiki.json

# Edit wiki page
cat > /home/debian/clawd/home/tmp/wiki_edit.json <<'JSON'
{"slug":"hal/my-page","content":"Updated content","description":"Edit summary"}
JSON
sudo /srv/phorge/phorge/bin/conduit call --local --method phriction.edit --as admin --input /home/debian/clawd/home/tmp/wiki_edit.json
```

### Web UI

- Tasks: https://hub.phantastic.ai/maniphest/
- Wiki: https://hub.phantastic.ai/w/

### Linking

- Tasks: `[T145](https://hub.phantastic.ai/T145)`
- Wiki: `[hal/page](https://hub.phantastic.ai/w/hal/page/)`

---

## Oracle: Consulting Other AI Models

When stuck, need a second opinion, or reviewing complex code.

### GPT-5.2-Pro (browser, fixed port)

```bash
npx -y @steipete/oracle --engine browser --remote-chrome 127.0.0.1:9223 --model gpt-5.2-pro -p "your prompt"
```

With files:
```bash
npx -y @steipete/oracle --engine browser --remote-chrome 127.0.0.1:9223 --model gpt-5.2-pro \
  --file /path/to/file.py \
  -p "Review this code"
```

**If browser not running yet (one-time setup, let the user know to forward port 5900 via ssh and open localhost VNC):**
```bash
npx -y @steipete/oracle --engine browser --browser-manual-login --browser-keep-browser --browser-port 9223 -p "hello"
# Login, keep window open. All subsequent calls use --remote-chrome 127.0.0.1:9223
```

### Gemini 3 Pro (API, fast, huge context)

```bash
npx -y @steipete/oracle --model gemini-3-pro --file <files> -p "your prompt"
```

**Tips:**
- Use `gemini-3-pro` NOT `gemini-2.5-pro`
- GPT-5.2-Pro requires `--engine browser` + `--remote-chrome`

---

## Workflow

1. **Check for existing Phorge ticket** before starting work
2. **Create exec plan** using `.agents/template/PLAN.md`; post and maintain it in the Phorge ticket (description or comment). Use `/home/debian/clawd/home/tmp/plan-<task-id>.md` only as a draft.
3. **Commit incrementally** with `T<id>` in commit messages
4. **Update ticket** when done (status → resolved)

---

## Rules

1. **Never delete files** without explicit human permission
2. **No destructive git commands** (`reset --hard`, `clean -fd`, `rm -rf`) without approval
3. **Test before declaring done** — run the code, verify it works

---

## Communication Style

- Be blunt + decisive. Lead with the answer.
- Avoid hedging: "maybe", "might", "could", "likely"
- If unsure, say "I don't know" + the fastest way to verify.
- Keep replies terse (<10 lines unless asked for more).
