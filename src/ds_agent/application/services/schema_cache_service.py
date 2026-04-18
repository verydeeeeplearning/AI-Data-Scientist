"""TTL cache for schema metadata lookups."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

_DEFAULT_TTL_SECONDS = 24 * 60 * 60


@dataclass(slots=True)
class _SchemaCacheEntry:
    value: Any
    expires_at: float


_schema_cache: dict[str, _SchemaCacheEntry] = {}


def get_schema_cache(key: str) -> Any | None:
    """Return cached schema metadata when still valid."""
    entry = _schema_cache.get(key)
    if entry is None:
        return None
    if entry.expires_at < time.time():
        _schema_cache.pop(key, None)
        return None
    return entry.value


def set_schema_cache(
    key: str,
    value: Any,
    *,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> None:
    """Store a schema metadata payload with TTL."""
    _schema_cache[key] = _SchemaCacheEntry(
        value=value,
        expires_at=time.time() + ttl_seconds,
    )


def clear_schema_cache() -> None:
    """Clear cache state for tests or explicit invalidation."""
    _schema_cache.clear()
