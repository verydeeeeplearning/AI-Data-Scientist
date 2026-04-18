"""DTOs for work object and integration workflow boundaries."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ds_agent.domain.entities.external_reference import ExternalSystem
from ds_agent.domain.entities.integration_event import IntegrationEvent
from ds_agent.domain.entities.work_object import WorkObject, WorkObjectPhase


class CreateWorkObjectDTO(BaseModel):
    """Input payload for creating a work object tied to a task contract."""

    task_contract_id: str
    title: str
    request_source: str
    requestor_id: str
    requestor_display: str
    original_text: str
    channel: str | None = None
    request_metadata: dict[str, Any] = Field(default_factory=dict)
    external_reference: dict[str, Any] | None = None
    delivery_pack_id: str | None = None
    owner_agent: str = "ds-agent"
    tags: list[str] = Field(default_factory=list)
    parent_work_object_id: str | None = None


class LinkExternalReferenceDTO(BaseModel):
    """Input payload for linking an external resource to a work object."""

    work_object_id: str
    system: ExternalSystem
    resource_type: str
    resource_id: str
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    location: Literal["request", "documentation", "follow_up"] = "documentation"
    action_type: Literal["ticket", "calendar", "message", "dashboard_update"] = "message"
    description: str | None = None
    policy_decision_id: str | None = None


class AdvanceWorkObjectPhaseDTO(BaseModel):
    """Input payload for advancing a work object's lifecycle phase."""

    work_object_id: str
    to_phase: WorkObjectPhase
    run_id: str | None = None


class CloseWorkObjectDTO(BaseModel):
    """Input payload for closing a work object."""

    work_object_id: str
    reason: str


class ListWorkObjectsDTO(BaseModel):
    """Query filters for work object listing."""

    session_id: str | None = None
    task_contract_id: str | None = None
    phase_filter: list[WorkObjectPhase] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=200)


class WorkObjectListItemDTO(BaseModel):
    """Compact view of a work object."""

    work_object_id: str
    task_contract_id: str
    title: str
    phase: str
    updated_at: str
    reference_count: int
    follow_up_count: int

    @classmethod
    def from_work_object(cls, work_object: WorkObject) -> WorkObjectListItemDTO:
        return cls(
            work_object_id=work_object.work_object_id,
            task_contract_id=work_object.execution.task_contract_id,
            title=work_object.title,
            phase=work_object.execution.current_phase.value,
            updated_at=work_object.updated_at.isoformat(),
            reference_count=len(work_object.documentation.references),
            follow_up_count=len(work_object.follow_up.actions),
        )


class WorkObjectViewDTO(BaseModel):
    """Detailed work object view for tools and UI surfaces."""

    work_object: WorkObject
    timeline: list[IntegrationEvent] = Field(default_factory=list)
