#!/usr/bin/env bash
# End-of-day compile wrapper.
#
# Resolves the project root from this script's location, runs `compile.py`
# via uv, and appends output to scripts/compile.log. Designed to be called
# from launchd / cron / Task Scheduler — uses absolute paths and inherits
# nothing from the calling shell.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="$SCRIPT_DIR/compile.log"

# Make sure uv is on PATH when launched by launchd (which has a minimal env).
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

{
  echo ""
  echo "===== compile-daily.sh @ $(date -u +'%Y-%m-%dT%H:%M:%SZ') ====="
  cd "$ROOT_DIR"
  uv run --directory "$ROOT_DIR" python "$SCRIPT_DIR/compile.py"
} >> "$LOG_FILE" 2>&1
