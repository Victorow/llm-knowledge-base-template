from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kb_app.core.paths import resolve_app_paths, resolve_kb_paths, validate_kb_root


class PathResolutionTests(unittest.TestCase):
    def test_resolves_windows_user_paths_from_environment(self) -> None:
        env = {
            "APPDATA": "C:/Users/me/AppData/Roaming",
            "LOCALAPPDATA": "C:/Users/me/AppData/Local",
            "USERPROFILE": "C:/Users/me",
        }

        paths = resolve_app_paths(platform="win32", env=env)

        self.assertEqual(paths.config_dir, Path("C:/Users/me/AppData/Roaming/LLM Knowledge Base"))
        self.assertEqual(paths.state_dir, Path("C:/Users/me/AppData/Roaming/LLM Knowledge Base"))
        self.assertEqual(paths.install_dir, Path("C:/Users/me/AppData/Local/Programs/LLM Knowledge Base"))
        self.assertEqual(paths.db_path.name, "app.db")
        self.assertEqual(paths.config_file.name, "config.toml")
        self.assertEqual(paths.logs_dir.name, "logs")
        self.assertEqual(paths.job_logs_dir.name, "job-logs")

    def test_resolves_linux_xdg_paths_from_environment(self) -> None:
        env = {
            "HOME": "/home/me",
            "XDG_CONFIG_HOME": "/home/me/.config",
            "XDG_STATE_HOME": "/home/me/.local/state",
        }

        paths = resolve_app_paths(platform="linux", env=env)

        self.assertEqual(paths.config_dir, Path("/home/me/.config/llm-knowledge-base"))
        self.assertEqual(paths.state_dir, Path("/home/me/.local/state/llm-knowledge-base"))
        self.assertEqual(paths.install_dir, Path("/home/me/Applications/llm-knowledge-base"))
        self.assertEqual(paths.db_path, paths.state_dir / "app.db")

    def test_resolves_kb_paths_without_repo_root_assumption(self) -> None:
        root = Path("D:/KnowledgeBases/personal")

        paths = resolve_kb_paths(root)

        self.assertEqual(paths.root, root)
        self.assertEqual(paths.daily_dir, root / "kb" / "daily")
        self.assertEqual(paths.knowledge_dir, root / "kb" / "knowledge")
        self.assertEqual(paths.index_file, root / "kb" / "knowledge" / "index.md")
        self.assertEqual(paths.agents_file, root / "AGENTS.md")

    def test_validate_kb_root_reports_missing_required_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kb" / "daily").mkdir(parents=True)

            result = validate_kb_root(root)

        self.assertFalse(result.valid)
        self.assertIn("AGENTS.md", result.missing)
        self.assertIn("kb/knowledge", result.missing)


if __name__ == "__main__":
    unittest.main()
