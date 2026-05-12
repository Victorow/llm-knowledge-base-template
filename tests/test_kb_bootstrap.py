from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kb_app.core.paths import (
    default_kb_root,
    ensure_kb_layout,
    is_same_path,
    resolve_app_paths,
    validate_kb_root,
)
from kb_app.profiles.store import ProfileStore
from kb_app.ui.app import normalize_startup_kb_root


class KbBootstrapTests(unittest.TestCase):
    def test_default_windows_kb_root_uses_documents_not_install_dir(self) -> None:
        env = {
            "USERPROFILE": "C:/Users/me",
            "APPDATA": "C:/Users/me/AppData/Roaming",
            "LOCALAPPDATA": "C:/Users/me/AppData/Local",
        }

        root = default_kb_root(platform="win32", env=env)
        app_paths = resolve_app_paths(platform="win32", env=env)

        self.assertEqual(root, Path("C:/Users/me/Documents/LLM Knowledge Base"))
        self.assertFalse(is_same_path(root, app_paths.install_dir))

    def test_ensure_kb_layout_makes_empty_directory_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "LLM Knowledge Base"

            paths = ensure_kb_layout(root)

            self.assertTrue(validate_kb_root(root).valid)
            self.assertTrue(paths.agents_file.exists())
            self.assertTrue(paths.index_file.exists())
            self.assertTrue(paths.log_file.exists())

    def test_startup_repairs_active_profile_that_points_to_install_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            env = {
                "USERPROFILE": str(base / "User"),
                "APPDATA": str(base / "User" / "AppData" / "Roaming"),
                "LOCALAPPDATA": str(base / "User" / "AppData" / "Local"),
            }
            app_paths = resolve_app_paths(platform="win32", env=env)
            store = ProfileStore(base / "app.db")
            profile_id = store.create_profile("Broken", app_paths.install_dir)
            store.set_active_profile(profile_id)

            root = normalize_startup_kb_root(
                requested_root=app_paths.install_dir,
                profile_store=store,
                app_paths=app_paths,
                platform="win32",
                env=env,
            )

            repaired = store.get_active_profile()
            self.assertEqual(root, default_kb_root(platform="win32", env=env))
            self.assertEqual(Path(repaired.root_path), root)
            self.assertTrue(validate_kb_root(root).valid)


if __name__ == "__main__":
    unittest.main()
