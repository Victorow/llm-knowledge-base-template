"""User-session background agent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from kb_app.jobs.queue import JobStore
from kb_app.jobs.runner import JobRunner, RunnerResult
from kb_app.profiles.store import ProfileStore


@dataclass(frozen=True)
class SchedulerResult:
    created: int


class BackgroundAgent:
    """Coordinates scheduled jobs and one-at-a-time queue execution."""

    def __init__(
        self,
        profile_store: ProfileStore,
        job_store: JobStore,
        runner: JobRunner,
    ) -> None:
        self.profile_store = profile_store
        self.job_store = job_store
        self.runner = runner

    def run_once(self) -> RunnerResult:
        self.enqueue_due_scheduled_jobs()
        return self.runner.run_next()

    def enqueue_due_scheduled_jobs(self, *, now: datetime | None = None) -> int:
        current = now or datetime.now()
        if not self.profile_store.get_setting("daily_compile_enabled", False):
            return 0

        active_profile = self.profile_store.get_active_profile()
        if active_profile is None:
            return 0

        target_time = self.profile_store.get_setting("daily_compile_time", "17:00")
        current_time = current.strftime("%H:%M")
        current_date = current.strftime("%Y-%m-%d")
        last_run = self.profile_store.get_setting("last_daily_compile_date")

        if current_time < target_time or last_run == current_date:
            return 0

        self.job_store.enqueue(
            profile_id=active_profile.id,
            job_type="compile_changed",
            backend=active_profile.backend,
            command_summary="Scheduled daily compile",
        )
        self.profile_store.set_setting("last_daily_compile_date", current_date)
        return 1
