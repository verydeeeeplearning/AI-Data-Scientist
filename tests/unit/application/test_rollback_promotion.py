"""Tests for rollback promotion use case."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from ds_agent.application.learning.rollback_promotion import (
    RollbackPromotionUseCase,
)
from ds_agent.domain.learning.learning_item import (
    LearningItem,
    LearningItemStatus,
    LearningItemType,
    SourceInfo,
)
from ds_agent.domain.learning.promotion_record import PromotionRecord

NOW = datetime(2026, 4, 16, 10, 0, tzinfo=UTC)


@dataclass
class _Clock:
    def now(self) -> datetime:
        return NOW


def _promoted_item() -> LearningItem:
    return LearningItem(
        item_id="LI-R001",
        item_type=LearningItemType.KB_ENTRY,
        status=LearningItemStatus.PROMOTED,
        title="Promoted KB",
        content="Content",
        signature="sig:r001",
        source=SourceInfo(),
        created_at=NOW,
        updated_at=NOW,
    )


def _promotion_record() -> PromotionRecord:
    return PromotionRecord(
        record_id="PR-001",
        item_id="LI-R001",
        item_type=LearningItemType.KB_ENTRY,
        eval_score=1.0,
        eval_threshold=1.0,
        promoted_asset_ref="domain_kb:churn:ltv",
        rollback_ref="snapshot:001",
        promoted_at=NOW,
    )


class TestRollback:
    def test_rollback_transitions_to_deprecated(self) -> None:
        store = MagicMock()
        store.get_item.return_value = _promoted_item()
        store.get_promotion_record.return_value = _promotion_record()
        uc = RollbackPromotionUseCase(store, _Clock())
        updated, dep_record = uc.execute(item_id="LI-R001", reason="test rollback")
        assert updated.status == LearningItemStatus.DEPRECATED
        assert "test rollback" in dep_record.notes
        # Post fix (S6): the use case persists both rows via a single
        # atomic call on LearningStoreAtomicPort, not the two legacy
        # single-row writers. See
        # Docs/qa_run_2026-04-17/S6_rollback_atomicity/CHANGELOG.md.
        store.save_item_and_deprecation.assert_called_once()
        store.save_item.assert_not_called()
        store.save_deprecation_record.assert_not_called()

    def test_rollback_not_promoted_fails(self) -> None:
        item = LearningItem(
            item_id="LI-R002",
            item_type=LearningItemType.KB_ENTRY,
            status=LearningItemStatus.PROPOSED,
            title="T",
            content="C",
            signature="sig:r002",
            created_at=NOW,
            updated_at=NOW,
        )
        store = MagicMock()
        store.get_item.return_value = item
        uc = RollbackPromotionUseCase(store, _Clock())
        with pytest.raises(ValueError, match="must be promoted or monitored"):
            uc.execute(item_id="LI-R002")

    def test_rollback_no_promotion_record_fails(self) -> None:
        store = MagicMock()
        store.get_item.return_value = _promoted_item()
        store.get_promotion_record.return_value = None
        uc = RollbackPromotionUseCase(store, _Clock())
        with pytest.raises(ValueError, match="No promotion record"):
            uc.execute(item_id="LI-R001")

    def test_rollback_not_found(self) -> None:
        store = MagicMock()
        store.get_item.return_value = None
        uc = RollbackPromotionUseCase(store, _Clock())
        with pytest.raises(ValueError, match="not found"):
            uc.execute(item_id="LI-NOPE")
