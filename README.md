# LLM Knowledge Base

A personal knowledge base that compiles itself from your Claude Code conversations. Inspired by [Andrej Karpathy's LLM Knowledge Base](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — but instead of ingesting external articles, it ingests **your own AI sessions**.

```
daily/          = source code        (raw conversation logs)
LLM             = compiler           (extracts structured knowledge)
knowledge/      = executable         (queryable wiki articles)
```

You don't manually organize anything. You have conversations, hooks capture them, and a scheduled compile turns them into a wiki you can query.

---

## What's in this repo

| Path | Purpose |
|------|---------|
| `hooks/session-start.py` | Injects KB index + recent daily log into every new Claude Code session |
| `hooks/session-end.py`   | Captures transcript when a session ends and spawns `flush.py` |
| `hooks/pre-compact.py`   | Same as `session-end`, but fires before Claude's auto-compaction |
| `scripts/flush.py`       | Uses Claude Agent SDK to summarize a transcript into a daily-log entry |
| `scripts/compile.py`     | Reads daily logs and produces structured wiki articles in `kb/knowledge/` |
| `scripts/query.py`       | Asks the wiki a question (index-guided retrieval, no embeddings) |
| `scripts/lint.py`        | Health checks: broken links, orphans, contradictions, etc. |
| `scripts/compile-daily.sh` | Wrapper script — used by launchd for the daily 17:00 compile |
| `AGENTS.md`              | Schema for daily logs and wiki articles (read by the compiler) |
| `kb/`                    | Your knowledge — `daily/` raw + `knowledge/` compiled |
| `.claude/settings.example.json` | Hook config to copy into `~/.claude/settings.json` |

---

## Prerequisites

- macOS or Linux (Windows works for the scripts; launchd automation is macOS-specific)
- [Claude Code](https://claude.com/claude-code) installed and authenticated
- [`uv`](https://docs.astral.sh/uv/) — Python project manager
- Python 3.12+

```bash
# install uv (macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/<YOUR-USER>/llm-knowledge-base.git ~/llm-knowledge-base
cd ~/llm-knowledge-base
uv sync
```

### 2. Wire up the Claude Code hooks

Copy the example settings and replace the placeholder paths with your absolute clone path:

```bash
# back up your current settings
cp ~/.claude/settings.json ~/.claude/settings.backup.json 2>/dev/null || true

# merge our hooks into your settings (see notes below)
cat .claude/settings.example.json
```

Open `~/.claude/settings.json` and add the three hook entries (`SessionStart`, `SessionEnd`, `PreCompact`) from `.claude/settings.example.json`. Replace `/ABSOLUTE/PATH/TO/llm-knowledge-base` with your actual clone path (e.g. `/Users/yourname/llm-knowledge-base`).

If your `~/.claude/settings.json` already has hooks, **merge** the arrays — don't overwrite. Each hook section accepts a list, so you can append.

### 3. Verify

Open a new Claude Code session and check that:
- The session opens with a "Knowledge Base Index" + "Recent Daily Log" block (means `session-start.py` ran)
- After ending the session, a new file appears in `kb/daily/YYYY-MM-DD.md` (means `session-end.py` → `flush.py` ran)

If something fails, tail `scripts/flush.log`.

---

## Daily workflow

You don't run anything manually during the day. Here's what happens automatically:

1. **You start a Claude Code session.** `session-start.py` injects the wiki index so Claude knows what you've already learned.
2. **You work normally.**
3. **Session ends (or context is auto-compacted).** `session-end.py` / `pre-compact.py` extract the transcript and spawn `flush.py` in the background.
4. **`flush.py` calls Claude Agent SDK** to summarize the conversation into structured notes and appends them to `kb/daily/YYYY-MM-DD.md`.
5. **At 17:00, launchd runs `compile-daily.sh`** (see next section), which reads new daily logs and produces wiki articles in `kb/knowledge/concepts/` and `kb/knowledge/connections/`.

---

## Automating end-of-day compile (macOS launchd)

The daily compile runs once at 17:00 via launchd. This replaces an older opportunistic trigger that only fired if a session happened to end after 17:00 — fragile, often missed days.

### One-time setup

```bash
cd ~/llm-knowledge-base

# 1) Copy the plist template into your LaunchAgents dir
cp scripts/com.user.kb-daily-compile.plist.example \
   ~/Library/LaunchAgents/com.user.kb-daily-compile.plist

# 2) Replace the placeholder path with your real clone path
sed -i '' "s|/ABSOLUTE/PATH/TO/llm-knowledge-base|$PWD|g" \
   ~/Library/LaunchAgents/com.user.kb-daily-compile.plist

# 3) Load it (requires user-session bootstrap)
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.kb-daily-compile.plist

# 4) (Optional) Run it once right now to verify
launchctl kickstart gui/$(id -u)/com.user.kb-daily-compile
tail -f scripts/compile.log
```

### Verify it's scheduled

```bash
launchctl print gui/$(id -u)/com.user.kb-daily-compile | head -20
```

Look for a `state = waiting` line — the agent is loaded and waiting for 17:00.

### Change the time

Edit `~/Library/LaunchAgents/com.user.kb-daily-compile.plist`, change the `Hour`/`Minute` values inside `StartCalendarInterval`, then reload:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.user.kb-daily-compile.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.kb-daily-compile.plist
```

### Disable / uninstall

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.user.kb-daily-compile.plist
rm ~/Library/LaunchAgents/com.user.kb-daily-compile.plist
```

### Notes

- launchd **doesn't** wake your Mac. If the laptop is asleep at 17:00, the job runs as soon as it wakes (this is the default behavior — launchd queues missed `StartCalendarInterval` runs).
- launchd has a minimal environment; that's why `compile-daily.sh` exports `PATH` itself. If `uv` isn't on the path the wrapper sets, edit the script.
- All output (stdout + stderr) goes to `scripts/compile.log`. That's where you debug.

### Linux (systemd) equivalent

If you're on Linux, use a systemd user timer instead. Create `~/.config/systemd/user/kb-compile.service`:

```ini
[Unit]
Description=Compile LLM knowledge base

[Service]
Type=oneshot
ExecStart=%h/llm-knowledge-base/scripts/compile-daily.sh
```

And `~/.config/systemd/user/kb-compile.timer`:

```ini
[Unit]
Description=Daily KB compile at 17:00

[Timer]
OnCalendar=*-*-* 17:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now kb-compile.timer
```

---

## Manual commands

```bash
# Compile only logs that changed since last compile
uv run python scripts/compile.py

# Force recompile everything
uv run python scripts/compile.py --all

# Compile a specific log
uv run python scripts/compile.py --file kb/daily/2026-04-29.md

# Dry-run (show what would compile without spending tokens)
uv run python scripts/compile.py --dry-run

# Ask the knowledge base a question
uv run python scripts/query.py "How should I handle auth redirects?"

# Same, but file the answer back as a Q&A article
uv run python scripts/query.py "How does X work?" --file-back

# Lint the wiki (broken links, orphans, contradictions...)
uv run python scripts/lint.py

# Lint without LLM checks (free, instant)
uv run python scripts/lint.py --structural-only
```

---

## Costs

Roughly:
- **Flush** (per session): ~$0.01–0.05 — small Haiku-class summary
- **Compile** (per daily log): ~$0.10–0.40 — full Sonnet-class extraction
- **Query**: ~$0.05–0.20 — depends on wiki size
- **Lint** (with contradictions check): ~$0.05–0.20

Token usage is tracked in `scripts/state.json` (`total_cost`). Use `--structural-only` and `--dry-run` to control spend.

---

## Architecture deep-dive

See `AGENTS.md` for the full schema (daily-log format, article structure, wikilink conventions) — that file is also what the LLM compiler reads as its spec.

---

## License

MIT — do whatever you want, but no warranty.
