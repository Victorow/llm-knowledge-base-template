"""Single executable entrypoint for source and packaged runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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
        choices=["session-start", "session-end", "pre-compact"],
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
