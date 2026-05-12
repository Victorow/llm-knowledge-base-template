from __future__ import annotations

import json
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


if __name__ == "__main__":
    unittest.main()
