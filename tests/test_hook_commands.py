from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kb_app.core.paths import resolve_kb_paths
from kb_app.hooks.commands import capture_hook, render_session_start_json


class HookCommandTests(unittest.TestCase):
    def make_kb(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "kb" / "daily").mkdir(parents=True)
        (root / "kb" / "knowledge").mkdir(parents=True)
        (root / "kb" / "knowledge" / "index.md").write_text(
            "# Knowledge Base Index\n\n| Article | Summary | Compiled From | Updated |",
            encoding="utf-8",
        )
        (root / "kb" / "daily" / "2026-05-11.md").write_text(
            "# Daily Log: 2026-05-11\n\nRecent decision",
            encoding="utf-8",
        )
        return temp, root

    def test_session_start_outputs_valid_hook_json(self) -> None:
        temp, root = self.make_kb()
        with temp:
            output = json.loads(render_session_start_json(resolve_kb_paths(root)))

            self.assertIn("hookSpecificOutput", output)
            context = output["hookSpecificOutput"]["additionalContext"]
            self.assertIn("Knowledge Base Index", context)
            self.assertIn("Recent Daily Log", context)

    def test_capture_hook_skips_missing_transcript_path(self) -> None:
        temp, root = self.make_kb()
        with temp:
            result = capture_hook(
                json.dumps({"session_id": "s1"}),
                resolve_kb_paths(root),
                state_dir=root / "state",
                spawn_flush=False,
            )

            self.assertEqual(result.status, "skipped")
            self.assertEqual(result.reason, "no transcript path")

    def test_capture_hook_writes_context_file_without_api_call(self) -> None:
        temp, root = self.make_kb()
        with temp:
            transcript = root / "session.jsonl"
            transcript.write_text(
                "\n".join(
                    [
                        json.dumps({"message": {"role": "user", "content": "Remember this"}}),
                        json.dumps({"message": {"role": "assistant", "content": "Captured"}}),
                    ]
                ),
                encoding="utf-8",
            )

            with patch("kb_app.hooks.commands.subprocess.Popen") as popen:
                result = capture_hook(
                    json.dumps({"session_id": "s1", "transcript_path": str(transcript)}),
                    resolve_kb_paths(root),
                    state_dir=root / "state",
                    min_turns=1,
                    spawn_flush=False,
                )

            self.assertEqual(result.status, "captured")
            self.assertIsNotNone(result.context_file)
            self.assertIn("**User:** Remember this", result.context_file.read_text(encoding="utf-8"))
            popen.assert_not_called()

    def test_module_hook_session_start_command_outputs_json(self) -> None:
        temp, root = self.make_kb()
        with temp:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "kb_app",
                    "--kb-root",
                    str(root),
                    "hook",
                    "session-start",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            output = json.loads(completed.stdout)
            self.assertIn("hookSpecificOutput", output)


if __name__ == "__main__":
    unittest.main()
