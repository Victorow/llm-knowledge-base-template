from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from kb_app.core.paths import resolve_app_paths, resolve_kb_paths
from kb_app.diagnostics.export import export_diagnostics
from kb_app.diagnostics.redaction import redact_text


class DiagnosticsTests(unittest.TestCase):
    def test_redact_text_masks_common_secret_values(self) -> None:
        text = "\n".join(
            [
                "OPENAI_API_KEY=sk-secret",
                "password = hunter2",
                "cookie: session-value",
                "normal=value",
            ]
        )

        redacted = redact_text(text)

        self.assertNotIn("sk-secret", redacted)
        self.assertNotIn("hunter2", redacted)
        self.assertNotIn("session-value", redacted)
        self.assertIn("normal=value", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_diagnostics_export_redacts_config_and_excludes_private_kb_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_home = root / "home"
            app_paths = resolve_app_paths(
                platform="linux",
                env={
                    "HOME": str(app_home),
                    "XDG_CONFIG_HOME": str(app_home / ".config"),
                    "XDG_STATE_HOME": str(app_home / ".local" / "state"),
                },
            )
            kb_root = root / "kb-root"
            kb_paths = resolve_kb_paths(kb_root)
            app_paths.config_dir.mkdir(parents=True)
            kb_paths.daily_dir.mkdir(parents=True)
            kb_paths.knowledge_dir.mkdir(parents=True)
            app_paths.config_file.write_text(
                "OPENAI_API_KEY=sk-secret\nnormal=value",
                encoding="utf-8",
            )
            (kb_paths.daily_dir / "2026-05-11.md").write_text(
                "private transcript content",
                encoding="utf-8",
            )

            bundle = export_diagnostics(app_paths, kb_paths, output_dir=root / "out")

            with zipfile.ZipFile(bundle) as zf:
                names = set(zf.namelist())
                metadata = json.loads(zf.read("metadata.json").decode("utf-8"))
                config = zf.read("config-redacted.txt").decode("utf-8")

            self.assertEqual(metadata["kb_root"], str(kb_root))
            self.assertIn("config-redacted.txt", names)
            self.assertNotIn("sk-secret", config)
            self.assertNotIn("kb/daily/2026-05-11.md", names)


if __name__ == "__main__":
    unittest.main()
