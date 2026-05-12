from __future__ import annotations

import subprocess
import sys
import unittest

from kb_app.ui.app import (
    PAGE_REGISTRY,
    build_quick_action_job,
    format_dashboard_summary,
    format_job_result_summary,
)


class UiModelTests(unittest.TestCase):
    def test_page_registry_contains_all_v1_pages(self) -> None:
        page_ids = [page.page_id for page in PAGE_REGISTRY]

        self.assertEqual(
            page_ids,
            [
                "tutorial",
                "dashboard",
                "setup",
                "profiles",
                "hooks",
                "daily_logs",
                "knowledge",
                "operations",
                "jobs",
                "settings",
                "diagnostics",
            ],
        )

    def test_quick_action_payloads_map_to_job_types(self) -> None:
        job = build_quick_action_job("manual_memory", profile_id=9, payload={"content": "x"})

        self.assertEqual(job["profile_id"], 9)
        self.assertEqual(job["job_type"], "manual_memory")
        self.assertEqual(job["payload"]["content"], "x")

    def test_system_actions_map_to_job_types(self) -> None:
        install = build_quick_action_job("install_autostart", profile_id=1)
        schedule = build_quick_action_job(
            "configure_daily_schedule",
            profile_id=1,
            payload={"enabled": True, "time": "17:00"},
        )

        self.assertEqual(install["job_type"], "install_autostart")
        self.assertEqual(schedule["job_type"], "configure_daily_schedule")

    def test_dashboard_summary_formats_missing_state(self) -> None:
        summary = format_dashboard_summary(
            profile_name=None,
            backend=None,
            agent_status="stopped",
            last_job_status=None,
        )

        self.assertIn("No active profile", summary)
        self.assertIn("agent: stopped", summary)

    def test_job_result_summary_labels_llm_usage_estimate(self) -> None:
        summary = format_job_result_summary({"files": ["2026-05-12.md"], "total_cost": 0.3429})

        self.assertIn("1 file", summary)
        self.assertIn("LLM backend usage estimate reported by provider: $0.3429", summary)
        self.assertNotIn("Total cost", summary)
        self.assertNotIn("API cost", summary)

    def test_ui_help_command_does_not_launch_qt(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "kb_app", "ui", "--help"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Launch desktop control panel", completed.stdout)


if __name__ == "__main__":
    unittest.main()
