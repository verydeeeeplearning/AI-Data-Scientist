"""SQLite repository for semantic metrics."""

from __future__ import annotations

import sqlite3
from collections import OrderedDict

from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.infrastructure.sqlite_base import (
    SemanticSqliteDatabase,
    json_dumps,
    json_loads,
    prepare_fts_query,
)


class SqliteMetricRepository:
    """SQLite-backed metric catalog repository."""

    def __init__(self, db: SemanticSqliteDatabase) -> None:
        self._db = db

    def get(self, metric_id: str) -> Metric | None:
        with self._db.lock, self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM semantic_metric WHERE metric_id = ?",
                (metric_id,),
            ).fetchone()
        return self._row_to_metric(row) if row is not None else None

    def resolve(self, query: str, *, grain: str | None = None, limit: int = 5) -> list[Metric]:
        normalized = query.strip()
        if not normalized:
            return []

        results: OrderedDict[str, Metric] = OrderedDict()
        with self._db.lock, self._db.connect() as conn:
            grain_clause = " AND grain = ?" if grain is not None else ""
            exact_params: list[object] = [
                normalized.casefold(),
                normalized.casefold(),
                normalized.casefold(),
            ]
            if grain is not None:
                exact_params.append(grain)
            exact_rows = conn.execute(
                f"""
                SELECT DISTINCT m.*
                FROM semantic_metric m
                LEFT JOIN semantic_metric_synonym s ON m.metric_id = s.metric_id
                WHERE lower(m.display_name) = ?
                   OR lower(m.metric_id) = ?
                   OR lower(s.synonym) = ?
                {grain_clause}
                LIMIT ?
                """,
                (*exact_params, limit),
            ).fetchall()
            for row in exact_rows:
                metric = self._row_to_metric(row)
                results[metric.metric_id] = metric

            if len(results) < limit:
                fts_params: list[object] = [prepare_fts_query(normalized)]
                fts_grain_clause = " AND m.grain = ?" if grain is not None else ""
                if grain is not None:
                    fts_params.append(grain)
                fts_rows = conn.execute(
                    f"""
                    SELECT m.*
                    FROM semantic_metric m
                    JOIN semantic_metric_fts f ON m.rowid = f.rowid
                    WHERE semantic_metric_fts MATCH ?
                    {fts_grain_clause}
                    LIMIT ?
                    """,
                    (*fts_params, limit - len(results)),
                ).fetchall()
                for row in fts_rows:
                    metric = self._row_to_metric(row)
                    results.setdefault(metric.metric_id, metric)
        return list(results.values())[:limit]

    def save(self, metric: Metric) -> None:
        payload = metric.model_dump(mode="json")
        synonyms = payload["synonyms"]
        with self._db.lock, self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO semantic_metric (
                    metric_id, display_name, owner, owner_contact, definition, synonyms_json,
                    synonyms_text, grain, unit, direction, typical_range_min, typical_range_max,
                    calculation_json, related_metrics_json, approved_by_json, caveats_json,
                    verified_query_ids_json, version, last_reviewed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metric.metric_id,
                    metric.display_name,
                    metric.owner,
                    metric.owner_contact,
                    metric.definition,
                    json_dumps(synonyms),
                    " ".join(synonyms),
                    metric.grain,
                    metric.unit,
                    metric.direction,
                    metric.typical_range[0] if metric.typical_range is not None else None,
                    metric.typical_range[1] if metric.typical_range is not None else None,
                    json_dumps(payload["calculation"]),
                    json_dumps(payload["related_metrics"]),
                    json_dumps(payload["approved_by"]),
                    json_dumps(payload["caveats"]),
                    json_dumps(payload["verified_query_ids"]),
                    metric.version,
                    metric.last_reviewed.isoformat() if metric.last_reviewed is not None else None,
                ),
            )
            conn.execute(
                "DELETE FROM semantic_metric_synonym WHERE metric_id = ?",
                (metric.metric_id,),
            )
            conn.executemany(
                "INSERT INTO semantic_metric_synonym(metric_id, synonym) VALUES (?, ?)",
                [(metric.metric_id, synonym) for synonym in metric.synonyms],
            )
            conn.commit()

    @staticmethod
    def _row_to_metric(row: sqlite3.Row) -> Metric:
        typical_range = None
        row_min = row["typical_range_min"]
        row_max = row["typical_range_max"]
        if row_min is not None and row_max is not None:
            typical_range = (float(row_min), float(row_max))
        return Metric.model_validate(
            {
                "metric_id": str(row["metric_id"]),
                "display_name": str(row["display_name"]),
                "owner": str(row["owner"]),
                "owner_contact": (
                    str(row["owner_contact"]) if row["owner_contact"] is not None else None
                ),
                "definition": str(row["definition"]),
                "synonyms": json_loads(row["synonyms_json"], default=[]),
                "grain": row["grain"],
                "unit": row["unit"],
                "direction": row["direction"],
                "typical_range": typical_range,
                "calculation": json_loads(row["calculation_json"], default={}),
                "related_metrics": json_loads(row["related_metrics_json"], default=[]),
                "approved_by": json_loads(row["approved_by_json"], default=[]),
                "caveats": json_loads(row["caveats_json"], default=[]),
                "verified_query_ids": json_loads(row["verified_query_ids_json"], default=[]),
                "version": int(row["version"]),
                "last_reviewed": (
                    str(row["last_reviewed"]) if row["last_reviewed"] is not None else None
                ),
            }
        )
