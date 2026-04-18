"""Execution policy value objects for separated runner paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ExecutionPath(StrEnum):
    """Available execution paths for tool code."""

    LOCAL = "local"
    WAREHOUSE = "warehouse"
    NETWORK = "network"


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    """Execution path policy selected for a tool."""

    path: ExecutionPath
    allowed_modules: tuple[str, ...] = field(default_factory=tuple)
    requires_approval: bool = False
    audit_required: bool = False
    allowed_domains: tuple[str, ...] = field(default_factory=tuple)
