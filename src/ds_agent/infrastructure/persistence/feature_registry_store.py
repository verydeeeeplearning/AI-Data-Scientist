"""SQLite-backed store for Decision OS feature definitions."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

from ds_agent.domain.entities.feature import Feature, FeatureAlias
from ds_agent.domain.errors.feature_registry_errors import FeatureVersionConflictError

_MIGRATION_V1_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feature_registry (
    feature_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL,
    transformation_logic TEXT NOT NULL,
    source_tables_json TEXT NOT NULL,
    owner TEXT NOT NULL,
    created_at TEXT NOT NULL,
    statistics_json TEXT NOT NULL,
    point_in_time_safe INTEGER NOT NULL,
    alias TEXT NOT NULL CHECK (alias IN ('stable', 'experimental', 'deprecated')),
    used_in_experiments_json TEXT NOT NULL DEFAULT '[]',
    tags_json TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (feature_id, version)
);

CREATE INDEX IF NOT EXISTS idx_feature_registry_latest
    ON feature_registry(feature_id, version DESC);
CREATE INDEX IF NOT EXISTS idx_feature_registry_alias
    ON feature_registry(alias);

CREATE TABLE IF NOT EXISTS feature_alias_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    alias TEXT NOT NULL CHECK (alias IN ('stable', 'experimental', 'deprecated')),
    changed_at TEXT NOT NULL,
    FOREIGN KEY (feature_id, version)
        REFERENCES feature_registry(feature_id, version)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_feature_alias_history_feature
    ON feature_alias_history(feature_id, changed_at DESC);

CREATE TABLE IF NOT EXISTS feature_source_table (
    feature_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    source_table TEXT NOT NULL,
    PRIMARY KEY (feature_id, version, source_table),
    FOREIGN KEY (feature_id, version)
        REFERENCES feature_registry(feature_id, version)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_feature_source_table_source
    ON feature_source_table(source_table);

INSERT OR REPLACE INTO schema_migrations(version, applied_at)
VALUES (1, datetime('now'));
"""


class SqliteFeatureRegistryStore:
    """SQLite implementation of the Decision OS feature registry."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    @classmethod
    def for_workspace(cls, workspace_dir: str | None = None) -> SqliteFeatureRegistryStore:
        """Create a store at the default Decision OS location for a workspace."""

        return cls(_default_db_path(workspace_dir))

    def get(self, feature_id: str, version: int) -> Feature | None:
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT *
                FROM feature_registry
                WHERE feature_id = ? AND version = ?
                """,
                (feature_id, version),
            ).fetchone()
        return self._row_to_feature(row) if row is not None else None

    def get_latest(self, feature_id: str) -> Feature | None:
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT *
                FROM feature_registry
                WHERE feature_id = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (feature_id,),
            ).fetchone()
        return self._row_to_feature(row) if row is not None else None

    def list_versions(self, feature_id: str) -> list[Feature]:
        with self._lock, closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM feature_registry
                WHERE feature_id = ?
                ORDER BY version DESC
                """,
                (feature_id,),
            ).fetchall()
        return [self._row_to_feature(row) for row in rows]

    def list_features(
        self,
        *,
        alias: FeatureAlias | None = None,
        limit: int = 100,
    ) -> list[Feature]:
        params: list[object] = []
        alias_filter = ""
        if alias is not None:
            alias_filter = "WHERE fr.alias = ?"
            params.append(alias)
        params.append(limit)
        with self._lock, closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT fr.*
                FROM feature_registry fr
                JOIN (
                    SELECT feature_id, MAX(version) AS version
                    FROM feature_registry
                    GROUP BY feature_id
                ) latest
                  ON latest.feature_id = fr.feature_id
                 AND latest.version = fr.version
                {alias_filter}
                ORDER BY fr.feature_id ASC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_feature(row) for row in rows]

    def save(self, feature: Feature) -> None:
        if self.get(feature.feature_id, feature.version) is not None:
            raise FeatureVersionConflictError(
                f"Feature {feature.feature_id} v{feature.version} already exists."
            )

        payload = feature.model_dump(mode="json")
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO feature_registry (
                    feature_id,
                    version,
                    display_name,
                    description,
                    transformation_logic,
                    source_tables_json,
                    owner,
                    created_at,
                    statistics_json,
                    point_in_time_safe,
                    alias,
                    used_in_experiments_json,
                    tags_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feature.feature_id,
                    feature.version,
                    feature.display_name,
                    feature.description,
                    feature.transformation_logic,
                    json.dumps(payload["source_tables"], ensure_ascii=False),
                    feature.owner,
                    feature.created_at.isoformat(),
                    json.dumps(payload["statistics"], ensure_ascii=False),
                    1 if feature.point_in_time_safe else 0,
                    feature.alias,
                    json.dumps(payload["used_in_experiments"], ensure_ascii=False),
                    json.dumps(payload["tags"], ensure_ascii=False),
                ),
            )
            conn.executemany(
                """
                INSERT INTO feature_source_table (feature_id, version, source_table)
                VALUES (?, ?, ?)
                """,
                [
                    (feature.feature_id, feature.version, source_table)
                    for source_table in feature.source_tables
                ],
            )
            conn.execute(
                """
                INSERT INTO feature_alias_history (feature_id, version, alias, changed_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    feature.feature_id,
                    feature.version,
                    feature.alias,
                    feature.created_at.isoformat(),
                ),
            )
            conn.commit()

    def list_experiments_using(self, feature_id: str) -> list[str]:
        experiments: list[str] = []
        seen: set[str] = set()
        for feature in self.list_versions(feature_id):
            for experiment_id in feature.used_in_experiments:
                if experiment_id in seen:
                    continue
                seen.add(experiment_id)
                experiments.append(experiment_id)
        return experiments

    def list_by_source_table(self, source_table: str) -> list[Feature]:
        with self._lock, closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT fr.*
                FROM feature_registry fr
                JOIN feature_source_table fst
                  ON fst.feature_id = fr.feature_id
                 AND fst.version = fr.version
                WHERE fst.source_table = ?
                ORDER BY fr.feature_id ASC, fr.version DESC
                """,
                (source_table,),
            ).fetchall()
        return [self._row_to_feature(row) for row in rows]

    def _initialize(self) -> None:
        with self._lock, closing(self._connect()) as conn:
            version = self._schema_version(conn)
            if version < 1:
                conn.executescript(_MIGRATION_V1_SQL)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _schema_version(conn: sqlite3.Connection) -> int:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        row = conn.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
        if row is None or row["version"] is None:
            return 0
        return int(row["version"])

    @staticmethod
    def _row_to_feature(row: sqlite3.Row) -> Feature:
        return Feature.model_validate(
            {
                "feature_id": str(row["feature_id"]),
                "display_name": str(row["display_name"]),
                "version": int(row["version"]),
                "description": str(row["description"]),
                "transformation_logic": str(row["transformation_logic"]),
                "source_tables": json.loads(str(row["source_tables_json"] or "[]")),
                "owner": str(row["owner"]),
                "created_at": str(row["created_at"]),
                "statistics": json.loads(str(row["statistics_json"])),
                "point_in_time_safe": bool(row["point_in_time_safe"]),
                "alias": str(row["alias"]),
                "used_in_experiments": json.loads(str(row["used_in_experiments_json"] or "[]")),
                "tags": json.loads(str(row["tags_json"] or "[]")),
            }
        )


def _default_db_path(workspace_dir: str | None) -> Path:
    if workspace_dir is not None:
        return Path(workspace_dir) / "data" / "memory" / "decision_os" / "feature_registry.db"
    return Path("data") / "memory" / "decision_os" / "feature_registry.db"
