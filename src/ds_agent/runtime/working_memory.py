"""File-backed working memory store for session-level short-horizon context."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from ds_agent.domain.entities.working_memory import SessionWorkingMemory
from ds_agent.domain.value_objects.analysis_stage import AnalysisStage
from ds_agent.runtime.channel_identity import telegram_legacy_session_id
from ds_agent.runtime.transcript_store import (
    _SESSION_ID_SAFE_CHARS,
    get_runtime_storage_root,
)


class JsonWorkingMemoryStore:
    """Persist short-horizon working memory as per-session JSON files."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        base_dir: str | Path | None = None,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._dir = root / "working-memory"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def load(self, session_id: str) -> SessionWorkingMemory | None:
        """Load working memory for a session."""
        path = self._session_file(session_id)
        data = self._read_memory(path)
        if data is None and not path.exists():
            legacy_session_id = telegram_legacy_session_id(session_id)
            if legacy_session_id is not None:
                data = self._read_memory(self._session_file(legacy_session_id))
        if data is None:
            return None
        return self._deserialize_memory(session_id, data)

    def save(self, memory: SessionWorkingMemory) -> None:
        """Persist working memory for a session."""
        path = self._session_file(memory.session_id)
        payload = {
            "session_id": memory.session_id,
            "active_goal_id": memory.active_goal_id,
            "last_run_id": memory.last_run_id,
            "last_user_message": memory.last_user_message,
            "current_summary": memory.current_summary,
            "next_step": memory.next_step,
            "pending_questions": list(memory.pending_questions),
            "last_reflection": memory.last_reflection,
            "recovery_note": memory.recovery_note,
            "current_stage": (
                None if memory.current_stage is None else memory.current_stage.value
            ),
            "stage_entered_at": memory.stage_entered_at,
            "updated_at": memory.updated_at,
            "pending_verifier_remediation": memory.pending_verifier_remediation,
        }
        with self._lock:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _session_file(self, session_id: str) -> Path:
        safe_id = _SESSION_ID_SAFE_CHARS.sub("_", session_id).strip("._-") or "session"
        return self._dir / f"{safe_id}.memory.json"

    def _read_memory(self, path: Path) -> dict[str, object] | None:
        if not path.exists():
            return None
        try:
            with self._lock:
                data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _deserialize_memory(session_id: str, data: dict[str, object]) -> SessionWorkingMemory:
        current_stage: AnalysisStage | None = None
        current_stage_raw = data.get("current_stage")
        if current_stage_raw is not None:
            try:
                current_stage = AnalysisStage(str(current_stage_raw))
            except ValueError:
                current_stage = None
        raw_remediation = data.get("pending_verifier_remediation")
        pending_verifier_remediation: list[dict] | None = None
        if isinstance(raw_remediation, list):
            pending_verifier_remediation = [
                item for item in raw_remediation if isinstance(item, dict)
            ]
        return SessionWorkingMemory(
            session_id=session_id,
            active_goal_id=(
                str(data["active_goal_id"]) if data.get("active_goal_id") is not None else None
            ),
            last_run_id=(str(data["last_run_id"]) if data.get("last_run_id") is not None else None),
            last_user_message=(
                str(data["last_user_message"])
                if data.get("last_user_message") is not None
                else None
            ),
            current_summary=str(data.get("current_summary", "")),
            next_step=str(data.get("next_step", "")),
            pending_questions=[
                str(item) for item in data.get("pending_questions", []) if isinstance(item, str)
            ],
            last_reflection=str(data.get("last_reflection", "")),
            recovery_note=(
                str(data["recovery_note"]) if data.get("recovery_note") is not None else None
            ),
            current_stage=current_stage,
            stage_entered_at=(
                float(data["stage_entered_at"])
                if data.get("stage_entered_at") is not None
                else None
            ),
            updated_at=float(data.get("updated_at", 0.0)),
            pending_verifier_remediation=pending_verifier_remediation,
        )
