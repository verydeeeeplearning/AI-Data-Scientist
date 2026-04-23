"""Background task manager for long-running autonomous work."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol

from ds_agent.domain.entities.session_checkpoint import SessionCheckpoint

BackgroundTaskStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
BackgroundTaskRunner = Callable[..., Awaitable[str]]
EmitEventFn = Callable[[str, dict[str, object]], None]


class BackgroundCheckpointStore(Protocol):
    """Checkpoint store subset used by the background task manager."""

    def load(self, session_id: str) -> SessionCheckpoint | None: ...


@dataclass(slots=True)
class BackgroundTaskRecord:
    """Tracked state for one background task."""

    task_id: str
    session_id: str
    prompt: str
    status: BackgroundTaskStatus = "pending"
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    checkpoint_step: int | None = None
    resumed_from_checkpoint: bool = False
    result_preview: str | None = None
    error: str | None = None


class BackgroundTaskManager:
    """Manage background task lifecycle and resume-on-checkpoint handoff."""

    def __init__(
        self,
        *,
        runner: BackgroundTaskRunner,
        checkpoint_store: BackgroundCheckpointStore | None = None,
        emit_event: EmitEventFn | None = None,
    ) -> None:
        self._runner = runner
        self._checkpoint_store = checkpoint_store
        self._emit_event = emit_event
        self._records: dict[str, BackgroundTaskRecord] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def start(
        self,
        *,
        session_id: str,
        prompt: str,
        resume_from_checkpoint: bool = False,
    ) -> BackgroundTaskRecord:
        """Start one background task and return its initial record."""
        task_id = uuid.uuid4().hex[:12]
        checkpoint = self._load_checkpoint(session_id) if resume_from_checkpoint else None
        record = BackgroundTaskRecord(
            task_id=task_id,
            session_id=session_id,
            prompt=prompt,
            checkpoint_step=None if checkpoint is None else checkpoint.step,
            resumed_from_checkpoint=checkpoint is not None,
        )
        self._records[task_id] = record
        task = asyncio.create_task(
            self._run(record, checkpoint=checkpoint),
            name=f"background-task:{task_id}",
        )
        self._tasks[task_id] = task
        return record

    def get(self, task_id: str) -> BackgroundTaskRecord | None:
        """Return one tracked background-task record."""
        return self._records.get(task_id)

    async def wait(
        self,
        task_id: str,
        *,
        timeout_seconds: float | None = None,
    ) -> BackgroundTaskRecord:
        """Wait until one tracked background task reaches a terminal state."""
        task = self._tasks.get(task_id)
        record = self._records.get(task_id)
        if task is None or record is None:
            raise ValueError(f"Unknown background task: {task_id}")
        if timeout_seconds is None:
            await asyncio.shield(task)
        else:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout_seconds)
        return record

    def cancel(self, task_id: str) -> bool:
        """Cancel one running background task."""
        task = self._tasks.get(task_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def _run(
        self,
        record: BackgroundTaskRecord,
        *,
        checkpoint: SessionCheckpoint | None,
    ) -> None:
        record.status = "running"
        record.started_at = time.time()
        self._emit(
            "task.started",
            {
                "taskId": record.task_id,
                "sessionId": record.session_id,
                "checkpointStep": record.checkpoint_step,
                "resumedFromCheckpoint": record.resumed_from_checkpoint,
            },
        )

        try:
            result = await self._runner(
                record.session_id,
                record.prompt,
                resume_from_checkpoint=checkpoint,
            )
            record.status = "completed"
            record.result_preview = result[:500]
            self._emit(
                "task.completed",
                {
                    "taskId": record.task_id,
                    "sessionId": record.session_id,
                    "checkpointStep": record.checkpoint_step,
                    "resumedFromCheckpoint": record.resumed_from_checkpoint,
                },
            )
        except asyncio.CancelledError:
            record.status = "cancelled"
            self._emit(
                "task.cancelled",
                {
                    "taskId": record.task_id,
                    "sessionId": record.session_id,
                },
            )
            raise
        except Exception as exc:
            record.status = "failed"
            record.error = str(exc)
            self._emit(
                "task.failed",
                {
                    "taskId": record.task_id,
                    "sessionId": record.session_id,
                    "error": str(exc),
                },
            )
        finally:
            record.finished_at = time.time()

    def _load_checkpoint(self, session_id: str) -> SessionCheckpoint | None:
        if self._checkpoint_store is None:
            return None
        return self._checkpoint_store.load(session_id)

    def _emit(self, event: str, payload: dict[str, object]) -> None:
        if self._emit_event is None:
            return
        self._emit_event(event, payload)
