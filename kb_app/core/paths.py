"""Path resolution for app data and knowledge-base data."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


APP_NAME_WINDOWS = "LLM Knowledge Base"
APP_NAME_POSIX = "llm-knowledge-base"


@dataclass(frozen=True)
class AppPaths:
    config_dir: Path
    state_dir: Path
    install_dir: Path
    config_file: Path
    db_path: Path
    logs_dir: Path
    job_logs_dir: Path
    backups_dir: Path
    diagnostics_dir: Path


@dataclass(frozen=True)
class KbPaths:
    root: Path
    kb_dir: Path
    daily_dir: Path
    knowledge_dir: Path
    concepts_dir: Path
    connections_dir: Path
    qa_dir: Path
    reports_dir: Path
    agents_file: Path
    context_file: Path
    index_file: Path
    log_file: Path
    scripts_dir: Path
    hooks_dir: Path
    state_file: Path
    last_flush_file: Path
    flush_log_file: Path


@dataclass(frozen=True)
class KbValidationResult:
    valid: bool
    missing: list[str]
    root: Path


def default_kb_root(
    *,
    platform: str | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Return the default user data directory for the knowledge base.

    This must be separate from the application install directory. Hooks and MCP
    should point here (or to an explicit profile root), never to the packaged
    executable folder.
    """
    selected_platform = platform or sys.platform
    selected_env = env or os.environ

    if selected_platform.startswith("win"):
        user_profile = Path(selected_env.get("USERPROFILE", str(Path.home())))
        return user_profile / "Documents" / APP_NAME_WINDOWS

    home = Path(selected_env.get("HOME", str(Path.home())))
    return home / "Documents" / APP_NAME_WINDOWS


def resolve_app_paths(
    *,
    platform: str | None = None,
    env: Mapping[str, str] | None = None,
) -> AppPaths:
    """Resolve per-user app paths without touching the filesystem."""
    selected_platform = platform or sys.platform
    selected_env = env or os.environ

    if selected_platform.startswith("win"):
        user_profile = Path(selected_env.get("USERPROFILE", str(Path.home())))
        roaming = Path(
            selected_env.get("APPDATA", str(user_profile / "AppData" / "Roaming"))
        )
        local = Path(
            selected_env.get("LOCALAPPDATA", str(user_profile / "AppData" / "Local"))
        )
        config_dir = roaming / APP_NAME_WINDOWS
        state_dir = config_dir
        install_dir = local / "Programs" / APP_NAME_WINDOWS
    else:
        home = Path(selected_env.get("HOME", str(Path.home())))
        config_home = Path(selected_env.get("XDG_CONFIG_HOME", str(home / ".config")))
        state_home = Path(selected_env.get("XDG_STATE_HOME", str(home / ".local" / "state")))
        config_dir = config_home / APP_NAME_POSIX
        state_dir = state_home / APP_NAME_POSIX
        install_dir = home / "Applications" / APP_NAME_POSIX

    return AppPaths(
        config_dir=config_dir,
        state_dir=state_dir,
        install_dir=install_dir,
        config_file=config_dir / "config.toml",
        db_path=state_dir / "app.db",
        logs_dir=state_dir / "logs",
        job_logs_dir=state_dir / "job-logs",
        backups_dir=state_dir / "backups",
        diagnostics_dir=state_dir / "diagnostics",
    )


def resolve_kb_paths(root: str | Path) -> KbPaths:
    """Resolve all KB paths from an explicit KB root."""
    root_path = Path(root)
    kb_dir = root_path / "kb"
    knowledge_dir = kb_dir / "knowledge"
    scripts_dir = root_path / "scripts"

    return KbPaths(
        root=root_path,
        kb_dir=kb_dir,
        daily_dir=kb_dir / "daily",
        knowledge_dir=knowledge_dir,
        concepts_dir=knowledge_dir / "concepts",
        connections_dir=knowledge_dir / "connections",
        qa_dir=knowledge_dir / "qa",
        reports_dir=root_path / "reports",
        agents_file=root_path / "AGENTS.md",
        context_file=root_path / "CONTEXT.md",
        index_file=knowledge_dir / "index.md",
        log_file=knowledge_dir / "log.md",
        scripts_dir=scripts_dir,
        hooks_dir=root_path / "hooks",
        state_file=scripts_dir / "state.json",
        last_flush_file=scripts_dir / "last-flush.json",
        flush_log_file=scripts_dir / "flush.log",
    )


def validate_kb_root(root: str | Path) -> KbValidationResult:
    """Validate whether a directory looks like a KB root."""
    root_path = Path(root)
    required = {
        "AGENTS.md": root_path / "AGENTS.md",
        "kb/daily": root_path / "kb" / "daily",
        "kb/knowledge": root_path / "kb" / "knowledge",
    }
    missing = [label for label, path in required.items() if not path.exists()]
    return KbValidationResult(valid=not missing, missing=missing, root=root_path)


def ensure_kb_layout(root: str | Path) -> KbPaths:
    """Create a complete KB directory skeleton if it does not exist yet."""
    paths = resolve_kb_paths(root)
    for directory in [
        paths.daily_dir,
        paths.concepts_dir,
        paths.connections_dir,
        paths.qa_dir,
        paths.scripts_dir,
        paths.reports_dir,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    if not paths.agents_file.exists():
        paths.agents_file.write_text(_load_default_agents_text(), encoding="utf-8")
    if not paths.index_file.exists():
        paths.index_file.write_text(
            "# Knowledge Base Index\n\n"
            "| Article | Summary | Compiled From | Updated |\n"
            "|---------|---------|---------------|---------|\n",
            encoding="utf-8",
        )
    if not paths.log_file.exists():
        paths.log_file.write_text("# Build Log\n\n", encoding="utf-8")
    if not paths.context_file.exists():
        paths.context_file.write_text(
            "# Context\n\nPersonal knowledge base managed by LLM Knowledge Base.\n",
            encoding="utf-8",
        )
    return paths


def is_same_path(left: str | Path, right: str | Path) -> bool:
    """Compare two filesystem paths using platform-normalized absolute text."""
    left_abs = os.path.abspath(os.fspath(left))
    right_abs = os.path.abspath(os.fspath(right))
    return os.path.normcase(left_abs) == os.path.normcase(right_abs)


def _load_default_agents_text() -> str:
    candidates = [
        Path(__file__).resolve().parents[2] / "AGENTS.md",
        Path(getattr(sys, "_MEIPASS", "")) / "AGENTS.md",
        Path(sys.executable).resolve().parent / "AGENTS.md",
        Path(sys.executable).resolve().parent / "_internal" / "AGENTS.md",
    ]
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate.read_text(encoding="utf-8")
        except OSError:
            continue
    return (
        "# Personal Knowledge Base Schema\n\n"
        "This knowledge base stores raw conversation logs in `kb/daily/` and "
        "compiled wiki articles in `kb/knowledge/`.\n"
    )
