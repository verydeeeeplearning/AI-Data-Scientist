from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ds_agent.domain.entities.external_reference import ExternalReference
from ds_agent.domain.entities.work_object import (
    ExecutionSection,
    FollowUpActionStatus,
    RequestSection,
    RequestSource,
    WorkObject,
    WorkObjectPhase,
)
from ds_agent.domain.errors.work_object_errors import WorkObjectStateError


def _work_object(now: datetime) -> WorkObject:
    return WorkObject(
        work_object_id="WO-2026-001",
        title="Growth churn investigation",
        request=RequestSection(
            source=RequestSource.SLACK,
            requestor_id="U123",
            requestor_display="Kim",
            original_text="Please investigate churn.",
            channel="growth-ds",
            received_at=now,
        ),
        execution=ExecutionSection(task_contract_id="TC-2026-001"),
        created_at=now,
        updated_at=now,
        owner_agent="ds-agent-prod",
    )


def test_work_object_phase_transitions_and_timestamps() -> None:
    now = datetime(2026, 4, 16, tzinfo=UTC)
    work_object = _work_object(now)

    work_object.advance_to(WorkObjectPhase.EXECUTING, when=now + timedelta(minutes=1))
    work_object.advance_to(WorkObjectPhase.REVIEW, when=now + timedelta(minutes=2))
    work_object.attach_reference(
        ExternalReference(
            system="confluence",
            resource_type="page",
            resource_id="12345",
            created_at=now + timedelta(minutes=3),
            idempotency_key="wo_WO-2026-001:confluence:create_page:abc123",
        ),
        location="documentation",
        when=now + timedelta(minutes=3),
    )
    work_object.advance_to(WorkObjectPhase.DOCUMENTING, when=now + timedelta(minutes=4))
    work_object.advance_to(WorkObjectPhase.FOLLOWUP, when=now + timedelta(minutes=5))
    work_object.attach_reference(
        ExternalReference(
            system="jira",
            resource_type="issue",
            resource_id="DS-101",
            created_at=now + timedelta(minutes=6),
            idempotency_key="wo_WO-2026-001:jira:create_issue:def456",
            metadata={"status": "completed"},
        ),
        location="follow_up",
        when=now + timedelta(minutes=6),
        action_type="ticket",
        description="Create retention ticket",
    )
    work_object.advance_to(WorkObjectPhase.CLOSED, when=now + timedelta(minutes=7))

    assert work_object.execution.started_at == now + timedelta(minutes=1)
    assert work_object.execution.completed_at == now + timedelta(minutes=7)
    assert work_object.execution.current_phase == WorkObjectPhase.CLOSED
    assert work_object.follow_up.actions[0].status == FollowUpActionStatus.COMPLETED


def test_work_object_rejects_invalid_transition() -> None:
    now = datetime(2026, 4, 16, tzinfo=UTC)
    work_object = _work_object(now)

    with pytest.raises(WorkObjectStateError):
        work_object.advance_to(WorkObjectPhase.CLOSED, when=now + timedelta(minutes=1))


def test_work_object_requires_completed_follow_up_before_close() -> None:
    now = datetime(2026, 4, 16, tzinfo=UTC)
    work_object = _work_object(now)
    work_object.advance_to(WorkObjectPhase.EXECUTING, when=now + timedelta(minutes=1))
    work_object.advance_to(WorkObjectPhase.REVIEW, when=now + timedelta(minutes=2))
    work_object.attach_reference(
        ExternalReference(
            system="confluence",
            resource_type="page",
            resource_id="12345",
            created_at=now + timedelta(minutes=3),
            idempotency_key="wo_WO-2026-001:confluence:create_page:abc123",
        ),
        location="documentation",
        when=now + timedelta(minutes=3),
    )
    work_object.advance_to(WorkObjectPhase.DOCUMENTING, when=now + timedelta(minutes=4))
    work_object.advance_to(WorkObjectPhase.FOLLOWUP, when=now + timedelta(minutes=5))
    work_object.attach_reference(
        ExternalReference(
            system="jira",
            resource_type="issue",
            resource_id="DS-101",
            created_at=now + timedelta(minutes=6),
            idempotency_key="wo_WO-2026-001:jira:create_issue:def456",
        ),
        location="follow_up",
        when=now + timedelta(minutes=6),
        action_type="ticket",
        description="Create retention ticket",
    )

    with pytest.raises(WorkObjectStateError):
        work_object.advance_to(WorkObjectPhase.CLOSED, when=now + timedelta(minutes=7))
