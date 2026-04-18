from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.application.dtos.work_object import WorkObjectListItemDTO, WorkObjectViewDTO
from ds_agent.domain.entities.external_reference import ExternalReference
from ds_agent.domain.entities.integration_event import IntegrationEvent, IntegrationEventStatus
from ds_agent.domain.entities.work_object import (
    DocumentationSection,
    ExecutionSection,
    FollowUpAction,
    FollowUpSection,
    RequestSection,
    RequestSource,
    WorkObject,
    WorkObjectPhase,
)
from ds_agent.presentation.work_object_presenters import (
    render_work_object_list,
    render_work_object_view,
)


def _work_object() -> WorkObject:
    now = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)
    reference = ExternalReference(
        system="jira",
        resource_type="issue",
        resource_id="DS-101",
        created_at=now,
        idempotency_key="wo_WO-2026-001:jira:create_issue:abc123",
    )
    return WorkObject(
        work_object_id="WO-2026-001",
        title="Retention workflow",
        request=RequestSection(
            source=RequestSource.SLACK,
            requestor_id="U123",
            requestor_display="Kim",
            original_text="Create the retention follow-up workflow.",
            channel="growth-ds",
            received_at=now,
        ),
        execution=ExecutionSection(
            task_contract_id="TC-2026-001",
            run_ids=["run-1"],
            current_phase=WorkObjectPhase.FOLLOWUP,
            started_at=now,
        ),
        documentation=DocumentationSection(references=[reference]),
        follow_up=FollowUpSection(
            actions=[
                FollowUpAction(
                    action_type="ticket",
                    description="Open implementation ticket",
                    external_ref=reference,
                    status="completed",
                )
            ]
        ),
        created_at=now,
        updated_at=now,
        owner_agent="ds-agent",
        tags=["retention"],
    )


def test_render_work_object_list_shows_compact_rows() -> None:
    text = render_work_object_list(
        [
            WorkObjectListItemDTO(
                work_object_id="WO-2026-001",
                task_contract_id="TC-2026-001",
                title="Retention workflow",
                phase="followup",
                updated_at="2026-04-16T12:00:00+00:00",
                reference_count=1,
                follow_up_count=1,
            )
        ]
    )

    assert "Work objects:" in text
    assert "WO-2026-001 | followup | Retention workflow" in text


def test_render_work_object_view_includes_timeline_and_references() -> None:
    work_object = _work_object()
    text = render_work_object_view(
        WorkObjectViewDTO(
            work_object=work_object,
            timeline=[
                IntegrationEvent(
                    event_id="IE-1",
                    work_object_id=work_object.work_object_id,
                    system="jira",
                    action="create_issue",
                    request_payload_hash="abc123",
                    idempotency_key="wo_WO-2026-001:jira:create_issue:abc123",
                    status=IntegrationEventStatus.SUCCESS,
                    external_ref=work_object.documentation.references[0],
                    started_at=work_object.updated_at,
                    finished_at=work_object.updated_at,
                )
            ],
        )
    )

    assert "Work object: WO-2026-001" in text
    assert "Source: slack" in text
    assert "Requestor: Kim (U123)" in text
    assert "Documentation refs:" in text
    assert "jira:issue:DS-101" in text
    assert "Timeline:" in text
    assert "success | jira.create_issue" in text
