"""SQLite-backed durable job queue."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
ALLOWED_TRANSITIONS = {
    "queued": {"running", "cancel_requested", "cancelled"},
    "running": {"succeeded", "failed", "cancel_requested", "cancelled"},
    "cancel_requested": {"cancelled", "failed"},
}


class InvalidJobTransition(ValueError):
    """Raised when a job transition would corrupt lifecycle state."""


@dataclass(frozen=True)
class JobRecord:
    id: str
    profile_id: int
    job_type: str
    status: str
    priority: int
    backend: str | None
    command_summary: str
    payload: dict[str, Any]
    result: dict[str, Any]
    error_message: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    mutation_snapshot: str | None


@dataclass(frozen=True)
class JobEvent:
    id: int
    job_id: str
    event: str
    message: str
    created_at: str


@dataclass(frozen=True)
class JobArtifact:
    id: int
    job_id: str
    kind: str
    path: str
    created_at: str


class JobStore:
    """Stores durable jobs, events, and artifacts."""

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
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    profile_id INTEGER NOT NULL,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    backend TEXT,
                    command_summary TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    result_json TEXT NOT NULL DEFAULT '{}',
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    mutation_snapshot TEXT
                );

                CREATE TABLE IF NOT EXISTS job_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS job_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def enqueue(
        self,
        *,
        profile_id: int,
        job_type: str,
        payload: dict[str, Any] | None = None,
        priority: int = 100,
        backend: str | None = None,
        command_summary: str = "",
    ) -> str:
        job_id = str(uuid.uuid4())
        now = utc_now()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    id, profile_id, job_type, status, priority, backend, command_summary,
                    payload_json, result_json, created_at
                )
                VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, '{}', ?)
                """,
                (
                    job_id,
                    profile_id,
                    job_type,
                    priority,
                    backend,
                    command_summary,
                    json.dumps(payload or {}),
                    now,
                ),
            )
        self.log_event(job_id, "queued")
        return job_id

    def claim_next(self) -> JobRecord | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id FROM jobs
                WHERE status = 'queued'
                ORDER BY priority ASC, created_at ASC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        self.transition(str(row["id"]), "running")
        return self.get_job(str(row["id"]))

    def get_job(self, job_id: str) -> JobRecord:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"Job not found: {job_id}")
        return self._row_to_job(row)

    def transition(
        self,
        job_id: str,
        status: str,
        *,
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
        message: str = "",
    ) -> None:
        current = self.get_job(job_id)
        allowed = ALLOWED_TRANSITIONS.get(current.status, set())
        if status not in allowed:
            raise InvalidJobTransition(f"Cannot transition {current.status} -> {status}")

        now = utc_now()
        started_at = current.started_at
        finished_at = current.finished_at
        if status == "running":
            started_at = now
        if status in TERMINAL_STATUSES:
            finished_at = now

        with self._connection() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, result_json = ?, error_message = ?, started_at = ?,
                    finished_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    json.dumps(result if result is not None else current.result),
                    error_message,
                    started_at,
                    finished_at,
                    job_id,
                ),
            )
        self.log_event(job_id, status, message)

    def mark_succeeded(self, job_id: str, result: dict[str, Any]) -> None:
        self.transition(job_id, "succeeded", result=result)

    def mark_failed(self, job_id: str, error_message: str) -> None:
        self.transition(job_id, "failed", error_message=error_message, message=error_message)

    def request_cancel(self, job_id: str) -> None:
        self.transition(job_id, "cancel_requested", message="Cancellation requested")

    def mark_cancelled(self, job_id: str, result: dict[str, Any] | None = None) -> None:
        self.transition(job_id, "cancelled", result=result or {}, message="Cancelled")

    def log_event(self, job_id: str, event: str, message: str = "") -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO job_events (job_id, event, message, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (job_id, event, message, utc_now()),
            )

    def list_events(self, job_id: str) -> list[JobEvent]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM job_events WHERE job_id = ? ORDER BY id",
                (job_id,),
            ).fetchall()
        return [
            JobEvent(
                id=int(row["id"]),
                job_id=str(row["job_id"]),
                event=str(row["event"]),
                message=str(row["message"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def add_artifact(self, job_id: str, kind: str, path: str) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO job_artifacts (job_id, kind, path, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (job_id, kind, path, utc_now()),
            )

    def list_artifacts(self, job_id: str) -> list[JobArtifact]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM job_artifacts WHERE job_id = ? ORDER BY id",
                (job_id,),
            ).fetchall()
        return [
            JobArtifact(
                id=int(row["id"]),
                job_id=str(row["job_id"]),
                kind=str(row["kind"]),
                path=str(row["path"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            id=str(row["id"]),
            profile_id=int(row["profile_id"]),
            job_type=str(row["job_type"]),
            status=str(row["status"]),
            priority=int(row["priority"]),
            backend=row["backend"],
            command_summary=str(row["command_summary"]),
            payload=json.loads(row["payload_json"] or "{}"),
            result=json.loads(row["result_json"] or "{}"),
            error_message=row["error_message"],
            created_at=str(row["created_at"]),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            mutation_snapshot=row["mutation_snapshot"],
        )
