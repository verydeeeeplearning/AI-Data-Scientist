"""File-backed session goal store."""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

from ds_agent.domain.entities.goal import GoalRecord, GoalStatus
from ds_agent.runtime.channel_identity import telegram_legacy_session_id
from ds_agent.runtime.transcript_store import (
    _SESSION_ID_SAFE_CHARS,
    get_runtime_storage_root,
)


class JsonGoalStore:
    """Persist session goals as per-session JSON files."""

    _ACTIVE_STATUSES = frozenset(
        {GoalStatus.PENDING.value, GoalStatus.IN_PROGRESS.value, GoalStatus.BLOCKED.value}
    )

    def __init__(
        self,
        workspace_dir: str | None = None,
        base_dir: str | Path | None = None,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._dir = root / "goals"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def get_active_goal(self, session_id: str) -> GoalRecord | None:
        """Return the current active goal for a session."""
        data = self._load_session(session_id)
        active_goal_id = data.get("active_goal_id")
        if not isinstance(active_goal_id, str):
            return None

        for goal_data in data.get("goals", []):
            if isinstance(goal_data, dict) and goal_data.get("goal_id") == active_goal_id:
                return self._deserialize_goal(goal_data)
        return None

    def list_goals(self, session_id: str) -> list[GoalRecord]:
        """List all goals for a session."""
        data = self._load_session(session_id)
        goals: list[GoalRecord] = []
        for item in data.get("goals", []):
            if isinstance(item, dict):
                goals.append(self._deserialize_goal(item))
        return goals

    def ensure_from_message(
        self,
        session_id: str,
        message: str,
        run_id: str | None = None,
    ) -> GoalRecord:
        """Create a goal for the session if none is active, else reuse the active one."""
        with self._lock:
            data = self._load_session(session_id)
            active = self._find_active_goal(data)
            if active is not None:
                if run_id is not None:
                    active.last_run_id = run_id
                active.updated_at = time.time()
                self._replace_goal(data, active)
                self._save_session(session_id, data)
                return active

            now = time.time()
            goal = GoalRecord(
                goal_id=uuid.uuid4().hex[:12],
                session_id=session_id,
                summary=_summarize_text(message, limit=120),
                detail=message.strip(),
                status=GoalStatus.PENDING,
                created_at=now,
                updated_at=now,
                last_run_id=run_id,
            )
            goals = list(data.get("goals", []))
            goals.append(self._serialize_goal(goal))
            data["goals"] = goals
            data["active_goal_id"] = goal.goal_id
            data["updated_at"] = now
            self._save_session(session_id, data)
            return goal

    def mark_status(
        self,
        session_id: str,
        goal_id: str,
        status: GoalStatus,
        *,
        run_id: str | None = None,
        note: str | None = None,
        blocked_reason: str | None = None,
    ) -> GoalRecord | None:
        """Update goal lifecycle state and persist the change."""
        with self._lock:
            data = self._load_session(session_id)
            goals = [
                self._deserialize_goal(item)
                for item in data.get("goals", [])
                if isinstance(item, dict)
            ]
            target = next((goal for goal in goals if goal.goal_id == goal_id), None)
            if target is None:
                return None

            now = time.time()
            target.status = status
            target.updated_at = now
            if run_id is not None:
                target.last_run_id = run_id
            if note:
                if note not in target.notes:
                    target.notes.append(note)
                target.notes = target.notes[-5:]
            if status == GoalStatus.BLOCKED:
                target.blocked_reason = blocked_reason
            elif blocked_reason is None:
                target.blocked_reason = None
            if status == GoalStatus.COMPLETED:
                target.completed_at = now
            if status in {GoalStatus.COMPLETED, GoalStatus.CANCELLED}:
                if data.get("active_goal_id") == goal_id:
                    data["active_goal_id"] = None
            else:
                data["active_goal_id"] = goal_id

            data["goals"] = [self._serialize_goal(goal) for goal in goals]
            data["updated_at"] = now
            self._save_session(session_id, data)
            return target

    def _load_session(self, session_id: str) -> dict[str, object]:
        path = self._session_file(session_id)
        data = self._read_session(path)
        if data is not None:
            return data
        if not path.exists():
            legacy_session_id = telegram_legacy_session_id(session_id)
            if legacy_session_id is not None:
                legacy = self._read_session(self._session_file(legacy_session_id))
                if legacy is not None:
                    return legacy
        return {"session_id": session_id, "active_goal_id": None, "goals": []}

    def _save_session(self, session_id: str, data: dict[str, object]) -> None:
        path = self._session_file(session_id)
        payload = {
            "session_id": session_id,
            "active_goal_id": data.get("active_goal_id"),
            "updated_at": time.time(),
            "goals": data.get("goals", []),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _find_active_goal(self, data: dict[str, object]) -> GoalRecord | None:
        active_goal_id = data.get("active_goal_id")
        goals = data.get("goals", [])
        if not isinstance(active_goal_id, str) or not isinstance(goals, list):
            return None

        for goal_data in goals:
            if not isinstance(goal_data, dict):
                continue
            if goal_data.get("goal_id") != active_goal_id:
                continue
            status = str(goal_data.get("status", GoalStatus.PENDING.value))
            if status not in self._ACTIVE_STATUSES:
                return None
            return self._deserialize_goal(goal_data)
        return None

    @staticmethod
    def _replace_goal(data: dict[str, object], goal: GoalRecord) -> None:
        goals = data.get("goals", [])
        if not isinstance(goals, list):
            goals = []
        serialized = JsonGoalStore._serialize_goal(goal)
        for index, item in enumerate(goals):
            if isinstance(item, dict) and item.get("goal_id") == goal.goal_id:
                goals[index] = serialized
                break
        data["goals"] = goals

    def _session_file(self, session_id: str) -> Path:
        safe_id = _SESSION_ID_SAFE_CHARS.sub("_", session_id).strip("._-") or "session"
        return self._dir / f"{safe_id}.goals.json"

    @staticmethod
    def _read_session(path: Path) -> dict[str, object] | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return dict(data) if isinstance(data, dict) else None

    @staticmethod
    def _serialize_goal(goal: GoalRecord) -> dict[str, object]:
        return {
            "goal_id": goal.goal_id,
            "session_id": goal.session_id,
            "summary": goal.summary,
            "detail": goal.detail,
            "status": goal.status.value,
            "created_at": goal.created_at,
            "updated_at": goal.updated_at,
            "last_run_id": goal.last_run_id,
            "blocked_reason": goal.blocked_reason,
            "completed_at": goal.completed_at,
            "notes": list(goal.notes),
        }

    @staticmethod
    def _deserialize_goal(data: dict[str, object]) -> GoalRecord:
        return GoalRecord(
            goal_id=str(data.get("goal_id", "")),
            session_id=str(data.get("session_id", "")),
            summary=str(data.get("summary", "")),
            detail=str(data.get("detail", "")),
            status=GoalStatus(str(data.get("status", GoalStatus.PENDING.value))),
            created_at=float(data.get("created_at", 0.0)),
            updated_at=float(data.get("updated_at", 0.0)),
            last_run_id=(str(data["last_run_id"]) if data.get("last_run_id") is not None else None),
            blocked_reason=(
                str(data["blocked_reason"]) if data.get("blocked_reason") is not None else None
            ),
            completed_at=(
                float(data["completed_at"]) if data.get("completed_at") is not None else None
            ),
            notes=[str(item) for item in data.get("notes", []) if isinstance(item, str)],
        )


def _summarize_text(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."
