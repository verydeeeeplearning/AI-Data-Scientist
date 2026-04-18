"""Use case: promote an approved learning item through eval gate."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import ClassVar, Protocol

from ds_agent.application.ports.learning_store_port import LearningStoreAtomicPort
from ds_agent.domain.interfaces.learning import LearningStore
from ds_agent.domain.learning.learning_item import (
    LearningItemStatus,
    LearningItemType,
)
from ds_agent.domain.learning.promotion_record import PromotionRecord


class Clock(Protocol):
    def now(self) -> datetime: ...


class PromoteLearningItemUseCase:
    """Promote an approved item to organization assets.

    Pipeline: conflict re-check -> eval threshold -> promote.
    Thresholds by type: pattern=1.00, kb_entry=1.00, custom_skill=1.02.
    """

    THRESHOLDS: ClassVar[dict[LearningItemType, float]] = {
        LearningItemType.PATTERN: 1.00,
        LearningItemType.KB_ENTRY: 1.00,
        LearningItemType.CUSTOM_SKILL: 1.02,
    }

    def __init__(
        self,
        store: LearningStore,
        clock: Clock,
    ) -> None:
        self._store = store
        self._clock = clock

    def execute(
        self,
        *,
        item_id: str,
        eval_score: float,
        baseline_score: float = 1.0,
        promoted_asset_ref: str = "",
        rollback_ref: str = "",
    ) -> PromotionRecord:
        item = self._store.get_item(item_id)
        if item is None:
            raise ValueError(f"Learning item {item_id} not found")
        if item.status != LearningItemStatus.APPROVED:
            raise ValueError(
                f"Cannot promote item in status {item.status.value} "
                f"(must be approved)",
            )

        # 1. Conflict re-check
        if item.has_unresolved_conflicts:
            raise ValueError(
                f"Cannot promote {item_id}: unresolved conflicts exist",
            )

        # 2. Eval threshold check
        threshold = self.THRESHOLDS.get(item.item_type, 1.0)
        required_score = baseline_score * threshold
        if eval_score < required_score:
            raise ValueError(
                f"Eval score {eval_score:.3f} below threshold "
                f"{required_score:.3f} "
                f"(baseline={baseline_score:.3f} x {threshold})",
            )

        # 3. Create promotion record
        now = self._clock.now()
        record = PromotionRecord(
            record_id=f"PR-{uuid.uuid4().hex[:8]}",
            item_id=item_id,
            item_type=item.item_type,
            eval_score=eval_score,
            eval_threshold=required_score,
            promoted_asset_ref=promoted_asset_ref,
            rollback_ref=rollback_ref,
            promoted_at=now,
        )

        # 4. Transition to promoted
        updated = item.transition_to(
            LearningItemStatus.PROMOTED,
            now=now,
        )

        # Single atomic commit: either both rows persist or neither does.
        # Closes R-1 (phantom-promotion audit split) per S9.
        # See ``LearningStoreAtomicPort.save_promotion_and_item``.
        atomic: LearningStoreAtomicPort = self._store  # type: ignore[assignment]
        atomic.save_promotion_and_item(promotion=record, item=updated)
        return record
