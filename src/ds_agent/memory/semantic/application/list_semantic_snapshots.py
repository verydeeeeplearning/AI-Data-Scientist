"""Use case for listing persisted semantic snapshots."""

from __future__ import annotations

from ds_agent.memory.semantic.application.dtos import SemanticSnapshotSummaryDTO
from ds_agent.memory.semantic.application.ports import (
    SemanticSnapshotRepository,
    SemanticSnapshotSummary,
)


class ListSemanticSnapshotsUseCase:
    """Return the latest semantic snapshots in operator-facing DTO form."""

    def __init__(self, snapshots: SemanticSnapshotRepository) -> None:
        self._snapshots = snapshots

    def execute(self, *, limit: int = 20) -> list[SemanticSnapshotSummaryDTO]:
        summaries = self._snapshots.list(limit=max(limit, 1))
        return [_to_dto(item) for item in summaries]


def _to_dto(summary: SemanticSnapshotSummary) -> SemanticSnapshotSummaryDTO:
    return SemanticSnapshotSummaryDTO(
        snapshot_id=summary.snapshot_id,
        source_name=summary.source_name,
        created_at=summary.created_at,
        note=summary.note,
        table_counts=dict(summary.table_counts),
        total_rows=summary.total_rows,
    )
