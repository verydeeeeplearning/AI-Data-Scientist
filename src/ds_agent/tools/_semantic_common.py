"""Shared runtime helpers for semantic-memory tools."""

from __future__ import annotations

import json
from datetime import date

from ds_agent.infrastructure.semantic_memory_runtime import (
    get_semantic_memory_container,
    set_semantic_memory_container,
)

__all__ = [
    "get_semantic_memory_container",
    "parse_iso_date",
    "semantic_error",
    "semantic_result",
    "set_semantic_memory_container",
]


def semantic_result(payload: dict[str, object]) -> str:
    """Serialize a successful semantic tool payload."""

    return json.dumps(payload, default=str)


def semantic_error(message: str, *, tool_name: str) -> str:
    """Serialize a semantic tool error in the standard tool format."""

    return json.dumps({"error": message, "tool": tool_name})


def parse_iso_date(value: str | None, *, tool_name: str) -> date | None:
    """Parse an optional ISO date and raise a tool-specific error if invalid."""

    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{tool_name}: invalid ISO date '{value}'") from exc
