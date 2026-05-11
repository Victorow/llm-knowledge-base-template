"""Provider-neutral hook command helpers."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from kb_app.core.paths import KbPaths
from kb_app.core.transcripts import extract_conversation_context
from kb_app.core.wiki import read_wiki_index

MAX_CONTEXT_CHARS = 20_000
MAX_LOG_LINES = 30


@dataclass(frozen=True)
class HookCaptureResult:
    status: str
    reason: str = ""
    context_file: Path | None = None
    turn_count: int = 0


def render_session_start_json(paths: KbPaths) -> str:
    """Render Claude/Codex-compatible SessionStart JSON output."""
    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": build_session_context(paths),
        }
    }
    return json.dumps(output)


def build_session_context(paths: KbPaths) -> str:
    """Build the context injected at session start."""
    today = datetime.now(timezone.utc).astimezone()
    parts = [f"## Today\n{today.strftime('%A, %B %d, %Y')}"]
    parts.append(f"## Knowledge Base Index\n\n{read_wiki_index(paths)}")
    parts.append(f"## Recent Daily Log\n\n{get_recent_log(paths)}")
    context = "\n\n---\n\n".join(parts)

    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n\n...(truncated)"
    return context


def get_recent_log(paths: KbPaths) -> str:
    """Read today's/yesterday's daily log, falling back to latest available."""
    today = datetime.now(timezone.utc).astimezone()
    candidates = []
    for offset in range(2):
        date = today - timedelta(days=offset)
        candidates.append(paths.daily_dir / f"{date.strftime('%Y-%m-%d')}.md")

    if paths.daily_dir.exists():
        candidates.extend(sorted(paths.daily_dir.glob("*.md"), reverse=True))

    seen: set[Path] = set()
    for log_path in candidates:
        if log_path in seen:
            continue
        seen.add(log_path)
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8").splitlines()
            recent = lines[-MAX_LOG_LINES:] if len(lines) > MAX_LOG_LINES else lines
            return "\n".join(recent)

    return "(no recent daily log)"


def capture_hook(
    raw_input: str,
    paths: KbPaths,
    *,
    state_dir: Path | None = None,
    min_turns: int = 1,
    max_turns: int = 30,
    max_context_chars: int = 15_000,
    context_prefix: str = "session-flush",
    spawn_flush: bool = True,
) -> HookCaptureResult:
    """Extract transcript context and optionally spawn background flush."""
    if os.environ.get("CLAUDE_INVOKED_BY") or os.environ.get("KB_INVOKED_BY"):
        return HookCaptureResult(status="skipped", reason="recursion guard")

    try:
        hook_input = parse_hook_input(raw_input)
    except (json.JSONDecodeError, ValueError) as e:
        return HookCaptureResult(status="skipped", reason=f"invalid input: {e}")

    session_id = str(hook_input.get("session_id", "unknown"))
    transcript_path_str = hook_input.get("transcript_path", "")
    if not transcript_path_str or not isinstance(transcript_path_str, str):
        return HookCaptureResult(status="skipped", reason="no transcript path")

    transcript_path = Path(transcript_path_str)
    if not transcript_path.exists():
        return HookCaptureResult(status="skipped", reason="transcript missing")

    context, turn_count = extract_conversation_context(
        transcript_path,
        max_turns=max_turns,
        max_context_chars=max_context_chars,
    )
    if not context.strip():
        return HookCaptureResult(status="skipped", reason="empty context", turn_count=turn_count)
    if turn_count < min_turns:
        return HookCaptureResult(status="skipped", reason="too few turns", turn_count=turn_count)

    target_state_dir = state_dir or paths.scripts_dir
    target_state_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    context_file = (
        target_state_dir
        / f"{context_prefix}-{safe_filename_fragment(session_id)}-{timestamp}.md"
    )
    context_file.write_text(context, encoding="utf-8")

    if spawn_flush:
        spawn_flush_process(paths, context_file, session_id)

    return HookCaptureResult(
        status="captured",
        context_file=context_file,
        turn_count=turn_count,
    )


def parse_hook_input(raw_input: str) -> dict:
    """Parse hook JSON, tolerating unescaped Windows backslashes from older clients."""
    try:
        parsed = json.loads(raw_input or "{}")
    except json.JSONDecodeError:
        fixed_input = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r"\\\\", raw_input)
        parsed = json.loads(fixed_input)
    if not isinstance(parsed, dict):
        raise ValueError("hook input must be a JSON object")
    return parsed


def safe_filename_fragment(value: str) -> str:
    """Return a conservative filename fragment for hook-provided ids."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")[:120] or "unknown"


def spawn_flush_process(paths: KbPaths, context_file: Path, session_id: str) -> None:
    """Spawn the source-tree flush worker without blocking the hook lifecycle."""
    flush_script = paths.scripts_dir / "flush.py"
    command = [
        "uv",
        "run",
        "--directory",
        str(paths.root),
        "python",
        str(flush_script),
        str(context_file),
        session_id,
    ]

    popen_kwargs = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        popen_kwargs["start_new_session"] = True

    subprocess.Popen(command, **popen_kwargs)
