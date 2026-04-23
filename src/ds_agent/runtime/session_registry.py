"""Runtime session registry shared by gateway surfaces."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from ds_agent.domain.entities.runtime_state import RuntimeSession
from ds_agent.runtime.transcript_store import get_runtime_storage_root


class RuntimeSessionRegistry:
    """Registry for runtime-visible session metadata, optionally persisted to disk."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        *,
        base_dir: str | Path | None = None,
    ) -> None:
        self._sessions: dict[str, RuntimeSession] = {}
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._file = root / "runtime-sessions.json"
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._lock:
            self._sessions = self._load_unlocked()

    def ensure(self, session_id: str, surface: str) -> RuntimeSession:
        """Create or refresh a runtime session."""
        now = time.time()
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = RuntimeSession(
                    session_id=session_id,
                    surface=surface,
                    created_at=now,
                    last_active=now,
                )
                self._sessions[session_id] = session
                self._save_unlocked()
                return session

            session.surface = surface
            session.last_active = now
            self._save_unlocked()
            return session

    def bind_run(self, session_id: str, run_id: str, surface: str) -> RuntimeSession:
        """Associate the latest run with a session."""
        with self._lock:
            now = time.time()
            session = self._sessions.get(session_id)
            if session is None:
                session = RuntimeSession(
                    session_id=session_id,
                    surface=surface,
                    created_at=now,
                    last_active=now,
                    last_run_id=run_id,
                )
                self._sessions[session_id] = session
            else:
                session.surface = surface
                session.last_active = now
                session.last_run_id = run_id
            self._save_unlocked()
            return session

    def get(self, session_id: str) -> RuntimeSession | None:
        """Return session metadata if present."""
        with self._lock:
            return self._sessions.get(session_id)

    def list(self, limit: int | None = None) -> list[RuntimeSession]:
        """List sessions ordered by most recent activity."""
        with self._lock:
            sessions = sorted(
                self._sessions.values(),
                key=lambda item: item.last_active,
                reverse=True,
            )
        if limit is None:
            return sessions
        return sessions[:limit]

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def _load_unlocked(self) -> dict[str, RuntimeSession]:
        if not self._file.exists():
            return {}
        try:
            payload = json.loads(self._file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(payload, dict):
            return {}
        raw_sessions = payload.get("sessions", [])
        if not isinstance(raw_sessions, list):
            return {}
        sessions: dict[str, RuntimeSession] = {}
        for item in raw_sessions:
            if not isinstance(item, dict):
                continue
            session = self._deserialize_session(item)
            sessions[session.session_id] = session
        return sessions

    def _save_unlocked(self) -> None:
        payload = {
            "sessions": [
                self._serialize_session(session)
                for session in sorted(
                    self._sessions.values(),
                    key=lambda item: item.last_active,
                    reverse=True,
                )
            ]
        }
        self._file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _serialize_session(session: RuntimeSession) -> dict[str, object]:
        return {
            "session_id": session.session_id,
            "surface": session.surface,
            "created_at": session.created_at,
            "last_active": session.last_active,
            "last_run_id": session.last_run_id,
        }

    @staticmethod
    def _deserialize_session(payload: dict[str, object]) -> RuntimeSession:
        return RuntimeSession(
            session_id=str(payload.get("session_id", "")),
            surface=str(payload.get("surface", "ws")),
            created_at=float(payload.get("created_at", time.time())),
            last_active=float(payload.get("last_active", time.time())),
            last_run_id=(
                str(payload["last_run_id"]) if payload.get("last_run_id") is not None else None
            ),
        )
