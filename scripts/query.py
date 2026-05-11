"""Query the knowledge base using index-guided retrieval."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from kb_app.core.operations import run_query
from kb_app.core.paths import resolve_kb_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Query the personal knowledge base")
    parser.add_argument("question", help="The question to ask")
    parser.add_argument(
        "--file-back",
        action="store_true",
        help="File the answer back into the knowledge base as a Q&A article",
    )
    args = parser.parse_args()

    paths = resolve_kb_paths(ROOT_DIR)
    print(f"Question: {args.question}")
    print(f"File back: {'yes' if args.file_back else 'no'}")
    print("-" * 60)
    print(run_query(paths, args.question, file_back=args.file_back))

    if args.file_back:
        print("\n" + "-" * 60)
        qa_count = len(list(paths.qa_dir.glob("*.md"))) if paths.qa_dir.exists() else 0
        print(f"Answer filed to knowledge/qa/ ({qa_count} Q&A articles total)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
