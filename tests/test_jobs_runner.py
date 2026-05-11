from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kb_app.jobs.queue import JobStore
from kb_app.jobs.runner import JobRunner


class JobRunnerTests(unittest.TestCase):
    def make_store(self) -> tuple[tempfile.TemporaryDirectory[str], JobStore]:
        temp = tempfile.TemporaryDirectory()
        store = JobStore(Path(temp.name) / "app.db")
        return temp, store

    def test_runner_marks_success_with_handler_result(self) -> None:
        temp, store = self.make_store()
        with temp:
            job_id = store.enqueue(profile_id=1, job_type="fake_success", payload={"x": 1})
            runner = JobRunner(store, handlers={"fake_success": lambda job: {"seen": job.payload["x"]}})

            result = runner.run_next()

            self.assertEqual(result.job_id, job_id)
            self.assertEqual(store.get_job(job_id).status, "succeeded")
            self.assertEqual(store.get_job(job_id).result["seen"], 1)

    def test_runner_marks_failure_when_handler_raises(self) -> None:
        temp, store = self.make_store()
        with temp:
            job_id = store.enqueue(profile_id=1, job_type="fake_failure")

            def fail(_job):
                raise RuntimeError("boom")

            runner = JobRunner(store, handlers={"fake_failure": fail})

            runner.run_next()

            job = store.get_job(job_id)
            self.assertEqual(job.status, "failed")
            self.assertIn("boom", job.error_message)

    def test_runner_honors_cancel_requested_during_handler(self) -> None:
        temp, store = self.make_store()
        with temp:
            job_id = store.enqueue(profile_id=1, job_type="fake_cancel")

            def cancel(job):
                store.request_cancel(job.id)
                return {"partial": True}

            runner = JobRunner(store, handlers={"fake_cancel": cancel})

            runner.run_next()

            self.assertEqual(store.get_job(job_id).status, "cancelled")


if __name__ == "__main__":
    unittest.main()
