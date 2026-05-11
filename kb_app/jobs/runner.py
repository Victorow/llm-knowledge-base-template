"""Job execution dispatch for queued background work."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from kb_app.core.operations import (
    append_manual_memory,
    compile_logs,
    run_lint,
    run_query,
    run_structural_lint,
)
from kb_app.core.paths import resolve_kb_paths
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

        raise ValueError(f"Unsupported job type: {job.job_type}")
