"""Secret redaction helpers for logs and support bundles."""

from __future__ import annotations

import re

SECRET_KEY_PATTERN = re.compile(
    r"(?i)\b("
    r"OPENAI_API_KEY|ANTHROPIC_API_KEY|api[_-]?key|token|auth|cookie|"
    r"session|password|secret"
    r")\b(\s*[:=]\s*)([^\s,;]+)"
)


def redact_text(text: str) -> str:
    """Redact common secret-looking key/value pairs from text."""
    return SECRET_KEY_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text)
