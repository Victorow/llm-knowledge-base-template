from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.agent_backend import (
    AgentResult,
    build_codex_exec_command,
    resolve_codex_executable,
    run_codex_agent,
    selected_backend,
)


class AgentBackendTests(unittest.TestCase):
    def test_selected_backend_defaults_to_claude(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(selected_backend(), "claude")

    def test_selected_backend_accepts_codex(self) -> None:
        with patch.dict(os.environ, {"KB_AGENT_BACKEND": "Codex"}):
            self.assertEqual(selected_backend(), "codex")

    def test_selected_backend_rejects_unknown_values(self) -> None:
        with patch.dict(os.environ, {"KB_AGENT_BACKEND": "other"}):
            with self.assertRaises(ValueError):
                selected_backend()

    def test_build_codex_exec_command_reads_prompt_from_stdin(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            command = build_codex_exec_command(
                cwd=Path("C:/repo"),
                output_path=Path("C:/tmp/last-message.txt"),
                writable=True,
            )

        self.assertEqual(command[1], "exec")
        self.assertIn("-m", command)
        self.assertIn("gpt-5.3-codex", command)
        self.assertIn("--skip-git-repo-check", command)
        self.assertNotIn("--disable", command)
        self.assertNotIn("codex_hooks", command)
        self.assertIn("--ephemeral", command)
        self.assertIn("--output-last-message", command)
        self.assertIn("workspace-write", command)
        self.assertNotIn("--ask-for-approval", command)
        self.assertEqual(command[-1], "-")

    def test_build_codex_exec_command_can_run_read_only(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            command = build_codex_exec_command(
                cwd=Path("/repo"),
                output_path=Path("/tmp/last-message.txt"),
                writable=False,
            )

        self.assertIn("read-only", command)
        self.assertNotIn("workspace-write", command)

    def test_build_codex_exec_command_honors_model_override(self) -> None:
        with patch.dict(os.environ, {"KB_CODEX_MODEL": "custom-model"}):
            command = build_codex_exec_command(
                cwd=Path("/repo"),
                output_path=Path("/tmp/last-message.txt"),
                writable=False,
            )

        self.assertIn("-m", command)
        self.assertIn("custom-model", command)

    def test_resolve_codex_executable_prefers_cmd_shim_on_windows(self) -> None:
        with (
            patch("scripts.agent_backend.sys.platform", "win32"),
            patch("scripts.agent_backend.shutil.which") as which,
        ):
            which.side_effect = lambda name: {
                "codex.exe": "C:/Program Files/Codex/codex.exe",
                "codex": "C:/Users/me/AppData/Roaming/npm/codex",
                "codex.cmd": "C:/Users/me/AppData/Roaming/npm/codex.cmd",
            }.get(name)

            self.assertEqual(
                resolve_codex_executable(),
                "C:/Users/me/AppData/Roaming/npm/codex.cmd",
            )

    def test_run_codex_agent_uses_utf8_for_prompt_input(self) -> None:
        calls = {}

        def fake_run(*args, **kwargs):
            calls.update(kwargs)
            output_arg_index = args[0].index("--output-last-message") + 1
            Path(args[0][output_arg_index]).write_text("ok", encoding="utf-8")

            class Completed:
                returncode = 0

            return Completed()

        with patch("scripts.agent_backend.subprocess.run", fake_run):
            result = run_codex_agent(
                "unicode prompt \ufeff",
                cwd=Path.cwd(),
                writable=False,
                timeout_seconds=10,
            )

        self.assertIsInstance(result, AgentResult)
        self.assertEqual(result.text, "ok")
        self.assertEqual(calls["encoding"], "utf-8")


if __name__ == "__main__":
    unittest.main()
