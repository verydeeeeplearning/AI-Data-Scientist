"""Repository interface for task contract persistence."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from ds_agent.domain.entities.task_contract import TaskContract, TaskContractStatus
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.entities.task_contract_event import TaskContractEvent


@runtime_checkable
class TaskContractStore(Protocol):
    """Persistence contract for task contracts and their child artifacts."""

    def create_bundle(
        self,
        bundle: TaskContractBundle,
        *,
        events: Sequence[TaskContractEvent] = (),
    ) -> None: ...

    def get_bundle(self, task_id: str) -> TaskContractBundle | None: ...

    def get_active_bundle(self, session_id: str) -> TaskContractBundle | None: ...

    def list_contracts(
        self,
        session_id: str | None = None,
        *,
        statuses: Sequence[TaskContractStatus] | None = None,
        limit: int = 20,
    ) -> list[TaskContract]: ...

    def save_bundle(
        self,
        bundle: TaskContractBundle,
        *,
        expected_version: int,
        events: Sequence[TaskContractEvent] = (),
    ) -> None: ...
