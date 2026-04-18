import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ds_agent.domain.entities.assumption_log import AssumptionLog
from ds_agent.domain.entities.goal_brief import GoalBrief
from ds_agent.domain.entities.task_contract import TaskContract
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.entities.task_contract_event import TaskContractEvent
from ds_agent.domain.errors.task_contract_errors import VersionConflictError
from ds_agent.infrastructure.persistence.task_contract_store import SqliteTaskContractStore


def _bundle() -> TaskContractBundle:
    now = datetime(2026, 4, 15, tzinfo=UTC)
    return TaskContractBundle(
        contract=TaskContract(
            task_id="TC-2026-001",
            session_id="session-1",
            type="churn_analysis",
            business_goal="Reduce churn",
            authority="delegate",
            audience="senior_staff",
            mission="weekly-kpi-triage",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"}
            ],
            goal_brief_id="GB-1",
            assumption_log_id="AL-1",
            created_at=now,
            updated_at=now,
        ),
        goal_brief=GoalBrief(
            brief_id="GB-1",
            task_id="TC-2026-001",
            business_question="Why churn?",
            ds_problem_statement="Binary classification",
            comparison_baseline="last quarter",
            decision_to_make="prioritize actions",
            expected_effort="M",
            created_at=now,
            updated_at=now,
        ),
        assumption_log=AssumptionLog(log_id="AL-1", task_id="TC-2026-001"),
    ).sync_references()


def _db_path() -> Path:
    base_dir = Path("task_contract_test_artifacts/task-contract-store")
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / f"{uuid.uuid4().hex}.db"


def test_sqlite_task_contract_round_trip() -> None:
    store = SqliteTaskContractStore(_db_path())
    bundle = _bundle()
    store.create_bundle(
        bundle,
        events=[
            TaskContractEvent(
                event_type="task_contract.created",
                task_id=bundle.contract.task_id,
                occurred_at=bundle.contract.created_at,
            )
        ],
    )

    restored = store.get_bundle(bundle.contract.task_id)
    assert restored is not None
    assert restored.contract.task_id == bundle.contract.task_id
    assert restored.contract.authority == bundle.contract.authority
    assert restored.contract.audience == bundle.contract.audience
    assert restored.contract.mission == bundle.contract.mission
    assert restored.goal_brief is not None
    assert restored.assumption_log is not None


def test_migration_v10_applies_and_is_idempotent() -> None:
    db_path = _db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (4, datetime('now'))"
        )
        conn.commit()

    SqliteTaskContractStore(db_path)
    SqliteTaskContractStore(db_path)

    with sqlite3.connect(db_path) as conn:
        version = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(task_contracts)").fetchall()
        }
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            ).fetchall()
        }
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='task_contracts'"
        ).fetchone()
    assert version == 10
    assert {"authority", "audience", "mission"}.issubset(columns)
    assert table is not None
    assert "delivery_log" in tables
    assert "v_delivery_summary" in tables


def test_optimistic_locking_rejects_stale_writer() -> None:
    store = SqliteTaskContractStore(_db_path())
    bundle = _bundle()
    store.create_bundle(bundle)
    bundle.contract.version = 2
    bundle.contract.business_goal = "Updated goal"

    with pytest.raises(VersionConflictError):
        store.save_bundle(bundle, expected_version=99)
