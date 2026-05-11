from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


class ScriptWrapperTests(unittest.TestCase):
    def test_compile_script_runs_directly_from_scripts_path(self) -> None:
        root = Path(__file__).resolve().parent.parent

        completed = subprocess.run(
            [sys.executable, "scripts/compile.py", "--dry-run"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
