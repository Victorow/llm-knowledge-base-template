from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


class PackagingFilesTests(unittest.TestCase):
    def test_packaging_files_exist(self) -> None:
        root = Path(__file__).resolve().parent.parent
        expected = [
            root / "packaging" / "pyinstaller" / "llm-knowledge-base.spec",
            root / "packaging" / "inno" / "llm-knowledge-base.iss",
            root / "packaging" / "linux" / "install.sh",
            root / "packaging" / "linux" / "uninstall.sh",
            root / "packaging" / "linux" / "llm-knowledge-base.desktop.template",
            root / "scripts" / "build-windows.ps1",
            root / "scripts" / "build-linux.sh",
            root / "scripts" / "smoke-packaged.py",
        ]

        for path in expected:
            self.assertTrue(path.exists(), f"Missing {path}")

    def test_inno_installer_is_user_level_and_does_not_install_hooks(self) -> None:
        root = Path(__file__).resolve().parent.parent
        content = (root / "packaging" / "inno" / "llm-knowledge-base.iss").read_text(
            encoding="utf-8"
        )

        self.assertIn("PrivilegesRequired=lowest", content)
        self.assertIn("{localappdata}\\Programs\\LLM Knowledge Base", content)
        self.assertNotIn(".claude", content)
        self.assertNotIn(".codex", content)

    def test_linux_installer_uses_user_directories(self) -> None:
        root = Path(__file__).resolve().parent.parent
        content = (root / "packaging" / "linux" / "install.sh").read_text(encoding="utf-8")

        self.assertIn("${HOME}/Applications/llm-knowledge-base", content)
        self.assertIn("${HOME}/.local/share/applications", content)
        self.assertNotIn("sudo", content)

    def test_smoke_packaged_python_module_mode(self) -> None:
        root = Path(__file__).resolve().parent.parent
        completed = subprocess.run(
            [sys.executable, "scripts/smoke-packaged.py", "--python-module"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Smoke passed", completed.stdout)


if __name__ == "__main__":
    unittest.main()
