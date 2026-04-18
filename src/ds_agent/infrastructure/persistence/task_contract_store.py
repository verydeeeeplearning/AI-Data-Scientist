"""SQLite-backed store for task contract aggregates."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from ds_agent.domain.entities.assumption_log import AssumptionLog
from ds_agent.domain.entities.dataset_manifest import DatasetManifest
from ds_agent.domain.entities.delivery_pack import DeliveryPack
from ds_agent.domain.entities.goal_brief import GoalBrief
from ds_agent.domain.entities.metric_spec import MetricSpec
from ds_agent.domain.entities.review_verdict import ReviewVerdict
from ds_agent.domain.entities.task_contract import TaskContract, TaskContractStatus
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.entities.task_contract_event import TaskContractEvent
from ds_agent.domain.errors.task_contract_errors import VersionConflictError
from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.domain.value_objects.authority_mode import AuthorityMode
from ds_agent.runtime.transcript_store import get_runtime_storage_root

_MIGRATION_V5_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_contracts (
    task_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('draft','agreed','in_progress','review','closed','abandoned')
    ),
    business_goal TEXT NOT NULL,
    primary_kpi_id TEXT,
    decision_owner TEXT,
    decision_deadline TEXT,
    budget_json TEXT NOT NULL,
    autonomy_json TEXT NOT NULL,
    allowed_sources_json TEXT NOT NULL,
    forbidden_patterns_json TEXT NOT NULL,
    required_deliverables_json TEXT NOT NULL,
    definition_of_done_json TEXT,
    goal_brief_id TEXT,
    dataset_manifest_id TEXT,
    assumption_log_id TEXT,
    delivery_pack_id TEXT,
    metric_spec_ids_json TEXT NOT NULL DEFAULT '[]',
    review_verdict_ids_json TEXT NOT NULL DEFAULT '[]',
    secondary_kpi_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'agent',
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_task_contracts_session ON task_contracts(session_id);
CREATE INDEX IF NOT EXISTS idx_task_contracts_status ON task_contracts(status);

CREATE TABLE IF NOT EXISTS goal_briefs (
    brief_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES task_contracts(task_id) ON DELETE CASCADE,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metric_specs (
    metric_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES task_contracts(task_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    is_primary_kpi INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metric_specs_task ON metric_specs(task_id);

CREATE TABLE IF NOT EXISTS dataset_manifests (
    manifest_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES task_contracts(task_id) ON DELETE CASCADE,
    payload_json TEXT NOT NULL,
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assumption_logs (
    log_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES task_contracts(task_id) ON DELETE CASCADE,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_verdicts (
    verdict_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES task_contracts(task_id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('pass','warn','fail')),
    reviewer TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_review_verdicts_task ON review_verdicts(task_id);

CREATE TABLE IF NOT EXISTS delivery_packs (
    pack_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES task_contracts(task_id) ON DELETE CASCADE,
    payload_json TEXT NOT NULL,
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_contract_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_task ON task_contract_events(task_id);

INSERT OR REPLACE INTO schema_migrations(version, applied_at)
VALUES (5, datetime('now'));
"""

_MIGRATION_V6_VERSION_SQL = """
INSERT OR REPLACE INTO schema_migrations(version, applied_at)
VALUES (6, datetime('now'));
"""

_MIGRATION_V10_SQL = """
CREATE TABLE IF NOT EXISTS delivery_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    pack_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('sent', 'blocked', 'duplicate', 'failed')
    ),
    attempted_at TEXT NOT NULL,
    reason TEXT,
    receipt_ref TEXT,
    adapter_name TEXT,
    idempotency_key TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_delivery_log_pack ON delivery_log(pack_id);
CREATE INDEX IF NOT EXISTS idx_delivery_log_idempotency ON delivery_log(idempotency_key);

CREATE VIEW IF NOT EXISTS v_delivery_summary AS
SELECT
    p.pack_id AS pack_id,
    p.task_id AS task_id,
    json_extract(p.payload_json, '$.status') AS status,
    COALESCE(json_array_length(p.payload_json, '$.artifacts'), 0) AS artifact_count,
    COALESCE(
        (
            SELECT COUNT(1)
            FROM json_each(p.payload_json, '$.artifacts') AS artifact
            WHERE json_extract(artifact.value, '$.rendered_uri') IS NOT NULL
        ),
        0
    ) AS rendered_count,
    (
        SELECT MAX(attempted_at)
        FROM delivery_log l
        WHERE l.pack_id = p.pack_id
    ) AS last_attempt
FROM delivery_packs p;
"""

_MIGRATION_V10_VERSION_SQL = """
INSERT OR REPLACE INTO schema_migrations(version, applied_at)
VALUES (10, datetime('now'));
"""


class SqliteTaskContractStore:
    """SQLite implementation of the task contract aggregate store."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    @property
    def db_path(self) -> Path:
        return self._db_path

    @classmethod
    def for_workspace(cls, workspace_dir: str | None = None) -> SqliteTaskContractStore:
        """Create a store at the default runtime location for a workspace."""

        return cls(get_runtime_storage_root(workspace_dir) / "task_contracts.db")

    def create_bundle(
        self,
        bundle: TaskContractBundle,
        *,
        events: Sequence[TaskContractEvent] = (),
    ) -> None:
        bundle.sync_references()
        with self._lock, self._connect() as conn:
            self._upsert_bundle(conn, bundle, insert_only=True)
            self._store_events(conn, events)
            conn.commit()

    def get_bundle(self, task_id: str) -> TaskContractBundle | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM task_contracts WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                return None
            return self._load_bundle(conn, row)

    def get_active_bundle(self, session_id: str) -> TaskContractBundle | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM task_contracts
                WHERE session_id = ?
                  AND status IN ('draft', 'agreed', 'in_progress', 'review')
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            return self._load_bundle(conn, row)

    def list_contracts(
        self,
        session_id: str | None = None,
        *,
        statuses: Sequence[TaskContractStatus] | None = None,
        limit: int = 20,
    ) -> list[TaskContract]:
        params: list[object] = []
        where = "1 = 1"
        if session_id is not None:
            where += " AND session_id = ?"
            params.append(session_id)
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            where += f" AND status IN ({placeholders})"
            params.extend(status.value for status in statuses)
        params.append(limit)
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM task_contracts
                WHERE {where}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._deserialize_contract(row) for row in rows]

    def save_bundle(
        self,
        bundle: TaskContractBundle,
        *,
        expected_version: int,
        events: Sequence[TaskContractEvent] = (),
    ) -> None:
        bundle.sync_references()
        with self._lock, self._connect() as conn:
            current = conn.execute(
                "SELECT version FROM task_contracts WHERE task_id = ?",
                (bundle.contract.task_id,),
            ).fetchone()
            if current is None:
                raise VersionConflictError(f"Task contract not found: {bundle.contract.task_id}")
            if int(current["version"]) != expected_version:
                raise VersionConflictError(
                    f"Expected version {expected_version}, got {current['version']}"
                )
            self._upsert_bundle(conn, bundle, insert_only=False)
            self._store_events(conn, events)
            conn.commit()

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            version = self._schema_version(conn)
            if version < 5:
                conn.executescript(_MIGRATION_V5_SQL)
            version = self._schema_version(conn)
            if version < 6:
                self._apply_v6(conn)
            version = self._schema_version(conn)
            if version < 10:
                self._apply_v10(conn)
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
    def _apply_v6(conn: sqlite3.Connection) -> None:
        columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(task_contracts)").fetchall()
        }
        additions = {
            "authority": "TEXT",
            "audience": "TEXT",
            "mission": "TEXT",
        }
        for name, column_type in additions.items():
            if name in columns:
                continue
            conn.execute(f"ALTER TABLE task_contracts ADD COLUMN {name} {column_type}")
        conn.executescript(_MIGRATION_V6_VERSION_SQL)

    @staticmethod
    def _apply_v10(conn: sqlite3.Connection) -> None:
        conn.executescript(_MIGRATION_V10_SQL)
        conn.executescript(_MIGRATION_V10_VERSION_SQL)

    def _upsert_bundle(
        self,
        conn: sqlite3.Connection,
        bundle: TaskContractBundle,
        *,
        insert_only: bool,
    ) -> None:
        payload = self._serialize_contract(bundle.contract)
        verb = "INSERT" if insert_only else "INSERT OR REPLACE"
        conn.execute(
            f"""
            {verb} INTO task_contracts (
                task_id, session_id, type, status, business_goal, primary_kpi_id,
                decision_owner, decision_deadline, budget_json, autonomy_json,
                allowed_sources_json, forbidden_patterns_json, required_deliverables_json,
                definition_of_done_json, authority, audience, mission,
                goal_brief_id, dataset_manifest_id,
                assumption_log_id, delivery_pack_id, metric_spec_ids_json,
                review_verdict_ids_json, secondary_kpi_ids_json, created_at,
                updated_at, created_by, version
            ) VALUES (
                :task_id, :session_id, :type, :status, :business_goal, :primary_kpi_id,
                :decision_owner, :decision_deadline, :budget_json, :autonomy_json,
                :allowed_sources_json, :forbidden_patterns_json, :required_deliverables_json,
                :definition_of_done_json, :authority, :audience, :mission,
                :goal_brief_id, :dataset_manifest_id,
                :assumption_log_id, :delivery_pack_id, :metric_spec_ids_json,
                :review_verdict_ids_json, :secondary_kpi_ids_json, :created_at,
                :updated_at, :created_by, :version
            )
            """,
            payload,
        )
        self._replace_children(conn, bundle)

    def _replace_children(self, conn: sqlite3.Connection, bundle: TaskContractBundle) -> None:
        task_id = bundle.contract.task_id
        for table in (
            "goal_briefs",
            "metric_specs",
            "dataset_manifests",
            "assumption_logs",
            "review_verdicts",
            "delivery_packs",
        ):
            conn.execute(f"DELETE FROM {table} WHERE task_id = ?", (task_id,))

        if bundle.goal_brief is not None:
            conn.execute(
                """
                INSERT INTO goal_briefs (brief_id, task_id, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    bundle.goal_brief.brief_id,
                    task_id,
                    bundle.goal_brief.model_dump_json(),
                    bundle.goal_brief.created_at.isoformat(),
                    bundle.goal_brief.updated_at.isoformat(),
                ),
            )

        for metric in bundle.metric_specs:
            conn.execute(
                """
                INSERT INTO metric_specs (
                    metric_id,
                    task_id,
                    name,
                    is_primary_kpi,
                    payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    metric.metric_id,
                    task_id,
                    metric.name,
                    1 if metric.is_primary_kpi else 0,
                    metric.model_dump_json(),
                    metric.created_at.isoformat(),
                ),
            )

        if bundle.dataset_manifest is not None:
            conn.execute(
                """
                INSERT INTO dataset_manifests (manifest_id, task_id, payload_json, generated_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    bundle.dataset_manifest.manifest_id,
                    task_id,
                    bundle.dataset_manifest.model_dump_json(),
                    bundle.dataset_manifest.generated_at.isoformat(),
                ),
            )

        if bundle.assumption_log is not None:
            conn.execute(
                """
                INSERT INTO assumption_logs (log_id, task_id, payload_json)
                VALUES (?, ?, ?)
                """,
                (
                    bundle.assumption_log.log_id,
                    task_id,
                    bundle.assumption_log.model_dump_json(),
                ),
            )

        for verdict in bundle.review_verdicts:
            conn.execute(
                """
                INSERT INTO review_verdicts (
                    verdict_id, task_id, category, result, reviewer, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    verdict.verdict_id,
                    task_id,
                    verdict.category,
                    verdict.result,
                    verdict.reviewer,
                    verdict.model_dump_json(),
                    verdict.created_at.isoformat(),
                ),
            )

        if bundle.delivery_pack is not None:
            conn.execute(
                """
                INSERT INTO delivery_packs (pack_id, task_id, payload_json, generated_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    bundle.delivery_pack.pack_id,
                    task_id,
                    bundle.delivery_pack.model_dump_json(),
                    bundle.delivery_pack.generated_at.isoformat(),
                ),
            )

    def _load_bundle(
        self,
        conn: sqlite3.Connection,
        contract_row: sqlite3.Row,
    ) -> TaskContractBundle:
        task_id = str(contract_row["task_id"])
        goal_row = conn.execute(
            "SELECT payload_json FROM goal_briefs WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        metric_rows = conn.execute(
            "SELECT payload_json FROM metric_specs WHERE task_id = ? ORDER BY created_at",
            (task_id,),
        ).fetchall()
        manifest_row = conn.execute(
            "SELECT payload_json FROM dataset_manifests WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        assumption_row = conn.execute(
            "SELECT payload_json FROM assumption_logs WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        verdict_rows = conn.execute(
            "SELECT payload_json FROM review_verdicts WHERE task_id = ? ORDER BY created_at",
            (task_id,),
        ).fetchall()
        delivery_row = conn.execute(
            "SELECT payload_json FROM delivery_packs WHERE task_id = ?",
            (task_id,),
        ).fetchone()

        bundle = TaskContractBundle(
            contract=self._deserialize_contract(contract_row),
            goal_brief=(
                GoalBrief.model_validate_json(goal_row["payload_json"]) if goal_row else None
            ),
            metric_specs=[
                MetricSpec.model_validate_json(row["payload_json"]) for row in metric_rows
            ],
            dataset_manifest=(
                DatasetManifest.model_validate_json(manifest_row["payload_json"])
                if manifest_row
                else None
            ),
            assumption_log=(
                AssumptionLog.model_validate_json(assumption_row["payload_json"])
                if assumption_row
                else None
            ),
            review_verdicts=[
                ReviewVerdict.model_validate_json(row["payload_json"]) for row in verdict_rows
            ],
            delivery_pack=(
                DeliveryPack.model_validate_json(delivery_row["payload_json"])
                if delivery_row
                else None
            ),
        )
        return bundle.sync_references()

    @staticmethod
    def _store_events(conn: sqlite3.Connection, events: Sequence[TaskContractEvent]) -> None:
        for event in events:
            conn.execute(
                """
                INSERT INTO task_contract_events (task_id, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    event.task_id,
                    event.event_type,
                    json.dumps(event.payload, ensure_ascii=False, default=str),
                    event.occurred_at.isoformat(),
                ),
            )

    @staticmethod
    def _serialize_contract(contract: TaskContract) -> dict[str, object]:
        return {
            "task_id": contract.task_id,
            "session_id": contract.session_id,
            "type": contract.type,
            "status": contract.status.value,
            "business_goal": contract.business_goal,
            "primary_kpi_id": contract.primary_kpi_id,
            "decision_owner": contract.decision_owner,
            "decision_deadline": (
                contract.decision_deadline.isoformat() if contract.decision_deadline else None
            ),
            "budget_json": contract.budget.model_dump_json(),
            "autonomy_json": contract.autonomy.model_dump_json(),
            "allowed_sources_json": json.dumps(
                [
                    item.model_dump(mode="json", by_alias=True)
                    for item in contract.allowed_data_sources
                ],
                ensure_ascii=False,
            ),
            "forbidden_patterns_json": json.dumps(
                contract.forbidden_data_patterns,
                ensure_ascii=False,
            ),
            "required_deliverables_json": json.dumps(
                [item.model_dump(mode="json") for item in contract.required_deliverables],
                ensure_ascii=False,
            ),
            "definition_of_done_json": (
                contract.definition_of_done.model_dump_json()
                if contract.definition_of_done is not None
                else None
            ),
            "authority": contract.authority.value if contract.authority is not None else None,
            "audience": contract.audience.value if contract.audience is not None else None,
            "mission": contract.mission,
            "goal_brief_id": contract.goal_brief_id,
            "dataset_manifest_id": contract.dataset_manifest_id,
            "assumption_log_id": contract.assumption_log_id,
            "delivery_pack_id": contract.delivery_pack_id,
            "metric_spec_ids_json": json.dumps(contract.metric_spec_ids, ensure_ascii=False),
            "review_verdict_ids_json": json.dumps(contract.review_verdict_ids, ensure_ascii=False),
            "secondary_kpi_ids_json": json.dumps(contract.secondary_kpi_ids, ensure_ascii=False),
            "created_at": contract.created_at.isoformat(),
            "updated_at": contract.updated_at.isoformat(),
            "created_by": contract.created_by,
            "version": contract.version,
        }

    @staticmethod
    def _deserialize_contract(row: sqlite3.Row) -> TaskContract:
        return TaskContract(
            task_id=str(row["task_id"]),
            session_id=str(row["session_id"]),
            type=str(row["type"]),
            status=TaskContractStatus(str(row["status"])),
            business_goal=str(row["business_goal"]),
            primary_kpi_id=(
                str(row["primary_kpi_id"]) if row["primary_kpi_id"] is not None else None
            ),
            secondary_kpi_ids=[
                str(item) for item in json.loads(str(row["secondary_kpi_ids_json"] or "[]"))
            ],
            decision_owner=(
                str(row["decision_owner"]) if row["decision_owner"] is not None else None
            ),
            decision_deadline=(
                datetime.fromisoformat(str(row["decision_deadline"]))
                if row["decision_deadline"] is not None
                else None
            ),
            allowed_data_sources=json.loads(str(row["allowed_sources_json"] or "[]")),
            forbidden_data_patterns=[
                str(item) for item in json.loads(str(row["forbidden_patterns_json"] or "[]"))
            ],
            budget=json.loads(str(row["budget_json"])),
            required_deliverables=json.loads(str(row["required_deliverables_json"] or "[]")),
            autonomy=json.loads(str(row["autonomy_json"])),
            definition_of_done=(
                json.loads(str(row["definition_of_done_json"]))
                if row["definition_of_done_json"] is not None
                else None
            ),
            authority=(
                AuthorityMode(str(row["authority"])) if row["authority"] is not None else None
            ),
            audience=(
                AudiencePersona(str(row["audience"])) if row["audience"] is not None else None
            ),
            mission=str(row["mission"]) if row["mission"] is not None else None,
            goal_brief_id=str(row["goal_brief_id"]) if row["goal_brief_id"] is not None else None,
            dataset_manifest_id=(
                str(row["dataset_manifest_id"]) if row["dataset_manifest_id"] is not None else None
            ),
            assumption_log_id=(
                str(row["assumption_log_id"]) if row["assumption_log_id"] is not None else None
            ),
            delivery_pack_id=(
                str(row["delivery_pack_id"]) if row["delivery_pack_id"] is not None else None
            ),
            metric_spec_ids=[
                str(item) for item in json.loads(str(row["metric_spec_ids_json"] or "[]"))
            ],
            review_verdict_ids=[
                str(item) for item in json.loads(str(row["review_verdict_ids_json"] or "[]"))
            ],
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
            created_by="user" if str(row["created_by"]) == "user" else "agent",
            version=int(row["version"]),
        )
