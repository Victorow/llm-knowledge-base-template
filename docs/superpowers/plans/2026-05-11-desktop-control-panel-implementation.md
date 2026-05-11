# Desktop Control Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows/Linux desktop control panel and background runner for the existing personal LLM knowledge base pipeline.

**Architecture:** Introduce an importable `kb_app` package that owns paths, profile state, operations, job queue, hook commands, diagnostics, and UI. Existing `scripts/*.py` and `hooks/*.py` remain as compatibility wrappers. PySide6 is used for the UI when installed; the packaged app uses the same command entrypoint for UI, agent, hooks, and operations.

**Tech Stack:** Python 3.12+, SQLite, PySide6, PyInstaller, Inno Setup, pytest/unittest-compatible tests, standard-library TOML via `tomllib` for reads and a small writer for app config.

---

## File Map

- Create `kb_app/__init__.py`: package metadata.
- Create `kb_app/__main__.py`: single executable CLI entrypoint.
- Create `kb_app/core/paths.py`: app-data, install, and KB-root path resolution.
- Create `kb_app/core/wiki.py`: KB filesystem helpers independent of repo root.
- Create `kb_app/core/transcripts.py`: moved canonical transcript parser.
- Create `kb_app/core/agent_backend.py`: moved backend abstraction.
- Create `kb_app/core/operations.py`: compile/query/lint/manual-memory orchestration APIs.
- Create `kb_app/core/config_merge.py`: safe JSON/TOML hook config backup/merge/rollback.
- Create `kb_app/profiles/store.py`: SQLite profile and settings store.
- Create `kb_app/jobs/queue.py`: durable job queue models and state transitions.
- Create `kb_app/jobs/runner.py`: executes queued jobs with logs and cancellation.
- Create `kb_app/agent/service.py`: background worker loop and scheduler.
- Create `kb_app/hooks/commands.py`: packaged hook subcommands.
- Create `kb_app/diagnostics/redaction.py`: secret redaction.
- Create `kb_app/diagnostics/export.py`: redacted support bundle.
- Create `kb_app/ui/app.py`: PySide6 control panel.
- Create `kb_app/ui/tray.py`: tray integration with fallback.
- Create `packaging/pyinstaller/llm-knowledge-base.spec`: PyInstaller config.
- Create `packaging/inno/llm-knowledge-base.iss`: Inno Setup installer.
- Create `packaging/linux/install.sh`: user-level Linux installer.
- Create `packaging/linux/uninstall.sh`: user-level Linux uninstaller.
- Create `packaging/linux/llm-knowledge-base.desktop.template`: desktop entry.
- Create `scripts/build-windows.ps1`: Windows build wrapper.
- Create `scripts/build-linux.sh`: Linux build wrapper.
- Create `scripts/smoke-packaged.py`: packaged executable smoke tests.
- Modify `scripts/compile.py`, `scripts/query.py`, `scripts/lint.py`, `scripts/flush.py`: compatibility wrappers using `kb_app`.
- Modify `scripts/transcripts.py`, `scripts/agent_backend.py`: wrappers re-exporting `kb_app.core`.
- Modify `hooks/session-start.py`, `hooks/session-end.py`, `hooks/pre-compact.py`: wrappers using packaged hook command implementation.
- Modify `pyproject.toml`: add PySide6/PyInstaller optional dependencies and package metadata.
- Modify `README.md`, `AGENTS.md`, `CONTEXT.md`: document desktop app flow and packaged hooks.
- Add tests under `tests/` for every core module and smoke path.

---

## Phase 1: Core Package And Path Model

### Task 1.1: Path Context

**Files:**
- Create: `kb_app/core/paths.py`
- Test: `tests/test_paths.py`

- [ ] Write tests for Windows/Linux app-data path resolution, KB root validation, and derived KB paths.
- [ ] Run `python -m pytest tests/test_paths.py -q` and confirm tests fail because `kb_app.core.paths` does not exist.
- [ ] Implement `AppPaths`, `KbPaths`, `resolve_app_paths()`, `resolve_kb_paths()`, and `validate_kb_root()`.
- [ ] Run `python -m pytest tests/test_paths.py -q` and confirm pass.

### Task 1.2: Wiki Helpers

**Files:**
- Create: `kb_app/core/wiki.py`
- Test: `tests/test_wiki.py`

- [ ] Write tests for state load/save, index fallback, article listing, daily log listing, wikilink extraction, inbound link count, and slugify.
- [ ] Run `python -m pytest tests/test_wiki.py -q` and confirm fail.
- [ ] Move path-independent helper logic from `scripts/utils.py` into `kb_app/core/wiki.py`.
- [ ] Run `python -m pytest tests/test_wiki.py -q` and confirm pass.

### Task 1.3: Transcript And Backend Compatibility

**Files:**
- Create: `kb_app/core/transcripts.py`
- Create: `kb_app/core/agent_backend.py`
- Modify: `scripts/transcripts.py`
- Modify: `scripts/agent_backend.py`
- Test: `tests/test_transcripts.py`
- Test: `tests/test_agent_backend.py`

- [ ] Update tests to import from `kb_app.core.transcripts` and `kb_app.core.agent_backend`.
- [ ] Run transcript/backend tests and confirm wrapper imports fail before implementation.
- [ ] Move existing implementations into `kb_app/core/`.
- [ ] Leave `scripts/transcripts.py` and `scripts/agent_backend.py` as compatibility re-export wrappers.
- [ ] Run transcript/backend tests and confirm pass.

### Task 1.4: Operation APIs

**Files:**
- Create: `kb_app/core/operations.py`
- Modify: `scripts/compile.py`
- Modify: `scripts/query.py`
- Modify: `scripts/lint.py`
- Modify: `scripts/flush.py`
- Test: `tests/test_operations.py`

- [ ] Write tests for dry-run compile selection, query state update with fake backend, structural lint report generation, and manual memory append.
- [ ] Run `python -m pytest tests/test_operations.py -q` and confirm fail.
- [ ] Implement operation functions with explicit `KbPaths`.
- [ ] Refactor CLI scripts into thin wrappers.
- [ ] Run operation tests and existing script tests.

**Phase 1 validation:**

- [ ] Run `python -m pytest tests/test_paths.py tests/test_wiki.py tests/test_transcripts.py tests/test_agent_backend.py tests/test_operations.py -q`.
- [ ] Run `python scripts/compile.py --dry-run`.
- [ ] Run `python scripts/lint.py --structural-only`.

---

## Phase 2: Profiles, Job Queue, Runner, And Scheduler

### Task 2.1: Profile Store

**Files:**
- Create: `kb_app/profiles/store.py`
- Test: `tests/test_profiles.py`

- [ ] Write tests for schema creation, creating profiles, selecting active profile, and reading settings.
- [ ] Run profile tests and confirm fail.
- [ ] Implement SQLite-backed `ProfileStore`.
- [ ] Run profile tests and confirm pass.

### Task 2.2: Job Queue

**Files:**
- Create: `kb_app/jobs/queue.py`
- Test: `tests/test_jobs_queue.py`

- [ ] Write tests for enqueue, claim next, state transition validation, event logging, and artifact records.
- [ ] Run queue tests and confirm fail.
- [ ] Implement `JobStore`, allowed states, and durable event writes.
- [ ] Run queue tests and confirm pass.

### Task 2.3: Job Runner

**Files:**
- Create: `kb_app/jobs/runner.py`
- Test: `tests/test_jobs_runner.py`

- [ ] Write tests using fake operation functions for success, failure, retry, and cancellation request.
- [ ] Run runner tests and confirm fail.
- [ ] Implement `JobRunner` dispatch for compile/query/lint/manual-memory/diagnostics/backend smoke test.
- [ ] Run runner tests and confirm pass.

### Task 2.4: Background Agent

**Files:**
- Create: `kb_app/agent/service.py`
- Test: `tests/test_agent_service.py`

- [ ] Write tests for single-tick job execution and missed daily compile enqueue.
- [ ] Run service tests and confirm fail.
- [ ] Implement `BackgroundAgent` with `run_once()` and scheduler check.
- [ ] Run service tests and confirm pass.

**Phase 2 validation:**

- [ ] Run `python -m pytest tests/test_profiles.py tests/test_jobs_queue.py tests/test_jobs_runner.py tests/test_agent_service.py -q`.
- [ ] Run full current test suite with `python -m pytest -q`.

---

## Phase 3: Hook Commands And Safe Config Merge

### Task 3.1: Safe Config Merge

**Files:**
- Create: `kb_app/core/config_merge.py`
- Test: `tests/test_config_merge.py`

- [ ] Write tests for JSON merge preserving unrelated hooks, backup creation, rollback on invalid write, and removal of KB hook entries.
- [ ] Run config merge tests and confirm fail.
- [ ] Implement parser-backed JSON merge and conservative TOML app config writer.
- [ ] Run config merge tests and confirm pass.

### Task 3.2: Packaged Hook Commands

**Files:**
- Create: `kb_app/hooks/commands.py`
- Modify: `hooks/session-start.py`
- Modify: `hooks/session-end.py`
- Modify: `hooks/pre-compact.py`
- Test: `tests/test_hook_commands.py`

- [ ] Write tests for session-start JSON output, missing transcript skip, context-file creation, and no-API hook behavior.
- [ ] Run hook command tests and confirm fail.
- [ ] Implement packaged hook handlers using active profile and app data.
- [ ] Convert legacy hook files to wrappers.
- [ ] Run hook command tests and confirm pass.

**Phase 3 validation:**

- [ ] Run `python -m pytest tests/test_config_merge.py tests/test_hook_commands.py -q`.
- [ ] Run `python -m kb_app hook session-start` and confirm valid JSON.

---

## Phase 4: Diagnostics And CLI Entrypoint

### Task 4.1: Diagnostics

**Files:**
- Create: `kb_app/diagnostics/redaction.py`
- Create: `kb_app/diagnostics/export.py`
- Test: `tests/test_diagnostics.py`

- [ ] Write tests for secret redaction and support bundle contents/exclusions.
- [ ] Run diagnostics tests and confirm fail.
- [ ] Implement redaction and zip export.
- [ ] Run diagnostics tests and confirm pass.

### Task 4.2: Single Entrypoint

**Files:**
- Create: `kb_app/__main__.py`
- Test: `tests/test_cli.py`

- [ ] Write tests for `--help`, `hook session-start`, `profiles list`, `jobs enqueue`, and operation subcommand parsing.
- [ ] Run CLI tests and confirm fail.
- [ ] Implement argparse entrypoint.
- [ ] Run CLI tests and confirm pass.

**Phase 4 validation:**

- [ ] Run `python -m pytest tests/test_diagnostics.py tests/test_cli.py -q`.
- [ ] Run `python -m kb_app --help`.
- [ ] Run `python -m kb_app diagnostics export --output reports`.

---

## Phase 5: PySide6 Control Panel

### Task 5.1: UI Shell

**Files:**
- Create: `kb_app/ui/app.py`
- Create: `kb_app/ui/tray.py`
- Test: `tests/test_ui_imports.py`

- [ ] Write tests that UI modules import cleanly when PySide6 is absent and expose a clear dependency error for launch.
- [ ] Run UI import tests and confirm fail.
- [ ] Implement lazy PySide6 imports and fallback messages.
- [ ] Run UI import tests and confirm pass.

### Task 5.2: Control Panel Pages

**Files:**
- Modify: `kb_app/ui/app.py`
- Test: `tests/test_ui_model.py`

- [ ] Write tests for page registry, quick action job payload creation, and dashboard summary formatting without constructing Qt widgets.
- [ ] Run UI model tests and confirm fail.
- [ ] Implement UI model helpers and PySide6 widgets for Dashboard, Setup, Profiles, Hooks, Daily Logs, Knowledge, Operations, Jobs, Settings, Diagnostics.
- [ ] Run UI model tests and confirm pass.

**Phase 5 validation:**

- [ ] Run `python -m pytest tests/test_ui_imports.py tests/test_ui_model.py -q`.
- [ ] Run `python -m kb_app ui --help`.

---

## Phase 6: Packaging

### Task 6.1: Build Config

**Files:**
- Create: `packaging/pyinstaller/llm-knowledge-base.spec`
- Create: `packaging/inno/llm-knowledge-base.iss`
- Create: `packaging/linux/install.sh`
- Create: `packaging/linux/uninstall.sh`
- Create: `packaging/linux/llm-knowledge-base.desktop.template`
- Create: `scripts/build-windows.ps1`
- Create: `scripts/build-linux.sh`
- Create: `scripts/smoke-packaged.py`
- Test: `tests/test_packaging_files.py`

- [ ] Write tests verifying packaging files exist, use user-level install paths, and do not install hooks silently.
- [ ] Run packaging tests and confirm fail.
- [ ] Implement packaging files and smoke script.
- [ ] Run packaging tests and confirm pass.

**Phase 6 validation:**

- [ ] Run `python -m pytest tests/test_packaging_files.py -q`.
- [ ] Run `python scripts/smoke-packaged.py --python-module`.

---

## Phase 7: Documentation And Final Verification

### Task 7.1: Docs

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CONTEXT.md`

- [ ] Document desktop app setup, background agent, packaged hooks, profiles, diagnostics, and packaging.
- [ ] Verify docs do not claim cloud sync exists.
- [ ] Verify docs state Claude Code/Codex are external dependencies.

### Task 7.2: Full Verification

**Commands:**

- [ ] Run `python -m pytest -q`.
- [ ] Run `python scripts/compile.py --dry-run`.
- [ ] Run `python scripts/lint.py --structural-only`.
- [ ] Run `python -m kb_app --help`.
- [ ] Run `python -m kb_app hook session-start`.
- [ ] Run `python scripts/smoke-packaged.py --python-module`.

