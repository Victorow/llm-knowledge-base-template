"""Agent backend abstraction for Claude Agent SDK and Codex CLI."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

VALID_BACKENDS = {"claude", "codex"}
DEFAULT_CODEX_MODEL = "gpt-5.3-codex"


@dataclass(frozen=True)
class AgentResult:
    text: str
    cost_usd: float = 0.0


def selected_backend() -> str:
    """Return the configured agent backend."""
    backend = os.environ.get("KB_AGENT_BACKEND", "claude").strip().lower()
    if backend not in VALID_BACKENDS:
        raise ValueError(
            f"Unsupported KB_AGENT_BACKEND={backend!r}. Expected one of: "
            f"{', '.join(sorted(VALID_BACKENDS))}."
        )
    return backend


async def run_agent_text(
    prompt: str,
    *,
    cwd: Path,
    writable: bool,
    backend: str | None = None,
    claude_allowed_tools: list[str] | None = None,
    claude_max_turns: int = 2,
    claude_system_prompt: dict | None = None,
    claude_permission_mode: str | None = None,
    timeout_seconds: int = 1800,
) -> AgentResult:
    """Run the selected LLM backend and return the final text/cost."""
    chosen = backend or selected_backend()
    if chosen == "claude":
        return await run_claude_agent(
            prompt,
            cwd=cwd,
            allowed_tools=claude_allowed_tools or [],
            max_turns=claude_max_turns,
            system_prompt=claude_system_prompt,
            permission_mode=claude_permission_mode,
        )
    if chosen == "codex":
        return await asyncio.to_thread(
            run_codex_agent,
            prompt,
            cwd=cwd,
            writable=writable,
            timeout_seconds=timeout_seconds,
        )

    raise ValueError(f"Unsupported agent backend: {chosen}")


async def run_claude_agent(
    prompt: str,
    *,
    cwd: Path,
    allowed_tools: list[str],
    max_turns: int,
    system_prompt: dict | None = None,
    permission_mode: str | None = None,
) -> AgentResult:
    """Run the Claude Agent SDK backend."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    response = ""
    cost = 0.0
    options_kwargs = {
        "cwd": str(cwd),
        "allowed_tools": allowed_tools,
        "max_turns": max_turns,
    }
    if system_prompt is not None:
        options_kwargs["system_prompt"] = system_prompt
    if permission_mode is not None:
        options_kwargs["permission_mode"] = permission_mode

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(**options_kwargs),
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    response += block.text
        elif isinstance(message, ResultMessage):
            cost = message.total_cost_usd or 0.0

    return AgentResult(text=response, cost_usd=cost)


def build_codex_exec_command(*, cwd: Path, output_path: Path, writable: bool) -> list[str]:
    """Build the Codex exec command. Prompt text is supplied through stdin."""
    sandbox = "workspace-write" if writable else "read-only"
    model = os.environ.get("KB_CODEX_MODEL", DEFAULT_CODEX_MODEL).strip()
    command = [
        resolve_codex_executable(),
        "exec",
    ]
    if model:
        command.extend(["-m", model])

    command.extend([
        "--cd",
        str(cwd),
        "--skip-git-repo-check",
        "--sandbox",
        sandbox,
        "--ephemeral",
        "--color",
        "never",
        "--output-last-message",
        str(output_path),
        "-",
    ])
    return command


def resolve_codex_executable() -> str:
    """Resolve the Codex executable safely across platforms."""
    if sys.platform == "win32":
        return (
            shutil.which("codex.cmd")
            or shutil.which("codex.exe")
            or shutil.which("codex")
            or "codex.cmd"
        )

    return shutil.which("codex") or "codex"


def run_codex_agent(
    prompt: str,
    *,
    cwd: Path,
    writable: bool,
    timeout_seconds: int,
) -> AgentResult:
    """Run Codex CLI in non-interactive mode."""
    tmp_dir = tempfile.mkdtemp(prefix="kb-codex-")
    try:
        output_path = Path(tmp_dir) / "last-message.txt"
        stdout_path = Path(tmp_dir) / "stdout.log"
        stderr_path = Path(tmp_dir) / "stderr.log"
        command = build_codex_exec_command(
            cwd=cwd,
            output_path=output_path,
            writable=writable,
        )
        env = os.environ.copy()
        env["KB_INVOKED_BY"] = "agent_backend"

        try:
            with (
                open(stdout_path, "w", encoding="utf-8") as stdout_file,
                open(stderr_path, "w", encoding="utf-8") as stderr_file,
            ):
                completed = subprocess.run(
                    command,
                    input=prompt,
                    text=True,
                    encoding="utf-8",
                    stdout=stdout_file,
                    stderr=stderr_file,
                    cwd=str(cwd),
                    env=env,
                    timeout=timeout_seconds,
                    check=False,
                )
        except subprocess.TimeoutExpired as e:
            stderr = stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:]
            raise TimeoutError(
                f"Codex backend timed out after {timeout_seconds} seconds.\n"
                f"stderr:\n{stderr or '<no stderr>'}"
            ) from e

        if completed.returncode != 0:
            stderr = stderr_path.read_text(encoding="utf-8", errors="replace").strip()[-4000:] or "<no stderr>"
            stdout = stdout_path.read_text(encoding="utf-8", errors="replace").strip()[-2000:]
            raise RuntimeError(
                f"Codex backend failed with exit code {completed.returncode}.\n"
                f"stderr:\n{stderr}\nstdout:\n{stdout}"
            )

        if output_path.exists():
            response = output_path.read_text(encoding="utf-8")
        else:
            response = stdout_path.read_text(encoding="utf-8", errors="replace")

        return AgentResult(text=response.strip(), cost_usd=0.0)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
