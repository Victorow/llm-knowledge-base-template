"""SessionStart hook wrapper."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kb_app.core.paths import resolve_kb_paths
from kb_app.hooks.commands import render_session_start_json


def main() -> None:
    print(render_session_start_json(resolve_kb_paths(ROOT)))


if __name__ == "__main__":
    main()
