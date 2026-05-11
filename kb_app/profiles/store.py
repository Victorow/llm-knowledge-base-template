"""SQLite-backed profile and settings storage."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class KbProfile:
    id: int
    name: str
    root_path: str
    backend: str
    active: bool
    created_at: str
    updated_at: str


class ProfileStore:
    """Owns KB profiles and global app settings."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS kb_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    root_path TEXT NOT NULL,
                    backend TEXT NOT NULL DEFAULT 'claude',
                    active INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def create_profile(self, name: str, root_path: str | Path, *, backend: str = "claude") -> int:
        now = utc_now()
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO kb_profiles (name, root_path, backend, active, created_at, updated_at)
                VALUES (?, ?, ?, 0, ?, ?)
                """,
                (name, str(root_path), backend, now, now),
            )
            return int(cursor.lastrowid)

    def get_profile(self, profile_id: int) -> KbProfile:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM kb_profiles WHERE id = ?",
                (profile_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Profile not found: {profile_id}")
        return self._row_to_profile(row)

    def list_profiles(self) -> list[KbProfile]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM kb_profiles ORDER BY name").fetchall()
        return [self._row_to_profile(row) for row in rows]

    def set_active_profile(self, profile_id: int) -> None:
        self.get_profile(profile_id)
        now = utc_now()
        with self._connection() as conn:
            conn.execute("UPDATE kb_profiles SET active = 0, updated_at = ?", (now,))
            conn.execute(
                "UPDATE kb_profiles SET active = 1, updated_at = ? WHERE id = ?",
                (now, profile_id),
            )

    def get_active_profile(self) -> KbProfile | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM kb_profiles WHERE active = 1 ORDER BY id LIMIT 1"
            ).fetchone()
        return self._row_to_profile(row) if row is not None else None

    def set_setting(self, key: str, value: Any) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO app_settings (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, json.dumps(value), utc_now()),
            )

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT value_json FROM app_settings WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return default
        return json.loads(row["value_json"])

    @staticmethod
    def _row_to_profile(row: sqlite3.Row) -> KbProfile:
        return KbProfile(
            id=int(row["id"]),
            name=str(row["name"]),
            root_path=str(row["root_path"]),
            backend=str(row["backend"]),
            active=bool(row["active"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
