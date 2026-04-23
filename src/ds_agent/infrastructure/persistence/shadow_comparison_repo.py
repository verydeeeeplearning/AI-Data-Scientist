"""SQLite-backed repository for verifier shadow comparison logs."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from ds_agent.domain.entities.shadow_comparison import ShadowComparisonRecord
from ds_agent.runtime.transcript_store import get_runtime_storage_root

_MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verifier_shadow_comparisons (
    comparison_id TEXT PRIMARY KEY,
    verdict_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shadow_comparisons_task_created
    ON verifier_shadow_comparisons(task_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_shadow_comparisons_verdict_created
    ON verifier_shadow_comparisons(verdict_id, created_at DESC);

INSERT OR REPLACE INTO schema_migrations(version, applied_at)
VALUES (1, datetime('now'));
"""


class SqliteShadowComparisonRepository:
    """Persist shadow-mode comparison records in SQLite."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    @classmethod
    def for_workspace(cls, workspace_dir: str | None = None) -> SqliteShadowComparisonRepository:
        return cls(get_runtime_storage_root(workspace_dir) / "verifier_shadow.db")

    def save(self, record: ShadowComparisonRecord) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO verifier_shadow_comparisons (
                    comparison_id, verdict_id, task_id, created_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.comparison_id,
                    record.verdict_id,
                    record.task_id,
                    record.created_at.isoformat(),
                    record.model_dump_json(),
                ),
            )
            conn.commit()

    def get(self, comparison_id: str) -> ShadowComparisonRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM verifier_shadow_comparisons
                WHERE comparison_id = ?
                """,
                (comparison_id,),
            ).fetchone()
        if row is None:
            return None
        return ShadowComparisonRecord.model_validate_json(row["payload_json"])

    def list_for_task(self, task_id: str) -> list[ShadowComparisonRecord]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM verifier_shadow_comparisons
                WHERE task_id = ?
                ORDER BY created_at DESC
                """,
                (task_id,),
            ).fetchall()
        return [ShadowComparisonRecord.model_validate_json(row["payload_json"]) for row in rows]

    def list_for_verdict(self, verdict_id: str) -> list[ShadowComparisonRecord]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM verifier_shadow_comparisons
                WHERE verdict_id = ?
                ORDER BY created_at DESC
                """,
                (verdict_id,),
            ).fetchall()
        return [ShadowComparisonRecord.model_validate_json(row["payload_json"]) for row in rows]

    def list_recent(self, *, limit: int = 50) -> list[ShadowComparisonRecord]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM verifier_shadow_comparisons
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [ShadowComparisonRecord.model_validate_json(row["payload_json"]) for row in rows]

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(_MIGRATION_SQL)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn
