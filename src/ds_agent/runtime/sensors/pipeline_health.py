"""Monitor recent runtime failures and emit pipeline health alerts."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress

from ds_agent.runtime.sensor_hub import SensorEvent, SensorHub

ListRunsFn = Callable[[], list[object]]


class PipelineHealthSensor:
    """Poll recent runs and emit degraded-health events for new failures."""

    def __init__(
        self,
        *,
        sensor_hub: SensorHub,
        list_recent_runs: ListRunsFn,
        poll_interval_seconds: float = 30.0,
        session_id: str = "autonomous:pipeline-health",
        surface: str = "daemon",
    ) -> None:
        self._hub = sensor_hub
        self._list_recent_runs = list_recent_runs
        self._poll_interval_seconds = poll_interval_seconds
        self._session_id = session_id
        self._surface = surface
        self._seen_failures: set[str] = set()
        self._task: asyncio.Task[None] | None = None

    def poll_once(self) -> list[SensorEvent]:
        """Check recent runs and emit events for unseen failures."""
        events: list[SensorEvent] = []
        for run in self._list_recent_runs():
            run_id = getattr(run, "run_id", "")
            status = getattr(getattr(run, "status", None), "value", "")
            if status not in {"failed", "cancelled"}:
                continue
            signature = f"{run_id}:{status}"
            if signature in self._seen_failures:
                continue
            self._seen_failures.add(signature)
            session_id = getattr(run, "session_id", self._session_id)
            message = f"Recent run {run_id or 'unknown'} ended with status {status}."
            events.append(
                self._hub.publish(
                    sensor="pipeline_health",
                    kind="pipeline.health.degraded",
                    session_id=session_id,
                    surface=self._surface,
                    message=message,
                    metadata={"runId": run_id, "status": status},
                )
            )
        return events

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop(), name="sensor:pipeline_health")

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
