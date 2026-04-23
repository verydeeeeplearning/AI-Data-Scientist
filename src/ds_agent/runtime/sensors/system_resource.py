"""Monitor runtime pressure and emit pressure/normal events."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress

from ds_agent.runtime.sensor_hub import SensorEvent, SensorHub

StatusProviderFn = Callable[[], dict[str, object]]


class SystemResourceSensor:
    """Monitor runtime queue pressure without external dependencies."""

    def __init__(
        self,
        *,
        sensor_hub: SensorHub,
        status_provider: StatusProviderFn,
        poll_interval_seconds: float = 10.0,
        surface: str = "daemon",
        backlog_threshold: int = 3,
        active_run_threshold: int = 2,
    ) -> None:
        self._hub = sensor_hub
        self._status_provider = status_provider
        self._poll_interval_seconds = poll_interval_seconds
        self._surface = surface
        self._backlog_threshold = backlog_threshold
        self._active_run_threshold = active_run_threshold
        self._pressure_active = False
        self._task: asyncio.Task[None] | None = None

    def poll_once(self) -> SensorEvent | None:
        """Emit a pressure change event when the pressure state flips."""
        status = self._status_provider()
        backlog = int(status.get("sensorBacklog", 0))
        active_runs = int(status.get("activeRuns", 0))
        pressure = backlog >= self._backlog_threshold or active_runs >= self._active_run_threshold

        if pressure == self._pressure_active:
            return None

        self._pressure_active = pressure
        kind = "system.resource.pressure" if pressure else "system.resource.normal"
        message = (
            f"Runtime pressure changed: activeRuns={active_runs}, sensorBacklog={backlog}."
        )
        return self._hub.publish(
            sensor="system_resource",
            kind=kind,
            session_id="autonomous:system",
            surface=self._surface,
            message=message,
            metadata={"activeRuns": active_runs, "sensorBacklog": backlog},
        )

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop(), name="sensor:system_resource")

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
