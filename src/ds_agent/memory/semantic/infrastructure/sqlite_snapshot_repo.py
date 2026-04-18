"""SQLite repository for semantic snapshots and rollback."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from ds_agent.memory.semantic.application.ports import (
    SemanticSnapshotRepository,
    SemanticSnapshotSummary,
)
from ds_agent.memory.semantic.infrastructure.sqlite_base import (
    SemanticSqliteDatabase,
    json_dumps,
    json_loads,
)

_SNAPSHOT_TABLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("semantic_metric", ("metric_id",)),
    ("semantic_glossary", ("term_id",)),
    ("semantic_table_trust", ("fqtn",)),
    ("semantic_verified_query", ("vq_id",)),
    # Secondary tables are restored after their parents.
    ("semantic_metric_synonym", ("metric_id", "synonym")),
    ("semantic_verified_query_audit", ("audit_id",)),
)


class SqliteSemanticSnapshotRepository(SemanticSnapshotRepository):
    """Persist and restore semantic snapshots against the canonical SQLite store."""

    def __init__(self, db: SemanticSqliteDatabase) -> None:
        self._db = db

    def create(
        self,
        *,
        snapshot_id: str,
        source_name: str,
        created_at: datetime,
        note: str | None = None,
    ) -> SemanticSnapshotSummary:
        table_counts: dict[str, int] = {}
        with self._db.lock, self._db.connect() as conn:
            conn.execute(
                """
                INSERT INTO semantic_snapshot_manifest (
                    snapshot_id, source_name, created_at, note, table_counts_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    source_name,
                    created_at.isoformat(),
                    note,
                    json_dumps({}),
                ),
            )
            for table_name, row_keys in _SNAPSHOT_TABLES:
                rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
                table_counts[table_name] = len(rows)
                conn.executemany(
                    """
                    INSERT INTO semantic_snapshot_row (
                        snapshot_id, table_name, row_key, payload_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            snapshot_id,
                            table_name,
                            _row_key(row, row_keys),
                            json_dumps(_row_to_payload(row)),
                        )
                        for row in rows
                    ],
                )
            conn.execute(
                """
                UPDATE semantic_snapshot_manifest
                SET table_counts_json = ?
                WHERE snapshot_id = ?
                """,
                (json_dumps(table_counts), snapshot_id),
            )
            conn.commit()
        return SemanticSnapshotSummary(
            snapshot_id=snapshot_id,
            source_name=source_name,
            created_at=created_at,
            note=note,
            table_counts=table_counts,
        )

    def get(self, snapshot_id: str) -> SemanticSnapshotSummary | None:
        with self._db.lock, self._db.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM semantic_snapshot_manifest
                WHERE snapshot_id = ?
                """,
                (snapshot_id,),
            ).fetchone()
        return self._row_to_summary(row) if row is not None else None

    def list(self, *, limit: int = 20) -> list[SemanticSnapshotSummary]:
        with self._db.lock, self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM semantic_snapshot_manifest
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_summary(row) for row in rows]

    def restore(self, snapshot_id: str) -> SemanticSnapshotSummary | None:
        summary = self.get(snapshot_id)
        if summary is None:
            return None

        with self._db.lock, self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT table_name, payload_json
                FROM semantic_snapshot_row
                WHERE snapshot_id = ?
                ORDER BY table_name, row_key
                """,
                (snapshot_id,),
            ).fetchall()
            rows_by_table: dict[str, list[dict[str, Any]]] = {
                table_name: [] for table_name, _row_keys in _SNAPSHOT_TABLES
            }
            for row in rows:
                table_name = str(row["table_name"])
                rows_by_table.setdefault(table_name, []).append(
                    json_loads(row["payload_json"], default={})
                )

            for table_name, _row_keys in reversed(_SNAPSHOT_TABLES):
                conn.execute(f"DELETE FROM {table_name}")
            conn.execute("DELETE FROM semantic_metric_fts")
            conn.execute("DELETE FROM semantic_glossary_fts")
            for table_name, payloads in rows_by_table.items():
                for payload in payloads:
                    columns = list(payload.keys())
                    if not columns:
                        continue
                    placeholders = ", ".join("?" for _ in columns)
                    column_sql = ", ".join(columns)
                    conn.execute(
                        f"INSERT INTO {table_name} ({column_sql}) VALUES ({placeholders})",
                        [payload[column] for column in columns],
                    )
            conn.commit()
        return summary

    @staticmethod
    def _row_to_summary(row: sqlite3.Row) -> SemanticSnapshotSummary:
        return SemanticSnapshotSummary(
            snapshot_id=str(row["snapshot_id"]),
            source_name=str(row["source_name"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            note=str(row["note"]) if row["note"] is not None else None,
            table_counts=json_loads(row["table_counts_json"], default={}),
        )


def _row_to_payload(row: sqlite3.Row) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    keys = row.keys()
    for key in keys:
        payload[str(key)] = row[key]
    return payload


def _row_key(row: sqlite3.Row, row_keys: tuple[str, ...]) -> str:
    return "::".join(str(row[key]) for key in row_keys)
