"""Use cases for workflow integration work objects."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ds_agent.application.dtos.work_object import (
    AdvanceWorkObjectPhaseDTO,
    CloseWorkObjectDTO,
    CreateWorkObjectDTO,
    LinkExternalReferenceDTO,
    ListWorkObjectsDTO,
    WorkObjectListItemDTO,
    WorkObjectViewDTO,
)
from ds_agent.domain.entities.external_reference import (
    ExternalReference,
    build_integration_idempotency_key,
    build_request_payload_hash,
)
from ds_agent.domain.entities.integration_event import IntegrationEvent, IntegrationEventStatus
from ds_agent.domain.entities.work_object import (
    DocumentationSection,
    ExecutionSection,
    RequestSection,
    RequestSource,
    WorkObject,
    WorkObjectPhase,
)
from ds_agent.domain.errors.work_object_errors import (
    WorkObjectAlreadyExistsError,
    WorkObjectNotFoundError,
)
from ds_agent.domain.interfaces.task_contract import TaskContractStore
from ds_agent.domain.interfaces.work_object import WorkObjectStore


class Clock(Protocol):
    def now(self) -> datetime: ...


class WorkObjectIdGenerator(Protocol):
    def new_work_object_id(self, now: datetime) -> str: ...

    def new_artifact_id(self, prefix: str) -> str: ...


class _BaseWorkObjectUseCase:
    def __init__(
        self,
        store: WorkObjectStore,
        task_store: TaskContractStore,
        clock: Clock,
        ids: WorkObjectIdGenerator,
    ) -> None:
        self._store = store
        self._task_store = task_store
        self._clock = clock
        self._ids = ids

    def _load(self, work_object_id: str) -> WorkObject:
        work_object = self._store.get(work_object_id)
        if work_object is None:
            raise WorkObjectNotFoundError(f"Work object not found: {work_object_id}")
        return work_object

    def _record_internal_event(
        self,
        *,
        work_object_id: str,
        action: str,
        payload: object,
        external_ref: ExternalReference | None = None,
        policy_decision_id: str | None = None,
    ) -> IntegrationEvent:
        now = self._clock.now()
        payload_hash = build_request_payload_hash(payload)
        event = IntegrationEvent(
            event_id=self._ids.new_artifact_id("IE"),
            work_object_id=work_object_id,
            system="internal",
            action=action,
            request_payload_hash=payload_hash,
            idempotency_key=build_integration_idempotency_key(
                work_object_id=work_object_id,
                system="internal",
                action=action,
                discriminator=payload_hash[:16],
            ),
            status=IntegrationEventStatus.SUCCESS,
            external_ref=external_ref,
            attempt=1,
            latency_ms=0,
            started_at=now,
            finished_at=now,
            policy_decision_id=policy_decision_id,
        )
        self._store.record_event(event)
        return event


class CreateWorkObjectUseCase(_BaseWorkObjectUseCase):
    """Create a work object if the task contract is valid and not yet linked."""

    def execute(self, dto: CreateWorkObjectDTO) -> WorkObjectViewDTO:
        if self._task_store.get_bundle(dto.task_contract_id) is None:
            raise WorkObjectNotFoundError(
                f"Task contract not found for work object creation: {dto.task_contract_id}"
            )
        if self._store.get_by_task_contract(dto.task_contract_id) is not None:
            raise WorkObjectAlreadyExistsError(
                f"Task contract already linked to a work object: {dto.task_contract_id}"
            )
        now = self._clock.now()
        work_object = WorkObject(
            work_object_id=self._ids.new_work_object_id(now),
            title=dto.title,
            request=RequestSection(
                source=RequestSource(dto.request_source),
                requestor_id=dto.requestor_id,
                requestor_display=dto.requestor_display,
                original_text=dto.original_text,
                channel=dto.channel,
                received_at=now,
                external_ref=(
                    None
                    if dto.external_reference is None
                    else ExternalReference.model_validate(dto.external_reference)
                ),
                metadata=dto.request_metadata,
            ),
            execution=ExecutionSection(task_contract_id=dto.task_contract_id),
            documentation=DocumentationSection(delivery_pack_id=dto.delivery_pack_id),
            created_at=now,
            updated_at=now,
            owner_agent=dto.owner_agent,
            tags=dto.tags,
            parent_work_object_id=dto.parent_work_object_id,
        )
        self._store.create(work_object)
        event = self._record_internal_event(
            work_object_id=work_object.work_object_id,
            action="create_work_object",
            payload=dto.model_dump(mode="json"),
        )
        return WorkObjectViewDTO(work_object=work_object, timeline=[event])


class GetWorkObjectUseCase(_BaseWorkObjectUseCase):
    """Load one work object and its timeline."""

    def execute(self, work_object_id: str, *, timeline_limit: int = 50) -> WorkObjectViewDTO:
        work_object = self._load(work_object_id)
        return WorkObjectViewDTO(
            work_object=work_object,
            timeline=self._store.list_events(work_object_id, limit=timeline_limit),
        )


class AttachExternalReferenceUseCase(_BaseWorkObjectUseCase):
    """Link one external resource to a work object."""

    def execute(self, dto: LinkExternalReferenceDTO) -> dict[str, object]:
        now = self._clock.now()
        work_object = self._load(dto.work_object_id)
        resource_payload = {
            "system": dto.system,
            "resource_type": dto.resource_type,
            "resource_id": dto.resource_id,
            "url": dto.url,
            "metadata": dto.metadata,
            "location": dto.location,
        }
        reference = ExternalReference(
            system=dto.system,
            resource_type=dto.resource_type,
            resource_id=dto.resource_id,
            url=dto.url,
            metadata=dto.metadata,
            created_at=now,
            idempotency_key=(
                dto.idempotency_key
                or build_integration_idempotency_key(
                    work_object_id=dto.work_object_id,
                    system=dto.system,
                    action="link_external_reference",
                    discriminator=build_request_payload_hash(resource_payload)[:16],
                )
            ),
        )
        work_object.attach_reference(
            reference,
            location=dto.location,
            when=now,
            action_type=dto.action_type,
            description=dto.description,
            policy_decision_id=dto.policy_decision_id,
        )
        self._store.save(work_object)
        event = self._record_internal_event(
            work_object_id=dto.work_object_id,
            action="link_external_reference",
            payload=resource_payload,
            external_ref=reference,
            policy_decision_id=dto.policy_decision_id,
        )
        return {
            "work_object_id": dto.work_object_id,
            "location": dto.location,
            "phase": work_object.execution.current_phase.value,
            "reference": reference.model_dump(mode="json"),
            "event_id": event.event_id,
        }


class AdvancePhaseUseCase(_BaseWorkObjectUseCase):
    """Advance a work object's phase and optionally attach a run id."""

    def execute(self, dto: AdvanceWorkObjectPhaseDTO) -> dict[str, object]:
        now = self._clock.now()
        work_object = self._load(dto.work_object_id)
        if dto.run_id is not None:
            work_object.register_run(dto.run_id, when=now)
        work_object.advance_to(dto.to_phase, when=now)
        self._store.save(work_object)
        event = self._record_internal_event(
            work_object_id=dto.work_object_id,
            action="advance_phase",
            payload=dto.model_dump(mode="json"),
        )
        return {
            "work_object_id": dto.work_object_id,
            "phase": work_object.execution.current_phase.value,
            "run_ids": list(work_object.execution.run_ids),
            "event_id": event.event_id,
        }


class CloseWorkObjectUseCase(_BaseWorkObjectUseCase):
    """Close a work object once follow-up is complete."""

    def execute(self, dto: CloseWorkObjectDTO) -> dict[str, object]:
        now = self._clock.now()
        work_object = self._load(dto.work_object_id)
        work_object.metadata["close_reason"] = dto.reason
        work_object.advance_to(WorkObjectPhase.CLOSED, when=now)
        self._store.save(work_object)
        event = self._record_internal_event(
            work_object_id=dto.work_object_id,
            action="close_work_object",
            payload=dto.model_dump(mode="json"),
        )
        return {
            "work_object_id": dto.work_object_id,
            "phase": work_object.execution.current_phase.value,
            "event_id": event.event_id,
            "close_reason": dto.reason,
        }


class ListWorkObjectsUseCase(_BaseWorkObjectUseCase):
    """List work objects with simple filters."""

    def execute(self, dto: ListWorkObjectsDTO) -> list[WorkObjectListItemDTO]:
        items = self._store.list(
            session_id=dto.session_id,
            task_contract_id=dto.task_contract_id,
            phases=dto.phase_filter or None,
            limit=dto.limit,
        )
        return [WorkObjectListItemDTO.from_work_object(item) for item in items]


class GetWorkObjectTimelineUseCase(_BaseWorkObjectUseCase):
    """Return the persisted integration timeline for one work object."""

    def execute(self, work_object_id: str, *, limit: int = 100) -> list[IntegrationEvent]:
        self._load(work_object_id)
        return self._store.list_events(work_object_id, limit=limit)
