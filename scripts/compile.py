"""Compile daily conversation logs into structured knowledge articles."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from kb_app.core.operations import compile_logs
from kb_app.core.paths import resolve_kb_paths
from kb_app.core.costs import format_llm_usage_estimate
from kb_app.core.wiki import list_wiki_articles


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile daily logs into knowledge articles")
    parser.add_argument("--all", action="store_true", help="Force recompile all logs")
    parser.add_argument("--file", type=str, help="Compile a specific daily log file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be compiled")
    args = parser.parse_args()

    paths = resolve_kb_paths(ROOT_DIR)
    try:
        result = compile_logs(
            paths,
            force_all=args.all,
            file_name=args.file,
            dry_run=args.dry_run,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    if not result.files:
        print("Nothing to compile - all daily logs are up to date.")
        return 0

    print(f"{'[DRY RUN] ' if result.dry_run else ''}Files to compile ({len(result.files)}):")
    for file_name in result.files:
        print(f"  - {file_name}")

    if not result.dry_run:
        articles = list_wiki_articles(paths)
        print("\nCompilation complete.")
        print(format_llm_usage_estimate(result.total_cost))
        print(f"Knowledge base: {len(articles)} articles")

    return 0


if __name__ == "__main__":
    sys.exit(main())
