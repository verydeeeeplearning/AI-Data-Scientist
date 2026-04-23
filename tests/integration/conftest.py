"""Shared fixtures for integration tests that need composition-root wiring."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ds_agent.application.services.lineage_capture_service import (
    LineageCaptureService,
    set_lineage_service,
)
from ds_agent.domain.entities.lineage import LineageRecord, LineageRecordType


class _InMemoryLineageStore:
    """Minimal lineage store for integration tests."""

    def __init__(self) -> None:
        self._records: dict[str, LineageRecord] = {}

    def save(self, record: LineageRecord) -> None:
        self._records[record.id] = record

    def get(self, record_id: str) -> LineageRecord | None:
        return self._records.get(record_id)

    def list(
        self,
        *,
        session_id: str | None = None,
        parent_id: str | None = None,
        record_type: LineageRecordType | None = None,
        limit: int = 100,
    ) -> list[LineageRecord]:
        records = list(self._records.values())
        if session_id is not None:
            records = [record for record in records if record.session_id == session_id]
        if parent_id is not None:
            records = [record for record in records if record.parent_id == parent_id]
        if record_type is not None:
            records = [record for record in records if record.record_type == record_type]
        records.sort(key=lambda record: record.timestamp, reverse=True)
        return records[:limit]

    def latest_for_session(
        self,
        session_id: str,
        *,
        record_type: LineageRecordType | None = None,
    ) -> LineageRecord | None:
        records = self.list(session_id=session_id, record_type=record_type, limit=1)
        return records[0] if records else None


@pytest.fixture(autouse=True)
def _default_lineage_service_for_integration_tests() -> Iterator[None]:
    from ds_agent.application.services import lineage_capture_service as lineage_module

    previous = lineage_module._lineage_service
    set_lineage_service(LineageCaptureService(_InMemoryLineageStore()))
    try:
        yield
    finally:
        lineage_module._lineage_service = previous
