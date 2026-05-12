"""End-to-end flow tests: profile → hooks → MCP → job runner.

These tests cover the happy path a new user follows after installation,
without requiring a real AI backend or display.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


class ProfileCreationFlowTest(unittest.TestCase):
    """First-run: create a profile and activate it."""

    def test_create_and_activate_profile(self):
        from kb_app.profiles.store import ProfileStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ProfileStore(Path(tmp) / "app.db")
            self.assertEqual(store.list_profiles(), [])

            profile_id = store.create_profile("Meu KB", tmp)
            store.set_active_profile(profile_id)

            active = store.get_active_profile()
            self.assertIsNotNone(active)
            self.assertEqual(active.name, "Meu KB")
            self.assertEqual(active.root_path, tmp)
            self.assertTrue(active.active)

    def test_no_active_profile_returns_none(self):
        from kb_app.profiles.store import ProfileStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ProfileStore(Path(tmp) / "app.db")
            self.assertIsNone(store.get_active_profile())


class HookInstallFlowTest(unittest.TestCase):
    """Job runner installs Claude Code and Codex hooks correctly."""

    def _make_env(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        kb_root = root / "kb"
        (kb_root / "daily").mkdir(parents=True)
        (kb_root / "knowledge").mkdir(parents=True)
        return tmp, root, kb_root

    def _make_runner(self, root):
        from kb_app.jobs.queue import JobStore
        from kb_app.jobs.runner import JobRunner
        from kb_app.profiles.store import ProfileStore

        db = root / "app.db"
        job_store = JobStore(db)
        profile_store = ProfileStore(db)
        runner = JobRunner(job_store, profile_store=profile_store)
        return job_store, profile_store, runner

    def test_install_claude_hooks(self):
        tmp, root, kb_root = self._make_env()
        with tmp:
            job_store, profile_store, runner = self._make_runner(root)
            config_path = root / "settings.json"

            profile_id = profile_store.create_profile("Test", str(kb_root))
            profile_store.set_active_profile(profile_id)

            job_id = job_store.enqueue(
                profile_id=profile_id,
                job_type="install_hooks",
                payload={
                    "client": "claude",
                    "config_path": str(config_path),
                    "backup_dir": str(root / "backups"),
                },
            )
            result = runner.run_next()
            self.assertEqual(result.status, "succeeded")

            cfg = json.loads(config_path.read_text())
            hooks_text = json.dumps(cfg)
            self.assertIn("LLM_KB_HOOK", hooks_text)
            self.assertIn("session-start", hooks_text)
            self.assertIn("session-end", hooks_text)

    def test_install_codex_hooks(self):
        tmp, root, kb_root = self._make_env()
        with tmp:
            job_store, profile_store, runner = self._make_runner(root)
            config_path = root / "hooks.json"

            profile_id = profile_store.create_profile("Test", str(kb_root))
            profile_store.set_active_profile(profile_id)

            job_id = job_store.enqueue(
                profile_id=profile_id,
                job_type="install_hooks",
                payload={
                    "client": "codex",
                    "config_path": str(config_path),
                    "backup_dir": str(root / "backups"),
                },
            )
            runner.run_next()

            cfg = json.loads(config_path.read_text())
            hooks_text = json.dumps(cfg)
            self.assertIn("LLM_KB_HOOK", hooks_text)
            self.assertIn("session-start", hooks_text)

    def test_remove_hooks_cleans_up(self):
        tmp, root, kb_root = self._make_env()
        with tmp:
            job_store, profile_store, runner = self._make_runner(root)
            config_path = root / "settings.json"

            profile_id = profile_store.create_profile("Test", str(kb_root))
            profile_store.set_active_profile(profile_id)

            # Install first
            job_store.enqueue(
                profile_id=profile_id,
                job_type="install_hooks",
                payload={
                    "client": "claude",
                    "config_path": str(config_path),
                    "backup_dir": str(root / "backups"),
                },
            )
            runner.run_next()
            self.assertIn("LLM_KB_HOOK", config_path.read_text())

            # Now remove
            job_store.enqueue(
                profile_id=profile_id,
                job_type="remove_hooks",
                payload={
                    "client": "claude",
                    "config_path": str(config_path),
                    "backup_dir": str(root / "backups"),
                },
            )
            runner.run_next()
            self.assertNotIn("LLM_KB_HOOK", config_path.read_text())


class McpSetupFlowTest(unittest.TestCase):
    """setup-mcp CLI configures Claude and Codex correctly."""

    def _mcp_args(self, tmp: str, claude_cfg, claude_code_cfg, codex_cfg) -> list:
        return [
            "--claude-config",      str(claude_cfg),
            "--claude-code-config", str(claude_code_cfg),
            "--codex-config",       str(codex_cfg),
        ]

    def test_setup_mcp_both_clients_via_cli(self):
        """Simulate: LLMKnowledgeBase setup-mcp --client both --kb-root ..."""
        from kb_app.__main__ import main

        with tempfile.TemporaryDirectory() as tmp:
            kb_root         = Path(tmp) / "kb"
            kb_root.mkdir()
            claude_cfg      = Path(tmp) / "claude_desktop_config.json"
            claude_code_cfg = Path(tmp) / "claude.json"
            codex_cfg       = Path(tmp) / "codex_config.toml"

            rc = main([
                "--kb-root", str(kb_root),
                "setup-mcp", "--client", "both",
                *self._mcp_args(tmp, claude_cfg, claude_code_cfg, codex_cfg),
            ])
            self.assertEqual(rc, 0)

            # Claude Desktop JSON
            self.assertTrue(claude_cfg.exists())
            cfg = json.loads(claude_cfg.read_text())
            self.assertIn("llm-knowledge-base", cfg["mcpServers"])

            # Claude Code CLI JSON
            self.assertTrue(claude_code_cfg.exists())
            cli_cfg = json.loads(claude_code_cfg.read_text())
            self.assertIn("llm-knowledge-base", cli_cfg["mcpServers"])
            self.assertEqual(cli_cfg["mcpServers"]["llm-knowledge-base"]["type"], "stdio")

            # Codex TOML
            self.assertTrue(codex_cfg.exists())
            self.assertIn("[mcp_servers.llm-knowledge-base]", codex_cfg.read_text())

    def test_setup_mcp_status_both_clients(self, capsys=None):
        from kb_app.__main__ import main

        with tempfile.TemporaryDirectory() as tmp:
            kb_root         = Path(tmp) / "kb"
            kb_root.mkdir()
            claude_cfg      = Path(tmp) / "claude_desktop_config.json"
            claude_code_cfg = Path(tmp) / "claude.json"
            codex_cfg       = Path(tmp) / "codex_config.toml"
            extra = self._mcp_args(tmp, claude_cfg, claude_code_cfg, codex_cfg)

            main(["--kb-root", str(kb_root), "setup-mcp", "--client", "both", *extra])

            rc = main([
                "--kb-root", str(kb_root),
                "setup-mcp", "--status", "--client", "both", *extra,
            ])
            self.assertEqual(rc, 0)

    def test_setup_mcp_remove_both_clients(self):
        from kb_app.__main__ import main
        from kb_app.core.mcp_setup import (
            mcp_is_configured,
            mcp_is_configured_claude_code,
            mcp_is_configured_codex,
        )

        with tempfile.TemporaryDirectory() as tmp:
            kb_root         = Path(tmp) / "kb"
            kb_root.mkdir()
            claude_cfg      = Path(tmp) / "claude_desktop_config.json"
            claude_code_cfg = Path(tmp) / "claude.json"
            codex_cfg       = Path(tmp) / "codex_config.toml"
            extra = self._mcp_args(tmp, claude_cfg, claude_code_cfg, codex_cfg)

            main(["--kb-root", str(kb_root), "setup-mcp", "--client", "both", *extra])
            main(["--kb-root", str(kb_root), "setup-mcp", "--remove", "--client", "both", *extra])

            self.assertFalse(mcp_is_configured(config_path=claude_cfg))
            self.assertFalse(mcp_is_configured_claude_code(config_path=claude_code_cfg))
            self.assertFalse(mcp_is_configured_codex(config_path=codex_cfg))


class JobRunnerTimerIntegrationTest(unittest.TestCase):
    """Verify that queued jobs complete when runner.run_next() is called."""

    def test_queued_job_executes_on_run_next(self):
        from kb_app.jobs.queue import JobStore
        from kb_app.jobs.runner import JobRunner

        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp) / "app.db")
            called = []
            runner = JobRunner(store, handlers={"test_action": lambda j: called.append(1) or {}})

            job_id = store.enqueue(profile_id=1, job_type="test_action")
            self.assertEqual(store.get_job(job_id).status, "queued")

            result = runner.run_next()
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(store.get_job(job_id).status, "succeeded")
            self.assertEqual(len(called), 1)

    def test_idle_when_no_jobs(self):
        from kb_app.jobs.queue import JobStore
        from kb_app.jobs.runner import JobRunner

        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp) / "app.db")
            runner = JobRunner(store)
            result = runner.run_next()
            self.assertEqual(result.status, "idle")


class UiFirstRunTest(unittest.TestCase):
    """Tutorial page and first-run dialog load without errors (offscreen)."""

    def test_tutorial_page_exists_in_registry(self):
        from kb_app.ui.app import PAGE_REGISTRY
        titles = [p.title for p in PAGE_REGISTRY]
        self.assertIn("Tutorial", titles)
        self.assertEqual(titles[0], "Tutorial")  # Must be first

    def test_window_constructs_with_tutorial_page(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6 import QtWidgets
        from kb_app.ui.app import ControlPanelWindow, PAGE_REGISTRY

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "kb"
            (root / "kb" / "daily").mkdir(parents=True)
            (root / "kb" / "knowledge").mkdir(parents=True)
            window = ControlPanelWindow(root, Path(tmp) / "app.db")
            self.assertEqual(window.stack.count(), len(PAGE_REGISTRY))

    def test_first_run_dialog_can_open_without_window_flag_type_error(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6 import QtWidgets
        from kb_app.ui.app import ControlPanelWindow

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "kb"
            window = ControlPanelWindow(root, Path(tmp) / "app.db")
            with mock.patch.object(QtWidgets.QDialog, "exec", return_value=0):
                window._show_first_run_dialog()


if __name__ == "__main__":
    unittest.main()
