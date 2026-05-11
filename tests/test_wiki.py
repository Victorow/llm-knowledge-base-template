from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kb_app.core.paths import resolve_kb_paths
from kb_app.core.wiki import (
    count_inbound_links,
    extract_wikilinks,
    list_raw_files,
    list_wiki_articles,
    load_state,
    read_wiki_index,
    save_state,
    slugify,
    wiki_article_exists,
)


class WikiHelperTests(unittest.TestCase):
    def make_kb(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "kb" / "daily").mkdir(parents=True)
        (root / "kb" / "knowledge" / "concepts").mkdir(parents=True)
        (root / "kb" / "knowledge" / "connections").mkdir(parents=True)
        (root / "kb" / "knowledge" / "qa").mkdir(parents=True)
        return temp, root

    def test_state_round_trip_uses_kb_paths(self) -> None:
        temp, root = self.make_kb()
        with temp:
            paths = resolve_kb_paths(root)
            state = load_state(paths)
            state["query_count"] = 4

            save_state(paths, state)

            self.assertEqual(load_state(paths)["query_count"], 4)

    def test_index_fallback_and_article_listing(self) -> None:
        temp, root = self.make_kb()
        with temp:
            paths = resolve_kb_paths(root)
            (paths.concepts_dir / "alpha.md").write_text("[[concepts/beta]]", encoding="utf-8")
            (paths.connections_dir / "beta.md").write_text("content", encoding="utf-8")
            (paths.daily_dir / "2026-05-11.md").write_text("daily", encoding="utf-8")

            self.assertIn("# Knowledge Base Index", read_wiki_index(paths))
            self.assertEqual([p.name for p in list_raw_files(paths)], ["2026-05-11.md"])
            self.assertEqual(
                [p.relative_to(paths.knowledge_dir).as_posix() for p in list_wiki_articles(paths)],
                ["concepts/alpha.md", "connections/beta.md"],
            )

    def test_wikilinks_and_inbound_counts(self) -> None:
        temp, root = self.make_kb()
        with temp:
            paths = resolve_kb_paths(root)
            (paths.concepts_dir / "alpha.md").write_text("[[concepts/beta]]", encoding="utf-8")
            (paths.concepts_dir / "beta.md").write_text("[[daily/2026-05-11]]", encoding="utf-8")

            self.assertEqual(extract_wikilinks("[[concepts/a]] and [[daily/x]]"), ["concepts/a", "daily/x"])
            self.assertTrue(wiki_article_exists(paths, "concepts/beta"))
            self.assertEqual(count_inbound_links(paths, "concepts/beta"), 1)

    def test_slugify_removes_punctuation_and_normalizes_spacing(self) -> None:
        self.assertEqual(slugify("  Codex Hooks: Windows + Linux!  "), "codex-hooks-windows-linux")


if __name__ == "__main__":
    unittest.main()
