from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ds_agent.domain.entities.assumption_log import AssumptionLog
from ds_agent.domain.entities.external_reference import ExternalReference
from ds_agent.domain.entities.goal_brief import GoalBrief
from ds_agent.domain.entities.integration_event import IntegrationEvent, IntegrationEventStatus
from ds_agent.domain.entities.task_contract import TaskContract
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.entities.work_object import (
    ExecutionSection,
    RequestSection,
    RequestSource,
    WorkObject,
)
from ds_agent.infrastructure.persistence.task_contract_store import SqliteTaskContractStore
from ds_agent.infrastructure.persistence.work_object_store import SqliteWorkObjectStore


def _db_path() -> Path:
    base_dir = Path("task_contract_test_artifacts/work-object-store")
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / f"{uuid.uuid4().hex}.db"


def _bundle(task_id: str) -> TaskContractBundle:
    now = datetime(2026, 4, 16, tzinfo=UTC)
    return TaskContractBundle(
        contract=TaskContract(
            task_id=task_id,
            session_id="session-1",
            type="churn_analysis",
            business_goal="Reduce churn",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"}
            ],
            goal_brief_id=f"GB-{task_id[-3:]}",
            assumption_log_id=f"AL-{task_id[-3:]}",
            created_at=now,
            updated_at=now,
        ),
        goal_brief=GoalBrief(
            brief_id=f"GB-{task_id[-3:]}",
            task_id=task_id,
            business_question="Why churn?",
            ds_problem_statement="Binary classification",
            comparison_baseline="last quarter",
            decision_to_make="prioritize actions",
            expected_effort="M",
            created_at=now,
            updated_at=now,
        ),
        assumption_log=AssumptionLog(log_id=f"AL-{task_id[-3:]}", task_id=task_id),
    ).sync_references()


def test_sqlite_work_object_store_round_trip_and_migration() -> None:
    db_path = _db_path()
    task_store = SqliteTaskContractStore(db_path)
    task_store.create_bundle(_bundle("TC-2026-001"))
    store = SqliteWorkObjectStore(db_path)
    now = datetime(2026, 4, 16, tzinfo=UTC)
    work_object = WorkObject(
        work_object_id="WO-2026-001",
        title="Churn request",
        request=RequestSection(
            source=RequestSource.SLACK,
            requestor_id="U123",
            requestor_display="Kim",
            original_text="Investigate churn",
            channel="growth-ds",
            received_at=now,
        ),
        execution=ExecutionSection(task_contract_id="TC-2026-001"),
        created_at=now,
        updated_at=now,
        owner_agent="ds-agent-prod",
    )
    work_object.attach_reference(
        ExternalReference(
            system="confluence",
            resource_type="page",
            resource_id="12345",
            created_at=now,
            idempotency_key="wo_WO-2026-001:confluence:create_page:abc123",
        ),
        location="documentation",
        when=now,
    )
    store.create(work_object)
    store.record_event(
        IntegrationEvent(
            event_id="IE-1",
            work_object_id="WO-2026-001",
            system="confluence",
            action="create_page",
            request_payload_hash="abc123",
            idempotency_key="wo_WO-2026-001:confluence:create_page:abc123",
            status=IntegrationEventStatus.SUCCESS,
            external_ref=work_object.documentation.references[0],
            attempt=1,
            latency_ms=10,
            started_at=now,
            finished_at=now,
        )
    )

    restored = store.get("WO-2026-001")
    assert restored is not None
    assert restored.execution.task_contract_id == "TC-2026-001"
    assert restored.documentation.references[0].resource_id == "12345"

    listed = store.list(task_contract_id="TC-2026-001")
    assert [item.work_object_id for item in listed] == ["WO-2026-001"]

    timeline = store.list_events("WO-2026-001")
    assert timeline[0].action == "create_page"
    assert timeline[0].external_ref is not None
    assert store.find_event_by_idempotency_key(
        "wo_WO-2026-001:confluence:create_page:abc123"
    ) is not None

    with sqlite3.connect(db_path) as conn:
        version = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        integration_event_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(integration_event_log)").fetchall()
        }
    assert version == 12
    assert {"work_objects", "integration_event_log", "external_reference"}.issubset(tables)
    # v12 adds request_payload_json column to integration_event_log for DLQ replay.
    assert "request_payload_json" in integration_event_columns
