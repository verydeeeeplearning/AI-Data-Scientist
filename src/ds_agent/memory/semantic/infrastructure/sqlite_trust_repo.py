"""SQLite repository for table trust metadata."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.infrastructure.sqlite_base import (
    SemanticSqliteDatabase,
    json_dumps,
    json_loads,
)


class SqliteTableTrustRepository:
    """SQLite-backed trust registry repository."""

    def __init__(self, db: SemanticSqliteDatabase) -> None:
        self._db = db

    def get(self, fqtn: str) -> TableTrust | None:
        with self._db.lock, self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM semantic_table_trust WHERE fqtn = ?",
                (fqtn,),
            ).fetchone()
        return self._row_to_table(row) if row is not None else None

    def bulk_get(self, fqtns: Sequence[str]) -> list[TableTrust]:
        values = list(fqtns)
        if not values:
            return []
        placeholders = ", ".join("?" for _ in values)
        with self._db.lock, self._db.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM semantic_table_trust WHERE fqtn IN ({placeholders})",
                values,
            ).fetchall()
        return [self._row_to_table(row) for row in rows]

    def save(self, table: TableTrust) -> None:
        payload = table.model_dump(mode="json")
        with self._db.lock, self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO semantic_table_trust (
                    fqtn, grade, owner, description, refresh_json, columns_json,
                    approved_joins_json, grade_rationale, last_audited
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    table.fqtn,
                    table.grade.value,
                    table.owner,
                    table.description,
                    json_dumps(payload["refresh"]),
                    json_dumps(payload["columns"]),
                    json_dumps(payload["approved_joins"]),
                    table.grade_rationale,
                    table.last_audited.isoformat(),
                ),
            )
            conn.commit()

    @staticmethod
    def _row_to_table(row: sqlite3.Row) -> TableTrust:
        return TableTrust.model_validate(
            {
                "fqtn": str(row["fqtn"]),
                "grade": row["grade"],
                "owner": str(row["owner"]),
                "description": str(row["description"]),
                "refresh": json_loads(row["refresh_json"], default={}),
                "columns": json_loads(row["columns_json"], default=[]),
                "approved_joins": json_loads(row["approved_joins_json"], default=[]),
                "grade_rationale": str(row["grade_rationale"]),
                "last_audited": str(row["last_audited"]),
            }
        )
