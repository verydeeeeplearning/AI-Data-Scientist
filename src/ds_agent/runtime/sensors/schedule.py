"""Periodic schedule sensor for low-frequency autonomy wake-ups."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress

from ds_agent.runtime.sensor_hub import SensorEvent, SensorHub


class ScheduleSensor:
    """Emit periodic schedule tick events."""

    def __init__(
        self,
        *,
        sensor_hub: SensorHub,
        interval_seconds: float = 300.0,
        session_id: str = "autonomous:schedule",
        surface: str = "daemon",
        dispatch: bool = False,
        on_tick: Callable[[SensorEvent], object | None] | None = None,
    ) -> None:
        self._hub = sensor_hub
        self._interval_seconds = interval_seconds
        self._session_id = session_id
        self._surface = surface
        self._dispatch = dispatch
        self._on_tick = on_tick
        self._task: asyncio.Task[None] | None = None

    def emit_tick(self) -> SensorEvent:
        """Publish one schedule tick immediately."""
        event = self._hub.publish(
            sensor="schedule",
            kind="schedule.tick",
            session_id=self._session_id,
            surface=self._surface,
            message="Periodic autonomous runtime check",
            metadata={"dispatch": self._dispatch},
        )
        if self._on_tick is not None:
            self._on_tick(event)
        return event

    async def start(self) -> None:
        """Start background schedule ticks if not already running."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop(), name="sensor:schedule")

    async def stop(self) -> None:
        """Stop background schedule ticks."""
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
            await asyncio.sleep(self._interval_seconds)
            self.emit_tick()
