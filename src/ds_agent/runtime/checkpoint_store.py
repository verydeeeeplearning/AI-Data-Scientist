"""File-backed checkpoint storage for in-progress agent sessions."""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

from ds_agent.domain.entities.session_checkpoint import NamedCheckpoint, SessionCheckpoint
from ds_agent.runtime.channel_identity import telegram_legacy_session_id
from ds_agent.runtime.transcript_store import JsonTranscriptStore, get_runtime_storage_root


class JsonCheckpointStore:
    """Persist in-progress session messages so interrupted work can resume."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        base_dir: str | Path | None = None,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._dir = root / "checkpoints"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._named_dir = self._dir / "named"
        self._named_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._transcript_codec = JsonTranscriptStore(base_dir=root)

    def load(self, session_id: str) -> SessionCheckpoint | None:
        """Load checkpoint for a session."""
        path = self._checkpoint_file(session_id)
        data = self._read_checkpoint(path)
        if data is None and not path.exists():
            legacy_session_id = telegram_legacy_session_id(session_id)
            if legacy_session_id is not None:
                data = self._read_checkpoint(self._checkpoint_file(legacy_session_id))
        if data is None:
            return None

        messages_data = data.get("messages", [])
        if not isinstance(messages_data, list):
            messages_data = []

        messages = [
            self._transcript_codec._deserialize_message(item)
            for item in messages_data
            if isinstance(item, dict)
        ]
        return SessionCheckpoint(
            session_id=session_id,
            step=int(data.get("step", 0)),
            messages=messages,
            updated_at=float(data.get("updated_at", 0.0)),
        )

    def save(self, checkpoint: SessionCheckpoint) -> None:
        """Save or replace a session checkpoint."""
        path = self._checkpoint_file(checkpoint.session_id)
        payload = {
            "session_id": checkpoint.session_id,
            "step": checkpoint.step,
            "updated_at": checkpoint.updated_at or time.time(),
            "messages": [
                self._transcript_codec._serialize_message(message)
                for message in checkpoint.messages
            ],
        }
        with self._lock:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def clear(self, session_id: str) -> None:
        """Delete checkpoint for a session if it exists."""
        path = self._checkpoint_file(session_id)
        with self._lock:
            if path.exists():
                path.unlink()

    def list(self, limit: int = 100) -> list[SessionCheckpoint]:
        """List persisted checkpoints ordered by most recent update."""
        checkpoints: list[SessionCheckpoint] = []
        for path in self._dir.glob("*.checkpoint.json"):
            try:
                with self._lock:
                    data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(data, dict):
                continue

            session_id = data.get("session_id")
            if not isinstance(session_id, str):
                continue

            messages_data = data.get("messages", [])
            if not isinstance(messages_data, list):
                messages_data = []
            messages = [
                self._transcript_codec._deserialize_message(item)
                for item in messages_data
                if isinstance(item, dict)
            ]
            checkpoints.append(
                SessionCheckpoint(
                    session_id=session_id,
                    step=int(data.get("step", 0)),
                    messages=messages,
                    updated_at=float(data.get("updated_at", 0.0)),
                )
            )
        checkpoints.sort(key=lambda item: item.updated_at, reverse=True)
        return checkpoints[:limit]

    def _checkpoint_file(self, session_id: str) -> Path:
        transcript_name = self._transcript_codec._session_file(session_id).stem
        return self._dir / f"{transcript_name}.checkpoint.json"

    def _read_checkpoint(self, path: Path) -> dict[str, object] | None:
        if not path.exists():
            return None
        try:
            with self._lock:
                data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return data if isinstance(data, dict) else None

    # -- Named checkpoints (operator-saved save points) --------------------

    def save_named(
        self,
        session_id: str,
        name: str,
        *,
        transcript_step: int,
        description: str | None = None,
    ) -> NamedCheckpoint:
        """Persist a new operator-named checkpoint and return its record.

        Named checkpoints live alongside the implicit per-session checkpoint
        but are immutable identifiers (one file per ``id``) so they can be
        referenced from branch / rerun operations without ambiguity.
        """
        clean_session_id = session_id.strip()
        if not clean_session_id:
            raise ValueError("session_id is required")
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("name is required")
        if transcript_step < 0:
            raise ValueError("transcript_step must be >= 0")

        record = NamedCheckpoint(
            id=f"ckpt_{uuid.uuid4().hex[:16]}",
            session_id=clean_session_id,
            name=clean_name,
            created_at=time.time(),
            transcript_step=int(transcript_step),
            description=(description.strip() if description and description.strip() else None),
        )
        path = self._named_file(record.id)
        with self._lock:
            path.write_text(
                json.dumps(self._serialize_named(record), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return record

    def list_named(self, session_id: str, limit: int = 50) -> list[NamedCheckpoint]:
        """List named checkpoints for a session, newest first."""
        clean_session_id = session_id.strip()
        records: list[NamedCheckpoint] = []
        for path in self._named_dir.glob("ckpt_*.json"):
            try:
                with self._lock:
                    data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(data, dict):
                continue
            if data.get("session_id") != clean_session_id:
                continue
            record = self._deserialize_named(data)
            if record is not None:
                records.append(record)
        records.sort(key=lambda item: item.created_at, reverse=True)
        return records[:limit]

    def get_named(self, checkpoint_id: str) -> NamedCheckpoint | None:
        """Return one named checkpoint by id, or ``None`` if missing."""
        clean_id = checkpoint_id.strip()
        if not clean_id:
            return None
        path = self._named_file(clean_id)
        if not path.exists():
            return None
        try:
            with self._lock:
                data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(data, dict):
            return None
        return self._deserialize_named(data)

    def _named_file(self, checkpoint_id: str) -> Path:
        return self._named_dir / f"{checkpoint_id}.json"

    @staticmethod
    def _serialize_named(record: NamedCheckpoint) -> dict[str, object]:
        return {
            "id": record.id,
            "session_id": record.session_id,
            "name": record.name,
            "created_at": record.created_at,
            "transcript_step": record.transcript_step,
            "description": record.description,
        }

    @staticmethod
    def _deserialize_named(data: dict[str, object]) -> NamedCheckpoint | None:
        try:
            return NamedCheckpoint(
                id=str(data["id"]),
                session_id=str(data["session_id"]),
                name=str(data["name"]),
                created_at=float(data.get("created_at", 0.0)),
                transcript_step=int(data.get("transcript_step", 0)),
                description=(
                    str(data["description"]) if data.get("description") is not None else None
                ),
            )
        except (KeyError, TypeError, ValueError):
            return None
