"""Polling file-watch sensor for autonomous inbox processing."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path

from ds_agent.runtime.sensor_hub import SensorEvent, SensorHub

_IGNORED_DIR_NAMES = frozenset(
    {
        ".git",
        ".idea",
        ".pytest_cache",
        ".venv",
        "__pycache__",
        "node_modules",
    }
)


class FileWatchSensor:
    """Poll a watch directory and publish file creation/update events."""

    def __init__(
        self,
        *,
        watch_dir: str | Path,
        sensor_hub: SensorHub,
        poll_interval_seconds: float = 2.0,
        session_id: str = "autonomous:inbox",
        surface: str = "daemon",
    ) -> None:
        self._watch_dir = Path(watch_dir).expanduser().resolve()
        self._watch_dir.mkdir(parents=True, exist_ok=True)
        self._hub = sensor_hub
        self._poll_interval_seconds = poll_interval_seconds
        self._session_id = session_id
        self._surface = surface
        self._snapshot: dict[str, int] = {}
        self._task: asyncio.Task[None] | None = None

    def prime(self) -> None:
        """Take an initial snapshot without emitting events."""
        self._snapshot = self._scan()

    def poll_once(self) -> list[SensorEvent]:
        """Detect changes since the last snapshot and publish events."""
        current = self._scan()
        events: list[SensorEvent] = []

        for rel_path, mtime_ns in current.items():
            previous = self._snapshot.get(rel_path)
            if previous is None:
                kind = "file.created"
                verb = "created"
            elif previous != mtime_ns:
                kind = "file.updated"
                verb = "updated"
            else:
                continue

            events.append(
                self._hub.publish(
                    sensor="file_watch",
                    kind=kind,
                    session_id=self._session_id,
                    surface=self._surface,
                    message=f"Autonomous inbox file {verb}: {rel_path}",
                    metadata={"path": rel_path},
                )
            )

        self._snapshot = current
        return events

    async def start(self) -> None:
        """Start background polling if it is not already running."""
        if self._task is not None:
            return
        self.prime()
        self._task = asyncio.create_task(self._loop(), name="sensor:file_watch")

    async def stop(self) -> None:
        """Stop background polling."""
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

    def _scan(self) -> dict[str, int]:
        snapshot: dict[str, int] = {}
        if not self._watch_dir.exists():
            return snapshot

        for path in self._watch_dir.rglob("*"):
            if not path.is_file():
                continue
            rel_parts = path.relative_to(self._watch_dir).parts
            if any(part in _IGNORED_DIR_NAMES for part in rel_parts):
                continue
            try:
                snapshot[path.relative_to(self._watch_dir).as_posix()] = path.stat().st_mtime_ns
            except OSError:
                continue
        return snapshot
