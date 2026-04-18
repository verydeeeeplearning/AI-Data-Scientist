"""Tests for deprecate learning item use case."""

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

NOW = datetime(2026, 4, 16, 10, 0, tzinfo=UTC)


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


def _mock_store(
    item: LearningItem | None,
    existing_dep: DeprecationRecord | None = None,
) -> MagicMock:
    store = MagicMock()
    store.get_item.return_value = item
    store.get_deprecation_record.return_value = existing_dep
    return store


class TestImmediateDeprecation:
    def test_immediate_transitions(self) -> None:
        store = _mock_store(_promoted_item())
        uc = DeprecateLearningItemUseCase(store, _Clock())
        record = uc.execute(
            item_id="LI-D001",
            reason=DeprecationReason.MANUAL,
            mode=DeprecationMode.IMMEDIATE,
        )
        assert record.reason == DeprecationReason.MANUAL
        assert record.mode == DeprecationMode.IMMEDIATE
        # Contract updated by S9 (R-2): IMMEDIATE path uses the atomic
        # port method; the separate save_item / save_deprecation_record
        # writers must NOT fire.
        store.save_item_and_deprecation.assert_called_once()
        store.save_item.assert_not_called()
        store.save_deprecation_record.assert_not_called()

    def test_proposed_cannot_deprecate(self) -> None:
        item = LearningItem(
            item_id="LI-D002",
            item_type=LearningItemType.KB_ENTRY,
            status=LearningItemStatus.PROPOSED,
            title="T",
            content="C",
            signature="sig:d002",
            created_at=NOW,
            updated_at=NOW,
        )
        store = _mock_store(item)
        uc = DeprecateLearningItemUseCase(store, _Clock())
        with pytest.raises(ValueError, match="must be promoted or monitored"):
            uc.execute(item_id="LI-D002", reason=DeprecationReason.MANUAL)


class TestGraceMode:
    def test_grace_sets_deadline(self) -> None:
        store = _mock_store(_promoted_item())
        uc = DeprecateLearningItemUseCase(store, _Clock())
        record = uc.execute(
            item_id="LI-D001",
            reason=DeprecationReason.SUPERSEDED,
            mode=DeprecationMode.GRACE,
            grace_days=7,
        )
        assert record.mode == DeprecationMode.GRACE
        assert record.grace_until is not None
        # Grace mode does NOT call save_item (status unchanged until grace expires)
        store.save_item.assert_not_called()


class TestAutoDeprecation:
    def test_first_failure_recorded_not_deprecated(self) -> None:
        store = _mock_store(_promoted_item(), existing_dep=None)
        uc = DeprecateLearningItemUseCase(store, _Clock())
        result = uc.auto_deprecate_on_failure(item_id="LI-D001")
        assert result is None
        store.save_deprecation_record.assert_called_once()

    def test_second_failure_triggers_deprecation(self) -> None:
        existing = DeprecationRecord(
            record_id="DR-existing",
            item_id="LI-D001",
            reason=DeprecationReason.EVAL_FAILURE,
            failure_count=1,
            deprecated_at=NOW,
        )
        store = _mock_store(_promoted_item(), existing_dep=existing)
        uc = DeprecateLearningItemUseCase(store, _Clock())
        result = uc.auto_deprecate_on_failure(item_id="LI-D001")
        assert result is not None
        assert result.reason == DeprecationReason.EVAL_FAILURE
