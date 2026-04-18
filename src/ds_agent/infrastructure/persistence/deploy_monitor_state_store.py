"""SQLite-backed store for Decision OS post-deploy monitoring state."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from datetime import datetime
from pathlib import Path

from ds_agent.domain.entities.post_deploy import PostDeployMonitorState

_MIGRATION_V1_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deploy_monitor_state (
    state_id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_version INTEGER NOT NULL,
    alias TEXT NOT NULL,
    window TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    overall_status TEXT NOT NULL,
    alerts_json TEXT NOT NULL DEFAULT '[]',
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_deploy_monitor_model
    ON deploy_monitor_state(model_id, observed_at DESC);

INSERT OR REPLACE INTO schema_migrations(version, applied_at)
VALUES (1, datetime('now'));
"""


class SqliteDeployMonitorStateStore:
    """SQLite implementation of post-deploy monitoring state persistence."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    @classmethod
    def for_workspace(cls, workspace_dir: str | None = None) -> SqliteDeployMonitorStateStore:
        """Create a store at the default Decision OS location for a workspace."""

        return cls(_default_db_path(workspace_dir))

    def save(self, state: PostDeployMonitorState) -> None:
        payload = state.model_dump(mode="json")
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO deploy_monitor_state (
                    state_id,
                    model_id,
                    model_version,
                    alias,
                    window,
                    observed_at,
                    overall_status,
                    alerts_json,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(state_id) DO UPDATE SET
                    model_id = excluded.model_id,
                    model_version = excluded.model_version,
                    alias = excluded.alias,
                    window = excluded.window,
                    observed_at = excluded.observed_at,
                    overall_status = excluded.overall_status,
                    alerts_json = excluded.alerts_json,
                    payload_json = excluded.payload_json
                """,
                (
                    state.state_id,
                    state.model_id,
                    state.model_version,
                    state.alias,
                    state.window,
                    state.observed_at.isoformat(),
                    state.overall_status,
                    json.dumps(payload["alerts"], ensure_ascii=False),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            conn.commit()

    def latest(self, model_id: str) -> PostDeployMonitorState | None:
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM deploy_monitor_state
                WHERE model_id = ?
                ORDER BY observed_at DESC
                LIMIT 1
                """,
                (model_id,),
            ).fetchone()
        if row is None:
            return None
        return PostDeployMonitorState.model_validate(json.loads(str(row["payload_json"])))

    def list_states(
        self,
        *,
        model_id: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[PostDeployMonitorState]:
        clauses: list[str] = []
        params: list[object] = []
        if model_id is not None:
            clauses.append("model_id = ?")
            params.append(model_id)
        if since is not None:
            clauses.append("observed_at >= ?")
            params.append(since.isoformat())
        where = ""
        if clauses:
            where = "WHERE " + " AND ".join(clauses)
        params.append(limit)
        with self._lock, closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT payload_json
                FROM deploy_monitor_state
                {where}
                ORDER BY observed_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [
            PostDeployMonitorState.model_validate(json.loads(str(row["payload_json"])))
            for row in rows
        ]

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


def _default_db_path(workspace_dir: str | None) -> Path:
    if workspace_dir is not None:
        return Path(workspace_dir) / "data" / "memory" / "decision_os" / "deploy_monitor.db"
    return Path("data") / "memory" / "decision_os" / "deploy_monitor.db"
