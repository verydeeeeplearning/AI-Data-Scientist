"""Composition root for workflow integration services."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from ds_agent.application.ports.work_object_support import WorkflowIntegrationPolicyPort
from ds_agent.application.services.work_object_usecases import (
    AdvancePhaseUseCase,
    AttachExternalReferenceUseCase,
    CloseWorkObjectUseCase,
    CreateWorkObjectUseCase,
    GetWorkObjectTimelineUseCase,
    GetWorkObjectUseCase,
    ListWorkObjectsUseCase,
)
from ds_agent.domain.interfaces.task_contract import TaskContractStore
from ds_agent.domain.interfaces.work_object import WorkObjectStore
from ds_agent.infrastructure.external.integration_hub import IntegrationHub
from ds_agent.infrastructure.persistence.task_contract_store import SqliteTaskContractStore
from ds_agent.infrastructure.persistence.work_object_store import SqliteWorkObjectStore
from ds_agent.infrastructure.work_object_policy import EvaluatorWorkflowIntegrationPolicy


class SystemClock:
    """Production clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class TimestampWorkObjectIdGenerator:
    """Timestamp-based identifier generator for work objects and events."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counter = 0

    def new_work_object_id(self, now: datetime) -> str:
        with self._lock:
            self._counter += 1
            suffix = int(now.timestamp() * 1000)
            return f"WO-{now.year}-{suffix}{self._counter:03d}"

    def new_artifact_id(self, prefix: str) -> str:
        with self._lock:
            self._counter += 1
            return f"{prefix}-{time.time_ns() + self._counter}"


@dataclass(frozen=True)
class WorkObjectContainer:
    """Wired use cases for workflow integration."""

    store: WorkObjectStore
    task_store: TaskContractStore
    clock: SystemClock
    ids: TimestampWorkObjectIdGenerator
    create: CreateWorkObjectUseCase
    get: GetWorkObjectUseCase
    list_work_objects: ListWorkObjectsUseCase
    attach_reference: AttachExternalReferenceUseCase
    advance_phase: AdvancePhaseUseCase
    close: CloseWorkObjectUseCase
    timeline: GetWorkObjectTimelineUseCase
    hub: IntegrationHub


def build_work_object_container(
    workspace_dir: str | None = None,
    *,
    store: WorkObjectStore | None = None,
    task_store: TaskContractStore | None = None,
    policy: WorkflowIntegrationPolicyPort | None = None,
) -> WorkObjectContainer:
    """Build a fully wired work object container."""

    resolved_store = store or SqliteWorkObjectStore.for_workspace(workspace_dir)
    default_task_store = SqliteTaskContractStore.for_workspace(workspace_dir)
    resolved_task_store = (
        task_store
        or SqliteTaskContractStore(
            resolved_store.db_path
            if isinstance(resolved_store, SqliteWorkObjectStore)
            else default_task_store.db_path
        )
    )
    clock = SystemClock()
    ids = TimestampWorkObjectIdGenerator()
    return WorkObjectContainer(
        store=resolved_store,
        task_store=resolved_task_store,
        clock=clock,
        ids=ids,
        create=CreateWorkObjectUseCase(resolved_store, resolved_task_store, clock, ids),
        get=GetWorkObjectUseCase(resolved_store, resolved_task_store, clock, ids),
        list_work_objects=ListWorkObjectsUseCase(resolved_store, resolved_task_store, clock, ids),
        attach_reference=AttachExternalReferenceUseCase(
            resolved_store,
            resolved_task_store,
            clock,
            ids,
        ),
        advance_phase=AdvancePhaseUseCase(resolved_store, resolved_task_store, clock, ids),
        close=CloseWorkObjectUseCase(resolved_store, resolved_task_store, clock, ids),
        timeline=GetWorkObjectTimelineUseCase(resolved_store, resolved_task_store, clock, ids),
        hub=IntegrationHub(
            store=resolved_store,
            clock=clock,
            policy=policy or EvaluatorWorkflowIntegrationPolicy(),
        ),
    )
