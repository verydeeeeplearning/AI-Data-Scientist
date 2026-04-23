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
from ds_agent.application.services.mission_required_artifacts import (
    MissionRequiredArtifactResolver,
)
from ds_agent.application.services.mission_required_delivery_channels import (
    MissionRequiredDeliveryChannelResolver,
)
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
from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore
from ds_agent.infrastructure.persistence.task_contract_store import SqliteTaskContractStore
from ds_agent.runtime.delivery_policy_store import JsonDeliveryPolicyStore
from ds_agent.runtime.task_contract_failure_signal_recorder import (
    LearningTaskContractFailureSignalRecorder,
)
from ds_agent.runtime.transcript_store import get_runtime_storage_root
from ds_agent.skills.mission_pack_loader import MissionPackLoader


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
    mission_required_artifact_resolver: MissionRequiredArtifactResolver
    mission_required_delivery_channel_resolver: MissionRequiredDeliveryChannelResolver
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
    mission_loader = MissionPackLoader()
    mission_required_artifact_resolver = MissionRequiredArtifactResolver(mission_loader)
    dispatch_log = (
        SqliteDeliveryDispatchLog(resolved_store.db_path)
        if isinstance(resolved_store, SqliteTaskContractStore)
        else JsonlDeliveryDispatchLog(runtime_root)
    )
    mission_required_delivery_channel_resolver = MissionRequiredDeliveryChannelResolver(
        mission_loader,
        dispatch_log,
    )
    failure_signal_recorder = LearningTaskContractFailureSignalRecorder(
        SqliteLearningStore(runtime_root / "learning.db")
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
        mission_required_artifact_resolver=mission_required_artifact_resolver,
        mission_required_delivery_channel_resolver=mission_required_delivery_channel_resolver,
        create=CreateTaskContractUseCase(resolved_store, clock, ids, publisher),
        update=UpdateTaskContractUseCase(
            resolved_store,
            clock,
            publisher,
            mission_required_artifact_resolver,
            mission_required_delivery_channel_resolver,
            failure_signal_recorder,
        ),
        get=GetTaskContractUseCase(
            resolved_store,
            clock,
            publisher,
            mission_required_artifact_resolver,
            mission_required_delivery_channel_resolver,
        ),
        list_contracts=ListTaskContractsUseCase(resolved_store, clock, publisher),
        add_assumption=AddAssumptionUseCase(resolved_store, clock, ids, publisher),
        verify_assumption=VerifyAssumptionUseCase(resolved_store, clock, publisher),
        close=CloseTaskContractUseCase(
            resolved_store,
            clock,
            publisher,
            mission_required_artifact_resolver,
            mission_required_delivery_channel_resolver,
        ),
        record_review_verdict=RecordReviewVerdictUseCase(resolved_store, clock, ids, publisher),
        build_delivery_pack=BuildDeliveryPackUseCase(
            resolved_store,
            clock,
            ids,
            publisher,
            mission_required_delivery_channel_resolver,
        ),
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
