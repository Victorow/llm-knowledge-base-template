"""User-facing labels for LLM backend usage estimates."""

from __future__ import annotations


def format_llm_usage_estimate(amount_usd: float) -> str:
    """Format provider-reported LLM usage without implying app billing."""
    return f"LLM backend usage estimate reported by provider: ${amount_usd:.4f}"
