"""SQLite repository for verified queries."""

from __future__ import annotations

import sqlite3
from datetime import date

from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery
from ds_agent.memory.semantic.infrastructure.sqlite_base import (
    SemanticSqliteDatabase,
    json_dumps,
    json_loads,
)


class SqliteVerifiedQueryRepository:
    """SQLite-backed verified query repository."""

    def __init__(self, db: SemanticSqliteDatabase) -> None:
        self._db = db

    def get(self, vq_id: str) -> VerifiedQuery | None:
        with self._db.lock, self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM semantic_verified_query WHERE vq_id = ?",
                (vq_id,),
            ).fetchone()
        return self._row_to_query(row) if row is not None else None

    def find_by_metric(
        self,
        metric_id: str,
        *,
        dialect: str | None = None,
    ) -> list[VerifiedQuery]:
        params: list[object] = [metric_id]
        where = "metric_id = ?"
        if dialect is not None:
            where += " AND dialect = ?"
            params.append(dialect)
        with self._db.lock, self._db.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM semantic_verified_query WHERE {where} ORDER BY last_verified DESC",
                params,
            ).fetchall()
        return [self._row_to_query(row) for row in rows]

    def save(self, query: VerifiedQuery) -> None:
        payload = query.model_dump(mode="json")
        with self._db.lock, self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO semantic_verified_query (
                    vq_id, metric_id, dialect, description, sql_template, parameters_json,
                    referenced_tables_json, verified_by, last_verified, verification_evidence,
                    failure_modes_json, tags_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query.vq_id,
                    query.metric_id,
                    query.dialect,
                    query.description,
                    query.sql_template,
                    json_dumps(payload["parameters"]),
                    json_dumps(payload["referenced_tables"]),
                    query.verified_by,
                    query.last_verified.isoformat(),
                    query.verification_evidence,
                    json_dumps(payload["failure_modes"]),
                    json_dumps(payload["tags"]),
                ),
            )
            conn.commit()

    def append_audit(
        self,
        vq_id: str,
        *,
        verified_by: str,
        verification_evidence: str,
        verified_at: date,
    ) -> None:
        with self._db.lock, self._db.connect() as conn:
            conn.execute(
                """
                INSERT INTO semantic_verified_query_audit (
                    vq_id, verified_by, verification_evidence, verified_at
                ) VALUES (?, ?, ?, ?)
                """,
                (vq_id, verified_by, verification_evidence, verified_at.isoformat()),
            )
            conn.commit()

    @staticmethod
    def _row_to_query(row: sqlite3.Row) -> VerifiedQuery:
        return VerifiedQuery.model_validate(
            {
                "vq_id": str(row["vq_id"]),
                "metric_id": str(row["metric_id"]) if row["metric_id"] is not None else None,
                "dialect": row["dialect"],
                "description": str(row["description"]),
                "sql_template": str(row["sql_template"]),
                "parameters": json_loads(row["parameters_json"], default=[]),
                "referenced_tables": json_loads(row["referenced_tables_json"], default=[]),
                "verified_by": str(row["verified_by"]),
                "last_verified": str(row["last_verified"]),
                "verification_evidence": str(row["verification_evidence"]),
                "failure_modes": json_loads(row["failure_modes_json"], default=[]),
                "tags": json_loads(row["tags_json"], default=[]),
            }
        )
