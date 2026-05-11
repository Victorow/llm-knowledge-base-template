"""Single executable entrypoint for source and packaged runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kb_app.core.mcp_setup import (
    configure_mcp,
    configure_mcp_claude_code,
    configure_mcp_codex,
    find_claude_code_config,
    find_claude_config,
    find_codex_config,
    mcp_is_configured,
    mcp_is_configured_claude_code,
    mcp_is_configured_codex,
    remove_mcp,
    remove_mcp_claude_code,
    remove_mcp_codex,
)
from kb_app.core.operations import compile_logs, run_lint, run_query
from kb_app.core.paths import resolve_app_paths
from kb_app.core.paths import resolve_kb_paths
from kb_app.diagnostics.export import export_diagnostics
from kb_app.hooks.commands import capture_hook, render_session_start_json
from kb_app.jobs.queue import JobStore
from kb_app.profiles.store import ProfileStore
from kb_app.ui.app import launch_ui


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="llm-knowledge-base")
    parser.add_argument(
        "--kb-root",
        default=str(Path.cwd()),
        help="Knowledge base root directory",
    )
    parser.add_argument(
        "--app-db",
        default=None,
        help="Path to app SQLite database",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    hook_parser = subparsers.add_parser("hook", help="Run AI-client hook command")
    hook_parser.add_argument(
        "hook_event",
        choices=["session-start", "session-end", "pre-compact", "post-compact"],
    )

    profiles_parser = subparsers.add_parser("profiles", help="Manage KB profiles")
    profiles_subparsers = profiles_parser.add_subparsers(dest="profiles_command", required=True)
    profiles_subparsers.add_parser("list")
    create_profile_parser = profiles_subparsers.add_parser("create")
    create_profile_parser.add_argument("name")
    create_profile_parser.add_argument("root_path")
    create_profile_parser.add_argument("--backend", default="claude")
    activate_profile_parser = profiles_subparsers.add_parser("activate")
    activate_profile_parser.add_argument("profile_id", type=int)

    jobs_parser = subparsers.add_parser("jobs", help="Manage background jobs")
    jobs_subparsers = jobs_parser.add_subparsers(dest="jobs_command", required=True)
    enqueue_parser = jobs_subparsers.add_parser("enqueue")
    enqueue_parser.add_argument("job_type")
    enqueue_parser.add_argument("--profile-id", type=int, required=True)
    enqueue_parser.add_argument("--payload-json", default="{}")
    enqueue_parser.add_argument("--priority", type=int, default=100)
    enqueue_parser.add_argument("--backend", default=None)

    compile_parser = subparsers.add_parser("compile", help="Compile daily logs")
    compile_parser.add_argument("--all", action="store_true")
    compile_parser.add_argument("--file", default=None)
    compile_parser.add_argument("--dry-run", action="store_true")

    query_parser = subparsers.add_parser("query", help="Query the knowledge base")
    query_parser.add_argument("question")
    query_parser.add_argument("--file-back", action="store_true")

    lint_parser = subparsers.add_parser("lint", help="Lint the knowledge base")
    lint_parser.add_argument("--structural-only", action="store_true")

    diagnostics_parser = subparsers.add_parser("diagnostics", help="Diagnostics operations")
    diagnostics_subparsers = diagnostics_parser.add_subparsers(
        dest="diagnostics_command",
        required=True,
    )
    export_parser = diagnostics_subparsers.add_parser("export")
    export_parser.add_argument("--output", default=None)

    ui_parser = subparsers.add_parser(
        "ui",
        help="Launch desktop control panel",
        description="Launch desktop control panel",
    )
    ui_parser.add_argument("--no-tray", action="store_true")

    mcp_parser = subparsers.add_parser("mcp", help="Start MCP server (stdio)")
    mcp_parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse"],
        help="MCP transport (default: stdio)",
    )

    setup_mcp_parser = subparsers.add_parser(
        "setup-mcp",
        help="Configure MCP server in Claude Code and/or Codex config files",
    )
    setup_mcp_parser.add_argument(
        "--client",
        choices=["claude", "codex", "both"],
        default="both",
        help="Which AI client to configure MCP for (default: both)",
    )
    setup_mcp_parser.add_argument(
        "--exe-path",
        default=None,
        help="Path to LLMKnowledgeBase.exe (uses packaged exe instead of uv)",
    )
    setup_mcp_parser.add_argument(
        "--claude-config",
        default=None,
        help="Override the Claude Desktop config file path (claude_desktop_config.json)",
    )
    setup_mcp_parser.add_argument(
        "--claude-code-config",
        default=None,
        help="Override the Claude Code CLI config file path (~/.claude.json)",
    )
    setup_mcp_parser.add_argument(
        "--codex-config",
        default=None,
        help="Override the Codex config.toml path",
    )
    setup_mcp_parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove the MCP entry instead of adding it",
    )
    setup_mcp_parser.add_argument(
        "--status",
        action="store_true",
        help="Print whether MCP is already configured and exit",
    )

    args = parser.parse_args(argv)
    app_paths = resolve_app_paths()
    paths = resolve_kb_paths(Path(args.kb_root))
    db_path = Path(args.app_db) if args.app_db else app_paths.db_path

    if args.command == "hook":
        if args.hook_event == "session-start":
            print(render_session_start_json(paths))
            return 0
        if args.hook_event == "session-end":
            capture_hook(sys.stdin.read(), paths, min_turns=1, context_prefix="session-flush")
            return 0
        if args.hook_event == "pre-compact":
            capture_hook(sys.stdin.read(), paths, min_turns=5, context_prefix="flush-context")
            return 0
        if args.hook_event == "post-compact":
            sys.stdin.read()  # drain stdin (Claude Code may send compaction metadata)
            store = ProfileStore(db_path)
            if store.get_setting("compile_on_compact", False):
                profile = store.get_active_profile()
                if profile is not None:
                    JobStore(db_path).enqueue(
                        profile_id=profile.id,
                        job_type="compile_changed",
                        payload={},
                        priority=90,
                    )
            return 0

    if args.command == "profiles":
        return _handle_profiles(args, db_path)

    if args.command == "jobs":
        return _handle_jobs(args, db_path)

    if args.command == "compile":
        result = compile_logs(
            paths,
            force_all=args.all,
            file_name=args.file,
            dry_run=args.dry_run,
        )
        if not result.files:
            print("Nothing to compile - all daily logs are up to date.")
            return 0
        print(f"{'[DRY RUN] ' if result.dry_run else ''}Files to compile ({len(result.files)}):")
        for file_name in result.files:
            print(f"  - {file_name}")
        return 0

    if args.command == "query":
        print(run_query(paths, args.question, file_back=args.file_back))
        return 0

    if args.command == "lint":
        result = run_lint(paths, structural_only=args.structural_only)
        if result.report_path:
            print(f"Report saved to: {result.report_path}")
        print(
            f"Results: {result.errors} errors, "
            f"{result.warnings} warnings, {result.suggestions} suggestions"
        )
        return 1 if result.errors else 0

    if args.command == "diagnostics":
        output_dir = Path(args.output) if args.output else None
        bundle = export_diagnostics(app_paths, paths, output_dir=output_dir)
        print(f"Diagnostics exported: {bundle}")
        return 0

    if args.command == "ui":
        return launch_ui(kb_root=paths.root, app_db=db_path, no_tray=args.no_tray)

    if args.command == "mcp":
        from kb_mcp.server import main as mcp_main
        return mcp_main(["--kb-root", str(paths.root), "--transport", args.transport])

    if args.command == "setup-mcp":
        return _handle_setup_mcp(args, paths.root)

    parser.error("unsupported command")
    return 2


def _handle_profiles(args: argparse.Namespace, db_path: Path) -> int:
    store = ProfileStore(db_path)
    if args.profiles_command == "list":
        profiles = store.list_profiles()
        if not profiles:
            print("No profiles configured.")
            return 0
        for profile in profiles:
            marker = "*" if profile.active else " "
            print(f"{marker} {profile.id}: {profile.name} [{profile.backend}] {profile.root_path}")
        return 0
    if args.profiles_command == "create":
        profile_id = store.create_profile(args.name, args.root_path, backend=args.backend)
        print(f"Created profile {profile_id}")
        return 0
    if args.profiles_command == "activate":
        store.set_active_profile(args.profile_id)
        print(f"Activated profile {args.profile_id}")
        return 0
    return 2


def _handle_setup_mcp(args: argparse.Namespace, kb_root: Path) -> int:
    client: str = args.client
    claude_config      = Path(args.claude_config)      if args.claude_config      else None
    claude_code_config = Path(args.claude_code_config) if args.claude_code_config else None
    codex_config       = Path(args.codex_config)       if args.codex_config       else None
    do_claude = client in ("claude", "both")
    do_codex  = client in ("codex", "both")

    if args.status:
        if do_claude:
            configured     = mcp_is_configured(config_path=claude_config)
            configured_cli = mcp_is_configured_claude_code(config_path=claude_code_config)
            print(f"Claude Desktop config : {claude_config or find_claude_config()}")
            print(f"  MCP configured: {'yes' if configured else 'no'}")
            print(f"Claude Code CLI config: {claude_code_config or find_claude_code_config()}")
            print(f"  MCP configured: {'yes' if configured_cli else 'no'}")
        if do_codex:
            configured_codex = mcp_is_configured_codex(config_path=codex_config)
            print(f"Codex config          : {codex_config or find_codex_config()}")
            print(f"  MCP configured: {'yes' if configured_codex else 'no'}")
        return 0

    exe_path = Path(args.exe_path) if args.exe_path else None

    if args.remove:
        if do_claude:
            result = remove_mcp(config_path=claude_config)
            print(f"Claude Desktop MCP removed from: {result}" if result else "Claude Desktop MCP entry not found.")
            result_cli = remove_mcp_claude_code(config_path=claude_code_config)
            print(f"Claude Code CLI MCP removed from: {result_cli}" if result_cli else "Claude Code CLI MCP entry not found.")
        if do_codex:
            result_codex = remove_mcp_codex(config_path=codex_config)
            print(f"Codex MCP removed from: {result_codex}" if result_codex else "Codex MCP entry not found.")
        return 0

    if do_claude:
        # Configure both Claude Desktop (claude_desktop_config.json) and
        # Claude Code CLI (~/.claude.json) — they are different apps/files.
        config_path = configure_mcp(kb_root, exe_path=exe_path, config_path=claude_config)
        print(f"Claude Desktop MCP configured in: {config_path}")
        config_path_cli = configure_mcp_claude_code(kb_root, exe_path=exe_path, config_path=claude_code_config)
        print(f"Claude Code CLI MCP configured in: {config_path_cli}")
    if do_codex:
        config_path_codex = configure_mcp_codex(kb_root, exe_path=exe_path, config_path=codex_config)
        print(f"Codex MCP configured in : {config_path_codex}")

    print(f"KB root: {kb_root}")
    print("Restart Claude Code / Codex to activate the MCP server.")
    return 0


def _handle_jobs(args: argparse.Namespace, db_path: Path) -> int:
    store = JobStore(db_path)
    if args.jobs_command == "enqueue":
        payload = json.loads(args.payload_json)
        if not isinstance(payload, dict):
            raise ValueError("--payload-json must be a JSON object")
        job_id = store.enqueue(
            profile_id=args.profile_id,
            job_type=args.job_type,
            payload=payload,
            priority=args.priority,
            backend=args.backend,
        )
        print(f"Queued job {job_id}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
