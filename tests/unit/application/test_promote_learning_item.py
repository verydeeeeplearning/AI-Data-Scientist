"""Tests for promote learning item use case."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from ds_agent.application.learning.promote_learning_item import (
    PromoteLearningItemUseCase,
)
from ds_agent.domain.learning.learning_item import (
    ConflictRef,
    LearningItem,
    LearningItemStatus,
    LearningItemType,
    SourceInfo,
)

NOW = datetime(2026, 4, 16, 10, 0, tzinfo=UTC)


@dataclass
class _Clock:
    def now(self) -> datetime:
        return NOW


def _approved_item(
    item_type: LearningItemType = LearningItemType.KB_ENTRY,
    conflict_refs: list[ConflictRef] | None = None,
) -> LearningItem:
    return LearningItem(
        item_id="LI-P001",
        item_type=item_type,
        status=LearningItemStatus.APPROVED,
        title="Test",
        content="Content",
        signature="sig:p001",
        source=SourceInfo(),
        conflict_refs=conflict_refs or [],
        created_at=NOW,
        updated_at=NOW,
    )


def _mock_store(item: LearningItem | None) -> MagicMock:
    store = MagicMock()
    store.get_item.return_value = item
    return store


class TestPromotionGate:
    def test_promote_kb_entry_passes(self) -> None:
        store = _mock_store(_approved_item())
        uc = PromoteLearningItemUseCase(store, _Clock())
        record = uc.execute(item_id="LI-P001", eval_score=1.0, baseline_score=1.0)
        assert record.item_id == "LI-P001"
        assert record.eval_score == 1.0
        # Contract updated by S9 (R-1): use case invokes the atomic
        # port method instead of two independent commits.
        store.save_promotion_and_item.assert_called_once()
        store.save_promotion_record.assert_not_called()
        store.save_item.assert_not_called()

    def test_custom_skill_needs_higher_threshold(self) -> None:
        store = _mock_store(_approved_item(LearningItemType.CUSTOM_SKILL))
        uc = PromoteLearningItemUseCase(store, _Clock())
        with pytest.raises(ValueError, match="below threshold"):
            uc.execute(item_id="LI-P001", eval_score=1.01, baseline_score=1.0)

    def test_custom_skill_passes_at_1_02(self) -> None:
        store = _mock_store(_approved_item(LearningItemType.CUSTOM_SKILL))
        uc = PromoteLearningItemUseCase(store, _Clock())
        record = uc.execute(item_id="LI-P001", eval_score=1.02, baseline_score=1.0)
        assert record.eval_score == 1.02

    def test_unresolved_conflict_blocks(self) -> None:
        item = _approved_item(
            conflict_refs=[ConflictRef(conflicting_item_id="LI-X", resolved=False)],
        )
        store = _mock_store(item)
        uc = PromoteLearningItemUseCase(store, _Clock())
        with pytest.raises(ValueError, match="unresolved conflicts"):
            uc.execute(item_id="LI-P001", eval_score=1.0)

    def test_not_approved_fails(self) -> None:
        item = LearningItem(
            item_id="LI-P002",
            item_type=LearningItemType.KB_ENTRY,
            status=LearningItemStatus.PROPOSED,
            title="T",
            content="C",
            signature="sig:p002",
            created_at=NOW,
            updated_at=NOW,
        )
        store = _mock_store(item)
        uc = PromoteLearningItemUseCase(store, _Clock())
        with pytest.raises(ValueError, match="must be approved"):
            uc.execute(item_id="LI-P002", eval_score=1.0)

    def test_not_found(self) -> None:
        store = _mock_store(None)
        uc = PromoteLearningItemUseCase(store, _Clock())
        with pytest.raises(ValueError, match="not found"):
            uc.execute(item_id="LI-NOPE", eval_score=1.0)
