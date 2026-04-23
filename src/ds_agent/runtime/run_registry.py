"""Runtime registry for tracked agent runs."""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

from ds_agent.domain.entities.runtime_state import RunState, RuntimeStatus
from ds_agent.runtime.session_registry import RuntimeSessionRegistry
from ds_agent.runtime.transcript_store import get_runtime_storage_root

_MAX_PREVIEW_LENGTH = 500


class RunRegistry:
    """Tracks run lifecycle independent of the transport surface."""

    def __init__(
        self,
        sessions: RuntimeSessionRegistry,
        workspace_dir: str | None = None,
        *,
        base_dir: str | Path | None = None,
    ) -> None:
        self._sessions = sessions
        self._runs: dict[str, RunState] = {}
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._file = root / "runtime-runs.json"
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._lock:
            self._runs = self._load_unlocked()

    def create(
        self,
        session_id: str,
        surface: str,
        message: str,
        *,
        parent_run_id: str | None = None,
    ) -> RunState:
        """Create a new running record for one agent turn.

        ``parent_run_id``, when set, is recorded on the new ``RunState`` as
        ``branched_from_run_id`` so downstream consumers (UI lineage, scorecards,
        etc.) can render the branch graph without a separate lookup table.
        """
        now = time.time()
        run = RunState(
            run_id=uuid.uuid4().hex[:12],
            session_id=session_id,
            surface=surface,
            message=message[:_MAX_PREVIEW_LENGTH],
            status=RuntimeStatus.RUNNING,
            created_at=now,
            started_at=now,
            branched_from_run_id=parent_run_id,
        )
        with self._lock:
            self._runs[run.run_id] = run
            self._save_unlocked()
        self._sessions.bind_run(session_id, run.run_id, surface)
        return run

    def attach_task(self, run_id: str, task_id: str) -> RunState | None:
        """Bind an asyncio task record to a run."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            run.task_id = task_id
            self._save_unlocked()
            return run

    def mark_succeeded(self, run_id: str, result: str, cost_usd: float = 0.0) -> RunState | None:
        """Mark a run as successful."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            run.status = RuntimeStatus.SUCCEEDED
            run.finished_at = time.time()
            run.result_preview = result[:_MAX_PREVIEW_LENGTH]
            run.cost_usd = cost_usd
            run.error = None
            self._save_unlocked()
            return run

    def mark_failed(self, run_id: str, error: str) -> RunState | None:
        """Mark a run as failed."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            run.status = RuntimeStatus.FAILED
            run.finished_at = time.time()
            run.error = error[:_MAX_PREVIEW_LENGTH]
            self._save_unlocked()
            return run

    def mark_cancelled(self, run_id: str) -> RunState | None:
        """Mark a run as cancelled."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            run.status = RuntimeStatus.CANCELLED
            run.finished_at = time.time()
            run.error = None
            self._save_unlocked()
            return run

    def get(self, run_id: str) -> RunState | None:
        """Return one run record by id."""
        with self._lock:
            return self._runs.get(run_id)

    def latest_for_session(
        self,
        session_id: str,
        *,
        statuses: set[RuntimeStatus] | None = None,
    ) -> RunState | None:
        """Return the most recent run for a session, optionally filtered by status."""
        with self._lock:
            matches = [
                run
                for run in self._runs.values()
                if run.session_id == session_id and (statuses is None or run.status in statuses)
            ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def list(
        self,
        *,
        session_id: str | None = None,
        status: RuntimeStatus | None = None,
        limit: int = 20,
    ) -> list[RunState]:
        """List runs ordered from newest to oldest."""
        with self._lock:
            runs = list(self._runs.values())
        if session_id is not None:
            runs = [run for run in runs if run.session_id == session_id]
        if status is not None:
            runs = [run for run in runs if run.status == status]
        runs.sort(key=lambda item: item.created_at, reverse=True)
        return runs[:limit]

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(1 for run in self._runs.values() if run.status == RuntimeStatus.RUNNING)

    def _load_unlocked(self) -> dict[str, RunState]:
        if not self._file.exists():
            return {}
        try:
            payload = json.loads(self._file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(payload, dict):
            return {}
        raw_runs = payload.get("runs", [])
        if not isinstance(raw_runs, list):
            return {}
        runs: dict[str, RunState] = {}
        for item in raw_runs:
            if not isinstance(item, dict):
                continue
            run = self._deserialize_run(item)
            runs[run.run_id] = run
        return runs

    def _save_unlocked(self) -> None:
        payload = {
            "runs": [
                self._serialize_run(run)
                for run in sorted(
                    self._runs.values(),
                    key=lambda item: item.created_at,
                    reverse=True,
                )
            ]
        }
        self._file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _serialize_run(run: RunState) -> dict[str, object]:
        return {
            "run_id": run.run_id,
            "session_id": run.session_id,
            "surface": run.surface,
            "message": run.message,
            "status": run.status.value,
            "created_at": run.created_at,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "task_id": run.task_id,
            "error": run.error,
            "result_preview": run.result_preview,
            "cost_usd": run.cost_usd,
            "branched_from_run_id": run.branched_from_run_id,
            "rerun_from_node_id": run.rerun_from_node_id,
        }

    @staticmethod
    def _deserialize_run(payload: dict[str, object]) -> RunState:
        return RunState(
            run_id=str(payload.get("run_id", "")),
            session_id=str(payload.get("session_id", "")),
            surface=str(payload.get("surface", "ws")),
            message=str(payload.get("message", "")),
            status=RuntimeStatus(str(payload.get("status", RuntimeStatus.RUNNING.value))),
            created_at=float(payload.get("created_at", time.time())),
            started_at=float(payload.get("started_at", time.time())),
            finished_at=(
                float(payload["finished_at"]) if payload.get("finished_at") is not None else None
            ),
            task_id=str(payload["task_id"]) if payload.get("task_id") is not None else None,
            error=str(payload["error"]) if payload.get("error") is not None else None,
            result_preview=(
                str(payload["result_preview"])
                if payload.get("result_preview") is not None
                else None
            ),
            cost_usd=float(payload.get("cost_usd", 0.0)),
            branched_from_run_id=(
                str(payload["branched_from_run_id"])
                if payload.get("branched_from_run_id") is not None
                else None
            ),
            rerun_from_node_id=(
                str(payload["rerun_from_node_id"])
                if payload.get("rerun_from_node_id") is not None
                else None
            ),
        )
