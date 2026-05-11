from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kb_app.jobs.queue import InvalidJobTransition, JobStore


class JobQueueTests(unittest.TestCase):
    def make_store(self) -> tuple[tempfile.TemporaryDirectory[str], JobStore]:
        temp = tempfile.TemporaryDirectory()
        store = JobStore(Path(temp.name) / "app.db")
        return temp, store

    def test_enqueue_and_claim_next_job(self) -> None:
        temp, store = self.make_store()
        with temp:
            low = store.enqueue(profile_id=1, job_type="compile_changed", priority=50)
            high = store.enqueue(profile_id=1, job_type="lint_structural", priority=10)

            claimed = store.claim_next()

            self.assertEqual(claimed.id, high)
            self.assertEqual(claimed.status, "running")
            self.assertEqual(store.get_job(low).status, "queued")

    def test_records_state_transitions_and_events(self) -> None:
        temp, store = self.make_store()
        with temp:
            job_id = store.enqueue(profile_id=1, job_type="query", payload={"question": "x"})
            store.claim_next()
            store.mark_succeeded(job_id, {"answer": "ok"})

            job = store.get_job(job_id)
            events = store.list_events(job_id)

            self.assertEqual(job.status, "succeeded")
            self.assertEqual(job.result["answer"], "ok")
            self.assertEqual([event.event for event in events], ["queued", "running", "succeeded"])

    def test_rejects_invalid_transition(self) -> None:
        temp, store = self.make_store()
        with temp:
            job_id = store.enqueue(profile_id=1, job_type="query")

            with self.assertRaises(InvalidJobTransition):
                store.mark_succeeded(job_id, {})

    def test_artifact_records_are_persisted(self) -> None:
        temp, store = self.make_store()
        with temp:
            job_id = store.enqueue(profile_id=1, job_type="lint_structural")

            store.add_artifact(job_id, "report", "reports/lint.md")

            artifacts = store.list_artifacts(job_id)
            self.assertEqual(artifacts[0].kind, "report")
            self.assertEqual(artifacts[0].path, "reports/lint.md")


if __name__ == "__main__":
    unittest.main()
