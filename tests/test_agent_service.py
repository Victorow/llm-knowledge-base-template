from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from kb_app.agent.service import BackgroundAgent
from kb_app.jobs.queue import JobStore
from kb_app.jobs.runner import JobRunner
from kb_app.profiles.store import ProfileStore


class BackgroundAgentTests(unittest.TestCase):
    def make_components(
        self,
    ) -> tuple[tempfile.TemporaryDirectory[str], ProfileStore, JobStore, JobRunner]:
        temp = tempfile.TemporaryDirectory()
        db_path = Path(temp.name) / "app.db"
        profiles = ProfileStore(db_path)
        jobs = JobStore(db_path)
        runner = JobRunner(jobs, handlers={"noop": lambda _job: {"ok": True}})
        return temp, profiles, jobs, runner

    def test_run_once_executes_one_queued_job(self) -> None:
        temp, profiles, jobs, runner = self.make_components()
        with temp:
            job_id = jobs.enqueue(profile_id=1, job_type="noop")
            agent = BackgroundAgent(profiles, jobs, runner)

            agent.run_once()

            self.assertEqual(jobs.get_job(job_id).status, "succeeded")

    def test_scheduler_enqueues_missed_daily_compile_for_active_profile(self) -> None:
        temp, profiles, jobs, runner = self.make_components()
        with temp:
            profile_id = profiles.create_profile("Personal", "D:/kb/personal")
            profiles.set_active_profile(profile_id)
            profiles.set_setting("daily_compile_enabled", True)
            profiles.set_setting("daily_compile_time", "17:00")
            profiles.set_setting("last_daily_compile_date", "2026-05-10")
            agent = BackgroundAgent(profiles, jobs, runner)

            created = agent.enqueue_due_scheduled_jobs(now=datetime(2026, 5, 11, 17, 1))

            self.assertEqual(created, 1)
            claimed = jobs.claim_next()
            self.assertEqual(claimed.job_type, "compile_changed")
            self.assertEqual(claimed.profile_id, profile_id)
            self.assertEqual(profiles.get_setting("last_daily_compile_date"), "2026-05-11")


if __name__ == "__main__":
    unittest.main()
