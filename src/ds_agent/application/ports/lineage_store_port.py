"""Port: ``LineageStorePort`` — abstraction for lineage record persistence.

The application layer depends only on this Protocol. Concrete persistence
adapters (SQLite, memory, cloud) live in ``ds_agent.infrastructure`` and
are wired at the composition root.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ds_agent.domain.entities.lineage import LineageRecord, LineageRecordType


@runtime_checkable
class LineageStorePort(Protocol):
    """Contract any lineage-record persistence adapter must honour."""

    def save(self, record: LineageRecord) -> None:
        """Persist ``record``. Overwrites on id collision."""

    def get(self, record_id: str) -> LineageRecord | None:
        """Return the record identified by ``record_id`` or ``None`` when absent."""

    def list(
        self,
        *,
        session_id: str | None = None,
        parent_id: str | None = None,
        record_type: LineageRecordType | None = None,
        limit: int = 100,
    ) -> list[LineageRecord]:
        """Return records ordered by creation time (newest first) matching the filters."""

    def latest_for_session(
        self,
        session_id: str,
        *,
        record_type: LineageRecordType | None = None,
    ) -> LineageRecord | None:
        """Return the most recent record for ``session_id`` (optionally of ``record_type``)."""
