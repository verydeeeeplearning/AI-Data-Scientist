"""Support ports for Decision OS run-diff use cases."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from ds_agent.domain.entities.experiment import ExperimentRun

MetricDirectionLabel = Literal["higher_is_better", "lower_is_better", "neutral"]


@runtime_checkable
class ExperimentRunReader(Protocol):
    """Read structured experiment runs by identifier."""

    def get_run(self, run_id: str) -> ExperimentRun | None: ...


@runtime_checkable
class MetricDirectionResolver(Protocol):
    """Resolve whether higher or lower metric values are preferable."""

    def direction_for(self, metric_name: str) -> MetricDirectionLabel: ...
