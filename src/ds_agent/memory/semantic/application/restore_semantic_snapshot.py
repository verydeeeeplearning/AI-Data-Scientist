"""Use case for restoring one persisted semantic snapshot."""

from __future__ import annotations

from ds_agent.memory.semantic.application.dtos import (
    RestoreSemanticSnapshotResultDTO,
    SemanticSnapshotSummaryDTO,
)
from ds_agent.memory.semantic.application.ports import (
    SemanticSnapshotRepository,
    SemanticSnapshotSummary,
)


class RestoreSemanticSnapshotUseCase:
    """Restore one semantic snapshot into the canonical store."""

    def __init__(self, snapshots: SemanticSnapshotRepository) -> None:
        self._snapshots = snapshots

    def execute(self, snapshot_id: str) -> RestoreSemanticSnapshotResultDTO:
        restored = self._snapshots.restore(snapshot_id)
        if restored is None:
            raise ValueError(f"Unknown semantic snapshot: {snapshot_id}")
        return RestoreSemanticSnapshotResultDTO(
            snapshot=_to_dto(restored),
            restored_tables=list(restored.table_counts.keys()),
            restored_rows=restored.total_rows,
        )


def _to_dto(summary: SemanticSnapshotSummary) -> SemanticSnapshotSummaryDTO:
    return SemanticSnapshotSummaryDTO(
        snapshot_id=summary.snapshot_id,
        source_name=summary.source_name,
        created_at=summary.created_at,
        note=summary.note,
        table_counts=dict(summary.table_counts),
        total_rows=summary.total_rows,
    )
