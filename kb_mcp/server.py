"""MCP server that exposes LLM Knowledge Base operations as tools.

Run with:
    uv run python -m kb_mcp --kb-root /path/to/your/kb

Configure in Claude Code (claude_desktop_config.json):
    {
      "mcpServers": {
        "llm-knowledge-base": {
          "command": "uv",
          "args": ["run", "python", "-m", "kb_mcp", "--kb-root", "/path/to/kb"],
          "cwd": "/path/to/llm-knowledge-base"
        }
      }
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from kb_app.core.mcp_setup import (
    configure_mcp,
    configure_mcp_claude_code,
    configure_mcp_codex,
    mcp_is_configured,
    mcp_is_configured_claude_code,
    mcp_is_configured_codex,
    remove_mcp,
    remove_mcp_claude_code,
    remove_mcp_codex,
)
from kb_app.core.operations import (
    append_manual_memory,
    compile_logs,
    run_lint,
    run_query,
    run_structural_lint,
)
from kb_app.core.paths import ensure_kb_layout, is_same_path, resolve_kb_paths
from kb_app.core.wiki import list_wiki_articles, read_wiki_index
from kb_app.diagnostics.export import export_diagnostics
from kb_app.hooks.commands import build_session_context
from kb_app.core.paths import resolve_app_paths
from kb_app.jobs.queue import JobStore
from kb_app.jobs.runner import JobRunner
from kb_app.profiles.store import ProfileStore
from kb_app.ui.app import ACTION_TO_JOB_TYPE

mcp = FastMCP("llm-knowledge-base")
MCP_UI_JOB_ACTIONS = dict(ACTION_TO_JOB_TYPE)

# kb_root is set once at server startup via --kb-root CLI arg
_kb_root: Path = Path.cwd()
_app_db_path: Path | None = None


def _paths():
    return resolve_kb_paths(_kb_root)


def _app_db() -> Path:
    return _app_db_path or resolve_app_paths().db_path


def _profile_store() -> ProfileStore:
    return ProfileStore(_app_db())


def _job_store() -> JobStore:
    return JobStore(_app_db())


def _active_profile_id() -> int:
    store = _profile_store()
    root = ensure_kb_layout(_kb_root).root
    active = store.get_active_profile()
    if active is None:
        profile_id = store.create_profile("MCP KB", root)
        store.set_active_profile(profile_id)
        return profile_id
    if not is_same_path(active.root_path, root):
        store.update_profile_root(active.id, root)
    return store.get_active_profile().id


def _run_ui_action(action: str, payload: dict | None = None, *, run_now: bool = True) -> str:
    if action not in MCP_UI_JOB_ACTIONS:
        known = ", ".join(sorted(MCP_UI_JOB_ACTIONS))
        return f"Unsupported UI action '{action}'. Known actions: {known}"

    jobs = _job_store()
    profile_id = _active_profile_id()
    job_id = jobs.enqueue(
        profile_id=profile_id,
        job_type=MCP_UI_JOB_ACTIONS[action],
        payload=payload or {},
        priority=0,
    )
    if not run_now:
        return f"Queued job {job_id}: {MCP_UI_JOB_ACTIONS[action]}"

    result = JobRunner(jobs, profile_store=_profile_store()).run_next()
    record = jobs.get_job(job_id)
    if result.job_id != job_id:
        return f"Queued job {job_id}; ran queued job {result.job_id} with status {result.status}."
    if record.status == "succeeded":
        return f"Job {job_id} succeeded: {json.dumps(record.result, ensure_ascii=False)}"
    return f"Job {job_id} {record.status}: {record.error_message or record.result}"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def kb_get_context() -> str:
    """Return the current KB context: wiki index + recent daily log.

    This is the same context injected into AI sessions by the session-start hook.
    Use it to understand what the knowledge base currently contains instead
    of opening PowerShell/cmd just to inspect local context.
    """
    paths = _paths()
    return build_session_context(paths)


@mcp.tool()
async def kb_query(question: str, file_back: bool = False) -> str:
    """Query the knowledge base with a natural language question.

    The LLM backend reads all wiki articles and answers using that knowledge.
    Responses cite sources using [[wikilinks]].

    Args:
        question: The question to ask the knowledge base.
        file_back: If True, saves the answer as a Q&A article in kb/knowledge/qa/.
    """
    import asyncio as _asyncio
    paths = _paths()
    return await _asyncio.to_thread(run_query, paths, question, file_back=file_back)


@mcp.tool()
async def kb_compile(
    force_all: bool = False,
    file_name: str | None = None,
    dry_run: bool = False,
) -> str:
    """Compile daily logs into wiki articles using the LLM backend.

    The compiler detects changes by SHA-256 hash — only modified logs are reprocessed
    unless force_all is True.

    Args:
        force_all: Recompile all logs even if unchanged.
        file_name: Compile only this specific log file (e.g. "2026-05-11.md").
        dry_run: List what would be compiled without actually running.

    Returns:
        Summary of compiled files and total cost in USD.
    """
    import asyncio as _asyncio
    paths = _paths()
    result = await _asyncio.to_thread(
        compile_logs, paths, force_all=force_all, file_name=file_name, dry_run=dry_run
    )
    if not result.files:
        return "Nothing to compile — all daily logs are up to date."
    prefix = "[DRY RUN] " if result.dry_run else ""
    lines = [f"{prefix}Files compiled ({len(result.files)}):"]
    for name in result.files:
        lines.append(f"  - {name}")
    if not dry_run and result.total_cost > 0:
        lines.append(f"Total cost: ${result.total_cost:.4f}")
    return "\n".join(lines)


@mcp.tool()
async def kb_lint(structural_only: bool = False) -> str:
    """Run health checks on the knowledge base.

    Structural checks are free (no LLM). Full lint also uses the LLM to detect
    contradictions between articles.

    Args:
        structural_only: If True, skip the LLM contradiction check (faster, no cost).

    Returns:
        Lint report with errors, warnings, and suggestions.
    """
    import asyncio as _asyncio
    paths = _paths()
    if structural_only:
        result = await _asyncio.to_thread(run_structural_lint, paths, write_report=True)
    else:
        result = await _asyncio.to_thread(run_lint, paths, structural_only=False, write_report=True)
    summary = (
        f"Results: {result.errors} errors, "
        f"{result.warnings} warnings, {result.suggestions} suggestions"
    )
    if result.report_path:
        summary += f"\nReport saved to: {result.report_path}"
    if result.issues:
        summary += "\n\n" + result.report
    else:
        summary += "\n\nAll checks passed. Knowledge base is healthy."
    return summary


@mcp.tool()
def kb_add_memory(content: str) -> str:
    """Append a manual memory entry to today's daily log.

    Use this to record decisions, learnings, or context that happened outside
    of a captured AI session.

    Args:
        content: The memory content to add. Supports markdown.

    Returns:
        Path of the daily log file that was updated.
    """
    paths = _paths()
    log_path = append_manual_memory(paths, content)
    return f"Memory added to: {log_path}"


@mcp.tool()
def kb_list_articles() -> str:
    """List all wiki articles in the knowledge base.

    Returns:
        Categorized list of articles in concepts/, connections/, and qa/.
    """
    paths = _paths()
    articles = list_wiki_articles(paths)

    if not articles:
        return "No wiki articles found. Run kb_compile to generate articles from daily logs."

    by_category: dict[str, list[str]] = {}
    for article in articles:
        rel = article.relative_to(paths.knowledge_dir)
        category = rel.parts[0] if len(rel.parts) > 1 else "root"
        by_category.setdefault(category, []).append(rel.as_posix())

    lines = [f"Total: {len(articles)} articles\n"]
    for category, paths_list in sorted(by_category.items()):
        lines.append(f"## {category}/ ({len(paths_list)})")
        for p in sorted(paths_list):
            lines.append(f"  - {p}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def kb_read_article(article_path: str) -> str:
    """Read the content of a specific wiki article.

    Args:
        article_path: Relative path from kb/knowledge/, e.g. "concepts/auth-patterns.md"
                      or just the article name slug.

    Returns:
        Full markdown content of the article.
    """
    paths = _paths()

    # Try exact path from knowledge dir
    target = paths.knowledge_dir / article_path
    if not target.exists() and not article_path.endswith(".md"):
        target = paths.knowledge_dir / f"{article_path}.md"

    if not target.exists():
        # Search by name across all categories
        matches = [
            a for a in list_wiki_articles(paths)
            if article_path.lower() in a.name.lower()
        ]
        if not matches:
            return f"Article '{article_path}' not found. Use kb_list_articles to see available articles."
        if len(matches) == 1:
            target = matches[0]
        else:
            names = [str(m.relative_to(paths.knowledge_dir)) for m in matches]
            return f"Multiple articles match '{article_path}':\n" + "\n".join(f"  - {n}" for n in names)

    return target.read_text(encoding="utf-8")


@mcp.tool()
def kb_wiki_index() -> str:
    """Return the wiki index table (index.md).

    The index is a markdown table with all articles, summaries, sources, and
    last updated timestamps. This is also what gets injected into AI sessions.

    Returns:
        Content of kb/knowledge/index.md.
    """
    paths = _paths()
    index = read_wiki_index(paths)
    if not index.strip():
        return "Wiki index is empty. Run kb_compile to populate it."
    return index


@mcp.tool()
def kb_diagnostics(output_dir: str | None = None) -> str:
    """Export a diagnostics bundle as a ZIP file.

    The bundle contains system metadata, redacted configuration, and logs.
    All secrets (API keys, tokens, passwords) are replaced with [REDACTED].

    Args:
        output_dir: Directory to write the ZIP file. Defaults to diagnostics/.

    Returns:
        Path of the exported ZIP file.
    """
    app_paths = resolve_app_paths()
    paths = _paths()
    out = Path(output_dir) if output_dir else None
    bundle = export_diagnostics(app_paths, paths, output_dir=out)
    return f"Diagnostics exported: {bundle}"


@mcp.tool()
def kb_status() -> str:
    """Return the current status of the knowledge base.

    Shows: KB root, daily log count, article count, last compile timestamp,
    query count, and total API cost spent so far.
    """
    from kb_app.core.wiki import load_state, list_raw_files, list_wiki_articles
    paths = _paths()
    state = load_state(paths)

    daily_count   = len(list_raw_files(paths))
    article_count = len(list_wiki_articles(paths))
    ingested      = state.get("ingested", {})
    compiled      = len(ingested)

    last_compile = "never"
    if ingested:
        latest = max(v.get("compiled_at", "") for v in ingested.values() if v.get("compiled_at"))
        if latest:
            last_compile = latest

    lines = [
        f"KB root       : {_kb_root}",
        f"Daily logs    : {daily_count} files ({compiled} compiled, {daily_count - compiled} pending)",
        f"Wiki articles : {article_count}",
        f"Last compile  : {last_compile}",
        f"Query count   : {state.get('query_count', 0)}",
        f"Total API cost: ${state.get('total_cost', 0.0):.4f}",
    ]
    return "\n".join(lines)


@mcp.tool()
def kb_pending_logs() -> str:
    """List daily logs that have not been compiled yet (or changed since last compile).

    Use this before calling kb_compile to understand what will be processed.
    """
    from kb_app.core.wiki import load_state, list_raw_files, file_hash
    from kb_app.core.operations import select_logs_to_compile
    paths = _paths()
    pending = select_logs_to_compile(paths, force_all=False)
    if not pending:
        return "All daily logs are up to date. Nothing to compile."
    lines = [f"Pending logs ({len(pending)} files):"]
    for p in pending:
        lines.append(f"  - {p.name}")
    return "\n".join(lines)


@mcp.tool()
def kb_ui_actions() -> str:
    """List every UI action that can also be executed through MCP."""
    lines = ["UI actions exposed through MCP:"]
    for action, job_type in sorted(MCP_UI_JOB_ACTIONS.items()):
        lines.append(f"- {action} -> {job_type}")
    return "\n".join(lines)


@mcp.tool()
def kb_profiles_list() -> str:
    """List KB profiles configured in the desktop app."""
    profiles = _profile_store().list_profiles()
    if not profiles:
        return "No KB profiles configured."
    lines = []
    for profile in profiles:
        marker = "*" if profile.active else " "
        lines.append(f"{marker} {profile.id}: {profile.name} [{profile.backend}] {profile.root_path}")
    return "\n".join(lines)


@mcp.tool()
def kb_profile_create(
    name: str,
    root_path: str,
    backend: str = "claude",
    activate: bool = True,
) -> str:
    """Create a KB profile, bootstrap its directory layout, and optionally activate it."""
    paths = ensure_kb_layout(root_path)
    store = _profile_store()
    profile_id = store.create_profile(name, paths.root, backend=backend)
    if activate:
        store.set_active_profile(profile_id)
    return f"Profile created: {profile_id} -> {paths.root}"


@mcp.tool()
def kb_profile_activate(profile_id: int) -> str:
    """Activate an existing KB profile."""
    _profile_store().set_active_profile(profile_id)
    return f"Activated profile {profile_id}"


@mcp.tool()
def kb_jobs_list(limit: int = 20) -> str:
    """List recent background jobs from the desktop app queue."""
    jobs = _job_store()
    with jobs._connection() as conn:
        rows = conn.execute(
            "SELECT id, job_type, status, created_at FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    if not rows:
        return "No jobs found."
    return "\n".join(
        f"{row['id']} | {row['status']} | {row['job_type']} | {row['created_at']}"
        for row in rows
    )


@mcp.tool()
def kb_job_run_next() -> str:
    """Run the next queued desktop background job."""
    result = JobRunner(_job_store(), profile_store=_profile_store()).run_next()
    return f"Runner result: {result.status} ({result.job_id or 'no job'})"


@mcp.tool()
def kb_job_cancel(job_id: str) -> str:
    """Request cancellation for a queued/running desktop job."""
    _job_store().request_cancel(job_id)
    return f"Cancellation requested for job {job_id}"


@mcp.tool()
def kb_enqueue_ui_action(action: str, payload_json: str = "{}", run_now: bool = False) -> str:
    """Queue any desktop UI action by name.

    Use kb_ui_actions first to see supported actions. payload_json must be a JSON object.
    """
    payload = json.loads(payload_json)
    if not isinstance(payload, dict):
        return "payload_json must decode to a JSON object."
    return _run_ui_action(action, payload, run_now=run_now)


@mcp.tool()
def kb_install_hooks(
    client: str,
    config_path: str | None = None,
    backup_dir: str | None = None,
    executable: str | None = None,
) -> str:
    """Install Claude Code or Codex capture hooks through the same UI job runner."""
    payload = {"client": client}
    if config_path:
        payload["config_path"] = config_path
    if backup_dir:
        payload["backup_dir"] = backup_dir
    if executable:
        payload["executable"] = executable
    return _run_ui_action("install_hooks", payload)


@mcp.tool()
def kb_repair_hooks(client: str) -> str:
    """Repair Claude Code or Codex capture hooks."""
    return _run_ui_action("repair_hooks", {"client": client})


@mcp.tool()
def kb_remove_hooks(client: str) -> str:
    """Remove this app's marked capture hooks from Claude Code or Codex."""
    return _run_ui_action("remove_hooks", {"client": client})


@mcp.tool()
def kb_backend_smoke_test() -> str:
    """Run the backend smoke test exposed by the UI."""
    return _run_ui_action("backend_smoke_test", {})


@mcp.tool()
def kb_flush_test() -> str:
    """Run the flush test exposed by the UI."""
    return _run_ui_action("flush_test", {})


@mcp.tool()
def kb_install_autostart() -> str:
    """Install user-session autostart for the desktop control panel."""
    return _run_ui_action("install_autostart", {})


@mcp.tool()
def kb_remove_autostart() -> str:
    """Remove user-session autostart for the desktop control panel."""
    return _run_ui_action("remove_autostart", {})


@mcp.tool()
def kb_configure_daily_schedule(enabled: bool = True, time: str = "17:00") -> str:
    """Configure the daily compile setting exposed by the UI."""
    return _run_ui_action("configure_daily_schedule", {"enabled": enabled, "time": time})


@mcp.tool()
def kb_configure_mcp(
    client: str = "both",
    remove: bool = False,
    exe_path: str | None = None,
) -> str:
    """Configure or remove this MCP server for Claude Code/Claude Desktop and/or Codex."""
    exe = Path(exe_path) if exe_path else None
    lines: list[str] = []
    if client in ("claude", "both"):
        if remove:
            lines.append(f"Claude Desktop removed: {remove_mcp()}")
            lines.append(f"Claude Code removed: {remove_mcp_claude_code()}")
        else:
            lines.append(f"Claude Desktop configured: {configure_mcp(_kb_root, exe_path=exe)}")
            lines.append(f"Claude Code configured: {configure_mcp_claude_code(_kb_root, exe_path=exe)}")
    if client in ("codex", "both"):
        if remove:
            lines.append(f"Codex removed: {remove_mcp_codex()}")
        else:
            lines.append(f"Codex configured: {configure_mcp_codex(_kb_root, exe_path=exe)}")
    return "\n".join(lines)


@mcp.tool()
def kb_mcp_status() -> str:
    """Return MCP configuration status for Claude Desktop, Claude Code CLI, and Codex."""
    return "\n".join(
        [
            f"Claude Desktop MCP: {'yes' if mcp_is_configured() else 'no'}",
            f"Claude Code MCP: {'yes' if mcp_is_configured_claude_code() else 'no'}",
            f"Codex MCP: {'yes' if mcp_is_configured_codex() else 'no'}",
        ]
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    global _app_db_path, _kb_root

    parser = argparse.ArgumentParser(
        prog="kb_mcp",
        description="MCP server for LLM Knowledge Base",
    )
    parser.add_argument(
        "--kb-root",
        default=str(Path.cwd()),
        help="Knowledge base root directory (default: current directory)",
    )
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse"],
        help="MCP transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--app-db",
        default=None,
        help="Desktop app SQLite database path",
    )

    args = parser.parse_args(argv)
    _kb_root = Path(args.kb_root).resolve()
    _app_db_path = Path(args.app_db) if args.app_db else None

    mcp.run(transport=args.transport)
    return 0


if __name__ == "__main__":
    sys.exit(main())
