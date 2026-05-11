"""Filesystem helpers for the markdown knowledge base."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from kb_app.core.paths import KbPaths


DEFAULT_STATE = {"ingested": {}, "query_count": 0, "last_lint": None, "total_cost": 0.0}


def load_state(paths: KbPaths) -> dict:
    """Load persistent compiler/query state."""
    if paths.state_file.exists():
        try:
            return json.loads(paths.state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_STATE)


def save_state(paths: KbPaths, state: dict) -> None:
    """Save persistent compiler/query state."""
    paths.state_file.parent.mkdir(parents=True, exist_ok=True)
    paths.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")


def file_hash(path: Path) -> str:
    """SHA-256 hash of a file, shortened for compact state files."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    value = text.lower().strip()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"[\s_]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-")


def extract_wikilinks(content: str) -> list[str]:
    """Extract all Obsidian-style wikilinks from markdown content."""
    return re.findall(r"\[\[([^\]]+)\]\]", content)


def wiki_article_exists(paths: KbPaths, link: str) -> bool:
    """Check if a wikilink target exists in the knowledge directory."""
    return (paths.knowledge_dir / f"{link}.md").exists()


def read_wiki_index(paths: KbPaths) -> str:
    """Read the knowledge base index, returning an empty table if absent."""
    if paths.index_file.exists():
        return paths.index_file.read_text(encoding="utf-8")
    return (
        "# Knowledge Base Index\n\n"
        "| Article | Summary | Compiled From | Updated |\n"
        "|---------|---------|---------------|---------|"
    )


def read_all_wiki_content(paths: KbPaths) -> str:
    """Read index and all articles into one prompt-friendly markdown string."""
    parts = [f"## INDEX\n\n{read_wiki_index(paths)}"]

    for article in list_wiki_articles(paths):
        rel = article.relative_to(paths.knowledge_dir)
        parts.append(f"## {rel.as_posix()}\n\n{article.read_text(encoding='utf-8')}")

    return "\n\n---\n\n".join(parts)


def list_wiki_articles(paths: KbPaths) -> list[Path]:
    """List concept, connection, and Q&A article files."""
    articles: list[Path] = []
    for directory in [paths.concepts_dir, paths.connections_dir, paths.qa_dir]:
        if directory.exists():
            articles.extend(sorted(directory.glob("*.md")))
    return articles


def list_raw_files(paths: KbPaths) -> list[Path]:
    """List daily log markdown files."""
    if not paths.daily_dir.exists():
        return []
    return sorted(paths.daily_dir.glob("*.md"))


def count_inbound_links(
    paths: KbPaths,
    target: str,
    *,
    exclude_file: Path | None = None,
) -> int:
    """Count articles that link to a target wikilink."""
    count = 0
    for article in list_wiki_articles(paths):
        if exclude_file is not None and article == exclude_file:
            continue
        content = article.read_text(encoding="utf-8")
        if f"[[{target}]]" in content:
            count += 1
    return count


def get_article_word_count(path: Path) -> int:
    """Count words in an article, excluding YAML frontmatter."""
    content = path.read_text(encoding="utf-8")
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3 :]
    return len(content.split())


def build_index_entry(rel_path: str, summary: str, sources: str, updated: str) -> str:
    """Build a markdown table row for the knowledge index."""
    link = rel_path.replace(".md", "")
    return f"| [[{link}]] | {summary} | {sources} | {updated} |"
