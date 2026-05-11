"""Transcript normalization for supported AI coding clients."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SUPPORTED_ROLES = {"user", "assistant"}
TEXT_BLOCK_TYPES = {"text", "input_text", "output_text"}


def extract_conversation_context(
    transcript_path: Path,
    *,
    max_turns: int = 30,
    max_context_chars: int = 15_000,
) -> tuple[str, int]:
    """Read a JSONL transcript and extract recent user/assistant turns."""
    turns: list[str] = []

    with open(transcript_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            role, content = extract_message(entry)
            if role not in SUPPORTED_ROLES or not content.strip():
                continue

            label = "User" if role == "user" else "Assistant"
            turns.append(f"**{label}:** {content.strip()}\n")

    recent = turns[-max_turns:]
    context = "\n".join(recent)

    if len(context) > max_context_chars:
        context = context[-max_context_chars:]
        boundary = context.find("\n**")
        if boundary > 0:
            context = context[boundary + 1 :]

    return context, len(recent)


def extract_message(entry: dict[str, Any]) -> tuple[str, str]:
    """Extract role and text from Claude Code or Codex JSONL entries."""
    claude_role, claude_content = extract_claude_code_message(entry)
    if claude_role or claude_content:
        return claude_role, claude_content

    return extract_codex_message(entry)


def extract_claude_code_message(entry: dict[str, Any]) -> tuple[str, str]:
    """Extract messages from Claude Code transcript JSONL records."""
    msg = entry.get("message", {})
    if isinstance(msg, dict):
        role = msg.get("role", "")
        content = msg.get("content", "")
    else:
        role = entry.get("role", "")
        content = entry.get("content", "")

    return str(role), content_to_text(content)


def extract_codex_message(entry: dict[str, Any]) -> tuple[str, str]:
    """Extract messages from Codex rollout JSONL records."""
    if entry.get("type") != "response_item":
        return "", ""

    payload = entry.get("payload", {})
    if not isinstance(payload, dict) or payload.get("type") != "message":
        return "", ""

    role = payload.get("role", "")
    content = payload.get("content", "")
    return str(role), content_to_text(content)


def content_to_text(content: Any) -> str:
    """Convert supported transcript content blocks to text."""
    if isinstance(content, str):
        return content

    if not isinstance(content, list):
        return ""

    text_parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            text_parts.append(block)
            continue

        if not isinstance(block, dict):
            continue

        block_type = block.get("type")
        if block_type in TEXT_BLOCK_TYPES:
            text = block.get("text", "")
            if isinstance(text, str):
                text_parts.append(text)

    return "\n".join(part for part in text_parts if part.strip())
