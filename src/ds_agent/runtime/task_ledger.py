"""Background asyncio task ledger for tracked runs."""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ds_agent.domain.entities.runtime_state import RuntimeStatus, TaskState
from ds_agent.runtime.transcript_store import get_runtime_storage_root


@dataclass(slots=True)
class _TaskRecord:
    task: asyncio.Task[Any] | None
    state: TaskState


class TaskLedger:
    """Tracks background asyncio tasks behind runtime runs."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        *,
        base_dir: str | Path | None = None,
    ) -> None:
        self._records: dict[str, _TaskRecord] = {}
        self._run_to_task: dict[str, str] = {}
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._file = root / "runtime-tasks.json"
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._lock:
            self._records, self._run_to_task = self._load_unlocked()

    def register(self, run_id: str, task: asyncio.Task[Any]) -> TaskState:
        """Register one task and return its task-state record."""
        task_id = uuid.uuid4().hex[:12]
        state = TaskState(task_id=task_id, run_id=run_id)
        with self._lock:
            self._records[task_id] = _TaskRecord(task=task, state=state)
            self._run_to_task[run_id] = task_id
            self._save_unlocked()
        task.add_done_callback(lambda _: self._finalize(task_id))
        return state

    def get_state(self, task_id: str) -> TaskState | None:
        """Return tracked task state."""
        with self._lock:
            record = self._records.get(task_id)
            if record is None:
                return None
            return record.state

    def get_state_for_run(self, run_id: str) -> TaskState | None:
        """Return the task-state record for a run."""
        with self._lock:
            task_id = self._run_to_task.get(run_id)
            if task_id is None:
                return None
            record = self._records.get(task_id)
            return None if record is None else record.state

    def get_task_for_run(self, run_id: str) -> asyncio.Task[Any] | None:
        """Return the raw asyncio task for a run."""
        with self._lock:
            task_id = self._run_to_task.get(run_id)
            if task_id is None:
                return None
            record = self._records.get(task_id)
            return None if record is None else record.task

    def list(
        self,
        *,
        run_id: str | None = None,
        status: RuntimeStatus | None = None,
        limit: int = 20,
    ) -> list[TaskState]:
        """List tracked task states ordered by creation time."""
        with self._lock:
            states = [record.state for record in self._records.values()]
        if run_id is not None:
            states = [state for state in states if state.run_id == run_id]
        if status is not None:
            states = [state for state in states if state.status == status]
        states.sort(key=lambda item: item.created_at, reverse=True)
        return states[:limit]

    def cancel_for_run(self, run_id: str) -> bool:
        """Cancel the task backing a run, if still active."""
        task = self.get_task_for_run(run_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def wait_for_run(
        self,
        run_id: str,
        timeout_seconds: float | None = None,
    ) -> TaskState | None:
        """Wait for the task behind a run, optionally with a timeout."""
        task = self.get_task_for_run(run_id)
        if task is None:
            return self.get_state_for_run(run_id)

        try:
            if timeout_seconds is None:
                await asyncio.shield(task)
            else:
                await asyncio.wait_for(asyncio.shield(task), timeout=timeout_seconds)
        except TimeoutError:
            pass
        except asyncio.CancelledError:
            pass

        return self.get_state_for_run(run_id)

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(
                1
                for record in self._records.values()
                if record.task is not None and not record.task.done()
            )

    def _finalize(self, task_id: str) -> None:
        """Project final asyncio-task state into the task ledger."""
        with self._lock:
            record = self._records.get(task_id)
            if record is None:
                return

            state = record.state
            if state.finished_at is not None or record.task is None:
                return

            state.finished_at = time.time()
            if record.task.cancelled():
                state.status = RuntimeStatus.CANCELLED
                record.task = None
                self._save_unlocked()
                return

            try:
                exc = record.task.exception()
            except asyncio.CancelledError:
                state.status = RuntimeStatus.CANCELLED
                record.task = None
                self._save_unlocked()
                return

            if exc is not None:
                state.status = RuntimeStatus.FAILED
                state.error = str(exc)
                record.task = None
                self._save_unlocked()
                return

            state.status = RuntimeStatus.SUCCEEDED
            record.task = None
            self._save_unlocked()

    def _load_unlocked(self) -> tuple[dict[str, _TaskRecord], dict[str, str]]:
        if not self._file.exists():
            return {}, {}
        try:
            payload = json.loads(self._file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}, {}
        if not isinstance(payload, dict):
            return {}, {}
        raw_tasks = payload.get("tasks", [])
        if not isinstance(raw_tasks, list):
            return {}, {}

        records: dict[str, _TaskRecord] = {}
        run_to_task: dict[str, str] = {}
        sorted_tasks = sorted(
            (item for item in raw_tasks if isinstance(item, dict)),
            key=lambda item: float(item.get("created_at", 0.0)),
            reverse=True,
        )
        for item in sorted_tasks:
            state = self._deserialize_state(item)
            records[state.task_id] = _TaskRecord(task=None, state=state)
            run_to_task.setdefault(state.run_id, state.task_id)
        return records, run_to_task

    def _save_unlocked(self) -> None:
        payload = {
            "tasks": [
                self._serialize_state(record.state)
                for record in sorted(
                    self._records.values(),
                    key=lambda item: item.state.created_at,
                    reverse=True,
                )
            ]
        }
        self._file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _serialize_state(state: TaskState) -> dict[str, object]:
        return {
            "task_id": state.task_id,
            "run_id": state.run_id,
            "status": state.status.value,
            "created_at": state.created_at,
            "started_at": state.started_at,
            "finished_at": state.finished_at,
            "error": state.error,
        }

    @staticmethod
    def _deserialize_state(payload: dict[str, object]) -> TaskState:
        return TaskState(
            task_id=str(payload.get("task_id", "")),
            run_id=str(payload.get("run_id", "")),
            status=RuntimeStatus(str(payload.get("status", RuntimeStatus.RUNNING.value))),
            created_at=float(payload.get("created_at", time.time())),
            started_at=float(payload.get("started_at", time.time())),
            finished_at=(
                float(payload["finished_at"]) if payload.get("finished_at") is not None else None
            ),
            error=str(payload["error"]) if payload.get("error") is not None else None,
        )
