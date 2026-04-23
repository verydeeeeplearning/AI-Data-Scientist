"""File-backed transcript storage for persisted chat history."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from pathlib import Path

from ds_agent.domain.entities.messages import ChatMessage, Role, ToolCall, ensure_message_ids
from ds_agent.runtime.channel_identity import telegram_legacy_session_id

_SESSION_ID_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def get_runtime_storage_root(workspace_dir: str | None = None) -> Path:
    """Return a stable runtime storage root for a workspace path."""
    if workspace_dir:
        workspace = Path(workspace_dir).expanduser().resolve()
        return workspace / ".ds-agent" / "runtime"

    workspace = Path.cwd().resolve()
    workspace_name = workspace.name or "workspace"
    safe_name = _SESSION_ID_SAFE_CHARS.sub("_", workspace_name).strip("._-") or "workspace"
    digest = hashlib.sha1(str(workspace).encode("utf-8")).hexdigest()[:12]
    return Path.home() / ".ds-agent" / "runtime" / f"{safe_name}-{digest}"


class JsonTranscriptStore:
    """Persist session transcript messages as per-session JSON files."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        base_dir: str | Path | None = None,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._dir = root / "transcripts"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def load_messages(self, session_id: str, limit: int | None = None) -> list[ChatMessage]:
        """Load transcript messages for a session."""
        path = self._session_file(session_id)
        loaded_path = path
        loaded_session_id = session_id
        data = self._read_session(path)
        if data is None and not path.exists():
            legacy_session_id = telegram_legacy_session_id(session_id)
            if legacy_session_id is not None:
                loaded_path = self._session_file(legacy_session_id)
                loaded_session_id = legacy_session_id
                data = self._read_session(loaded_path)
        if data is None:
            return []

        raw_messages = data.get("messages", [])
        if not isinstance(raw_messages, list):
            return []

        messages = [
            self._deserialize_message(item) for item in raw_messages if isinstance(item, dict)
        ]
        if ensure_message_ids(messages):
            session_value = (
                data.get("session_id")
                if isinstance(data.get("session_id"), str)
                else loaded_session_id
            )
            self._write_session(
                loaded_path,
                {
                    "session_id": session_value,
                    "updated_at": time.time(),
                    "message_count": len(messages),
                    "messages": [self._serialize_message(message) for message in messages],
                },
            )
        if limit is None:
            return messages
        return messages[-limit:]

    def replace_messages(self, session_id: str, messages: list[ChatMessage]) -> None:
        """Replace the persisted transcript for a session."""
        path = self._session_file(session_id)
        ensure_message_ids(messages)
        payload = {
            "session_id": session_id,
            "updated_at": time.time(),
            "message_count": len(messages),
            "messages": [self._serialize_message(message) for message in messages],
        }
        self._write_session(path, payload)

    def _session_file(self, session_id: str) -> Path:
        safe_id = _SESSION_ID_SAFE_CHARS.sub("_", session_id).strip("._-")
        if not safe_id:
            safe_id = "session"
        digest = hashlib.sha1(session_id.encode("utf-8")).hexdigest()[:10]
        return self._dir / f"{safe_id}-{digest}.json"

    def _read_session(self, path: Path) -> dict[str, object] | None:
        if not path.exists():
            return None
        try:
            with self._lock:
                data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return data if isinstance(data, dict) else None

    def _write_session(self, path: Path, payload: dict[str, object]) -> None:
        with self._lock:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _serialize_message(message: ChatMessage) -> dict[str, object]:
        payload: dict[str, object] = {"role": message.role.value}
        if message.content is not None:
            payload["content"] = message.content
        if message.tool_calls:
            payload["tool_calls"] = [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in message.tool_calls
            ]
        if message.tool_call_id is not None:
            payload["tool_call_id"] = message.tool_call_id
        if message.name is not None:
            payload["name"] = message.name
        if message.cache_control is not None:
            payload["cache_control"] = message.cache_control
        if message.message_id is not None:
            payload["message_id"] = message.message_id
        return payload

    @staticmethod
    def _deserialize_message(data: dict[str, object]) -> ChatMessage:
        tool_calls_data = data.get("tool_calls")
        tool_calls: list[ToolCall] | None = None
        if isinstance(tool_calls_data, list):
            tool_calls = []
            for item in tool_calls_data:
                if isinstance(item, dict):
                    tool_calls.append(
                        ToolCall(
                            id=str(item.get("id", "")),
                            name=str(item.get("name", "")),
                            arguments=dict(item.get("arguments", {})),
                        )
                    )

        role_value = str(data.get("role", Role.USER.value))
        return ChatMessage(
            role=Role(role_value),
            content=data.get("content") if isinstance(data.get("content"), str) else None,
            tool_calls=tool_calls,
            tool_call_id=(
                data.get("tool_call_id") if isinstance(data.get("tool_call_id"), str) else None
            ),
            name=data.get("name") if isinstance(data.get("name"), str) else None,
            cache_control=(
                dict(data.get("cache_control", {}))
                if isinstance(data.get("cache_control"), dict)
                else None
            ),
            message_id=(
                data.get("message_id")
                if isinstance(data.get("message_id"), str)
                else (data.get("messageId") if isinstance(data.get("messageId"), str) else None)
            ),
        )
