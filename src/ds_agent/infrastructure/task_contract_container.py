"""Composition root for task contract backend services."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from ds_agent.application.ports.task_contract_support import Clock, EventPublisher, IdGenerator
from ds_agent.application.services.audience_renderer import ArtifactExporter, AudienceRenderer
from ds_agent.application.services.task_contract_usecases import (
    AddAssumptionUseCase,
    BuildDeliveryPackUseCase,
    CloseTaskContractUseCase,
    CreateTaskContractUseCase,
    DispatchDeliveryUseCase,
    GetTaskContractUseCase,
    ListDeliveryLogUseCase,
    ListTaskContractsUseCase,
    RecordDeliveryPackUseCase,
    RecordReviewVerdictUseCase,
    RenderDeliveryArtifactUseCase,
    UpdateTaskContractUseCase,
    VerifyAssumptionUseCase,
)
from ds_agent.domain.entities.task_contract_event import TaskContractEvent
from ds_agent.domain.interfaces.llm_provider import LLMProvider
from ds_agent.domain.interfaces.task_contract import TaskContractStore
from ds_agent.infrastructure.delivery import (
    DeliveryPolicyEngine,
    DeliveryRouter,
    JsonlDeliveryDispatchLog,
    LLMNarrativeGateway,
    SqliteDeliveryDispatchLog,
    build_default_channel_adapters,
)
from ds_agent.infrastructure.persistence.task_contract_store import SqliteTaskContractStore
from ds_agent.runtime.delivery_policy_store import JsonDeliveryPolicyStore
from ds_agent.runtime.transcript_store import get_runtime_storage_root


class SystemClock(Clock):
    """Production clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class TimestampIdGenerator(IdGenerator):
    """Timestamp-based id generator that matches the spec regexes."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counter = 0

    def new_task_id(self, now: datetime) -> str:
        with self._lock:
            self._counter += 1
            suffix = int(now.timestamp() * 1000)
            return f"TC-{now.year}-{suffix}{self._counter:03d}"

    def new_artifact_id(self, prefix: str) -> str:
        with self._lock:
            self._counter += 1
            return f"{prefix}-{time.time_ns() + self._counter}"


class InMemoryEventPublisher(EventPublisher):
    """Simple event sink for tests and runtime introspection."""

    def __init__(self) -> None:
        self.events: list[TaskContractEvent] = []

    def publish(self, event: TaskContractEvent) -> None:
        self.events.append(event)


@dataclass(frozen=True)
class TaskContractContainer:
    """Wired use cases for the task contract subsystem."""

    store: TaskContractStore
    clock: Clock
    ids: IdGenerator
    publisher: InMemoryEventPublisher
    create: CreateTaskContractUseCase
    update: UpdateTaskContractUseCase
    get: GetTaskContractUseCase
    list_contracts: ListTaskContractsUseCase
    add_assumption: AddAssumptionUseCase
    verify_assumption: VerifyAssumptionUseCase
    close: CloseTaskContractUseCase
    record_review_verdict: RecordReviewVerdictUseCase
    build_delivery_pack: BuildDeliveryPackUseCase
    render_delivery_artifact: RenderDeliveryArtifactUseCase
    dispatch_delivery: DispatchDeliveryUseCase
    list_delivery_log: ListDeliveryLogUseCase
    record_delivery_pack: RecordDeliveryPackUseCase


def build_task_contract_container(
    workspace_dir: str | None = None,
    *,
    store: TaskContractStore | None = None,
    llm_provider: LLMProvider | None = None,
) -> TaskContractContainer:
    """Build a fully wired task contract container for one workspace."""

    from ds_agent.infrastructure.exporters import (
        FileSystemThemeLoader,
        IpynbExporter,
        MarkdownExporter,
        PdfExporter,
        PptxExporter,
        StaticTemplateRegistry,
    )

    resolved_store = store or SqliteTaskContractStore.for_workspace(workspace_dir)
    clock = SystemClock()
    ids = TimestampIdGenerator()
    publisher = InMemoryEventPublisher()
    theme_loader = FileSystemThemeLoader()
    renderer = AudienceRenderer(
        llm_gateway=LLMNarrativeGateway(llm_provider) if llm_provider is not None else None,
        template_registry=StaticTemplateRegistry(),
        exporters=cast(
            "list[ArtifactExporter]",
            [
                MarkdownExporter(),
                IpynbExporter(),
                PdfExporter(theme_loader=theme_loader),
                PptxExporter(theme_loader=theme_loader),
            ],
        ),
    )
    runtime_root = _resolve_runtime_root(workspace_dir, resolved_store)
    dispatch_log = (
        SqliteDeliveryDispatchLog(resolved_store.db_path)
        if isinstance(resolved_store, SqliteTaskContractStore)
        else JsonlDeliveryDispatchLog(runtime_root)
    )
    dispatcher = DeliveryRouter(
        adapters=build_default_channel_adapters(),
        policy=DeliveryPolicyEngine(
            policy_store=(
                JsonDeliveryPolicyStore(workspace_dir) if workspace_dir is not None else None
            ),
        ),
        log=dispatch_log,
    )
    return TaskContractContainer(
        store=resolved_store,
        clock=clock,
        ids=ids,
        publisher=publisher,
        create=CreateTaskContractUseCase(resolved_store, clock, ids, publisher),
        update=UpdateTaskContractUseCase(resolved_store, clock, publisher),
        get=GetTaskContractUseCase(resolved_store, clock, publisher),
        list_contracts=ListTaskContractsUseCase(resolved_store, clock, publisher),
        add_assumption=AddAssumptionUseCase(resolved_store, clock, ids, publisher),
        verify_assumption=VerifyAssumptionUseCase(resolved_store, clock, publisher),
        close=CloseTaskContractUseCase(resolved_store, clock, publisher),
        record_review_verdict=RecordReviewVerdictUseCase(resolved_store, clock, ids, publisher),
        build_delivery_pack=BuildDeliveryPackUseCase(resolved_store, clock, ids, publisher),
        render_delivery_artifact=RenderDeliveryArtifactUseCase(
            resolved_store,
            clock,
            publisher,
            renderer,
        ),
        dispatch_delivery=DispatchDeliveryUseCase(
            resolved_store,
            clock,
            publisher,
            dispatcher,
        ),
        list_delivery_log=ListDeliveryLogUseCase(
            resolved_store,
            clock,
            publisher,
            dispatch_log,
        ),
        record_delivery_pack=RecordDeliveryPackUseCase(resolved_store, clock, ids, publisher),
    )


def _resolve_runtime_root(
    workspace_dir: str | None,
    store: TaskContractStore,
) -> Path:
    if workspace_dir is not None:
        return get_runtime_storage_root(workspace_dir)
    if isinstance(store, SqliteTaskContractStore):
        return store.db_path.parent
    return get_runtime_storage_root(None)
