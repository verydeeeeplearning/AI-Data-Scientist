"""Shared fixtures for application-layer unit tests.

This conftest owns wiring that normally happens at the composition root
(``ds_agent.agent.factory.create_agent``) but is not executed when a
unit test drives lower-level services directly. In particular,
``LineageCaptureHook()`` — constructed inside
``agent.factory.build_hook_registry`` — now strictly requires a
previously-configured process-global ``LineageCaptureService``
(see ``set_lineage_service``). Tests that exercise the subagent
orchestrator go through ``build_hook_registry`` indirectly via
``ProcessSubagent.execute`` and therefore need that wiring in place.

The fixture below satisfies the wiring with an in-memory
``LineageStorePort`` implementation so no SQLite file is created and no
real persistence layer is touched. It is autouse so individual tests do
not need to know about it; the previous value is restored on teardown
so tests that *do* perform their own explicit wiring remain isolated.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ds_agent.application.services.lineage_capture_service import (
    LineageCaptureService,
    set_lineage_service,
)
from ds_agent.domain.entities.lineage import LineageRecord, LineageRecordType


class _InMemoryLineageStore:
    """Minimal ``LineageStorePort`` implementation for unit tests.

    Records are held in-process only; nothing is written to disk. The
    semantics mirror ``SqliteLineageStore`` just closely enough for
    hooks that capture lineage during a subagent run without failing.
    """

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
            records = [r for r in records if r.session_id == session_id]
        if parent_id is not None:
            records = [r for r in records if r.parent_id == parent_id]
        if record_type is not None:
            records = [r for r in records if r.record_type == record_type]
        records.sort(key=lambda r: r.timestamp, reverse=True)
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
def _default_lineage_service_for_application_tests() -> Iterator[None]:
    """Wire a process-global lineage service so hooks constructed during
    ``build_hook_registry`` do not raise ``RuntimeError``.

    Tests that construct their own ``LineageCaptureService`` explicitly
    (e.g. ``test_lineage_service.py``) still override the hook-level
    service via the constructor argument, so this autouse fixture does
    not interfere with their assertions.
    """
    from ds_agent.application.services import lineage_capture_service as _mod

    previous = _mod._lineage_service
    set_lineage_service(LineageCaptureService(_InMemoryLineageStore()))
    try:
        yield
    finally:
        _mod._lineage_service = previous
