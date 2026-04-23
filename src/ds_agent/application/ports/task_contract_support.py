"""Support ports for task contract use cases."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ds_agent.application.dtos.delivery import (
    DeliveryLogQueryResult,
    DeliveryLogSummary,
    DispatchDeliveryResult,
    RenderedArtifact,
)
from ds_agent.domain.entities.delivery_pack import DeliveryChannel, DeliveryPack
from ds_agent.domain.entities.task_contract_event import TaskContractEvent
from ds_agent.domain.value_objects.audience_persona import AudiencePersona


@runtime_checkable
class Clock(Protocol):
    """Abstraction over wall-clock time for deterministic testing."""

    def now(self) -> datetime: ...


@runtime_checkable
class IdGenerator(Protocol):
    """Artifact identifier generation."""

    def new_task_id(self, now: datetime) -> str: ...

    def new_artifact_id(self, prefix: str) -> str: ...


@runtime_checkable
class EventPublisher(Protocol):
    """Publishes task contract domain events."""

    def publish(self, event: TaskContractEvent) -> None: ...


@runtime_checkable
class DeliveryArtifactRenderer(Protocol):
    """Renders one DeliveryPack artifact to a concrete file."""

    def render(
        self,
        *,
        analysis: Mapping[str, Any] | str,
        output_dir: Path,
        pack: DeliveryPack,
        artifact_id: str,
        audience_profile: AudiencePersona | None = None,
    ) -> RenderedArtifact: ...


@runtime_checkable
class DeliveryArtifactDispatcher(Protocol):
    """Dispatches one or more rendered artifacts through channel adapters."""

    def dispatch(
        self,
        *,
        pack: DeliveryPack,
        artifact_ids: set[str] | None = None,
        channels: set[DeliveryChannel] | None = None,
        dry_run: bool = False,
        approve_manual_review: bool = False,
    ) -> DispatchDeliveryResult: ...


@runtime_checkable
class DeliveryDispatchLogReader(Protocol):
    """Reads persisted dispatch-log records for stakeholder delivery."""

    def query(
        self,
        *,
        task_id: str,
        pack_id: str | None = None,
        artifact_ids: set[str] | None = None,
        channels: set[DeliveryChannel] | None = None,
        limit: int = 50,
    ) -> DeliveryLogQueryResult: ...

    def summarize(self, *, pack: DeliveryPack) -> DeliveryLogSummary: ...


@runtime_checkable
class TaskContractFailureSignalRecorder(Protocol):
    """Projects task-contract gate failures into governed learning signals."""

    def record_transition_failure(
        self,
        *,
        task_id: str,
        session_id: str | None,
        run_id: str | None,
        transition_to: str | None,
        error_code: str,
        message: str,
        metadata: Mapping[str, object] | None = None,
    ) -> None: ...

    def record_operator_intervention(
        self,
        *,
        task_id: str,
        session_id: str | None,
        run_id: str | None,
        intervention_kind: str,
        reason: str | None,
        metadata: Mapping[str, object] | None = None,
    ) -> None: ...
