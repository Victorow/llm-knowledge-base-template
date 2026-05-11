from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kb_app.jobs.queue import JobStore
from kb_app.jobs.runner import JobRunner
from kb_app.profiles.store import ProfileStore


class JobRunnerIntegrationTests(unittest.TestCase):
    def make_runtime(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        db_path = root / "app.db"
        kb_root = root / "kb-root"
        (kb_root / "kb" / "daily").mkdir(parents=True)
        (kb_root / "kb" / "knowledge").mkdir(parents=True)
        (kb_root / "AGENTS.md").write_text("# Schema", encoding="utf-8")
        profiles = ProfileStore(db_path)
        jobs = JobStore(db_path)
        profile_id = profiles.create_profile("Personal", kb_root, backend="claude")
        profiles.set_active_profile(profile_id)
        runner = JobRunner(jobs, profile_store=profiles)
        return temp, root, profiles, jobs, profile_id, runner

    def test_diagnostics_export_job_creates_bundle(self) -> None:
        temp, root, _profiles, jobs, profile_id, runner = self.make_runtime()
        with temp:
            output_dir = root / "diagnostics"
            job_id = jobs.enqueue(
                profile_id=profile_id,
                job_type="diagnostics_export",
                payload={"output_dir": str(output_dir)},
            )

            runner.run_next()

            result = jobs.get_job(job_id).result
            self.assertEqual(jobs.get_job(job_id).status, "succeeded")
            self.assertTrue(Path(result["bundle_path"]).exists())

    def test_configure_daily_schedule_job_updates_settings(self) -> None:
        temp, _root, profiles, jobs, profile_id, runner = self.make_runtime()
        with temp:
            jobs.enqueue(
                profile_id=profile_id,
                job_type="configure_daily_schedule",
                payload={"enabled": True, "time": "18:30"},
            )

            runner.run_next()

            self.assertIs(profiles.get_setting("daily_compile_enabled"), True)
            self.assertEqual(profiles.get_setting("daily_compile_time"), "18:30")

    def test_install_and_remove_hooks_jobs_use_backed_up_json_merge(self) -> None:
        temp, root, _profiles, jobs, profile_id, runner = self.make_runtime()
        with temp:
            config_path = root / "settings.json"
            config_path.write_text(
                json.dumps({"hooks": {"SessionStart": [{"hooks": [{"command": "echo keep"}]}]}}),
                encoding="utf-8",
            )
            payload = {
                "client": "claude",
                "config_path": str(config_path),
                "backup_dir": str(root / "backups"),
                "executable": "LLMKnowledgeBase.exe",
            }
            install_id = jobs.enqueue(profile_id=profile_id, job_type="install_hooks", payload=payload)

            runner.run_next()

            installed = json.loads(config_path.read_text(encoding="utf-8"))
            commands = [
                hook["command"]
                for group in installed["hooks"]["SessionStart"]
                for hook in group["hooks"]
            ]
            self.assertEqual(jobs.get_job(install_id).status, "succeeded")
            self.assertIn("echo keep", commands)
            self.assertTrue(any("LLMKnowledgeBase.exe" in command for command in commands))
            self.assertTrue(any((root / "backups").iterdir()))

            remove_id = jobs.enqueue(profile_id=profile_id, job_type="remove_hooks", payload=payload)
            runner.run_next()

            removed = json.loads(config_path.read_text(encoding="utf-8"))
            remaining_commands = [
                hook["command"]
                for group in removed["hooks"]["SessionStart"]
                for hook in group["hooks"]
            ]
            self.assertEqual(jobs.get_job(remove_id).status, "succeeded")
            self.assertEqual(remaining_commands, ["echo keep"])

    def test_autostart_jobs_write_and_remove_user_level_launcher(self) -> None:
        temp, root, _profiles, jobs, profile_id, runner = self.make_runtime()
        with temp:
            startup_dir = root / "startup"
            payload = {"startup_dir": str(startup_dir), "executable": "LLMKnowledgeBase.exe"}
            install_id = jobs.enqueue(profile_id=profile_id, job_type="install_autostart", payload=payload)

            runner.run_next()

            launcher_path = Path(jobs.get_job(install_id).result["launcher_path"])
            self.assertTrue(launcher_path.exists())

            remove_id = jobs.enqueue(profile_id=profile_id, job_type="remove_autostart", payload=payload)
            runner.run_next()

            self.assertEqual(jobs.get_job(remove_id).status, "succeeded")
            self.assertFalse(launcher_path.exists())


if __name__ == "__main__":
    unittest.main()
