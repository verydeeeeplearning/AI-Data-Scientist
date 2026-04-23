"""Persisted VAPID subject config for web push."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from ds_agent.runtime.transcript_store import get_runtime_storage_root

_ALLOWED_PREFIXES = ("mailto:", "https://")


class WebPushSubjectError(ValueError):
    """Raised when a subject URI does not meet the allowed shape."""


def _normalize_subject(subject: str) -> str:
    normalized = subject.strip()
    if not normalized:
        raise WebPushSubjectError("subject must be a non-empty mailto: or https: URI")
    if not normalized.startswith(_ALLOWED_PREFIXES):
        raise WebPushSubjectError("subject must start with mailto: or https://")
    return normalized


@dataclass(frozen=True, slots=True)
class WebPushSubjectRecord:
    subject: str
    updated_at: float


class JsonWebPushSubjectStore:
    """Persist one workspace-level VAPID subject config."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        *,
        base_dir: str | Path | None = None,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._path = root / "web_push_config.json"
        self._lock = threading.Lock()

    def load(self) -> str | None:
        """Return the persisted subject, or ``None`` when unset."""

        with self._lock:
            if not self._path.exists():
                return None
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        if not isinstance(raw, dict):
            return None
        subject = raw.get("subject")
        if not isinstance(subject, str):
            return None
        try:
            return _normalize_subject(subject)
        except WebPushSubjectError:
            return None

    def save(self, subject: str) -> str:
        """Persist a validated subject and return its normalized form."""

        normalized = _normalize_subject(subject)
        payload = WebPushSubjectRecord(subject=normalized, updated_at=time.time())
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(asdict(payload), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return normalized


__all__ = [
    "JsonWebPushSubjectStore",
    "WebPushSubjectError",
]
