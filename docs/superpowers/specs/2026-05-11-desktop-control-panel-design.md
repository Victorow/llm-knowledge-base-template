# Desktop Control Panel Design

## Objective

Build a cross-platform desktop control panel for the personal LLM knowledge base. The app must expose the existing capture, flush, compile, query, lint, scheduling, hook setup, diagnostics, and background execution workflows through a simple operational UI on Windows and mainstream Linux desktop distributions.

The V1 is a control plane over the current pipeline, not a rewrite of the knowledge system. The existing `kb/daily` -> `kb/knowledge` compiler model remains the domain core.

## Approved Scope

Included in V1:

- Background tray application running in the user session.
- PySide6/Qt desktop UI.
- Persistent job queue for long-running operations.
- First-run setup wizard.
- Multiple KB profiles, with one active capture target.
- Hook installation, validation, repair, removal, backup, and rollback.
- Claude Code and Codex support through external client detection.
- Manual memory entry into daily logs.
- Daily log browser.
- Knowledge article browser/search/open-external flow.
- Compile, query, file-back query, lint, and diagnostics from the UI.
- Internal daily compile scheduler.
- User-level Windows installer with PyInstaller + Inno Setup.
- Linux package/archive with desktop entry and autostart support.
- Packaged runtime that does not require `uv` to be installed.

Explicitly excluded from V1:

- Direct editor for `kb/knowledge`.
- Cloud sync, cloud login, remote storage, conflict resolution, or encryption service.
- Bundling Claude Code or Codex.
- System service/daemon installed with elevated privileges.
- Hard support guarantees for Alpine, NixOS, minimal/headless Linux, or non-glibc systems.
- Replacing AI-client hooks as the source of automatic capture.

## Core Architecture

Use a core-first modular Python package:

```text
kb_app/
  __main__.py
  core/
    paths.py
    operations.py
    agent_backend.py
    transcripts.py
    config_merge.py
  profiles/
    store.py
  jobs/
    queue.py
    runner.py
    logs.py
  agent/
    service.py
    scheduler.py
  hooks/
    commands.py
  ui/
    app.py
    tray.py
    windows/
  packaging/
    pyinstaller/
    inno/
    linux/
```

Existing scripts become thin wrappers around `kb_app.core` so CLI compatibility is preserved while the packaged desktop app uses the same implementation.

The packaged executable exposes subcommands:

```bash
llm-knowledge-base ui
llm-knowledge-base agent
llm-knowledge-base hook session-start
llm-knowledge-base hook session-end
llm-knowledge-base hook pre-compact
llm-knowledge-base compile
llm-knowledge-base query
llm-knowledge-base lint
llm-knowledge-base diagnostics export
```

Windows uses the same executable:

```powershell
LLMKnowledgeBase.exe ui
LLMKnowledgeBase.exe agent
LLMKnowledgeBase.exe hook session-start
```

## Data And State

The install directory is treated as read-only at runtime.

Windows install path:

```text
%LOCALAPPDATA%\Programs\LLM Knowledge Base\
```

Linux install path:

```text
~/Applications/llm-knowledge-base/
```

or another user-selected/app-managed location.

Windows app data:

```text
%APPDATA%\LLM Knowledge Base\
  app.db
  config.toml
  logs/
  job-logs/
  backups/
  diagnostics/
```

Linux app data:

```text
~/.config/llm-knowledge-base/config.toml
~/.local/state/llm-knowledge-base/app.db
~/.local/state/llm-knowledge-base/logs/
~/.local/state/llm-knowledge-base/job-logs/
~/.local/state/llm-knowledge-base/backups/
~/.local/state/llm-knowledge-base/diagnostics/
```

KB data is user-owned and profile-specific:

```text
<kb-root>/
  AGENTS.md
  CONTEXT.md
  kb/
    daily/
    knowledge/
      index.md
      log.md
      concepts/
      connections/
      qa/
```

The desktop app must not assume the repository root is the active KB root. Every operation receives explicit context:

- app context
- active KB profile
- operation options

The new architecture must remove `ROOT_DIR = Path(__file__).parents[...]` as the source of truth for packaged flows.

## SQLite Schema

The app database owns operational state:

- `kb_profiles`: profile name, KB root path, backend preference, active flag, timestamps.
- `app_settings`: global UI, tray, scheduler, and startup settings.
- `jobs`: durable job records with status, payload, result, error, backend, and timestamps.
- `job_events`: append-only job lifecycle log.
- `job_artifacts`: output files, reports, diagnostics, or snapshots produced by jobs.
- `hook_installations`: detected/installed hook state per AI client and config path.
- `config_backups`: backup metadata for hook/config changes.
- `scheduler_rules`: daily compile settings and missed-run policy.
- `diagnostic_exports`: generated support bundles and redaction metadata.

## Job Queue

All long-running or mutating actions run through the persistent job queue.

Job types:

- `flush_test`
- `compile_changed`
- `compile_all`
- `compile_file`
- `query`
- `query_file_back`
- `lint_structural`
- `lint_full`
- `install_hooks`
- `repair_hooks`
- `remove_hooks`
- `install_autostart`
- `remove_autostart`
- `configure_daily_schedule`
- `manual_memory`
- `diagnostics_export`
- `backend_smoke_test`

Job states:

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancel_requested`
- `cancelled`

Each job stores:

- id
- profile id
- job type
- status
- priority
- backend
- command summary
- payload JSON
- result JSON
- error message
- stdout/stderr path or inline excerpt
- mutation snapshot reference
- created, started, finished timestamps

The background agent executes queued jobs one at a time by default. Future concurrency can be added for read-only jobs, but V1 should optimize for correctness and transparent state.

## Cancellation And Recovery

Read-only jobs can be cancelled by terminating their child process and marking the job `cancelled`.

Mutable jobs must use a safer flow:

1. Capture a mutation snapshot or backup before touching files.
2. Mark the job `cancel_requested` when the user cancels.
3. Let cooperative code stop at defined checkpoints.
4. If a child process must be killed, run post-cancel health checks.
5. Restore from snapshot where the operation supports rollback.
6. Record recovery status in `job_events`.

Hook/config operations require backup + rollback. Knowledge compile operations require at least pre-operation snapshots of affected files when run through the desktop app.

## Background Agent And Scheduler

The background agent is a user-session process, usually launched by the tray app. It is not a privileged system service.

Responsibilities:

- Own the job queue runner.
- Execute scheduled daily compile jobs.
- Maintain tray status.
- Receive job requests from the UI.
- Keep durable logs.
- Detect missed scheduled runs.

Scheduler settings:

- `daily_compile_enabled`
- `daily_compile_time`
- `missed_run_policy = run_when_agent_starts`

The internal scheduler is the default cross-platform path. OS schedulers can remain as compatibility helpers, but the V1 UI should not depend on cron, launchd, systemd timers, or Task Scheduler for normal operation.

## UI Structure

The UI should feel like a compact operational control panel, not a marketing page.

Global layout:

- Top bar: active KB profile, selected backend, agent status, last job status.
- Sidebar: main navigation.
- Main pane: task-specific controls and state.
- Bottom bar: current status, last error, link to logs.

Pages:

- Dashboard: health summary, active profile, last flush, last compile, last lint, latest errors, quick actions.
- Setup: first-run wizard and environment validation.
- Profiles: create/select/validate KB profiles; mark active capture profile.
- Hooks: Claude Code/Codex detection, installed hook status, install/repair/remove, backup history.
- Daily Logs: browse daily files, add manual memory, trigger compile for selected log.
- Knowledge: browse/search index, open article externally, run query, run file-back query.
- Operations: compile changed/all/file, lint structural/full, backend smoke test.
- Jobs: durable queue, running job, history, logs, retry, cancel.
- Settings: backend defaults, scheduler, startup/tray behavior, paths.
- Diagnostics: export redacted support bundle and view environment status.

Knowledge articles are viewable in V1 but not directly editable inside the app. Editing compiled output manually fights the compiler model and creates avoidable data integrity problems.

## First-Run Wizard

Wizard steps:

1. Welcome: explain local KB control panel and privacy boundary.
2. KB Profile: create/select KB root, validate required structure, initialize missing directories/files if requested.
3. Agent Backend: detect Claude Code and Codex, choose default backend, run smoke test.
4. Hooks: show existing config, install/merge hooks, create backup, validate result.
5. Background: enable tray/background autostart and daily compile schedule.
6. Finish: show final health summary and next recommended action.

The wizard must make setup reversible. It should never silently overwrite user config.

## Hook Model

Hooks call the packaged app entrypoint:

Windows:

```powershell
"%LOCALAPPDATA%\Programs\LLM Knowledge Base\LLMKnowledgeBase.exe" hook session-start
"%LOCALAPPDATA%\Programs\LLM Knowledge Base\LLMKnowledgeBase.exe" hook session-end
"%LOCALAPPDATA%\Programs\LLM Knowledge Base\LLMKnowledgeBase.exe" hook pre-compact
```

Linux:

```bash
llm-knowledge-base hook session-start
llm-knowledge-base hook session-end
llm-knowledge-base hook pre-compact
```

Hooks must:

- Read JSON input from stdin when provided by the AI client.
- Resolve the active KB profile from app data.
- Preserve recursion guards.
- Spawn flush work quickly without blocking the AI client lifecycle.
- Produce valid hook JSON output for session-start context injection.
- Log failures to app logs without exposing secrets.

Codex and Claude Code hook formats remain provider-specific, but transcript parsing stays centralized in `kb_app.core.transcripts`.

## Hook Config Safety

Hook install/repair must use structured config merge:

1. Read existing config.
2. Parse as JSON/TOML with a real parser.
3. Detect existing KB hook entries.
4. Create timestamped backup.
5. Apply minimal merge.
6. Validate syntax.
7. Run hook smoke test.
8. Roll back automatically on failure.
9. Record backup and result in SQLite.

Blind overwrite is not acceptable.

## External Client Detection

The app does not bundle Claude Code or Codex.

It detects:

- CLI executable presence.
- Auth/config presence where safely detectable.
- Version output where available.
- Whether the backend can complete a small smoke test.

The UI should clearly distinguish:

- not installed
- installed but not authenticated/configured
- installed and ready
- installed but incompatible

## Packaging

Packaging files:

```text
packaging/
  pyinstaller/
    llm-knowledge-base.spec
  inno/
    llm-knowledge-base.iss
  linux/
    install.sh
    uninstall.sh
    llm-knowledge-base.desktop.template
scripts/
  build-windows.ps1
  build-linux.sh
  smoke-packaged.py
```

Windows:

- Build with PyInstaller.
- Install with Inno Setup.
- User-level installation by default.
- No admin requirement.
- No hook modification during installer execution.
- Start Menu shortcut.
- Optional startup entry controlled by wizard/settings.
- Uninstaller removes app files and startup entry, but does not delete KB data by default.

Linux:

- Build PyInstaller executable on mainstream glibc Linux.
- Distribute tar.gz or app directory.
- Provide installer script for desktop entry and optional autostart.
- Support GNOME/KDE/XFCE-style XDG environments.
- Continue operating without tray icon when tray integration is unavailable.

The packaged runtime must include Python dependencies needed by the app. Users should not need `uv` to run the installed desktop app.

## Security And Privacy

Security constraints:

- No API keys or auth tokens stored in cleartext app DB.
- No full transcripts in diagnostics by default.
- No daily logs or knowledge articles in diagnostics by default.
- No hook config overwrite without backup.
- No mutation without a durable job record.
- No privileged installer behavior in V1.
- No cloud sync in V1.

Diagnostics redaction must mask likely secrets, including:

- `api_key`
- `token`
- `auth`
- `cookie`
- `session`
- `password`
- `secret`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- Claude/Codex credential paths or tokens

Diagnostics export may include:

- app version
- OS/platform info
- Python/runtime info
- install path
- app data path
- redacted config
- profile metadata
- backend detection status
- recent job history
- redacted job logs
- hook config status
- lint report metadata
- smoke test result

Diagnostics export must exclude by default:

- raw credentials
- full conversation transcripts
- full `kb/daily`
- full `kb/knowledge`

## Documentation Updates

Update public docs to reflect the desktop app:

- `README.md`: add desktop app overview, install path, setup flow, CLI compatibility, backend requirements.
- `AGENTS.md`: keep schema/domain behavior authoritative and document the packaged hook entrypoints.
- `CONTEXT.md`: maintain vocabulary for app, profiles, jobs, hooks, app data, and KB data.
- ADRs: keep already-approved architectural decisions captured and concise.

## Phased Delivery

Phase 1: Core refactor

- Introduce `kb_app` package.
- Move shared logic from scripts into importable modules.
- Preserve existing CLI script behavior.
- Add app context/profile path resolution.
- Add tests around transcript parsing, path resolution, backend invocation wrappers, and config merge.

Phase 2: Job system and background agent

- Add SQLite store.
- Implement job queue, job runner, event log, and cancellation model.
- Add internal scheduler.
- Add CLI subcommands for job execution and agent lifecycle.

Phase 3: Desktop shell

- Add PySide6 app shell.
- Implement tray integration and fallback.
- Build dashboard, jobs page, operations page, settings base.

Phase 4: Setup, hooks, and profiles

- Implement first-run wizard.
- Implement safe hook install/repair/remove.
- Add profile management.
- Add backend detection and smoke tests.

Phase 5: KB UX and diagnostics

- Implement daily log browser.
- Implement manual memory.
- Implement knowledge browser/query/file-back.
- Implement diagnostics export with redaction.

Phase 6: Packaging

- Add PyInstaller spec.
- Add Inno Setup installer.
- Add Linux installer/archive scripts.
- Add packaged smoke tests.

## Acceptance Criteria

Functional:

- User can create/select a KB profile from the UI.
- User can configure Claude Code and Codex hooks from the UI.
- User can run compile/query/lint/file-back/manual-memory from the UI.
- User can inspect job status, logs, failures, retries, and cancellation.
- User can enable background startup and daily compile from the UI.
- Hooks can call the packaged executable without requiring the source repo or `uv`.
- Existing CLI workflows continue working.

Cross-platform:

- Windows app installs with Inno Setup without admin.
- Windows app starts UI/tray/background agent successfully.
- Windows hooks execute through the packaged executable.
- Linux app starts UI/tray/background agent on mainstream glibc desktop environments.
- Linux app degrades cleanly when tray support is unavailable.

Safety:

- Hook installation creates backups and can roll back on failure.
- Config merge preserves unrelated user config.
- Diagnostics are redacted and exclude full private KB content by default.
- Mutable jobs are recorded durably before execution.

Verification:

- Unit tests cover core operations, config merge, transcript parsing, job state transitions, and redaction.
- Integration tests cover hook command smoke tests and profile path resolution.
- Packaged smoke test validates executable subcommands, app startup, hook startup output, and basic operation dispatch.
- Manual UI smoke test covers wizard, dashboard, job run, cancellation, diagnostics export, and hook status.

