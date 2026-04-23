"""JSONL-backed access audit log with bounded retention."""

from __future__ import annotations

import builtins
import json
import threading
import time
from pathlib import Path

from ds_agent.domain.access.access_log_entry import AccessLogEntry
from ds_agent.runtime.transcript_store import get_runtime_storage_root

_DEFAULT_RETENTION_SECONDS = 90 * 24 * 60 * 60


class JsonAccessLogStore:
    """Persist redacted access audit entries to disk."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        *,
        base_dir: str | Path | None = None,
        retention_seconds: float = _DEFAULT_RETENTION_SECONDS,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._file_path = root / "access" / "access_log.jsonl"
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._retention_seconds = max(float(retention_seconds), 0.0)
        self._lock = threading.Lock()

    def append(self, entry: AccessLogEntry) -> AccessLogEntry:
        with self._lock:
            entries = self._load_entries_unlocked(now=entry.created_at)
            entries.append(entry)
            self._write_entries_unlocked(entries)
        return entry

    def list(
        self,
        *,
        resource_type: str | None = None,
        resource_id: str | None = None,
        since: float | None = None,
        until: float | None = None,
        limit: int = 50,
        now: float | None = None,
    ) -> builtins.list[AccessLogEntry]:
        capped = max(int(limit), 0)
        if capped == 0:
            return []
        with self._lock:
            entries = self._load_entries_unlocked(now=now)

        filtered: builtins.list[AccessLogEntry] = []
        for entry in reversed(entries):
            if resource_type is not None and entry.resource_type != resource_type:
                continue
            if resource_id is not None and entry.resource_id != resource_id:
                continue
            if since is not None and entry.created_at < float(since):
                continue
            if until is not None and entry.created_at > float(until):
                continue
            filtered.append(entry)
            if len(filtered) >= capped:
                break
        return filtered

    def _load_entries_unlocked(
        self,
        *,
        now: float | None = None,
    ) -> builtins.list[AccessLogEntry]:
        timestamp = time.time() if now is None else float(now)
        if not self._file_path.exists():
            return []

        try:
            lines = self._file_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []

        cutoff = timestamp - self._retention_seconds
        entries: builtins.list[AccessLogEntry] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            entry = self._deserialize(payload)
            if entry.created_at < cutoff:
                continue
            entries.append(entry)

        self._write_entries_unlocked(entries)
        return entries

    def _write_entries_unlocked(self, entries: builtins.list[AccessLogEntry]) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        if not entries:
            self._file_path.write_text("", encoding="utf-8")
            return
        payload = "\n".join(
            json.dumps(self._serialize(entry), ensure_ascii=False) for entry in entries
        )
        self._file_path.write_text(payload + "\n", encoding="utf-8")

    @staticmethod
    def _serialize(entry: AccessLogEntry) -> dict[str, object]:
        return {
            "entry_id": entry.entry_id,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "action": entry.action,
            "actor_ref": entry.actor_ref,
            "allowed": entry.allowed,
            "role": entry.role,
            "reason": entry.reason,
            "metadata": dict(entry.metadata),
            "created_at": entry.created_at,
        }

    @staticmethod
    def _deserialize(payload: dict[str, object]) -> AccessLogEntry:
        metadata = payload.get("metadata")
        created_at = payload.get("created_at", 0.0)
        return AccessLogEntry(
            resource_type=str(payload.get("resource_type", "")),
            resource_id=str(payload.get("resource_id", "")),
            action=str(payload.get("action", "view")),  # type: ignore[arg-type]
            actor_ref=str(payload.get("actor_ref", "anonymous")),
            allowed=bool(payload.get("allowed", False)),
            role=(
                str(payload["role"])  # type: ignore[arg-type]
                if payload.get("role") is not None
                else None
            ),
            reason=str(payload["reason"]) if payload.get("reason") is not None else None,
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
            entry_id=str(payload.get("entry_id", "")),
            created_at=float(created_at) if isinstance(created_at, (int, float)) else 0.0,
        )
