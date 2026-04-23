"""Async event hub for autonomous runtime sensors."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field


@dataclass(slots=True)
class SensorEvent:
    """One sensor-originated event consumed by the autonomous coordinator."""

    event_id: str
    sensor: str
    kind: str
    session_id: str
    surface: str
    message: str
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class SensorHub:
    """Shared async queue for autonomous runtime wake-up events."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[SensorEvent] = asyncio.Queue()

    def publish(
        self,
        *,
        sensor: str,
        kind: str,
        session_id: str,
        surface: str,
        message: str,
        metadata: dict[str, object] | None = None,
    ) -> SensorEvent:
        """Create and enqueue one sensor event."""
        event = SensorEvent(
            event_id=uuid.uuid4().hex[:12],
            sensor=sensor,
            kind=kind,
            session_id=session_id,
            surface=surface,
            message=message,
            metadata=dict(metadata or {}),
        )
        self._queue.put_nowait(event)
        return event

    async def next_event(self, timeout_seconds: float | None = None) -> SensorEvent | None:
        """Return the next pending event or ``None`` on timeout."""
        if timeout_seconds is None:
            return await self._queue.get()
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout_seconds)
        except TimeoutError:
            return None

    def task_done(self) -> None:
        """Mark one queued event as processed."""
        self._queue.task_done()

    @property
    def backlog(self) -> int:
        """Return the number of queued events."""
        return self._queue.qsize()
