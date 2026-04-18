"""Support ports for Decision OS post-deploy monitoring."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from ds_agent.domain.entities.experiment import ExperimentRun
from ds_agent.domain.entities.model import Model
from ds_agent.domain.entities.post_deploy import (
    PostDeployMonitorState,
    PostDeploySnapshot,
    TriggerMode,
)


@runtime_checkable
class DeployMonitorStateStore(Protocol):
    """Persistence contract for post-deploy monitoring state."""

    def save(self, state: PostDeployMonitorState) -> None: ...

    def latest(self, model_id: str) -> PostDeployMonitorState | None: ...

    def list_states(
        self,
        *,
        model_id: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[PostDeployMonitorState]: ...


@runtime_checkable
class PostDeploySnapshotProvider(Protocol):
    """Load one monitoring snapshot for a deployed model."""

    def load(self, model_id: str, model_version: int) -> PostDeploySnapshot | None: ...


@runtime_checkable
class PostDeployAutomationPolicyResolver(Protocol):
    """Resolve automatic-trigger mode and schedule policy for post-deploy monitoring."""

    def mode_for(self, model_id: str, alias: str) -> TriggerMode: ...

    def schedule_cron(self) -> str: ...


@runtime_checkable
class AutoRetrainExecutor(Protocol):
    """Execute an automatic retrain request derived from one monitoring state."""

    def execute(
        self,
        model: Model,
        baseline_run: ExperimentRun,
        state: PostDeployMonitorState,
    ) -> dict[str, object]: ...


@runtime_checkable
class AutoRollbackExecutor(Protocol):
    """Execute an automatic rollback for one monitored model."""

    def execute(
        self,
        model: Model,
        state: PostDeployMonitorState,
    ) -> dict[str, object]: ...
