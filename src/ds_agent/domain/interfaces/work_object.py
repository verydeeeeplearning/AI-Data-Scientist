"""Repository protocol for work object persistence."""

from __future__ import annotations

import builtins
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from ds_agent.domain.entities.integration_event import (
    IntegrationEvent,
    IntegrationEventStatus,
)
from ds_agent.domain.entities.work_object import WorkObject, WorkObjectPhase


@runtime_checkable
class WorkObjectStore(Protocol):
    """Persistence contract for workflow integration state."""

    def create(self, work_object: WorkObject) -> None: ...

    def get(self, work_object_id: str) -> WorkObject | None: ...

    def get_by_task_contract(self, task_contract_id: str) -> WorkObject | None: ...

    def list(
        self,
        *,
        session_id: str | None = None,
        task_contract_id: str | None = None,
        phases: Sequence[WorkObjectPhase] | None = None,
        limit: int = 20,
    ) -> builtins.list[WorkObject]: ...

    def save(self, work_object: WorkObject) -> None: ...

    def record_event(self, event: IntegrationEvent) -> None: ...

    def list_events(
        self,
        work_object_id: str,
        *,
        limit: int = 100,
    ) -> builtins.list[IntegrationEvent]: ...

    def find_event_by_idempotency_key(self, idempotency_key: str) -> IntegrationEvent | None: ...

    def list_events_by_status(
        self,
        status: IntegrationEventStatus,
        *,
        system: str | None = None,
        limit: int = 100,
    ) -> builtins.list[IntegrationEvent]: ...

    def get_event(self, event_id: str) -> IntegrationEvent | None: ...

    def update_event_status(
        self,
        event_id: str,
        new_status: IntegrationEventStatus,
        *,
        attempt: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None: ...
