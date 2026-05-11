"""Lint the knowledge base for structural and semantic health."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from kb_app.core.operations import run_lint
from kb_app.core.paths import resolve_kb_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint the knowledge base")
    parser.add_argument(
        "--structural-only",
        action="store_true",
        help="Skip LLM-based checks (contradictions) - faster and free",
    )
    args = parser.parse_args()

    paths = resolve_kb_paths(ROOT_DIR)
    print("Running knowledge base lint checks...")
    result = run_lint(paths, structural_only=args.structural_only)

    if result.report_path:
        print(f"\nReport saved to: {result.report_path}")

    print(
        f"\nResults: {result.errors} errors, "
        f"{result.warnings} warnings, {result.suggestions} suggestions"
    )

    if result.errors:
        print("\nErrors found - knowledge base needs attention!")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
