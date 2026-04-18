"""Memory port interfaces (Domain layer).

Defines abstract contracts for memory storage and retrieval.
Infrastructure layer provides concrete implementations.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ds_agent.domain.entities.memory import MemoryEntry, MemoryType


@runtime_checkable
class MemoryStorePort(Protocol):
    """Port interface for persistent memory storage."""

    def store(self, entry: MemoryEntry) -> str:
        """Store or upsert a memory entry. Returns the entry ID."""
        ...

    def search(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        max_results: int = 5,
    ) -> list[MemoryEntry]:
        """Full-text search with optional type filtering."""
        ...

    def get(self, entry_id: str) -> MemoryEntry | None:
        """Get a single entry by ID."""
        ...

    def update(
        self,
        entry_id: str,
        content: str | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        """Update an existing entry. Returns True if found and updated."""
        ...

    def delete(self, entry_id: str) -> bool:
        """Delete an entry. Returns True if found and deleted."""
        ...

    def list_by_type(self, memory_type: MemoryType, limit: int = 50) -> list[MemoryEntry]:
        """List all entries of a given type."""
        ...
