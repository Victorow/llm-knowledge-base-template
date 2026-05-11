"""Single executable entrypoint for source and packaged runs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kb_app.core.paths import resolve_kb_paths
from kb_app.hooks.commands import capture_hook, render_session_start_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="llm-knowledge-base")
    parser.add_argument(
        "--kb-root",
        default=str(Path.cwd()),
        help="Knowledge base root directory",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    hook_parser = subparsers.add_parser("hook", help="Run AI-client hook command")
    hook_parser.add_argument(
        "hook_event",
        choices=["session-start", "session-end", "pre-compact"],
    )

    args = parser.parse_args(argv)
    paths = resolve_kb_paths(Path(args.kb_root))

    if args.command == "hook":
        if args.hook_event == "session-start":
            print(render_session_start_json(paths))
            return 0
        if args.hook_event == "session-end":
            capture_hook(sys.stdin.read(), paths, min_turns=1, context_prefix="session-flush")
            return 0
        if args.hook_event == "pre-compact":
            capture_hook(sys.stdin.read(), paths, min_turns=5, context_prefix="flush-context")
            return 0

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
