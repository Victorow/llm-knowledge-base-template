from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from kb_app.core.operations import (
    append_manual_memory,
    compile_logs,
    run_query,
    run_structural_lint,
    select_logs_to_compile,
)
from kb_app.core.paths import resolve_kb_paths
from kb_app.core.wiki import save_state


class OperationTests(unittest.TestCase):
    def make_kb(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "kb" / "daily").mkdir(parents=True)
        (root / "kb" / "knowledge" / "concepts").mkdir(parents=True)
        (root / "kb" / "knowledge" / "connections").mkdir(parents=True)
        (root / "kb" / "knowledge" / "qa").mkdir(parents=True)
        (root / "AGENTS.md").write_text("# Schema", encoding="utf-8")
        (root / "kb" / "knowledge" / "index.md").write_text("# Knowledge Base Index", encoding="utf-8")
        (root / "kb" / "knowledge" / "log.md").write_text("# Build Log", encoding="utf-8")
        return temp, root

    def test_select_logs_to_compile_skips_unchanged_logs(self) -> None:
        temp, root = self.make_kb()
        with temp:
            paths = resolve_kb_paths(root)
            daily = paths.daily_dir / "2026-05-11.md"
            daily.write_text("entry", encoding="utf-8")
            save_state(paths, {"ingested": {"2026-05-11.md": {"hash": "wrong"}}, "query_count": 0})

            self.assertEqual(select_logs_to_compile(paths, force_all=False, file_name=None), [daily])

            from kb_app.core.wiki import file_hash

            save_state(paths, {"ingested": {"2026-05-11.md": {"hash": file_hash(daily)}}})
            self.assertEqual(select_logs_to_compile(paths, force_all=False, file_name=None), [])

    def test_compile_logs_dry_run_returns_selected_files_without_backend_call(self) -> None:
        temp, root = self.make_kb()
        with temp:
            paths = resolve_kb_paths(root)
            (paths.daily_dir / "2026-05-11.md").write_text("entry", encoding="utf-8")

            result = compile_logs(paths, dry_run=True)

            self.assertTrue(result.dry_run)
            self.assertEqual(result.files, ["2026-05-11.md"])

    def test_query_updates_state_with_fake_backend(self) -> None:
        temp, root = self.make_kb()
        with temp:
            paths = resolve_kb_paths(root)

            async_result = AsyncMock()
            async_result.return_value.text = "answer"
            async_result.return_value.cost_usd = 0.25

            with patch("kb_app.core.operations.run_agent_text", async_result):
                answer = run_query(paths, "What changed?")

            self.assertEqual(answer, "answer")

    def test_structural_lint_reports_broken_links(self) -> None:
        temp, root = self.make_kb()
        with temp:
            paths = resolve_kb_paths(root)
            (paths.concepts_dir / "alpha.md").write_text("[[concepts/missing]]", encoding="utf-8")

            result = run_structural_lint(paths, write_report=False)

            self.assertEqual(result.errors, 1)
            self.assertEqual(result.issues[0]["check"], "broken_link")

    def test_manual_memory_appends_to_today_daily_log(self) -> None:
        temp, root = self.make_kb()
        with temp:
            paths = resolve_kb_paths(root)

            log_path = append_manual_memory(paths, "Important decision", today="2026-05-11", time_text="14:30")

            content = log_path.read_text(encoding="utf-8")
            self.assertIn("### Manual Memory (14:30)", content)
            self.assertIn("Important decision", content)


if __name__ == "__main__":
    unittest.main()
