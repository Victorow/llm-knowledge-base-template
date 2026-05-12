from __future__ import annotations

import json
import asyncio
import tempfile
import unittest
from pathlib import Path


class McpUiActionsTests(unittest.TestCase):
    def test_mcp_declares_every_ui_job_action(self) -> None:
        from kb_app.ui.app import ACTION_TO_JOB_TYPE
        from kb_mcp.server import MCP_UI_JOB_ACTIONS

        self.assertEqual(set(ACTION_TO_JOB_TYPE), set(MCP_UI_JOB_ACTIONS))
        self.assertEqual(set(ACTION_TO_JOB_TYPE.values()), set(MCP_UI_JOB_ACTIONS.values()))

    def test_mcp_can_create_activate_profile_and_run_hook_install_job(self) -> None:
        import kb_mcp.server as server
        from kb_app.profiles.store import ProfileStore

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            kb_root = base / "kb-data"
            db_path = base / "app.db"
            config_path = base / "settings.json"
            backup_dir = base / "backups"
            server._kb_root = kb_root
            server._app_db_path = db_path

            create_result = server.kb_profile_create(
                name="Personal",
                root_path=str(kb_root),
                backend="claude",
                activate=True,
            )
            self.assertIn("Profile created", create_result)
            self.assertTrue((kb_root / "AGENTS.md").exists())

            result = server.kb_install_hooks(
                client="claude",
                config_path=str(config_path),
                backup_dir=str(backup_dir),
                executable="LLMKnowledgeBase.exe",
            )

            self.assertIn("succeeded", result)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            commands = [
                hook["command"]
                for groups in config["hooks"].values()
                for group in groups
                for hook in group["hooks"]
            ]
            hooks_text = json.dumps(config)
            self.assertTrue(any(str(kb_root) in command for command in commands))
            self.assertIn("LLM_KB_HOOK", hooks_text)

            active = ProfileStore(db_path).get_active_profile()
            self.assertEqual(Path(active.root_path), kb_root)

    def test_kb_compile_force_all_enqueues_job_without_running_backend(self) -> None:
        import kb_mcp.server as server
        from kb_app.jobs.queue import JobStore

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            kb_root = base / "kb-data"
            db_path = base / "app.db"
            server._kb_root = kb_root
            server._app_db_path = db_path

            result = asyncio.run(server.kb_compile(force_all=True))
            self.assertIn("Queued job", result)
            self.assertIn("compile_all", result)

            jobs = JobStore(db_path)
            queued = jobs.claim_next()
            self.assertEqual(queued.job_type, "compile_all")

    def test_kb_compile_file_enqueues_file_job_with_payload(self) -> None:
        import kb_mcp.server as server
        from kb_app.jobs.queue import JobStore

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            kb_root = base / "kb-data"
            db_path = base / "app.db"
            server._kb_root = kb_root
            server._app_db_path = db_path

            result = asyncio.run(server.kb_compile(file_name="2026-05-12.md"))

            self.assertIn("Queued job", result)
            self.assertIn("compile_file", result)

            queued = JobStore(db_path).claim_next()
            self.assertEqual(queued.job_type, "compile_file")
            self.assertEqual(queued.payload["file"], "2026-05-12.md")

    def test_kb_status_counts_changed_logs_as_pending(self) -> None:
        import kb_mcp.server as server
        from kb_app.core.paths import resolve_kb_paths
        from kb_app.core.wiki import save_state

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = resolve_kb_paths(root)
            paths.daily_dir.mkdir(parents=True)
            paths.knowledge_dir.mkdir(parents=True)
            daily = paths.daily_dir / "2026-05-12.md"
            daily.write_text("changed", encoding="utf-8")
            save_state(paths, {"ingested": {"2026-05-12.md": {"hash": "old"}}, "query_count": 0})
            server._kb_root = root

            status = server.kb_status()

            self.assertIn("Daily logs    : 1 files (0 compiled, 1 pending)", status)


if __name__ == "__main__":
    unittest.main()
