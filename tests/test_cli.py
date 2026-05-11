from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from kb_app.jobs.queue import JobStore


class CliTests(unittest.TestCase):
    def test_help_command(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "kb_app", "--help"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("llm-knowledge-base", completed.stdout)

    def test_profiles_list_uses_app_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "app.db"

            completed = subprocess.run(
                [sys.executable, "-m", "kb_app", "--app-db", str(db_path), "profiles", "list"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("No profiles", completed.stdout)

    def test_jobs_enqueue_writes_to_app_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "app.db"
            payload = json.dumps({"content": "remember this"})

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "kb_app",
                    "--app-db",
                    str(db_path),
                    "jobs",
                    "enqueue",
                    "manual_memory",
                    "--profile-id",
                    "7",
                    "--payload-json",
                    payload,
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Queued job", completed.stdout)
            claimed = JobStore(db_path).claim_next()
            self.assertEqual(claimed.job_type, "manual_memory")
            self.assertEqual(claimed.profile_id, 7)

    def test_compile_dry_run_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_root = Path(tmp)
            (kb_root / "kb" / "daily").mkdir(parents=True)
            (kb_root / "kb" / "knowledge").mkdir(parents=True)
            (kb_root / "AGENTS.md").write_text("# Schema", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "kb_app",
                    "--kb-root",
                    str(kb_root),
                    "compile",
                    "--dry-run",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Nothing to compile", completed.stdout)


if __name__ == "__main__":
    unittest.main()
