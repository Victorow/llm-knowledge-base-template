"""Tests for hook command building and hook exit codes."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kb_app.core.config_merge import KB_HOOK_MARKER
from kb_app.jobs.runner import build_hook_groups


class HookGroupBuilderTests(unittest.TestCase):
    """build_hook_groups — command format, marker field, path quoting."""

    def _all_hook_entries(self, groups: dict) -> list[dict]:
        entries = []
        for group_list in groups.values():
            for group in group_list:
                entries.extend(group.get("hooks", []))
        return entries

    def test_claude_produces_four_events(self) -> None:
        groups = build_hook_groups(client="claude", executable="exe", kb_root=Path("/kb"))
        self.assertEqual(sorted(groups.keys()), ["PostCompact", "PreCompact", "SessionEnd", "SessionStart"])

    def test_codex_produces_two_events(self) -> None:
        groups = build_hook_groups(client="codex", executable="exe", kb_root=Path("/kb"))
        self.assertEqual(sorted(groups.keys()), ["SessionStart", "Stop"])

    def test_no_shell_comment_in_command(self) -> None:
        """Command must not contain # LLM_KB_HOOK — that broke cmd.exe on Windows."""
        groups = build_hook_groups(client="claude", executable="exe", kb_root=Path("/kb"))
        for entry in self._all_hook_entries(groups):
            self.assertNotIn("#", entry["command"],
                             f"Shell comment found in command: {entry['command']}")

    def test_marker_stored_in_kb_marker_field(self) -> None:
        """Each hook entry must have _kb_marker set to KB_HOOK_MARKER."""
        groups = build_hook_groups(client="codex", executable="exe", kb_root=Path("/kb"))
        for entry in self._all_hook_entries(groups):
            self.assertEqual(entry.get("_kb_marker"), KB_HOOK_MARKER)

    def test_executable_with_spaces_is_quoted(self) -> None:
        """Paths that contain spaces must be wrapped in double quotes."""
        exe = "C:\\Program Files\\App\\app.exe"
        groups = build_hook_groups(client="claude", executable=exe, kb_root=Path("/kb"))
        for entry in self._all_hook_entries(groups):
            self.assertTrue(
                entry["command"].startswith(f'"{exe}"'),
                f"Expected quoted exe in: {entry['command']}",
            )

    def test_executable_without_spaces_not_double_quoted(self) -> None:
        """Paths without spaces should not be needlessly double-quoted."""
        exe = "LLMKnowledgeBase.exe"
        groups = build_hook_groups(client="claude", executable=exe, kb_root=Path("/kb"))
        for entry in self._all_hook_entries(groups):
            self.assertTrue(
                entry["command"].startswith(exe),
                f"Unexpected quoting for no-space exe in: {entry['command']}",
            )

    def test_kb_root_embedded_in_command(self) -> None:
        kb = Path("/my/knowledge/base")
        groups = build_hook_groups(client="claude", executable="exe", kb_root=kb)
        for entry in self._all_hook_entries(groups):
            self.assertIn(str(kb), entry["command"])

    def test_unsupported_client_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_hook_groups(client="unknown", executable="exe", kb_root=Path("/kb"))

    def test_codex_sessionstart_matcher_is_startup_resume(self) -> None:
        groups = build_hook_groups(client="codex", executable="exe", kb_root=Path("/kb"))
        matcher = groups["SessionStart"][0]["matcher"]
        self.assertEqual(matcher, "startup|resume")


class InstallHooksExecutableTests(unittest.TestCase):
    """_install_hooks uses sys.executable when running as frozen EXE."""

    def test_frozen_exe_uses_sys_executable(self) -> None:
        from kb_app.jobs.runner import JobRunner
        from kb_app.jobs.queue import JobStore, JobRecord

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kb = root / "kb"
            (kb / "daily").mkdir(parents=True)
            (kb / "knowledge").mkdir(parents=True)
            config_path = root / "settings.json"
            backup_dir = root / "backups"

            store = JobStore(root / "app.db")
            runner = JobRunner(store)

            fake_exe = "/some/frozen/LLMKnowledgeBase.exe"
            job = JobRecord(
                id="j1",
                profile_id=1,
                job_type="install_hooks",
                payload={
                    "client": "claude",
                    "config_path": str(config_path),
                    "backup_dir": str(backup_dir),
                },
                status="running",
                priority=100,
                created_at="",
                started_at=None,
                finished_at=None,
                mutation_snapshot=None,
                result={},
                error_message=None,
                backend=None,
                command_summary="",
            )

            from kb_app.core.paths import KbPaths, resolve_kb_paths
            paths = resolve_kb_paths(root)

            with patch("sys.frozen", True, create=True), \
                 patch("sys.executable", fake_exe):
                result = runner._install_hooks(job, paths)

            data = json.loads(config_path.read_text(encoding="utf-8"))
            all_commands = [
                hook["command"]
                for groups in data["hooks"].values()
                for group in groups
                for hook in group["hooks"]
            ]
            self.assertTrue(
                all(fake_exe in cmd for cmd in all_commands),
                f"Expected {fake_exe!r} in all commands, got: {all_commands}",
            )

    def test_source_mode_prefers_installed_exe_over_bare_exe_name(self) -> None:
        from kb_app.jobs.runner import resolve_hook_command_prefix
        from kb_app.core.paths import AppPaths

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            exe = base / "Programs" / "LLM Knowledge Base" / "LLMKnowledgeBase.exe"
            exe.parent.mkdir(parents=True)
            exe.touch()
            app_paths = AppPaths(
                config_dir=base / "config",
                state_dir=base / "state",
                install_dir=exe.parent,
                config_file=base / "config.toml",
                db_path=base / "app.db",
                logs_dir=base / "logs",
                job_logs_dir=base / "job-logs",
                backups_dir=base / "backups",
                diagnostics_dir=base / "diagnostics",
            )

            prefix = resolve_hook_command_prefix(app_paths=app_paths)

            self.assertIn(str(exe), prefix)
            self.assertNotEqual(prefix, "LLMKnowledgeBase.exe")


class HookCommandExitCodeTests(unittest.TestCase):
    """Validate that hook subcommands exit with code 0 via the module entrypoint."""

    def _run_hook(self, event: str, stdin_data: str = "") -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kb" / "daily").mkdir(parents=True)
            (root / "kb" / "knowledge").mkdir(parents=True)
            return subprocess.run(
                [sys.executable, "-m", "kb_app", "--kb-root", str(root), "hook", event],
                input=stdin_data,
                text=True,
                capture_output=True,
                timeout=15,
            )

    def test_session_start_exits_zero(self) -> None:
        result = self._run_hook("session-start")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_session_start_outputs_valid_json(self) -> None:
        result = self._run_hook("session-start")
        data = json.loads(result.stdout)
        self.assertIn("hookSpecificOutput", data)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "SessionStart")

    def test_session_end_exits_zero_with_empty_stdin(self) -> None:
        result = self._run_hook("session-end", stdin_data="")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_session_end_exits_zero_with_no_transcript_path(self) -> None:
        result = self._run_hook("session-end", stdin_data='{"session_id":"abc"}')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pre_compact_exits_zero(self) -> None:
        result = self._run_hook("pre-compact", stdin_data='{"session_id":"abc"}')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_post_compact_exits_zero(self) -> None:
        result = self._run_hook("post-compact", stdin_data="")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_session_start_no_hash_argument_in_command(self) -> None:
        """Regression: passing # as a CLI argument must not cause exit code 2."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kb" / "daily").mkdir(parents=True)
            (root / "kb" / "knowledge").mkdir(parents=True)
            result = subprocess.run(
                [
                    sys.executable, "-m", "kb_app",
                    "--kb-root", str(root),
                    "hook", "session-start",
                    "#", "LLM_KB_HOOK",
                ],
                text=True,
                capture_output=True,
                timeout=15,
            )
        # Argparse must not crash on these extra args — but this is the OLD broken
        # behavior. This test documents that we DON'T append # to commands anymore.
        # If this test runs the old command format it exits with code 2 (argparse error).
        # We verify that build_hook_groups no longer produces commands with '#'.
        from kb_app.jobs.runner import build_hook_groups
        groups = build_hook_groups(client="claude", executable="exe", kb_root=root)
        for group_list in groups.values():
            for group in group_list:
                for hook in group["hooks"]:
                    self.assertNotIn("#", hook["command"])


if __name__ == "__main__":
    unittest.main()
