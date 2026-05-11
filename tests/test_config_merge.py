from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kb_app.core.config_merge import (
    KB_HOOK_MARKER,
    merge_json_hooks,
    remove_json_hooks,
    write_json_with_backup,
)


class ConfigMergeTests(unittest.TestCase):
    def test_merge_preserves_unrelated_hooks_and_creates_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "settings.json"
            backup_dir = root / "backups"
            config_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SessionStart": [
                                {
                                    "matcher": "old",
                                    "hooks": [{"type": "command", "command": "echo old"}],
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            result = merge_json_hooks(
                config_path,
                {
                    "SessionStart": [
                        {
                            "matcher": "",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": f"LLMKnowledgeBase.exe hook session-start # {KB_HOOK_MARKER}",
                                }
                            ],
                        }
                    ]
                },
                backup_dir=backup_dir,
            )

            data = json.loads(config_path.read_text(encoding="utf-8"))
            commands = [
                hook["command"]
                for group in data["hooks"]["SessionStart"]
                for hook in group["hooks"]
            ]
            self.assertTrue(result.changed)
            self.assertTrue(result.backup_path.exists())
            self.assertIn("echo old", commands)
            self.assertIn(f"LLMKnowledgeBase.exe hook session-start # {KB_HOOK_MARKER}", commands)

    def test_remove_json_hooks_only_removes_marked_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "settings.json"
            backup_dir = root / "backups"
            config_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "Stop": [
                                {
                                    "hooks": [
                                        {"type": "command", "command": "echo keep"},
                                        {
                                            "type": "command",
                                            "command": f"LLMKnowledgeBase.exe hook session-end # {KB_HOOK_MARKER}",
                                        },
                                    ]
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            remove_json_hooks(config_path, backup_dir=backup_dir)

            data = json.loads(config_path.read_text(encoding="utf-8"))
            commands = [hook["command"] for hook in data["hooks"]["Stop"][0]["hooks"]]
            self.assertEqual(commands, ["echo keep"])

    def test_remove_json_hooks_removes_entries_with_kb_marker_field(self) -> None:
        """New-style hooks use _kb_marker field instead of # MARKER in command."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "settings.json"
            backup_dir = root / "backups"
            config_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SessionStart": [
                                {
                                    "matcher": "",
                                    "hooks": [
                                        {"type": "command", "command": "echo keep"},
                                        {
                                            "type": "command",
                                            "command": "LLMKnowledgeBase.exe hook session-start",
                                            "_kb_marker": KB_HOOK_MARKER,
                                        },
                                    ],
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            remove_json_hooks(config_path, backup_dir=backup_dir)

            data = json.loads(config_path.read_text(encoding="utf-8"))
            commands = [hook["command"] for hook in data["hooks"]["SessionStart"][0]["hooks"]]
            self.assertEqual(commands, ["echo keep"])

    def test_remove_json_hooks_legacy_command_marker_still_detected(self) -> None:
        """Old-style hooks with '# LLM_KB_HOOK' in command are still removed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "settings.json"
            backup_dir = root / "backups"
            config_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SessionEnd": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": f"old_exe hook session-end # {KB_HOOK_MARKER}",
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            remove_json_hooks(config_path, backup_dir=backup_dir)

            data = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertNotIn("SessionEnd", data.get("hooks", {}))

    def test_write_json_with_backup_restores_original_on_write_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "settings.json"
            backup_dir = root / "backups"
            original = {"hooks": {"SessionStart": []}}
            config_path.write_text(json.dumps(original), encoding="utf-8")

            def failing_writer(_path: Path, _text: str) -> None:
                config_path.write_text("{broken", encoding="utf-8")
                raise OSError("disk full")

            with self.assertRaises(OSError):
                write_json_with_backup(config_path, {"hooks": {}}, backup_dir, writer=failing_writer)

            self.assertEqual(json.loads(config_path.read_text(encoding="utf-8")), original)


if __name__ == "__main__":
    unittest.main()
