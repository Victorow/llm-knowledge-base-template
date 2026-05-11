"""Safe config merge helpers for AI-client hook files."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

KB_HOOK_MARKER = "LLM_KB_HOOK"


@dataclass(frozen=True)
class ConfigChangeResult:
    config_path: Path
    backup_path: Path | None
    changed: bool


JsonWriter = Callable[[Path, str], None]


def merge_json_hooks(
    config_path: Path,
    hooks_to_add: dict[str, list[dict]],
    *,
    backup_dir: Path,
    marker: str = KB_HOOK_MARKER,
) -> ConfigChangeResult:
    """Merge marked hook groups into a JSON config without overwriting unrelated data."""
    original = _read_json_object(config_path)
    updated = json.loads(json.dumps(original))
    hooks = updated.setdefault("hooks", {})

    _strip_marked_hooks_from_hooks_map(hooks, marker)

    for event_name, groups in hooks_to_add.items():
        event_groups = hooks.setdefault(event_name, [])
        event_groups.extend(groups)

    changed = updated != original
    if not changed:
        return ConfigChangeResult(config_path=config_path, backup_path=None, changed=False)

    backup_path = write_json_with_backup(config_path, updated, backup_dir)
    return ConfigChangeResult(config_path=config_path, backup_path=backup_path, changed=True)


def remove_json_hooks(
    config_path: Path,
    *,
    backup_dir: Path,
    marker: str = KB_HOOK_MARKER,
) -> ConfigChangeResult:
    """Remove only marked KB hook entries from a JSON config."""
    original = _read_json_object(config_path)
    updated = json.loads(json.dumps(original))
    hooks = updated.get("hooks", {})
    if isinstance(hooks, dict):
        _strip_marked_hooks_from_hooks_map(hooks, marker)

    changed = updated != original
    if not changed:
        return ConfigChangeResult(config_path=config_path, backup_path=None, changed=False)

    backup_path = write_json_with_backup(config_path, updated, backup_dir)
    return ConfigChangeResult(config_path=config_path, backup_path=backup_path, changed=True)


def write_json_with_backup(
    config_path: Path,
    data: dict,
    backup_dir: Path,
    *,
    writer: JsonWriter | None = None,
) -> Path:
    """Write JSON with a timestamped backup and rollback on write/validation failure."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    original_text = config_path.read_text(encoding="utf-8") if config_path.exists() else None
    backup_path = _backup_path(config_path, backup_dir)
    if original_text is not None:
        backup_path.write_text(original_text, encoding="utf-8")
    else:
        backup_path.write_text("", encoding="utf-8")

    text = json.dumps(data, indent=2, ensure_ascii=False)
    json.loads(text)
    selected_writer = writer or _default_writer

    try:
        selected_writer(config_path, text)
        json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        if original_text is None:
            config_path.unlink(missing_ok=True)
        else:
            config_path.write_text(original_text, encoding="utf-8")
        raise

    return backup_path


def _read_json_object(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON config root must be an object: {config_path}")
    return data


def _strip_marked_hooks_from_hooks_map(hooks: dict, marker: str) -> None:
    for event_name, groups in list(hooks.items()):
        if not isinstance(groups, list):
            continue

        kept_groups = []
        for group in groups:
            if not isinstance(group, dict):
                kept_groups.append(group)
                continue

            hook_entries = group.get("hooks")
            if not isinstance(hook_entries, list):
                kept_groups.append(group)
                continue

            kept_hooks = [
                hook
                for hook in hook_entries
                if marker not in str(hook.get("command", ""))
            ]

            if kept_hooks:
                new_group = dict(group)
                new_group["hooks"] = kept_hooks
                kept_groups.append(new_group)

        if kept_groups:
            hooks[event_name] = kept_groups
        else:
            hooks.pop(event_name, None)


def _backup_path(config_path: Path, backup_dir: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    return backup_dir / f"{config_path.name}.{timestamp}.bak"


def _default_writer(path: Path, text: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    shutil.move(str(tmp_path), str(path))
