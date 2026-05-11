"""Configure the MCP server entry in Claude Code and/or Codex config files."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
from datetime import datetime
from pathlib import Path

_SERVER_NAME = "llm-knowledge-base"


# ---------------------------------------------------------------------------
# Claude Desktop — JSON config  (claude_desktop_config.json)
# ---------------------------------------------------------------------------

def find_claude_config() -> Path:
    """Return the path of Claude Desktop's config file."""
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "Claude" / "claude_desktop_config.json"


def configure_mcp(
    kb_root: Path,
    *,
    exe_path: Path | None = None,
    config_path: Path | None = None,
) -> Path:
    """Add (or update) the llm-knowledge-base MCP entry in Claude Desktop's config."""
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
            "args": ["--kb-root", str(kb_root), "mcp"],
        }
    else:
        entry = {
            "command": "uv",
            "args": ["run", "python", "-m", "kb_mcp", "--kb-root", str(kb_root)],
        }

    config.setdefault("mcpServers", {})
    config["mcpServers"][_SERVER_NAME] = entry
    target.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def remove_mcp(*, config_path: Path | None = None) -> Path | None:
    """Remove the llm-knowledge-base MCP entry from Claude Desktop's config."""
    target = config_path or find_claude_config()
    if not target.exists():
        return None
    try:
        config = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    servers = config.get("mcpServers", {})
    if _SERVER_NAME not in servers:
        return None

    _backup(target)
    del servers[_SERVER_NAME]
    target.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def mcp_is_configured(*, config_path: Path | None = None) -> bool:
    """Return True if the MCP entry already exists in Claude Desktop's config."""
    target = config_path or find_claude_config()
    if not target.exists():
        return False
    try:
        config = json.loads(target.read_text(encoding="utf-8"))
        return _SERVER_NAME in config.get("mcpServers", {})
    except (json.JSONDecodeError, OSError):
        return False


# ---------------------------------------------------------------------------
# Claude Code CLI — ~/.claude.json  (user-scoped MCP servers)
# ---------------------------------------------------------------------------

def find_claude_code_config() -> Path:
    """Return the path of Claude Code CLI's user config (~/.claude.json)."""
    return Path.home() / ".claude.json"


def configure_mcp_claude_code(
    kb_root: Path,
    *,
    exe_path: Path | None = None,
    config_path: Path | None = None,
) -> Path:
    """Add (or update) the llm-knowledge-base MCP entry in Claude Code CLI's config.

    Claude Code CLI (the `claude` command) reads user-scoped MCP servers from
    ~/.claude.json under the top-level `mcpServers` key, with a `type` field.
    """
    target = config_path or find_claude_code_config()
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
            "type": "stdio",
            "command": str(exe_path),
            "args": ["--kb-root", str(kb_root), "mcp"],
        }
    else:
        entry = {
            "type": "stdio",
            "command": "uv",
            "args": ["run", "python", "-m", "kb_mcp", "--kb-root", str(kb_root)],
        }

    config.setdefault("mcpServers", {})
    config["mcpServers"][_SERVER_NAME] = entry
    target.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def remove_mcp_claude_code(*, config_path: Path | None = None) -> Path | None:
    """Remove the llm-knowledge-base MCP entry from Claude Code CLI's config."""
    target = config_path or find_claude_code_config()
    if not target.exists():
        return None
    try:
        config = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    servers = config.get("mcpServers", {})
    if _SERVER_NAME not in servers:
        return None

    _backup(target)
    del servers[_SERVER_NAME]
    target.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def mcp_is_configured_claude_code(*, config_path: Path | None = None) -> bool:
    """Return True if the MCP entry exists in Claude Code CLI's config."""
    target = config_path or find_claude_code_config()
    if not target.exists():
        return False
    try:
        config = json.loads(target.read_text(encoding="utf-8"))
        return _SERVER_NAME in config.get("mcpServers", {})
    except (json.JSONDecodeError, OSError):
        return False


# ---------------------------------------------------------------------------
# Codex — TOML config  (~/.codex/config.toml)
# ---------------------------------------------------------------------------

def find_codex_config() -> Path:
    """Return the path of Codex's config.toml (same on all platforms)."""
    return Path.home() / ".codex" / "config.toml"


def configure_mcp_codex(
    kb_root: Path,
    *,
    exe_path: Path | None = None,
    config_path: Path | None = None,
) -> Path:
    """Add (or update) the llm-knowledge-base MCP entry in Codex's config.toml.

    Codex uses TOML with [mcp_servers.<name>] tables, not JSON.
    """
    target = config_path or find_codex_config()
    target.parent.mkdir(parents=True, exist_ok=True)

    if exe_path and exe_path.exists():
        command = str(exe_path)
        args = ["--kb-root", str(kb_root), "mcp"]
    else:
        command = "uv"
        args = ["run", "python", "-m", "kb_mcp", "--kb-root", str(kb_root)]

    args_toml = ", ".join(f'"{_toml_escape(a)}"' for a in args)
    new_section = (
        f"[mcp_servers.{_SERVER_NAME}]\n"
        f'command = "{_toml_escape(command)}"\n'
        f"args = [{args_toml}]\n"
    )

    if target.exists():
        _backup(target)
        text = target.read_text(encoding="utf-8")
        text = _remove_toml_mcp_section(text)
    else:
        text = ""

    separator = "\n\n" if text.strip() else ""
    target.write_text(text.rstrip() + separator + new_section, encoding="utf-8")
    return target


def remove_mcp_codex(*, config_path: Path | None = None) -> Path | None:
    """Remove the llm-knowledge-base MCP entry from Codex's config.toml."""
    target = config_path or find_codex_config()
    if not target.exists():
        return None

    text = target.read_text(encoding="utf-8")
    if not _has_toml_mcp_section(text):
        return None

    _backup(target)
    new_text = _remove_toml_mcp_section(text).rstrip() + "\n"
    target.write_text(new_text, encoding="utf-8")
    return target


def mcp_is_configured_codex(*, config_path: Path | None = None) -> bool:
    """Return True if the MCP entry already exists in Codex's config.toml."""
    target = config_path or find_codex_config()
    if not target.exists():
        return False
    return _has_toml_mcp_section(target.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _toml_escape(s: str) -> str:
    """Escape a string for use inside a TOML basic string (double-quoted)."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _has_toml_mcp_section(text: str) -> bool:
    return bool(re.search(rf'^\[mcp_servers\.{re.escape(_SERVER_NAME)}\]', text, re.MULTILINE))


def _remove_toml_mcp_section(text: str) -> str:
    """Remove the [mcp_servers.llm-knowledge-base] block from TOML text.

    Stops at the next section header (line starting with '['), so inline
    arrays in values like `args = [...]` are not confused with section starts.

    Also removes invalid array-style headers left by older buggy installs,
    e.g.:  ["mcp", "--kb-root", "..."]  or  ["--kb-root", "...", "mcp"]
    """
    # Remove the section: header + all following lines that don't start a new section
    text = re.sub(
        rf'(?m)^\[mcp_servers\.{re.escape(_SERVER_NAME)}\][ \t]*\n'
        rf'(?:(?!\[).*\n?)*',
        '',
        text,
    )
    # Remove leftover invalid TOML lines from old buggy writes
    text = re.sub(r'(?m)^\["(?:mcp|--kb-root)[^\]]*\][ \t]*\n?', '', text)
    return text


def _backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup = path.with_suffix(f".backup-{stamp}{path.suffix}")
    shutil.copy2(path, backup)
    return backup
