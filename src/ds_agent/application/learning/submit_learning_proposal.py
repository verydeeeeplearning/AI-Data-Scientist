"""Use case: submit a learning proposal from extractors."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Protocol

from ds_agent.domain.interfaces.learning import LearningStore
from ds_agent.domain.learning.learning_item import (
    ConflictRef,
    Evidence,
    LearningItem,
    LearningItemStatus,
    LearningItemType,
    SourceInfo,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class SubmitLearningProposalUseCase:
    """Receive extracted knowledge and create a proposed LearningItem.

    Dedup: if an item with the same signature exists and is not
    archived/rejected, the existing item is returned unchanged.
    If the existing item was rejected, a re-submission is allowed.
    """

    def __init__(self, store: LearningStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def execute(
        self,
        *,
        item_type: LearningItemType,
        title: str,
        content: str,
        signature: str,
        source: SourceInfo | None = None,
        evidence: list[Evidence] | None = None,
        conflict_refs: list[ConflictRef] | None = None,
        tags: list[str] | None = None,
        scope: Literal["project", "domain", "global"] = "project",
        metadata: dict[str, Any] | None = None,
    ) -> LearningItem:
        existing = self._store.find_by_signature(signature)
        if existing is not None and existing.status not in {
            LearningItemStatus.ARCHIVED,
            LearningItemStatus.REJECTED,
        }:
            return existing
        # Rejected/archived items allow re-submission as new proposals.

        now = self._clock.now()
        item = LearningItem(
            item_id=f"LI-{uuid.uuid4().hex[:8]}",
            item_type=item_type,
            status=LearningItemStatus.PROPOSED,
            title=title,
            content=content,
            signature=signature,
            source=source or SourceInfo(),
            evidence=evidence or [],
            conflict_refs=conflict_refs or [],
            tags=tags or [],
            scope=scope,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self._store.save_item(item)
        return item
