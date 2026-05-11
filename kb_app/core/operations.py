"""High-level KB operations used by CLI, jobs, hooks, and UI."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from kb_app.core.agent_backend import run_agent_text
from kb_app.core.paths import KbPaths
from kb_app.core.wiki import (
    count_inbound_links,
    extract_wikilinks,
    file_hash,
    get_article_word_count,
    list_raw_files,
    list_wiki_articles,
    load_state,
    read_all_wiki_content,
    read_wiki_index,
    save_state,
    wiki_article_exists,
)


@dataclass(frozen=True)
class CompileResult:
    files: list[str]
    dry_run: bool
    total_cost: float = 0.0


@dataclass(frozen=True)
class LintResult:
    issues: list[dict]
    report: str
    report_path: Path | None = None

    @property
    def errors(self) -> int:
        return sum(1 for issue in self.issues if issue["severity"] == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for issue in self.issues if issue["severity"] == "warning")

    @property
    def suggestions(self) -> int:
        return sum(1 for issue in self.issues if issue["severity"] == "suggestion")


def now_iso() -> str:
    """Current timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    """Current local date in ISO 8601 format."""
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")


def select_logs_to_compile(
    paths: KbPaths,
    *,
    force_all: bool = False,
    file_name: str | None = None,
) -> list[Path]:
    """Select daily logs that need compilation."""
    if file_name:
        target = Path(file_name)
        if not target.is_absolute():
            target = paths.daily_dir / target.name
        if not target.exists():
            fallback = paths.root / file_name
            if fallback.exists():
                target = fallback
        if not target.exists():
            raise FileNotFoundError(f"{file_name} not found")
        return [target]

    all_logs = list_raw_files(paths)
    if force_all:
        return all_logs

    state = load_state(paths)
    selected: list[Path] = []
    for log_path in all_logs:
        previous = state.get("ingested", {}).get(log_path.name, {})
        if not previous or previous.get("hash") != file_hash(log_path):
            selected.append(log_path)
    return selected


def compile_logs(
    paths: KbPaths,
    *,
    force_all: bool = False,
    file_name: str | None = None,
    dry_run: bool = False,
    backend: str | None = None,
) -> CompileResult:
    """Compile selected daily logs into knowledge articles."""
    selected = select_logs_to_compile(paths, force_all=force_all, file_name=file_name)
    file_names = [path.name for path in selected]
    if dry_run or not selected:
        return CompileResult(files=file_names, dry_run=dry_run, total_cost=0.0)

    state = load_state(paths)
    total_cost = 0.0
    for log_path in selected:
        total_cost += asyncio.run(_compile_daily_log(paths, log_path, state, backend=backend))

    return CompileResult(files=file_names, dry_run=False, total_cost=total_cost)


async def _compile_daily_log(
    paths: KbPaths,
    log_path: Path,
    state: dict,
    *,
    backend: str | None,
) -> float:
    log_content = log_path.read_text(encoding="utf-8")
    schema = (
        paths.agents_file.read_text(encoding="utf-8")
        if paths.agents_file.exists()
        else "# Knowledge Base Schema"
    )
    wiki_index = read_wiki_index(paths)

    existing_articles_context = ""
    existing_parts: list[str] = []
    for article_path in list_wiki_articles(paths):
        rel = article_path.relative_to(paths.knowledge_dir).as_posix()
        content = article_path.read_text(encoding="utf-8")
        existing_parts.append(f"### {rel}\n```markdown\n{content}\n```")
    if existing_parts:
        existing_articles_context = "\n\n".join(existing_parts)

    timestamp = now_iso()
    prompt = f"""You are a knowledge compiler. Read a daily conversation log and update
the markdown knowledge base following the schema exactly.

## Schema

{schema}

## Current Wiki Index

{wiki_index}

## Existing Wiki Articles

{existing_articles_context if existing_articles_context else "(No existing articles yet)"}

## Daily Log

File: {log_path.name}

{log_content}

## Task

Create or update concept and connection articles, update `kb/knowledge/index.md`,
and append a compile entry to `kb/knowledge/log.md`.

Use these paths:
- concepts: {paths.concepts_dir}
- connections: {paths.connections_dir}
- index: {paths.index_file}
- log: {paths.log_file}
- timestamp: {timestamp}
"""
    result = await run_agent_text(
        prompt=prompt,
        cwd=paths.root,
        writable=True,
        backend=backend,
        claude_allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
        claude_system_prompt={"type": "preset", "preset": "claude_code"},
        claude_permission_mode="acceptEdits",
        claude_max_turns=30,
        timeout_seconds=int(os.environ.get("KB_COMPILE_TIMEOUT_SECONDS", "3600")),
    )

    cost = result.cost_usd
    state.setdefault("ingested", {})[log_path.name] = {
        "hash": file_hash(log_path),
        "compiled_at": now_iso(),
        "cost_usd": cost,
    }
    state["total_cost"] = state.get("total_cost", 0.0) + cost
    save_state(paths, state)
    return cost


def run_query(
    paths: KbPaths,
    question: str,
    *,
    file_back: bool = False,
    backend: str | None = None,
) -> str:
    """Query the knowledge base and optionally file the answer back."""
    wiki_content = read_all_wiki_content(paths)
    tools = ["Read", "Glob", "Grep"]
    if file_back:
        tools.extend(["Write", "Edit"])

    file_back_instructions = ""
    if file_back:
        timestamp = now_iso()
        file_back_instructions = f"""

## File Back Instructions

Create a Q&A article in {paths.qa_dir}, update {paths.index_file}, and append
a query entry to {paths.log_file}. Timestamp: {timestamp}.
"""

    prompt = f"""You are a knowledge base query engine. Answer by consulting the
knowledge base below. Cite sources using [[wikilinks]]. If the KB lacks relevant
information, say so honestly.

## Knowledge Base

{wiki_content}

## Question

{question}
{file_back_instructions}"""

    try:
        result = asyncio.run(
            run_agent_text(
                prompt=prompt,
                cwd=paths.root,
                writable=file_back,
                backend=backend,
                claude_allowed_tools=tools,
                claude_system_prompt={"type": "preset", "preset": "claude_code"},
                claude_permission_mode="acceptEdits",
                claude_max_turns=15,
                timeout_seconds=int(os.environ.get("KB_QUERY_TIMEOUT_SECONDS", "1800")),
            )
        )
        answer = result.text
        cost = result.cost_usd
    except Exception as e:
        answer = f"Error querying knowledge base: {e}"
        cost = 0.0

    state = load_state(paths)
    state["query_count"] = state.get("query_count", 0) + 1
    state["total_cost"] = state.get("total_cost", 0.0) + cost
    save_state(paths, state)
    return answer


def append_manual_memory(
    paths: KbPaths,
    content: str,
    *,
    today: str | None = None,
    time_text: str | None = None,
) -> Path:
    """Append a user-authored memory entry to a daily log."""
    date_text = today or today_iso()
    time_value = time_text or datetime.now(timezone.utc).astimezone().strftime("%H:%M")
    paths.daily_dir.mkdir(parents=True, exist_ok=True)
    log_path = paths.daily_dir / f"{date_text}.md"

    if not log_path.exists():
        log_path.write_text(f"# Daily Log: {date_text}\n\n## Sessions\n\n", encoding="utf-8")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"### Manual Memory ({time_value})\n\n{content.strip()}\n\n")

    return log_path


def run_structural_lint(paths: KbPaths, *, write_report: bool = True) -> LintResult:
    """Run free structural health checks."""
    issues: list[dict] = []
    checks = [
        check_broken_links,
        check_orphan_pages,
        check_orphan_sources,
        check_stale_articles,
        check_missing_backlinks,
        check_sparse_articles,
    ]
    for check in checks:
        issues.extend(check(paths))

    report = generate_lint_report(issues)
    report_path = None
    if write_report:
        paths.reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = paths.reports_dir / f"lint-{today_iso()}.md"
        report_path.write_text(report, encoding="utf-8")

    state = load_state(paths)
    state["last_lint"] = now_iso()
    save_state(paths, state)
    return LintResult(issues=issues, report=report, report_path=report_path)


def run_lint(
    paths: KbPaths,
    *,
    structural_only: bool = False,
    write_report: bool = True,
    backend: str | None = None,
) -> LintResult:
    """Run structural lint and optionally LLM contradiction checks."""
    structural = run_structural_lint(paths, write_report=False)
    issues = list(structural.issues)

    if not structural_only:
        issues.extend(asyncio.run(check_contradictions(paths, backend=backend)))

    report = generate_lint_report(issues)
    report_path = None
    if write_report:
        paths.reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = paths.reports_dir / f"lint-{today_iso()}.md"
        report_path.write_text(report, encoding="utf-8")

    state = load_state(paths)
    state["last_lint"] = now_iso()
    save_state(paths, state)
    return LintResult(issues=issues, report=report, report_path=report_path)


async def check_contradictions(paths: KbPaths, *, backend: str | None = None) -> list[dict]:
    """Use the selected LLM backend to detect cross-article contradictions."""
    wiki_content = read_all_wiki_content(paths)
    prompt = f"""Review this knowledge base for contradictions, inconsistencies, or
conflicting claims across articles.

## Knowledge Base

{wiki_content}

## Instructions

For each issue found, output exactly one line in this format:
CONTRADICTION: [file1] vs [file2] - description
INCONSISTENCY: [file] - description

If no issues are found, output exactly: NO_ISSUES
"""

    try:
        result = await run_agent_text(
            prompt=prompt,
            cwd=paths.root,
            writable=False,
            backend=backend,
            claude_allowed_tools=[],
            claude_max_turns=2,
            timeout_seconds=int(os.environ.get("KB_LINT_TIMEOUT_SECONDS", "900")),
        )
    except Exception as e:
        return [
            {
                "severity": "error",
                "check": "contradiction",
                "file": "(system)",
                "detail": f"LLM check failed: {e}",
            }
        ]

    response = result.text.strip()
    if "NO_ISSUES" in response:
        return []

    issues = []
    for line in response.splitlines():
        line = line.strip()
        if line.startswith(("CONTRADICTION:", "INCONSISTENCY:")):
            issues.append(
                {
                    "severity": "warning",
                    "check": "contradiction",
                    "file": "(cross-article)",
                    "detail": line,
                }
            )
    return issues


def check_broken_links(paths: KbPaths) -> list[dict]:
    issues = []
    for article in list_wiki_articles(paths):
        content = article.read_text(encoding="utf-8")
        rel = article.relative_to(paths.knowledge_dir).as_posix()
        for link in extract_wikilinks(content):
            if link.startswith("daily/"):
                continue
            if not wiki_article_exists(paths, link):
                issues.append(
                    {
                        "severity": "error",
                        "check": "broken_link",
                        "file": rel,
                        "detail": f"Broken link: [[{link}]] - target does not exist",
                    }
                )
    return issues


def check_orphan_pages(paths: KbPaths) -> list[dict]:
    issues = []
    for article in list_wiki_articles(paths):
        rel = article.relative_to(paths.knowledge_dir).as_posix()
        target = rel.replace(".md", "")
        inbound = count_inbound_links(paths, target)
        if inbound == 0:
            issues.append(
                {
                    "severity": "warning",
                    "check": "orphan_page",
                    "file": rel,
                    "detail": f"Orphan page: no other articles link to [[{target}]]",
                }
            )
    return issues


def check_orphan_sources(paths: KbPaths) -> list[dict]:
    state = load_state(paths)
    ingested = state.get("ingested", {})
    issues = []
    for log_path in list_raw_files(paths):
        if log_path.name not in ingested:
            issues.append(
                {
                    "severity": "warning",
                    "check": "orphan_source",
                    "file": f"daily/{log_path.name}",
                    "detail": f"Uncompiled daily log: {log_path.name} has not been ingested",
                }
            )
    return issues


def check_stale_articles(paths: KbPaths) -> list[dict]:
    state = load_state(paths)
    ingested = state.get("ingested", {})
    issues = []
    for log_path in list_raw_files(paths):
        previous = ingested.get(log_path.name)
        if previous and previous.get("hash") != file_hash(log_path):
            issues.append(
                {
                    "severity": "warning",
                    "check": "stale_article",
                    "file": f"daily/{log_path.name}",
                    "detail": f"Stale: {log_path.name} has changed since last compilation",
                }
            )
    return issues


def check_missing_backlinks(paths: KbPaths) -> list[dict]:
    issues = []
    for article in list_wiki_articles(paths):
        content = article.read_text(encoding="utf-8")
        rel = article.relative_to(paths.knowledge_dir).as_posix()
        source_link = rel.replace(".md", "")

        for link in extract_wikilinks(content):
            if link.startswith("daily/"):
                continue
            target_path = paths.knowledge_dir / f"{link}.md"
            if target_path.exists():
                target_content = target_path.read_text(encoding="utf-8")
                if f"[[{source_link}]]" not in target_content:
                    issues.append(
                        {
                            "severity": "suggestion",
                            "check": "missing_backlink",
                            "file": rel,
                            "detail": f"[[{source_link}]] links to [[{link}]] but not vice versa",
                            "auto_fixable": True,
                        }
                    )
    return issues


def check_sparse_articles(paths: KbPaths) -> list[dict]:
    issues = []
    for article in list_wiki_articles(paths):
        word_count = get_article_word_count(article)
        if word_count < 200:
            rel = article.relative_to(paths.knowledge_dir).as_posix()
            issues.append(
                {
                    "severity": "suggestion",
                    "check": "sparse_article",
                    "file": rel,
                    "detail": f"Sparse article: {word_count} words (minimum recommended: 200)",
                }
            )
    return issues


def generate_lint_report(issues: list[dict]) -> str:
    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    suggestions = [i for i in issues if i["severity"] == "suggestion"]

    lines = [
        f"# Lint Report - {today_iso()}",
        "",
        f"**Total issues:** {len(issues)}",
        f"- Errors: {len(errors)}",
        f"- Warnings: {len(warnings)}",
        f"- Suggestions: {len(suggestions)}",
        "",
    ]

    for title, group, marker in [
        ("Errors", errors, "x"),
        ("Warnings", warnings, "!"),
        ("Suggestions", suggestions, "?"),
    ]:
        if not group:
            continue
        lines.append(f"## {title}")
        lines.append("")
        for issue in group:
            fixable = " (auto-fixable)" if issue.get("auto_fixable") else ""
            lines.append(f"- **[{marker}]** `{issue['file']}` - {issue['detail']}{fixable}")
        lines.append("")

    if not issues:
        lines.append("All checks passed. Knowledge base is healthy.")
        lines.append("")

    return "\n".join(lines)
