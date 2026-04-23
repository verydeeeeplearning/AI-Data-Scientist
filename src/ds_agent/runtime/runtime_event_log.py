"""Operator-facing runtime event log with optional file-backed persistence."""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from ds_agent.runtime.transcript_store import get_runtime_storage_root

RuntimeSeverity = str


@dataclass(slots=True)
class RuntimeEventRecord:
    """One operator-visible runtime event for Electron and Telegram surfaces."""

    event_id: str
    category: str
    kind: str
    severity: RuntimeSeverity
    message: str
    session_id: str | None = None
    run_id: str | None = None
    surface: str = "daemon"
    source: str = "runtime"
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class RuntimeEventLog:
    """Keep a bounded runtime event log, optionally shared through disk."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        *,
        max_events: int = 200,
        base_dir: str | Path | None = None,
    ) -> None:
        self._max_events = max_events
        self._events: deque[RuntimeEventRecord] = deque(maxlen=max_events)
        self._lock = threading.Lock()
        root = Path(base_dir) if base_dir is not None else None
        if root is None and workspace_dir is not None:
            root = get_runtime_storage_root(workspace_dir)
        self._file_path = None if root is None else root / "runtime-events.jsonl"
        if self._file_path is not None:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        category: str,
        kind: str,
        severity: RuntimeSeverity,
        message: str,
        session_id: str | None = None,
        run_id: str | None = None,
        surface: str = "daemon",
        source: str = "runtime",
        metadata: dict[str, object] | None = None,
        created_at: float | None = None,
    ) -> RuntimeEventRecord:
        """Append one runtime event and return it."""
        event = RuntimeEventRecord(
            event_id=uuid.uuid4().hex[:12],
            category=category,
            kind=kind,
            severity=severity,
            message=message,
            session_id=session_id,
            run_id=run_id,
            surface=surface,
            source=source,
            metadata=dict(metadata or {}),
            created_at=time.time() if created_at is None else float(created_at),
        )
        with self._lock:
            self._events.append(event)
            self._append_to_disk_unlocked(event)
        return event

    def list(
        self,
        *,
        limit: int = 50,
        session_id: str | None = None,
        category: str | None = None,
    ) -> list[RuntimeEventRecord]:
        """Return recent events ordered newest first."""
        with self._lock:
            events = self._load_events_unlocked()

        filtered: list[RuntimeEventRecord] = []
        for event in reversed(events):
            if session_id and event.session_id != session_id:
                continue
            if category and event.category != category:
                continue
            filtered.append(event)
            if len(filtered) >= max(0, limit):
                break
        return filtered

    def get(self, event_id: str) -> RuntimeEventRecord | None:
        """Return one event by id, or ``None`` if absent."""
        with self._lock:
            events = self._load_events_unlocked()
        for event in reversed(events):
            if event.event_id == event_id:
                return event
        return None

    def _append_to_disk_unlocked(self, event: RuntimeEventRecord) -> None:
        if self._file_path is None:
            return

        payload = self._serialize_event(event)
        with self._file_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._trim_disk_unlocked()

    def _load_events_unlocked(self) -> list[RuntimeEventRecord]:
        if self._file_path is None or not self._file_path.exists():
            return list(self._events)

        events: list[RuntimeEventRecord] = []
        try:
            lines = self._file_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return list(self._events)

        for line in lines[-self._max_events :]:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            events.append(self._deserialize_event(payload))

        self._events = deque(events, maxlen=self._max_events)
        return list(self._events)

    def _trim_disk_unlocked(self) -> None:
        if self._file_path is None or not self._file_path.exists():
            return
        try:
            lines = self._file_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        if len(lines) <= self._max_events:
            return
        trimmed = lines[-self._max_events :]
        try:
            self._file_path.write_text(
                "\n".join(trimmed) + ("\n" if trimmed else ""),
                encoding="utf-8",
            )
        except OSError:
            return

    @staticmethod
    def _serialize_event(event: RuntimeEventRecord) -> dict[str, object]:
        return {
            "event_id": event.event_id,
            "category": event.category,
            "kind": event.kind,
            "severity": event.severity,
            "message": event.message,
            "session_id": event.session_id,
            "run_id": event.run_id,
            "surface": event.surface,
            "source": event.source,
            "metadata": dict(event.metadata),
            "created_at": event.created_at,
        }

    @staticmethod
    def _deserialize_event(payload: dict[str, object]) -> RuntimeEventRecord:
        metadata = payload.get("metadata")
        return RuntimeEventRecord(
            event_id=str(payload.get("event_id", "")),
            category=str(payload.get("category", "runtime")),
            kind=str(payload.get("kind", "")),
            severity=str(payload.get("severity", "info")),
            message=str(payload.get("message", "")),
            session_id=(
                str(payload["session_id"]) if payload.get("session_id") is not None else None
            ),
            run_id=str(payload["run_id"]) if payload.get("run_id") is not None else None,
            surface=str(payload.get("surface", "daemon")),
            source=str(payload.get("source", "runtime")),
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
            created_at=float(payload.get("created_at", 0.0)),
        )
