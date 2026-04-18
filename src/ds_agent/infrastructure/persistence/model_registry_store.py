"""SQLite-backed store for Decision OS model registry."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from datetime import datetime
from pathlib import Path

from ds_agent.domain.entities.model import Model, ModelAlias

_MIGRATION_V1_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_registry (
    model_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    alias TEXT NOT NULL CHECK (alias IN ('challenger', 'champion', 'canary', 'retired')),
    lineage_run_id TEXT NOT NULL,
    artifact_json TEXT NOT NULL,
    serving_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    promoted_at TEXT,
    retired_at TEXT,
    description TEXT NOT NULL,
    PRIMARY KEY (model_id, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_model_registry_active_alias
    ON model_registry(alias)
    WHERE alias != 'retired';

CREATE INDEX IF NOT EXISTS idx_model_registry_run
    ON model_registry(lineage_run_id, created_at DESC);

INSERT OR REPLACE INTO schema_migrations(version, applied_at)
VALUES (1, datetime('now'));
"""


class SqliteModelRegistryStore:
    """SQLite implementation of the Decision OS model registry."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    @classmethod
    def for_workspace(cls, workspace_dir: str | None = None) -> SqliteModelRegistryStore:
        """Create a store at the default Decision OS location for a workspace."""

        return cls(_default_db_path(workspace_dir))

    def get(self, model_id: str, version: int) -> Model | None:
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT *
                FROM model_registry
                WHERE model_id = ? AND version = ?
                """,
                (model_id, version),
            ).fetchone()
        return self._row_to_model(row) if row is not None else None

    def get_by_alias(self, alias: ModelAlias) -> Model | None:
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT *
                FROM model_registry
                WHERE alias = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (alias,),
            ).fetchone()
        return self._row_to_model(row) if row is not None else None

    def list_from_run(self, run_id: str) -> list[Model]:
        with self._lock, closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM model_registry
                WHERE lineage_run_id = ?
                ORDER BY version DESC
                """,
                (run_id,),
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def list_models(
        self,
        *,
        alias: ModelAlias | None = None,
        limit: int = 100,
    ) -> list[Model]:
        params: list[object] = []
        where = ""
        if alias is not None:
            where = "WHERE alias = ?"
            params.append(alias)
        params.append(limit)
        with self._lock, closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM model_registry
                {where}
                ORDER BY created_at DESC, model_id ASC, version DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def save(self, model: Model) -> None:
        payload = model.model_dump(mode="json")
        try:
            with self._lock, closing(self._connect()) as conn:
                conn.execute(
                    """
                    INSERT INTO model_registry (
                        model_id,
                        version,
                        alias,
                        lineage_run_id,
                        artifact_json,
                        serving_json,
                        created_at,
                        promoted_at,
                        retired_at,
                        description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        model.model_id,
                        model.version,
                        model.alias,
                        model.lineage_run_id,
                        json.dumps(payload["artifact"], ensure_ascii=False),
                        json.dumps(payload["serving"], ensure_ascii=False),
                        model.created_at.isoformat(),
                        model.promoted_at.isoformat() if model.promoted_at is not None else None,
                        model.retired_at.isoformat() if model.retired_at is not None else None,
                        model.description,
                    ),
                )
                conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Model alias conflict or duplicate version: {exc}") from exc

    def update_alias(
        self,
        model_id: str,
        version: int,
        alias: ModelAlias,
        *,
        promoted_at: datetime | None = None,
        retired_at: datetime | None = None,
    ) -> None:
        try:
            with self._lock, closing(self._connect()) as conn:
                conn.execute(
                    """
                    UPDATE model_registry
                    SET alias = ?,
                        promoted_at = ?,
                        retired_at = ?
                    WHERE model_id = ? AND version = ?
                    """,
                    (
                        alias,
                        promoted_at.isoformat() if promoted_at is not None else None,
                        retired_at.isoformat() if retired_at is not None else None,
                        model_id,
                        version,
                    ),
                )
                conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Model alias conflict: {exc}") from exc

    def _initialize(self) -> None:
        with self._lock, closing(self._connect()) as conn:
            version = self._schema_version(conn)
            if version < 1:
                conn.executescript(_MIGRATION_V1_SQL)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
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
    def _row_to_model(row: sqlite3.Row) -> Model:
        return Model.model_validate(
            {
                "model_id": str(row["model_id"]),
                "version": int(row["version"]),
                "alias": str(row["alias"]),
                "lineage_run_id": str(row["lineage_run_id"]),
                "artifact": json.loads(str(row["artifact_json"])),
                "serving": json.loads(str(row["serving_json"])),
                "created_at": str(row["created_at"]),
                "promoted_at": str(row["promoted_at"]) if row["promoted_at"] is not None else None,
                "retired_at": str(row["retired_at"]) if row["retired_at"] is not None else None,
                "description": str(row["description"]),
            }
        )


def _default_db_path(workspace_dir: str | None) -> Path:
    if workspace_dir is not None:
        return Path(workspace_dir) / "data" / "memory" / "decision_os" / "model_registry.db"
    return Path("data") / "memory" / "decision_os" / "model_registry.db"
