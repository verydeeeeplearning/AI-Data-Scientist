"""SQLite-backed persistence for lineage records."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from ds_agent.domain.entities.lineage import LineageRecord, LineageRecordType


class SqliteLineageStore:
    """Persist lineage records in a local SQLite database."""

    def __init__(self, db_path: str = "data/memory/lineage.db") -> None:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = path
        self._lock = threading.Lock()
        self._initialize()

    def save(self, record: LineageRecord) -> None:
        with self._lock, sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO lineage_records
                (id, record_type, parent_id, content_json, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.record_type.value,
                    record.parent_id,
                    json.dumps(record.content, default=str),
                    record.session_id,
                    record.timestamp,
                ),
            )
            conn.commit()

    def get(self, record_id: str) -> LineageRecord | None:
        with self._lock, sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT id, record_type, parent_id, content_json, session_id, created_at
                FROM lineage_records
                WHERE id = ?
                """,
                (record_id,),
            ).fetchone()
        return None if row is None else self._from_row(row)

    def list(
        self,
        *,
        session_id: str | None = None,
        parent_id: str | None = None,
        record_type: LineageRecordType | None = None,
        limit: int = 100,
    ) -> list[LineageRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if parent_id is not None:
            clauses.append("parent_id = ?")
            params.append(parent_id)
        if record_type is not None:
            clauses.append("record_type = ?")
            params.append(record_type.value)

        where = ""
        if clauses:
            where = "WHERE " + " AND ".join(clauses)

        with self._lock, sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT id, record_type, parent_id, content_json, session_id, created_at
                FROM lineage_records
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def latest_for_session(
        self,
        session_id: str,
        *,
        record_type: LineageRecordType | None = None,
    ) -> LineageRecord | None:
        results = self.list(session_id=session_id, record_type=record_type, limit=1)
        return results[0] if results else None

    def _initialize(self) -> None:
        with self._lock, sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lineage_records (
                    id TEXT PRIMARY KEY,
                    record_type TEXT NOT NULL,
                    parent_id TEXT,
                    content_json TEXT NOT NULL,
                    session_id TEXT,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_lineage_parent_id ON lineage_records(parent_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_lineage_session_id ON lineage_records(session_id)"
            )
            conn.commit()

    @staticmethod
    def _from_row(row: tuple[object, ...]) -> LineageRecord:
        record_id, record_type, parent_id, content_json, session_id, created_at = row
        content = json.loads(str(content_json))
        return LineageRecord(
            id=str(record_id),
            record_type=LineageRecordType(str(record_type)),
            parent_id=str(parent_id) if parent_id is not None else None,
            content=content if isinstance(content, dict) else {},
            session_id=str(session_id) if session_id is not None else None,
            timestamp=float(created_at),  # type: ignore[arg-type]
        )
