"""SQLite-backed store for workflow integration work objects."""

from __future__ import annotations

import builtins
import json
import sqlite3
import threading
from collections.abc import Sequence
from hashlib import sha1
from pathlib import Path

from ds_agent.domain.entities.external_reference import ExternalReference
from ds_agent.domain.entities.integration_event import IntegrationEvent, IntegrationEventStatus
from ds_agent.domain.entities.work_object import WorkObject, WorkObjectPhase
from ds_agent.domain.interfaces.work_object import WorkObjectStore
from ds_agent.infrastructure.persistence.task_contract_store import SqliteTaskContractStore
from ds_agent.runtime.transcript_store import get_runtime_storage_root

_MIGRATION_V11_SQL = """
CREATE TABLE IF NOT EXISTS work_objects (
    work_object_id TEXT PRIMARY KEY,
    task_contract_id TEXT NOT NULL,
    parent_work_object_id TEXT,
    title TEXT NOT NULL,
    request_source TEXT NOT NULL,
    requestor_id TEXT NOT NULL,
    current_phase TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (task_contract_id) REFERENCES task_contracts(task_id),
    FOREIGN KEY (parent_work_object_id) REFERENCES work_objects(work_object_id)
);

CREATE INDEX IF NOT EXISTS idx_wo_phase ON work_objects(current_phase);
CREATE INDEX IF NOT EXISTS idx_wo_task_contract ON work_objects(task_contract_id);
CREATE INDEX IF NOT EXISTS idx_wo_updated ON work_objects(updated_at DESC);

CREATE TABLE IF NOT EXISTS integration_credentials (
    credential_id TEXT PRIMARY KEY,
    system TEXT NOT NULL,
    label TEXT NOT NULL,
    auth_type TEXT NOT NULL,
    encrypted_blob BLOB NOT NULL,
    scopes_json TEXT NOT NULL DEFAULT '[]',
    expires_at TEXT,
    rotated_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (system, label)
);

CREATE TABLE IF NOT EXISTS integration_event_log (
    event_id TEXT PRIMARY KEY,
    work_object_id TEXT NOT NULL,
    system TEXT NOT NULL,
    action TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_payload_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    external_ref_json TEXT,
    attempt INTEGER NOT NULL DEFAULT 1,
    error_code TEXT,
    error_message TEXT,
    policy_decision_id TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    latency_ms INTEGER,
    FOREIGN KEY (work_object_id) REFERENCES work_objects(work_object_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_event_idempotency
  ON integration_event_log(idempotency_key)
  WHERE status IN ('success','duplicate');

CREATE INDEX IF NOT EXISTS idx_event_wo ON integration_event_log(work_object_id);
CREATE INDEX IF NOT EXISTS idx_event_dlq ON integration_event_log(status);

CREATE TABLE IF NOT EXISTS external_reference (
    reference_id TEXT PRIMARY KEY,
    work_object_id TEXT NOT NULL,
    system TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    url TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    idempotency_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (work_object_id) REFERENCES work_objects(work_object_id),
    UNIQUE (system, resource_type, resource_id)
);

CREATE INDEX IF NOT EXISTS idx_extref_wo ON external_reference(work_object_id);
"""

_MIGRATION_V11_VERSION_SQL = """
INSERT OR REPLACE INTO schema_migrations(version, applied_at)
VALUES (11, datetime('now'));
"""

_MIGRATION_V11_1_SQL = """
-- Add request_payload_json column for DLQ replay support.
-- Backward-compatible: existing rows get NULL.
ALTER TABLE integration_event_log ADD COLUMN request_payload_json TEXT;
"""

_MIGRATION_V11_1_VERSION_SQL = """
INSERT OR REPLACE INTO schema_migrations(version, applied_at)
VALUES (12, datetime('now'));
"""


def _safe_get(row: sqlite3.Row, key: str) -> str | None:
    """Safely access a column that may not exist in older schema rows."""
    try:
        value: str | None = row[key]
        return value
    except (IndexError, KeyError):
        return None


class SqliteWorkObjectStore(WorkObjectStore):
    """SQLite implementation of workflow integration persistence."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        SqliteTaskContractStore(self._db_path)
        self._initialize()

    @property
    def db_path(self) -> Path:
        return self._db_path

    @classmethod
    def for_workspace(cls, workspace_dir: str | None = None) -> SqliteWorkObjectStore:
        return cls(get_runtime_storage_root(workspace_dir) / "task_contracts.db")

    def create(self, work_object: WorkObject) -> None:
        with self._lock, self._connect() as conn:
            self._upsert_work_object(conn, work_object, insert_only=True)
            conn.commit()

    def get(self, work_object_id: str) -> WorkObject | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM work_objects WHERE work_object_id = ?",
                (work_object_id,),
            ).fetchone()
        if row is None:
            return None
        return WorkObject.model_validate(json.loads(row["payload_json"]))

    def get_by_task_contract(self, task_contract_id: str) -> WorkObject | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM work_objects WHERE task_contract_id = ?",
                (task_contract_id,),
            ).fetchone()
        if row is None:
            return None
        return WorkObject.model_validate(json.loads(row["payload_json"]))

    def list(
        self,
        *,
        session_id: str | None = None,
        task_contract_id: str | None = None,
        phases: Sequence[WorkObjectPhase] | None = None,
        limit: int = 20,
    ) -> builtins.list[WorkObject]:
        params: list[object] = []
        join = ""
        where = ["1 = 1"]
        if session_id is not None:
            join = "JOIN task_contracts tc ON tc.task_id = wo.task_contract_id"
            where.append("tc.session_id = ?")
            params.append(session_id)
        if task_contract_id is not None:
            where.append("wo.task_contract_id = ?")
            params.append(task_contract_id)
        if phases:
            placeholders = ", ".join("?" for _ in phases)
            where.append(f"wo.current_phase IN ({placeholders})")
            params.extend(phase.value for phase in phases)
        params.append(limit)
        sql = f"""
            SELECT wo.payload_json
            FROM work_objects wo
            {join}
            WHERE {' AND '.join(where)}
            ORDER BY wo.updated_at DESC
            LIMIT ?
        """
        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [WorkObject.model_validate(json.loads(row["payload_json"])) for row in rows]

    def save(self, work_object: WorkObject) -> None:
        with self._lock, self._connect() as conn:
            self._upsert_work_object(conn, work_object, insert_only=False)
            conn.commit()

    def record_event(self, event: IntegrationEvent) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO integration_event_log(
                    event_id, work_object_id, system, action, idempotency_key,
                    request_payload_hash, status, external_ref_json, attempt,
                    error_code, error_message, policy_decision_id, started_at,
                    finished_at, latency_ms, request_payload_json
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    event.event_id,
                    event.work_object_id,
                    event.system,
                    event.action,
                    event.idempotency_key,
                    event.request_payload_hash,
                    event.status.value,
                    (
                        None
                        if event.external_ref is None
                        else json.dumps(
                            event.external_ref.model_dump(mode="json")
                        )
                    ),
                    event.attempt,
                    event.error_code,
                    event.error_message,
                    event.policy_decision_id,
                    event.started_at.isoformat(),
                    (
                        None
                        if event.finished_at is None
                        else event.finished_at.isoformat()
                    ),
                    event.latency_ms,
                    event.request_payload_json,
                ),
            )
            conn.commit()

    def list_events(
        self,
        work_object_id: str,
        *,
        limit: int = 100,
    ) -> builtins.list[IntegrationEvent]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM integration_event_log
                WHERE work_object_id = ?
                ORDER BY started_at ASC
                LIMIT ?
                """,
                (work_object_id, limit),
            ).fetchall()
        return [self._deserialize_event(row) for row in rows]

    def find_event_by_idempotency_key(self, idempotency_key: str) -> IntegrationEvent | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM integration_event_log
                WHERE idempotency_key = ?
                  AND status IN ('success', 'duplicate')
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (idempotency_key,),
            ).fetchone()
        if row is None:
            return None
        return self._deserialize_event(row)

    def get_event(self, event_id: str) -> IntegrationEvent | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM integration_event_log WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        if row is None:
            return None
        return self._deserialize_event(row)

    def list_events_by_status(
        self,
        status: IntegrationEventStatus,
        *,
        system: str | None = None,
        limit: int = 100,
    ) -> builtins.list[IntegrationEvent]:
        with self._lock, self._connect() as conn:
            if system:
                rows = conn.execute(
                    """
                    SELECT * FROM integration_event_log
                    WHERE status = ? AND system = ?
                    ORDER BY started_at DESC LIMIT ?
                    """,
                    (status.value, system, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM integration_event_log
                    WHERE status = ?
                    ORDER BY started_at DESC LIMIT ?
                    """,
                    (status.value, limit),
                ).fetchall()
        return [self._deserialize_event(row) for row in rows]

    def update_event_status(
        self,
        event_id: str,
        new_status: IntegrationEventStatus,
        *,
        attempt: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        with self._lock, self._connect() as conn:
            parts = ["status = ?"]
            params: builtins.list[object] = [new_status.value]
            if attempt is not None:
                parts.append("attempt = ?")
                params.append(attempt)
            if error_code is not None:
                parts.append("error_code = ?")
                params.append(error_code)
            if error_message is not None:
                parts.append("error_message = ?")
                params.append(error_message)
            params.append(event_id)
            conn.execute(
                f"UPDATE integration_event_log SET {', '.join(parts)} "
                "WHERE event_id = ?",
                params,
            )
            conn.commit()

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            version = self._schema_version(conn)
            if version < 11:
                conn.executescript(_MIGRATION_V11_SQL)
                conn.executescript(_MIGRATION_V11_VERSION_SQL)
            version = self._schema_version(conn)
            if version < 12:
                import contextlib

                with contextlib.suppress(Exception):
                    conn.executescript(_MIGRATION_V11_1_SQL)
                conn.executescript(_MIGRATION_V11_1_VERSION_SQL)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _schema_version(conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
        return 0 if row is None or row["version"] is None else int(row["version"])

    def _upsert_work_object(
        self,
        conn: sqlite3.Connection,
        work_object: WorkObject,
        *,
        insert_only: bool,
    ) -> None:
        sql = (
            """
            INSERT INTO work_objects(
                work_object_id, task_contract_id, parent_work_object_id,
                title, request_source, requestor_id, current_phase,
                payload_json, tags_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            if insert_only
            else """
            INSERT INTO work_objects(
                work_object_id, task_contract_id, parent_work_object_id,
                title, request_source, requestor_id, current_phase,
                payload_json, tags_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(work_object_id) DO UPDATE SET
                task_contract_id=excluded.task_contract_id,
                parent_work_object_id=excluded.parent_work_object_id,
                title=excluded.title,
                request_source=excluded.request_source,
                requestor_id=excluded.requestor_id,
                current_phase=excluded.current_phase,
                payload_json=excluded.payload_json,
                tags_json=excluded.tags_json,
                created_at=excluded.created_at,
                updated_at=excluded.updated_at
            """
        )
        conn.execute(
            sql,
            (
                work_object.work_object_id,
                work_object.execution.task_contract_id,
                work_object.parent_work_object_id,
                work_object.title,
                work_object.request.source.value,
                work_object.request.requestor_id,
                work_object.execution.current_phase.value,
                json.dumps(work_object.model_dump(mode="json"), ensure_ascii=False),
                json.dumps(work_object.tags, ensure_ascii=False),
                work_object.created_at.isoformat(),
                work_object.updated_at.isoformat(),
            ),
        )
        conn.execute(
            "DELETE FROM external_reference WHERE work_object_id = ?",
            (work_object.work_object_id,),
        )
        self._store_references(conn, work_object.work_object_id, work_object)

    def _store_references(
        self,
        conn: sqlite3.Connection,
        work_object_id: str,
        work_object: WorkObject,
    ) -> None:
        pairs: list[tuple[str, ExternalReference]] = []
        if work_object.request.external_ref is not None:
            pairs.append(("request", work_object.request.external_ref))
        pairs.extend(("documentation", ref) for ref in work_object.documentation.references)
        pairs.extend(("follow_up", action.external_ref) for action in work_object.follow_up.actions)
        for location, reference in pairs:
            metadata = dict(reference.metadata)
            metadata["location"] = location
            digest = sha1(f"{work_object_id}:{reference.identity}".encode()).hexdigest()
            reference_id = f"ER-{digest[:20]}"
            conn.execute(
                """
                INSERT OR REPLACE INTO external_reference(
                    reference_id, work_object_id, system, resource_type, resource_id,
                    url, metadata_json, idempotency_key, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reference_id,
                    work_object_id,
                    reference.system,
                    reference.resource_type,
                    reference.resource_id,
                    reference.url,
                    json.dumps(metadata, ensure_ascii=False),
                    reference.idempotency_key,
                    reference.created_at.isoformat(),
                ),
            )

    @staticmethod
    def _deserialize_event(row: sqlite3.Row) -> IntegrationEvent:
        external_ref = row["external_ref_json"]
        return IntegrationEvent(
            event_id=row["event_id"],
            work_object_id=row["work_object_id"],
            system=row["system"],
            action=row["action"],
            request_payload_hash=row["request_payload_hash"],
            idempotency_key=row["idempotency_key"],
            status=IntegrationEventStatus(row["status"]),
            external_ref=(
                None
                if not external_ref
                else ExternalReference.model_validate(json.loads(str(external_ref)))
            ),
            attempt=int(row["attempt"]),
            latency_ms=int(row["latency_ms"] or 0),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            policy_decision_id=row["policy_decision_id"],
            request_payload_json=_safe_get(row, "request_payload_json"),
        )
