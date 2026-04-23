"""Application use case for listing redacted access-audit entries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ds_agent.domain.access.access_log_entry import AccessLogEntry

_DEFAULT_OWNER_OPERATOR_ID = "local-user"
_MAX_LIST_LIMIT = 200


class AccessLogStorePort(Protocol):
    """Read-only audit log port used by the listing surface."""

    def list(
        self,
        *,
        resource_type: str | None = None,
        resource_id: str | None = None,
        since: float | None = None,
        until: float | None = None,
        limit: int = 50,
    ) -> list[AccessLogEntry]: ...


@dataclass(frozen=True, slots=True)
class ListAccessLogInput:
    """Query payload for one access-log listing request."""

    operator_id: str
    resource_type: str | None = None
    since: float | None = None
    until: float | None = None
    limit: int = 50


class ListAccessLogUseCase:
    """Return a filtered, newest-first slice of access log entries.

    The desktop product currently runs in sole-user mode, so the only
    owner who may inspect the log is the local operator.
    """

    def __init__(self, store: AccessLogStorePort) -> None:
        self._store = store

    def execute(self, request: ListAccessLogInput) -> list[AccessLogEntry]:
        operator_id = request.operator_id.strip() if isinstance(request.operator_id, str) else ""
        if operator_id != _DEFAULT_OWNER_OPERATOR_ID:
            return []

        resource_type = _normalize_text(request.resource_type)
        since = _normalize_timestamp(request.since)
        until = _normalize_timestamp(request.until)
        limit = _normalize_limit(request.limit)
        if limit == 0:
            return []

        return self._store.list(
            resource_type=resource_type,
            since=since,
            until=until,
            limit=limit,
        )


def _normalize_text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _normalize_timestamp(value: float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _normalize_limit(value: int) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return 0
    if limit <= 0:
        return 0
    return min(limit, _MAX_LIST_LIMIT)
