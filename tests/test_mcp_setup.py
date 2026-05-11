"""Tests for MCP configuration — Claude Code (JSON) and Codex (TOML)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kb_app.core.mcp_setup import (
    configure_mcp,
    configure_mcp_claude_code,
    configure_mcp_codex,
    mcp_is_configured,
    mcp_is_configured_claude_code,
    mcp_is_configured_codex,
    remove_mcp,
    remove_mcp_claude_code,
    remove_mcp_codex,
)


class ClaudeMcpTests(unittest.TestCase):
    """configure_mcp / remove_mcp / mcp_is_configured — JSON format."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tmp.name) / "claude_desktop_config.json"
        self.kb_root = Path(self.tmp.name) / "kb"

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_config_when_absent(self):
        configure_mcp(self.kb_root, config_path=self.config_path)
        self.assertTrue(self.config_path.exists())

    def test_entry_present_after_configure(self):
        configure_mcp(self.kb_root, config_path=self.config_path)
        cfg = json.loads(self.config_path.read_text())
        self.assertIn("llm-knowledge-base", cfg["mcpServers"])

    def test_is_configured_returns_true_after_configure(self):
        configure_mcp(self.kb_root, config_path=self.config_path)
        self.assertTrue(mcp_is_configured(config_path=self.config_path))

    def test_is_configured_returns_false_when_absent(self):
        self.assertFalse(mcp_is_configured(config_path=self.config_path))

    def test_uses_exe_path_when_provided(self):
        exe = Path(self.tmp.name) / "LLMKnowledgeBase.exe"
        exe.touch()
        configure_mcp(self.kb_root, exe_path=exe, config_path=self.config_path)
        cfg = json.loads(self.config_path.read_text())
        entry = cfg["mcpServers"]["llm-knowledge-base"]
        self.assertEqual(entry["command"], str(exe))

    def test_falls_back_to_uv_when_no_exe(self):
        configure_mcp(self.kb_root, config_path=self.config_path)
        cfg = json.loads(self.config_path.read_text())
        entry = cfg["mcpServers"]["llm-knowledge-base"]
        self.assertEqual(entry["command"], "uv")

    def test_preserves_existing_keys(self):
        self.config_path.write_text(json.dumps({"otherKey": 42}))
        configure_mcp(self.kb_root, config_path=self.config_path)
        cfg = json.loads(self.config_path.read_text())
        self.assertEqual(cfg["otherKey"], 42)

    def test_creates_backup_when_config_exists(self):
        self.config_path.write_text(json.dumps({"existing": True}))
        configure_mcp(self.kb_root, config_path=self.config_path)
        backups = list(Path(self.tmp.name).glob("*.backup-*.json"))
        self.assertGreater(len(backups), 0)

    def test_remove_deletes_entry(self):
        configure_mcp(self.kb_root, config_path=self.config_path)
        remove_mcp(config_path=self.config_path)
        cfg = json.loads(self.config_path.read_text())
        self.assertNotIn("llm-knowledge-base", cfg.get("mcpServers", {}))

    def test_remove_returns_none_when_not_configured(self):
        result = remove_mcp(config_path=self.config_path)
        self.assertIsNone(result)

    def test_is_configured_false_after_remove(self):
        configure_mcp(self.kb_root, config_path=self.config_path)
        remove_mcp(config_path=self.config_path)
        self.assertFalse(mcp_is_configured(config_path=self.config_path))

    def test_configure_overwrites_existing_entry(self):
        configure_mcp(self.kb_root, config_path=self.config_path)
        new_root = Path(self.tmp.name) / "new_kb"
        configure_mcp(new_root, config_path=self.config_path)
        cfg = json.loads(self.config_path.read_text())
        args = cfg["mcpServers"]["llm-knowledge-base"]["args"]
        self.assertIn(str(new_root), args)


class CodexMcpTests(unittest.TestCase):
    """configure_mcp_codex / remove_mcp_codex / mcp_is_configured_codex — TOML format."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tmp.name) / "config.toml"
        self.kb_root = Path(self.tmp.name) / "kb"

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_toml_when_absent(self):
        configure_mcp_codex(self.kb_root, config_path=self.config_path)
        self.assertTrue(self.config_path.exists())

    def test_entry_present_in_toml(self):
        configure_mcp_codex(self.kb_root, config_path=self.config_path)
        text = self.config_path.read_text()
        self.assertIn("[mcp_servers.llm-knowledge-base]", text)

    def test_is_configured_returns_true_after_configure(self):
        configure_mcp_codex(self.kb_root, config_path=self.config_path)
        self.assertTrue(mcp_is_configured_codex(config_path=self.config_path))

    def test_is_configured_returns_false_when_absent(self):
        self.assertFalse(mcp_is_configured_codex(config_path=self.config_path))

    def test_uses_exe_path_when_provided(self):
        exe = Path(self.tmp.name) / "LLMKnowledgeBase"
        exe.touch()
        configure_mcp_codex(self.kb_root, exe_path=exe, config_path=self.config_path)
        text = self.config_path.read_text()
        self.assertIn(str(exe).replace("\\", "\\\\"), text)

    def test_falls_back_to_uv_when_no_exe(self):
        configure_mcp_codex(self.kb_root, config_path=self.config_path)
        text = self.config_path.read_text()
        self.assertIn('command = "uv"', text)

    def test_preserves_existing_toml_content(self):
        self.config_path.write_text("[features]\ncodex_hooks = true\n")
        configure_mcp_codex(self.kb_root, config_path=self.config_path)
        text = self.config_path.read_text()
        self.assertIn("codex_hooks = true", text)
        self.assertIn("[mcp_servers.llm-knowledge-base]", text)

    def test_creates_backup_when_config_exists(self):
        self.config_path.write_text("[features]\ncodex_hooks = true\n")
        configure_mcp_codex(self.kb_root, config_path=self.config_path)
        backups = list(Path(self.tmp.name).glob("*.backup-*.toml"))
        self.assertGreater(len(backups), 0)

    def test_remove_deletes_section(self):
        configure_mcp_codex(self.kb_root, config_path=self.config_path)
        remove_mcp_codex(config_path=self.config_path)
        text = self.config_path.read_text()
        self.assertNotIn("[mcp_servers.llm-knowledge-base]", text)

    def test_remove_returns_none_when_not_configured(self):
        result = remove_mcp_codex(config_path=self.config_path)
        self.assertIsNone(result)

    def test_is_configured_false_after_remove(self):
        configure_mcp_codex(self.kb_root, config_path=self.config_path)
        remove_mcp_codex(config_path=self.config_path)
        self.assertFalse(mcp_is_configured_codex(config_path=self.config_path))

    def test_configure_replaces_existing_section(self):
        configure_mcp_codex(self.kb_root, config_path=self.config_path)
        new_root = Path(self.tmp.name) / "new_kb"
        configure_mcp_codex(new_root, config_path=self.config_path)
        text = self.config_path.read_text()
        self.assertIn(str(new_root).replace("\\", "\\\\"), text)
        # Should appear only once
        self.assertEqual(text.count("[mcp_servers.llm-knowledge-base]"), 1)

    def test_repeated_configure_leaves_no_args_fragment(self):
        """Running configure twice must not leave orphaned args=[...] lines.

        The old regex stopped at the first '[' inside the section body,
        which meant the 'args = [...]' line was split and its tail
        '["--kb-root", ...]' was left behind as invalid TOML.
        """
        configure_mcp_codex(self.kb_root, config_path=self.config_path)
        configure_mcp_codex(self.kb_root, config_path=self.config_path)
        configure_mcp_codex(self.kb_root, config_path=self.config_path)
        text = self.config_path.read_text()
        # The section must appear exactly once
        self.assertEqual(text.count("[mcp_servers.llm-knowledge-base]"), 1)
        # No orphaned array fragments starting a line
        self.assertNotIn('["--kb-root"', text)
        self.assertNotIn('["mcp"', text)
        # The args value must still be present and correct
        self.assertIn('args = [', text)

    def test_windows_backslashes_escaped(self):
        """Paths with backslashes must be TOML-escaped."""
        win_root = Path("C:\\Users\\Test\\kb")
        configure_mcp_codex(win_root, config_path=self.config_path)
        text = self.config_path.read_text()
        # Backslashes in TOML strings must be doubled
        self.assertIn("C:\\\\Users\\\\Test\\\\kb", text)


class ClaudeCodeCliMcpTests(unittest.TestCase):
    """configure_mcp_claude_code / remove_mcp_claude_code — ~/.claude.json format."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tmp.name) / "claude.json"
        self.kb_root = Path(self.tmp.name) / "kb"

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_config_when_absent(self):
        configure_mcp_claude_code(self.kb_root, config_path=self.config_path)
        self.assertTrue(self.config_path.exists())

    def test_entry_present_after_configure(self):
        configure_mcp_claude_code(self.kb_root, config_path=self.config_path)
        cfg = json.loads(self.config_path.read_text())
        self.assertIn("llm-knowledge-base", cfg["mcpServers"])

    def test_type_field_is_stdio(self):
        configure_mcp_claude_code(self.kb_root, config_path=self.config_path)
        cfg = json.loads(self.config_path.read_text())
        entry = cfg["mcpServers"]["llm-knowledge-base"]
        self.assertEqual(entry["type"], "stdio")

    def test_args_order_kb_root_before_mcp(self):
        """--kb-root must come before 'mcp' subcommand in the args list."""
        exe = Path(self.tmp.name) / "LLMKnowledgeBase.exe"
        exe.touch()
        configure_mcp_claude_code(self.kb_root, exe_path=exe, config_path=self.config_path)
        cfg = json.loads(self.config_path.read_text())
        args = cfg["mcpServers"]["llm-knowledge-base"]["args"]
        kb_idx  = args.index("--kb-root")
        mcp_idx = args.index("mcp")
        self.assertLess(kb_idx, mcp_idx, "--kb-root must come before 'mcp'")

    def test_is_configured_returns_true_after_configure(self):
        configure_mcp_claude_code(self.kb_root, config_path=self.config_path)
        self.assertTrue(mcp_is_configured_claude_code(config_path=self.config_path))

    def test_is_configured_returns_false_when_absent(self):
        self.assertFalse(mcp_is_configured_claude_code(config_path=self.config_path))

    def test_preserves_existing_keys(self):
        self.config_path.write_text(json.dumps({"numStartups": 5}))
        configure_mcp_claude_code(self.kb_root, config_path=self.config_path)
        cfg = json.loads(self.config_path.read_text())
        self.assertEqual(cfg["numStartups"], 5)

    def test_remove_deletes_entry(self):
        configure_mcp_claude_code(self.kb_root, config_path=self.config_path)
        remove_mcp_claude_code(config_path=self.config_path)
        cfg = json.loads(self.config_path.read_text())
        self.assertNotIn("llm-knowledge-base", cfg.get("mcpServers", {}))

    def test_remove_returns_none_when_not_configured(self):
        result = remove_mcp_claude_code(config_path=self.config_path)
        self.assertIsNone(result)

    def test_is_configured_false_after_remove(self):
        configure_mcp_claude_code(self.kb_root, config_path=self.config_path)
        remove_mcp_claude_code(config_path=self.config_path)
        self.assertFalse(mcp_is_configured_claude_code(config_path=self.config_path))


class BothClientsMcpTests(unittest.TestCase):
    """Test configuring both Claude and Codex in sequence (as the installer does)."""

    def test_configure_both_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            claude_cfg      = Path(tmp) / "claude_desktop_config.json"
            claude_code_cfg = Path(tmp) / "claude.json"
            codex_cfg       = Path(tmp) / "config.toml"
            kb_root         = Path(tmp) / "kb"

            configure_mcp(kb_root, config_path=claude_cfg)
            configure_mcp_claude_code(kb_root, config_path=claude_code_cfg)
            configure_mcp_codex(kb_root, config_path=codex_cfg)

            self.assertTrue(mcp_is_configured(config_path=claude_cfg))
            self.assertTrue(mcp_is_configured_claude_code(config_path=claude_code_cfg))
            self.assertTrue(mcp_is_configured_codex(config_path=codex_cfg))

    def test_remove_both_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            claude_cfg      = Path(tmp) / "claude_desktop_config.json"
            claude_code_cfg = Path(tmp) / "claude.json"
            codex_cfg       = Path(tmp) / "config.toml"
            kb_root         = Path(tmp) / "kb"

            configure_mcp(kb_root, config_path=claude_cfg)
            configure_mcp_claude_code(kb_root, config_path=claude_code_cfg)
            configure_mcp_codex(kb_root, config_path=codex_cfg)

            remove_mcp(config_path=claude_cfg)
            remove_mcp_claude_code(config_path=claude_code_cfg)
            remove_mcp_codex(config_path=codex_cfg)

            self.assertFalse(mcp_is_configured(config_path=claude_cfg))
            self.assertFalse(mcp_is_configured_claude_code(config_path=claude_code_cfg))
            self.assertFalse(mcp_is_configured_codex(config_path=codex_cfg))


if __name__ == "__main__":
    unittest.main()
