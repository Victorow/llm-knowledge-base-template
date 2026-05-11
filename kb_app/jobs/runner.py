"""Job execution dispatch for queued background work."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Callable

from kb_app.core.config_merge import KB_HOOK_MARKER, merge_json_hooks, remove_json_hooks
from kb_app.core.operations import (
    append_manual_memory,
    compile_logs,
    run_lint,
    run_query,
    run_structural_lint,
)
from kb_app.core.paths import ensure_kb_layout, is_same_path, resolve_app_paths, resolve_kb_paths
from kb_app.diagnostics.export import export_diagnostics
from kb_app.jobs.queue import JobRecord, JobStore
from kb_app.profiles.store import ProfileStore

JobHandler = Callable[[JobRecord], dict[str, Any]]


@dataclass(frozen=True)
class RunnerResult:
    job_id: str | None
    status: str


class JobRunner:
    """Claims and executes jobs one at a time."""

    def __init__(
        self,
        job_store: JobStore,
        *,
        profile_store: ProfileStore | None = None,
        handlers: dict[str, JobHandler] | None = None,
    ) -> None:
        self.job_store = job_store
        self.profile_store = profile_store
        self.handlers = handlers or {}

    def run_next(self) -> RunnerResult:
        job = self.job_store.claim_next()
        if job is None:
            return RunnerResult(job_id=None, status="idle")

        try:
            handler = self.handlers.get(job.job_type) or self._default_handler
            result = handler(job)
            current = self.job_store.get_job(job.id)
            if current.status == "cancel_requested":
                self.job_store.mark_cancelled(job.id, result)
                return RunnerResult(job_id=job.id, status="cancelled")
            self.job_store.mark_succeeded(job.id, result)
            return RunnerResult(job_id=job.id, status="succeeded")
        except Exception as e:
            current = self.job_store.get_job(job.id)
            if current.status == "cancel_requested":
                self.job_store.mark_cancelled(job.id, {"error": str(e)})
                return RunnerResult(job_id=job.id, status="cancelled")
            self.job_store.mark_failed(job.id, f"{type(e).__name__}: {e}")
            return RunnerResult(job_id=job.id, status="failed")

    def _default_handler(self, job: JobRecord) -> dict[str, Any]:
        if self.profile_store is None:
            raise ValueError(f"No handler registered for job type: {job.job_type}")

        profile = self.profile_store.get_profile(job.profile_id)
        paths = resolve_kb_paths(Path(profile.root_path))
        backend = job.backend or profile.backend

        if job.job_type == "compile_changed":
            result = compile_logs(paths, backend=backend)
            return {"files": result.files, "dry_run": result.dry_run, "total_cost": result.total_cost}
        if job.job_type == "compile_all":
            result = compile_logs(paths, force_all=True, backend=backend)
            return {"files": result.files, "dry_run": result.dry_run, "total_cost": result.total_cost}
        if job.job_type == "compile_file":
            result = compile_logs(paths, file_name=job.payload["file"], backend=backend)
            return {"files": result.files, "dry_run": result.dry_run, "total_cost": result.total_cost}
        if job.job_type == "query":
            answer = run_query(paths, job.payload["question"], backend=backend)
            return {"answer": answer}
        if job.job_type == "query_file_back":
            answer = run_query(paths, job.payload["question"], file_back=True, backend=backend)
            return {"answer": answer, "file_back": True}
        if job.job_type == "lint_structural":
            result = run_structural_lint(paths)
            return {
                "errors": result.errors,
                "warnings": result.warnings,
                "suggestions": result.suggestions,
                "report_path": str(result.report_path) if result.report_path else None,
            }
        if job.job_type == "lint_full":
            result = run_lint(paths, structural_only=False, backend=backend)
            return {
                "errors": result.errors,
                "warnings": result.warnings,
                "suggestions": result.suggestions,
                "report_path": str(result.report_path) if result.report_path else None,
            }
        if job.job_type == "manual_memory":
            log_path = append_manual_memory(paths, job.payload["content"])
            return {"log_path": str(log_path)}
        if job.job_type == "backend_smoke_test":
            return {"backend": backend, "status": "configured"}
        if job.job_type in {"install_hooks", "repair_hooks"}:
            return self._install_hooks(job, paths)
        if job.job_type == "remove_hooks":
            return self._remove_hooks(job)
        if job.job_type == "install_autostart":
            return self._install_autostart(job)
        if job.job_type == "remove_autostart":
            return self._remove_autostart(job)
        if job.job_type == "configure_daily_schedule":
            enabled = bool(job.payload.get("enabled", True))
            time_text = str(job.payload.get("time", "17:00"))
            self.profile_store.set_setting("daily_compile_enabled", enabled)
            self.profile_store.set_setting("daily_compile_time", time_text)
            return {"enabled": enabled, "time": time_text}
        if job.job_type == "diagnostics_export":
            app_paths = resolve_app_paths()
            output_dir = Path(job.payload["output_dir"]) if job.payload.get("output_dir") else None
            bundle = export_diagnostics(app_paths, paths, output_dir=output_dir)
            return {"bundle_path": str(bundle)}
        if job.job_type == "flush_test":
            return {"status": "ok", "kb_root": str(paths.root)}

        raise ValueError(f"Unsupported job type: {job.job_type}")

    def _install_hooks(self, job: JobRecord, paths) -> dict[str, Any]:
        app_paths = resolve_app_paths()
        client = str(job.payload.get("client", "claude")).lower()
        if is_same_path(paths.root, app_paths.install_dir):
            raise ValueError(
                "Active KB profile points to the application install directory. "
                "Select a real KB data directory before installing hooks."
            )
        paths = ensure_kb_layout(paths.root)
        executable = resolve_hook_command_prefix(
            explicit=job.payload.get("executable"),
            app_paths=app_paths,
        )
        config_path = Path(job.payload.get("config_path") or default_hook_config_path(client))
        backup_dir = Path(job.payload.get("backup_dir") or app_paths.backups_dir)
        hooks = build_hook_groups(client=client, executable=executable, kb_root=paths.root)
        result = merge_json_hooks(config_path, hooks, backup_dir=backup_dir)
        return {
            "client": client,
            "config_path": str(config_path),
            "backup_path": str(result.backup_path) if result.backup_path else None,
            "changed": result.changed,
        }

    def _remove_hooks(self, job: JobRecord) -> dict[str, Any]:
        app_paths = resolve_app_paths()
        client = str(job.payload.get("client", "claude")).lower()
        config_path = Path(job.payload.get("config_path") or default_hook_config_path(client))
        backup_dir = Path(job.payload.get("backup_dir") or app_paths.backups_dir)
        result = remove_json_hooks(config_path, backup_dir=backup_dir)
        return {
            "client": client,
            "config_path": str(config_path),
            "backup_path": str(result.backup_path) if result.backup_path else None,
            "changed": result.changed,
        }

    def _install_autostart(self, job: JobRecord) -> dict[str, Any]:
        executable = str(
            job.payload.get(
                "executable",
                "LLMKnowledgeBase.exe" if sys.platform == "win32" else "llm-knowledge-base",
            )
        )
        startup_dir = Path(job.payload.get("startup_dir") or default_autostart_dir())
        startup_dir.mkdir(parents=True, exist_ok=True)
        launcher_path = startup_dir / (
            "LLM Knowledge Base.cmd" if sys.platform == "win32" else "llm-knowledge-base.desktop"
        )
        if sys.platform == "win32":
            launcher_path.write_text(f'@echo off\nstart "" "{executable}" ui\n', encoding="utf-8")
        else:
            launcher_path.write_text(
                "\n".join(
                    [
                        "[Desktop Entry]",
                        "Type=Application",
                        "Name=LLM Knowledge Base",
                        f"Exec={executable} ui",
                        "Terminal=false",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
        return {"launcher_path": str(launcher_path)}

    def _remove_autostart(self, job: JobRecord) -> dict[str, Any]:
        startup_dir = Path(job.payload.get("startup_dir") or default_autostart_dir())
        candidates = [
            startup_dir / "LLM Knowledge Base.cmd",
            startup_dir / "llm-knowledge-base.desktop",
        ]
        removed = []
        for path in candidates:
            if path.exists():
                path.unlink()
                removed.append(str(path))
        return {"removed": removed}


def default_hook_config_path(client: str) -> Path:
    if client == "claude":
        return Path.home() / ".claude" / "settings.json"
    if client == "codex":
        return Path.home() / ".codex" / "hooks.json"
    raise ValueError(f"Unsupported hook client: {client}")


def resolve_hook_command_prefix(*, explicit: Any = None, app_paths=None) -> str:
    """Return a stable command prefix for installed hooks.

    On Windows this prefers the packaged GUI executable by absolute path so AI
    clients do not rely on PATH lookup and do not flash a console window for
    context lookups. Source-tree fallback is only for development.
    """
    if explicit:
        return _quote_command_prefix(str(explicit))

    if getattr(sys, "frozen", False):
        return _quote_command_prefix(str(sys.executable))

    resolved_app_paths = app_paths or resolve_app_paths()
    win_exe = resolved_app_paths.install_dir / "LLMKnowledgeBase.exe"
    posix_exe = resolved_app_paths.install_dir / "llm-knowledge-base"
    if sys.platform == "win32" and win_exe.exists():
        return _quote_command_prefix(str(win_exe))
    if sys.platform != "win32" and posix_exe.exists():
        return _quote_command_prefix(str(posix_exe))

    source_root = Path(__file__).resolve().parents[2]
    return f'uv run --directory "{source_root}" python -m kb_app'


def build_hook_groups(*, client: str, executable: str, kb_root: Path) -> dict[str, list[dict]]:
    exe_str = _quote_command_prefix(executable)

    def command(event: str) -> str:
        return f'{exe_str} --kb-root "{kb_root}" hook {event}'

    if client == "claude":
        return {
            "SessionStart": [_hook_group("", command("session-start"), 15)],
            "SessionEnd":   [_hook_group("", command("session-end"), 10)],
            "PreCompact":   [_hook_group("", command("pre-compact"), 10)],
            "PostCompact":  [_hook_group("", command("post-compact"), 30)],
        }
    if client == "codex":
        return {
            "SessionStart": [_hook_group("startup|resume", command("session-start"), 15)],
            "Stop": [_hook_group("", command("session-end"), 10)],
        }
    raise ValueError(f"Unsupported hook client: {client}")


def _hook_group(matcher: str, command: str, timeout: int) -> dict:
    return {
        "matcher": matcher,
        "hooks": [{
            "type": "command",
            "command": command,
            "timeout": timeout,
            "_kb_marker": KB_HOOK_MARKER,
        }],
    }


def _quote_command_prefix(command_prefix: str) -> str:
    value = command_prefix.strip()
    if not value or value.startswith('"') or value.startswith("uv "):
        return value
    if " -m " in value or " --directory " in value:
        return value
    return f'"{value}"' if " " in value else value


def default_autostart_dir() -> Path:
    if sys.platform == "win32":
        return (
            Path.home()
            / "AppData"
            / "Roaming"
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
        )
    return Path.home() / ".config" / "autostart"
