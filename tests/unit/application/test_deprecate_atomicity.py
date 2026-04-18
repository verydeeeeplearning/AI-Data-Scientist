"""Atomicity tests for DeprecateLearningItemUseCase IMMEDIATE path (S9 / R-2).

Guards against the same audit-trail split shape as FAIL-B11-8, but on
the immediate-deprecation path (explicit call by operator, not just the
rollback pathway). GRACE mode remains a single-row write and is not
covered here (by definition atomic on its own commit).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from ds_agent.application.learning.deprecate_learning_item import (
    DeprecateLearningItemUseCase,
)
from ds_agent.domain.learning.deprecation_record import (
    DeprecationMode,
    DeprecationReason,
    DeprecationRecord,
)
from ds_agent.domain.learning.learning_item import (
    LearningItem,
    LearningItemStatus,
    LearningItemType,
    SourceInfo,
)

NOW = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)


@dataclass
class _Clock:
    def now(self) -> datetime:
        return NOW


def _promoted_item() -> LearningItem:
    return LearningItem(
        item_id="LI-D001",
        item_type=LearningItemType.KB_ENTRY,
        status=LearningItemStatus.PROMOTED,
        title="Promoted KB",
        content="Content",
        signature="sig:d001",
        source=SourceInfo(),
        created_at=NOW,
        updated_at=NOW,
    )


class TestDeprecateImmediateAtomicity:
    """IMMEDIATE mode must use the atomic port method."""

    def test_immediate_uses_atomic_write(self) -> None:
        store = MagicMock()
        store.get_item.return_value = _promoted_item()

        uc = DeprecateLearningItemUseCase(store, _Clock())
        record = uc.execute(
            item_id="LI-D001",
            reason=DeprecationReason.MANUAL,
            mode=DeprecationMode.IMMEDIATE,
        )

        assert store.save_item_and_deprecation.call_count == 1
        kwargs = store.save_item_and_deprecation.call_args.kwargs
        assert isinstance(kwargs["item"], LearningItem)
        assert isinstance(kwargs["deprecation"], DeprecationRecord)
        assert kwargs["item"].status == LearningItemStatus.DEPRECATED
        assert kwargs["deprecation"].mode == DeprecationMode.IMMEDIATE

        # Legacy pair must NOT fire on IMMEDIATE path.
        store.save_item.assert_not_called()
        store.save_deprecation_record.assert_not_called()

        assert record.item_id == "LI-D001"

    def test_immediate_failure_propagates_without_split_writes(self) -> None:
        store = MagicMock()
        store.get_item.return_value = _promoted_item()
        store.save_item_and_deprecation.side_effect = RuntimeError("injected")

        uc = DeprecateLearningItemUseCase(store, _Clock())

        with pytest.raises(RuntimeError, match="injected"):
            uc.execute(
                item_id="LI-D001",
                reason=DeprecationReason.MANUAL,
                mode=DeprecationMode.IMMEDIATE,
            )

        assert store.save_item_and_deprecation.call_count == 1
        store.save_item.assert_not_called()
        store.save_deprecation_record.assert_not_called()


class TestDeprecateGraceBehavior:
    """GRACE mode still uses the single-row writer (no atomic port needed)."""

    def test_grace_uses_single_record_writer(self) -> None:
        store = MagicMock()
        store.get_item.return_value = _promoted_item()

        uc = DeprecateLearningItemUseCase(store, _Clock())
        record = uc.execute(
            item_id="LI-D001",
            reason=DeprecationReason.MANUAL,
            mode=DeprecationMode.GRACE,
            grace_days=7,
        )

        store.save_deprecation_record.assert_called_once()
        store.save_item.assert_not_called()  # no transition in GRACE
        store.save_item_and_deprecation.assert_not_called()

        assert record.mode == DeprecationMode.GRACE
        assert record.grace_until is not None
