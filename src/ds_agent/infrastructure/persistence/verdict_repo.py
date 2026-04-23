"""SQLite-backed repository for verifier verdicts."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from ds_agent.domain.entities.review_verdict import ReviewVerdict
from ds_agent.runtime.transcript_store import get_runtime_storage_root

_MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_verdicts (
    verdict_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_review_verdicts_task_created
    ON review_verdicts(task_id, created_at DESC);

INSERT OR REPLACE INTO schema_migrations(version, applied_at)
VALUES (1, datetime('now'));
"""


class SqliteVerdictRepository:
    """Persist verifier verdicts in a dedicated SQLite database."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    @classmethod
    def for_workspace(cls, workspace_dir: str | None = None) -> SqliteVerdictRepository:
        return cls(get_runtime_storage_root(workspace_dir) / "review_verdicts.db")

    def save(self, verdict: ReviewVerdict) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO review_verdicts (
                    verdict_id, task_id, created_at, payload_json
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    verdict.verdict_id,
                    verdict.task_id,
                    verdict.created_at.isoformat(),
                    verdict.model_dump_json(),
                ),
            )
            conn.commit()

    def get(self, verdict_id: str) -> ReviewVerdict | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM review_verdicts WHERE verdict_id = ?",
                (verdict_id,),
            ).fetchone()
        if row is None:
            return None
        return ReviewVerdict.model_validate_json(row["payload_json"])

    def list_for_task(self, task_id: str) -> list[ReviewVerdict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM review_verdicts
                WHERE task_id = ?
                ORDER BY created_at DESC
                """,
                (task_id,),
            ).fetchall()
        return [ReviewVerdict.model_validate_json(row["payload_json"]) for row in rows]

    def list_recent(self, *, limit: int = 50) -> list[ReviewVerdict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM review_verdicts
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [ReviewVerdict.model_validate_json(row["payload_json"]) for row in rows]

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(_MIGRATION_SQL)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn
