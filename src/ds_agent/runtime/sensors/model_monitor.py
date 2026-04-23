"""Monitor recent experiment quality and emit degraded-model alerts."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from ds_agent.memory.experiment_log import ExperimentLog
from ds_agent.runtime.sensor_hub import SensorEvent, SensorHub

_BOUNDED_SCORE_METRICS = frozenset({"accuracy", "f1", "precision", "recall", "roc_auc", "r2"})


class ModelMonitorSensor:
    """Poll experiment logs and emit alerts for degraded bounded-score metrics."""

    def __init__(
        self,
        *,
        sensor_hub: SensorHub,
        experiment_log: ExperimentLog,
        poll_interval_seconds: float = 45.0,
        surface: str = "daemon",
        degradation_threshold: float = 0.6,
    ) -> None:
        self._hub = sensor_hub
        self._experiment_log = experiment_log
        self._poll_interval_seconds = poll_interval_seconds
        self._surface = surface
        self._degradation_threshold = degradation_threshold
        self._seen_experiment_ids: set[str] = set()
        self._task: asyncio.Task[None] | None = None

    def poll_once(self) -> list[SensorEvent]:
        """Emit alerts for newly observed degraded experiment results."""
        events: list[SensorEvent] = []
        experiments = self._experiment_log.get_experiments(limit=20)
        for experiment in experiments:
            exp_id = str(experiment.get("id", ""))
            if not exp_id or exp_id in self._seen_experiment_ids:
                continue
            self._seen_experiment_ids.add(exp_id)
            metrics = experiment.get("metrics", {})
            if not isinstance(metrics, dict):
                continue
            metric_name, metric_value = _find_degraded_metric(metrics, self._degradation_threshold)
            if metric_name is None:
                continue
            events.append(
                self._hub.publish(
                    sensor="model_monitor",
                    kind="model.monitor.degraded",
                    session_id=str(experiment.get("project_id", "autonomous:model-monitor")),
                    surface=self._surface,
                    message=(
                        f"Experiment {exp_id} has degraded {metric_name}={metric_value:.3f} "
                        f"for model {experiment.get('model_type', 'unknown')}."
                    ),
                    metadata={
                        "experimentId": exp_id,
                        "metricName": metric_name,
                        "metricValue": metric_value,
                        "modelType": str(experiment.get("model_type", "unknown")),
                    },
                )
            )
        return events

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop(), name="sensor:model_monitor")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._poll_interval_seconds)
            self.poll_once()


def _find_degraded_metric(
    metrics: dict[object, object],
    threshold: float,
) -> tuple[str | None, float]:
    for raw_name, raw_value in metrics.items():
        name = str(raw_name).lower()
        if name not in _BOUNDED_SCORE_METRICS:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if value < threshold:
            return name, value
    return None, 0.0
