"""Distributed execution interface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class DistributedExecutor(Protocol):
    """Protocol for distributed execution backends."""

    async def execute(self, code: str, data_path: str) -> str: ...

    def is_available(self) -> bool: ...
