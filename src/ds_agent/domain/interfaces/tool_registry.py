"""Tool registry port interface (Domain layer)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ToolRegistry(Protocol):
    """Tool dispatch port — application layer depends on this abstraction."""

    def get_definitions(self) -> list[dict]: ...

    async def dispatch(self, name: str, arguments: dict) -> str: ...
