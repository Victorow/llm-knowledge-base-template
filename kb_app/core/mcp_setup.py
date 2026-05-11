"""Configure the MCP server entry in the Claude Code desktop config."""

from __future__ import annotations

import json
import os
import platform
import shutil
from datetime import datetime
from pathlib import Path


def find_claude_config() -> Path:
    """Return the likely path of Claude Code's desktop config file.

    Returns the path whether or not it exists yet — callers create it if needed.
    """
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    # Linux / other
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "Claude" / "claude_desktop_config.json"


def configure_mcp(
    kb_root: Path,
    *,
    exe_path: Path | None = None,
    config_path: Path | None = None,
) -> Path:
    """Add (or update) the llm-knowledge-base MCP entry in Claude's config.

    Args:
        kb_root:     Absolute path to the knowledge base root directory.
        exe_path:    Path to the installed LLMKnowledgeBase.exe.  When provided
                     the entry uses the packaged exe (no uv/Python required).
                     When None the entry falls back to `uv run python -m kb_mcp`.
        config_path: Override the auto-detected Claude config path.

    Returns:
        The path of the config file that was written.
    """
    target = config_path or find_claude_config()
    target.parent.mkdir(parents=True, exist_ok=True)

    config: dict = {}
    if target.exists():
        try:
            config = json.loads(target.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            config = {}
        _backup(target)

    if exe_path and exe_path.exists():
        entry: dict = {
            "command": str(exe_path),
            "args": ["mcp", "--kb-root", str(kb_root)],
        }
    else:
        entry = {
            "command": "uv",
            "args": [
                "run",
                "python",
                "-m",
                "kb_mcp",
                "--kb-root",
                str(kb_root),
            ],
        }

    config.setdefault("mcpServers", {})
    config["mcpServers"]["llm-knowledge-base"] = entry

    target.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def remove_mcp(*, config_path: Path | None = None) -> Path | None:
    """Remove the llm-knowledge-base MCP entry from Claude's config.

    Returns the config path if the entry was found and removed, else None.
    """
    target = config_path or find_claude_config()
    if not target.exists():
        return None

    try:
        config = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    servers = config.get("mcpServers", {})
    if "llm-knowledge-base" not in servers:
        return None

    _backup(target)
    del servers["llm-knowledge-base"]
    target.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def mcp_is_configured(*, config_path: Path | None = None) -> bool:
    """Return True if the MCP entry already exists in Claude's config."""
    target = config_path or find_claude_config()
    if not target.exists():
        return False
    try:
        config = json.loads(target.read_text(encoding="utf-8"))
        return "llm-knowledge-base" in config.get("mcpServers", {})
    except (json.JSONDecodeError, OSError):
        return False


def _backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup = path.with_suffix(f".backup-{stamp}.json")
    shutil.copy2(path, backup)
    return backup
