"""Redacted diagnostics bundle export."""

from __future__ import annotations

import json
import platform
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from kb_app.core.paths import AppPaths, KbPaths
from kb_app.diagnostics.redaction import redact_text


def export_diagnostics(
    app_paths: AppPaths,
    kb_paths: KbPaths,
    *,
    output_dir: Path | None = None,
    include_private: bool = False,
) -> Path:
    """Create a redacted diagnostics zip bundle."""
    target_dir = output_dir or app_paths.diagnostics_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    bundle_path = target_dir / f"llm-kb-diagnostics-{timestamp}.zip"

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "platform": platform.platform(),
        "app_config_dir": str(app_paths.config_dir),
        "app_state_dir": str(app_paths.state_dir),
        "kb_root": str(kb_paths.root),
        "include_private": include_private,
    }

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("metadata.json", json.dumps(metadata, indent=2))

        if app_paths.config_file.exists():
            zf.writestr(
                "config-redacted.txt",
                redact_text(app_paths.config_file.read_text(encoding="utf-8", errors="replace")),
            )

        _write_redacted_logs(zf, app_paths.logs_dir, "logs")
        _write_redacted_logs(zf, app_paths.job_logs_dir, "job-logs")

        if include_private:
            _write_private_kb_manifest(zf, kb_paths)

    return bundle_path


def _write_redacted_logs(zf: zipfile.ZipFile, logs_dir: Path, archive_root: str) -> None:
    if not logs_dir.exists():
        return
    for log_path in sorted(logs_dir.glob("*.log")):
        zf.writestr(
            f"{archive_root}/{log_path.name}",
            redact_text(log_path.read_text(encoding="utf-8", errors="replace")),
        )


def _write_private_kb_manifest(zf: zipfile.ZipFile, kb_paths: KbPaths) -> None:
    daily_count = len(list(kb_paths.daily_dir.glob("*.md"))) if kb_paths.daily_dir.exists() else 0
    knowledge_count = (
        len(list(kb_paths.knowledge_dir.rglob("*.md"))) if kb_paths.knowledge_dir.exists() else 0
    )
    zf.writestr(
        "kb-manifest.json",
        json.dumps({"daily_logs": daily_count, "knowledge_articles": knowledge_count}, indent=2),
    )
