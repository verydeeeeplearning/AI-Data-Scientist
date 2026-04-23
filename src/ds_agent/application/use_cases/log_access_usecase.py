"""Application use case for redacted access-audit logging."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from ds_agent.domain.access import AccessAction
from ds_agent.domain.access.access_log_entry import AccessLogEntry
from ds_agent.domain.access.viewer_role import ViewerRole

_SENSITIVE_METADATA_KEYS = (
    "email",
    "phone",
    "name",
    "address",
    "ip",
    "token",
    "secret",
    "password",
    "ssn",
    "user",
)


class AccessLogStorePort(Protocol):
    """Append-only audit sink for access decisions."""

    def append(self, entry: AccessLogEntry) -> AccessLogEntry: ...


@dataclass(frozen=True, slots=True)
class LogAccessInput:
    """Request payload for recording one access decision."""

    resource_type: str
    resource_id: str
    action: AccessAction
    allowed: bool
    actor_user_id: str | None = None
    role: ViewerRole | None = None
    reason: str | None = None
    metadata: Mapping[str, object] | None = None
    occurred_at: float | None = None


class LogAccessUseCase:
    """Persist one access decision without storing raw principal PII."""

    def __init__(self, store: AccessLogStorePort) -> None:
        self._store = store

    def execute(self, request: LogAccessInput) -> AccessLogEntry:
        resource_type = request.resource_type.strip()
        resource_id = request.resource_id.strip()
        if not resource_type:
            raise ValueError("resource_type is required")
        if not resource_id:
            raise ValueError("resource_id is required")

        reason = (
            request.reason.strip()
            if isinstance(request.reason, str) and request.reason.strip()
            else None
        )
        entry = AccessLogEntry(
            resource_type=resource_type,
            resource_id=resource_id,
            action=request.action,
            actor_ref=self._actor_ref(request.actor_user_id),
            allowed=bool(request.allowed),
            role=request.role,
            reason=reason,
            metadata=self._sanitize_metadata(request.metadata),
            created_at=time.time() if request.occurred_at is None else float(request.occurred_at),
        )
        return self._store.append(entry)

    @staticmethod
    def _actor_ref(actor_user_id: str | None) -> str:
        if actor_user_id is None or not actor_user_id.strip():
            return "anonymous"
        digest = hashlib.sha256(actor_user_id.strip().encode("utf-8")).hexdigest()[:12]
        return f"user:{digest}"

    @classmethod
    def _sanitize_metadata(
        cls,
        metadata: Mapping[str, object] | None,
    ) -> dict[str, object]:
        if metadata is None:
            return {}

        sanitized: dict[str, object] = {}
        for raw_key, raw_value in metadata.items():
            key = str(raw_key).strip()
            if not key:
                continue
            lowered = key.lower()
            if any(token in lowered for token in _SENSITIVE_METADATA_KEYS):
                continue
            value = cls._sanitize_value(raw_value)
            if value is not None:
                sanitized[key] = value
        return sanitized

    @classmethod
    def _sanitize_value(cls, value: object) -> object | None:
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            return value[:256]
        if isinstance(value, Mapping):
            return cls._sanitize_metadata(value)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            items: list[object] = []
            for item in value:
                sanitized_item = cls._sanitize_value(item)
                if sanitized_item is not None:
                    items.append(sanitized_item)
            return items
        return str(type(value).__name__)
