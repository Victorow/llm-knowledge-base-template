from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test packaged app entrypoints")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--python-module", action="store_true")
    mode.add_argument("--exe", type=Path)
    args = parser.parse_args()

    if args.python_module:
        base_command = [sys.executable, "-m", "kb_app"]
    else:
        base_command = [str(args.exe)]

    with tempfile.TemporaryDirectory() as tmp:
        kb_root = Path(tmp) / "kb-root"
        (kb_root / "kb" / "daily").mkdir(parents=True)
        (kb_root / "kb" / "knowledge").mkdir(parents=True)
        (kb_root / "kb" / "knowledge" / "index.md").write_text(
            "# Knowledge Base Index\n\n| Article | Summary | Compiled From | Updated |",
            encoding="utf-8",
        )
        (kb_root / "AGENTS.md").write_text("# Schema", encoding="utf-8")

        run_checked(base_command + ["--help"])
        hook = run_checked(base_command + ["--kb-root", str(kb_root), "hook", "session-start"])
        json.loads(hook.stdout)
        compile_result = run_checked(
            base_command + ["--kb-root", str(kb_root), "compile", "--dry-run"]
        )
        if "Nothing to compile" not in compile_result.stdout:
            raise AssertionError(compile_result.stdout)

    print("Smoke passed")
    return 0


def run_checked(command: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(command)}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


if __name__ == "__main__":
    raise SystemExit(main())
