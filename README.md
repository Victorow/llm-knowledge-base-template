# LLM Knowledge Base

A personal knowledge base that compiles itself from AI coding sessions. It is inspired by Andrej Karpathy's LLM Knowledge Base architecture, but the source material is your own conversations with Claude Code or Codex.

```
kb/daily/       = source code        (raw conversation memories)
Agent backend   = compiler           (extracts structured knowledge)
kb/knowledge/   = executable         (queryable wiki articles)
```

You work normally. Hooks capture sessions, a flush step writes structured daily logs, and compile turns those logs into a markdown wiki.

## Supported Clients

| Surface | Status | How it works |
|---------|--------|--------------|
| Claude Code | Supported | `SessionStart`, `SessionEnd`, and `PreCompact` hooks |
| Codex | Supported | `SessionStart` and `Stop` hooks with `features.codex_hooks = true` |
| Desktop Control Panel | Supported | PySide6 UI, job queue, diagnostics, packaged hook entrypoint |
| macOS/Linux automation | Supported | `scripts/compile-daily.sh` with launchd or systemd |
| Windows automation | Supported | `scripts/compile-daily.ps1` with Task Scheduler |

The transcript parser is provider-neutral: Claude Code JSONL and Codex rollout JSONL are normalized into the same user/assistant turn stream before flushing.

## What's In This Repo

| Path | Purpose |
|------|---------|
| `hooks/session-start.py` | Injects KB index + recent daily log into Claude Code or Codex sessions |
| `hooks/session-end.py` | Captures a transcript and spawns `flush.py`; used by Claude `SessionEnd` and Codex `Stop` |
| `hooks/pre-compact.py` | Claude Code safety hook before compaction |
| `kb_app/` | Importable core package, job queue, hook commands, diagnostics, and UI |
| `scripts/transcripts.py` | Normalizes Claude Code and Codex JSONL transcripts |
| `scripts/agent_backend.py` | Selects Claude Agent SDK or Codex CLI for LLM execution |
| `scripts/flush.py` | Summarizes captured context into `kb/daily/YYYY-MM-DD.md` |
| `scripts/compile.py` | Compiles daily logs into `kb/knowledge/` articles |
| `scripts/query.py` | Asks the wiki a question, optionally filing the answer back |
| `scripts/lint.py` | Structural and semantic health checks |
| `scripts/compile-daily.sh` | macOS/Linux daily compile wrapper |
| `scripts/compile-daily.ps1` | Windows daily compile wrapper |
| `scripts/register-windows-task.ps1` | Registers the Windows scheduled task |
| `scripts/build-windows.ps1` | Builds PyInstaller app and optional Inno Setup installer |
| `scripts/build-linux.sh` | Builds the Linux PyInstaller app directory |
| `scripts/smoke-packaged.py` | Verifies packaged/module entrypoints |
| `packaging/` | PyInstaller, Inno Setup, and Linux desktop installer files |
| `.claude/*.example.json` | Claude Code hook templates |
| `.codex/*.example.*` | Codex hook/config templates |
| `CONTEXT.md` | Project language and boundaries |
| `AGENTS.md` | Schema and compiler specification |

## Prerequisites

- Python 3.12+ and `uv`
- One AI client:
  - Claude Code installed and authenticated, or
  - Codex CLI/App installed and authenticated
- One agent backend:
  - default: Claude Agent SDK credentials from Claude Code
  - Codex: set `KB_AGENT_BACKEND=codex`

Install dependencies:

```bash
uv sync
```

On Windows PowerShell:

```powershell
uv sync
```

## Desktop Control Panel

The desktop app is a control panel over the existing KB pipeline. It does not replace Claude Code or Codex, and it does not bundle either client. It exposes profiles, hook setup, daily logs, knowledge browsing, compile/query/lint operations, job history, scheduler settings, and diagnostics through a local PySide6 UI.

Run from source:

```bash
uv run python -m kb_app ui
```

Run command-mode operations through the same entrypoint:

```bash
uv run python -m kb_app --help
uv run python -m kb_app compile --dry-run
uv run python -m kb_app lint --structural-only
uv run python -m kb_app diagnostics export --output reports
uv run python -m kb_app hook session-start
```

The app separates:

- install directory: packaged executable and libraries
- app data: SQLite DB, UI config, job history, logs, diagnostics
- KB data: `AGENTS.md`, `CONTEXT.md`, `kb/daily`, `kb/knowledge`

Cloud sync is not implemented in V1. You can put KB data inside an externally synced folder, but the app does not manage cloud login, encryption, conflict resolution, or remote storage.

## Agent Backend

The client that produced the transcript and the backend that performs LLM work are deliberately separate.

Default backend:

```bash
uv run python scripts/query.py "What auth patterns do I use?"
```

Codex backend:

```bash
KB_AGENT_BACKEND=codex uv run python scripts/query.py "What auth patterns do I use?"
```

Windows PowerShell:

```powershell
$env:KB_AGENT_BACKEND = "codex"
uv run python scripts/query.py "What auth patterns do I use?"
```

Valid values are `claude` and `codex`. The Codex backend runs `codex exec` non-interactively and sends prompts through stdin. Recursive hook execution is prevented by `KB_INVOKED_BY`, which makes the capture hooks exit immediately inside backend child processes.

By default the Codex backend passes `-m gpt-5.3-codex` because older Codex CLI builds can fail when a user config points at a newer model. Override it when your local Codex supports a different model:

```bash
KB_CODEX_MODEL=gpt-5.5 KB_AGENT_BACKEND=codex uv run python scripts/query.py "What do I know?"
```

PowerShell:

```powershell
$env:KB_CODEX_MODEL = "gpt-5.5"
$env:KB_AGENT_BACKEND = "codex"
uv run python scripts\query.py "What do I know?"
```

## Claude Code Setup

Copy or merge the hook config into `~/.claude/settings.json`.

macOS/Linux template:

```bash
cat .claude/settings.example.json
```

Windows template:

```powershell
Get-Content .claude\settings.windows.example.json
```

Replace `/ABSOLUTE/PATH/TO/llm-knowledge-base` or `C:\ABSOLUTE\PATH\TO\llm-knowledge-base` with your real clone path. If you already have hooks, merge arrays instead of overwriting them.

## Codex Setup

Codex hooks require the feature flag:

```toml
[features]
codex_hooks = true
```

You can copy that from `.codex/config.example.toml` into either:

- `~/.codex/config.toml` for user-wide hooks, or
- `<repo>/.codex/config.toml` for project-local hooks.

Then copy one hooks template:

macOS/Linux:

```bash
cp .codex/hooks.example.json .codex/hooks.json
```

Windows:

```powershell
Copy-Item .codex\hooks.windows.example.json .codex\hooks.json
```

Replace the placeholder paths with your absolute project path. Project-local hooks only load when the project `.codex/` layer is trusted.

Codex uses:

- `SessionStart` to inject the KB index and recent daily log.
- `Stop` to capture the transcript and spawn `flush.py`.

## Daily Compile Automation

### macOS Launchd

Copy the plist template and replace the placeholder path:

```bash
cp scripts/com.user.kb-daily-compile.plist.example \
   ~/Library/LaunchAgents/com.user.kb-daily-compile.plist

sed -i '' "s|/ABSOLUTE/PATH/TO/llm-knowledge-base|$PWD|g" \
   ~/Library/LaunchAgents/com.user.kb-daily-compile.plist

launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.kb-daily-compile.plist
launchctl kickstart gui/$(id -u)/com.user.kb-daily-compile
tail -f scripts/compile.log
```

### Linux Systemd

Create `~/.config/systemd/user/kb-compile.service`:

```ini
[Unit]
Description=Compile LLM knowledge base

[Service]
Type=oneshot
ExecStart=%h/llm-knowledge-base/scripts/compile-daily.sh
```

Create `~/.config/systemd/user/kb-compile.timer`:

```ini
[Unit]
Description=Daily KB compile at 17:00

[Timer]
OnCalendar=*-*-* 17:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable it:

```bash
systemctl --user daemon-reload
systemctl --user enable --now kb-compile.timer
```

### Windows Task Scheduler

Dry-run the wrapper:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\compile-daily.ps1 -DryRun
```

Register the daily task:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\register-windows-task.ps1 -At 17:00
```

Verify or run it manually:

```powershell
Get-ScheduledTask -TaskName LLMKnowledgeBaseDailyCompile
Start-ScheduledTask -TaskName LLMKnowledgeBaseDailyCompile
Get-Content scripts\compile.log -Tail 80
```

## Manual Commands

```bash
# Compile only logs that changed since last compile
uv run python scripts/compile.py

# Force recompile everything
uv run python scripts/compile.py --all

# Compile a specific log
uv run python scripts/compile.py --file kb/daily/2026-04-29.md

# Dry-run
uv run python scripts/compile.py --dry-run

# Ask the knowledge base a question
uv run python scripts/query.py "How should I handle auth redirects?"

# File the answer back into kb/knowledge/qa/
uv run python scripts/query.py "How does X work?" --file-back

# Lint the wiki
uv run python scripts/lint.py

# Free structural lint only
uv run python scripts/lint.py --structural-only
```

PowerShell uses the same commands:

```powershell
uv run python scripts\compile.py --dry-run
uv run python scripts\query.py "How should I handle auth redirects?"
uv run python scripts\lint.py --structural-only
```

## Packaging

Windows build:

```powershell
uv run pyinstaller packaging\pyinstaller\llm-knowledge-base.spec --noconfirm --clean
uv run python scripts\smoke-packaged.py --exe dist\LLMKnowledgeBase\LLMKnowledgeBase.exe
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build-windows.ps1
```

`scripts/build-windows.ps1` uses Inno Setup when `ISCC.exe` is available. The installer is user-level (`%LOCALAPPDATA%\Programs\LLM Knowledge Base`) and does not modify Claude/Codex hooks during install; hook setup belongs to the app wizard/config flow.

Linux build:

```bash
sh scripts/build-linux.sh
sh packaging/linux/install.sh dist/LLMKnowledgeBase
```

The Linux installer writes to user directories (`~/Applications`, `~/.local/bin`, `~/.local/share/applications`) and does not require `sudo`.

## Daily Workflow

1. Start a Claude Code or Codex session.
2. `session-start.py` injects the current KB index and recent daily log.
3. Work normally.
4. The end hook captures the transcript and starts `flush.py` in the background.
5. `flush.py` writes structured memory to `kb/daily/YYYY-MM-DD.md`.
6. The daily automation runs `compile.py`, creating or updating articles in `kb/knowledge/`.

## State And Logs

Runtime files are gitignored:

- `scripts/state.json`
- `scripts/last-flush.json`
- `scripts/flush.log`
- `scripts/compile.log`
- `reports/`

## Costs

Costs depend on the selected backend and wiki size.

| Operation | Typical cost |
|-----------|--------------|
| Flush | Small summary request |
| Compile | Larger extraction/editing request |
| Query | Depends on wiki size |
| Structural lint | Free |

Claude backend records SDK-reported cost in `scripts/state.json`. Codex CLI does not currently expose cost through this wrapper, so the state file records `0.0` for those runs.

## Architecture Deep Dive

Read `AGENTS.md` for the daily-log schema, article format, wikilink conventions, hook details, and compiler behavior. Read `CONTEXT.md` for the project vocabulary and boundary decisions.

## License

MIT.
