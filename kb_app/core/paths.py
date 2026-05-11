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
