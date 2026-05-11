"""PreCompact hook wrapper."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kb_app.core.paths import resolve_kb_paths
from kb_app.hooks.commands import capture_hook


def main() -> None:
    capture_hook(
        sys.stdin.read(),
        resolve_kb_paths(ROOT),
        min_turns=5,
        context_prefix="flush-context",
        spawn_flush=True,
    )


if __name__ == "__main__":
    main()
