"""Tests for revalidation scheduler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import MagicMock

from ds_agent.application.learning.deprecate_learning_item import (
    DeprecateLearningItemUseCase,
)
from ds_agent.application.learning.revalidation_scheduler import (
    RevalidationScheduler,
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
    now_value: datetime = NOW

    def now(self) -> datetime:
        return self.now_value


def _monitored_item(
    item_id: str = "LI-M001",
    item_type: LearningItemType = LearningItemType.KB_ENTRY,
    last_revalidation: str | None = None,
) -> LearningItem:
    metadata = {}
    if last_revalidation:
        metadata["last_revalidation_at"] = last_revalidation
    return LearningItem(
        item_id=item_id,
        item_type=item_type,
        status=LearningItemStatus.MONITORED,
        title="Monitored item",
        content="Content",
        signature=f"sig:{item_id}",
        source=SourceInfo(),
        metadata=metadata,
        created_at=NOW,
        updated_at=NOW,
    )


def _mock_store(monitored: list[LearningItem] | None = None) -> MagicMock:
    store = MagicMock()
    store.list_monitored_items.return_value = monitored or []
    store.get_item.side_effect = lambda item_id: next(
        (i for i in (monitored or []) if i.item_id == item_id), None,
    )
    store.get_deprecation_record.return_value = None
    return store


class TestDueItems:
    def test_never_evaluated_is_due(self) -> None:
        item = _monitored_item()
        store = _mock_store([item])
        sched = RevalidationScheduler(
            store, DeprecateLearningItemUseCase(store, _Clock()), _Clock(),
        )
        due = sched.get_due_items()
        assert len(due) == 1

    def test_recently_evaluated_not_due(self) -> None:
        item = _monitored_item(last_revalidation=NOW.isoformat())
        store = _mock_store([item])
        sched = RevalidationScheduler(
            store, DeprecateLearningItemUseCase(store, _Clock()), _Clock(),
        )
        due = sched.get_due_items()
        assert len(due) == 0

    def test_old_evaluation_is_due(self) -> None:
        old = "2026-02-01T00:00:00+00:00"
        item = _monitored_item(last_revalidation=old)
        store = _mock_store([item])
        sched = RevalidationScheduler(
            store, DeprecateLearningItemUseCase(store, _Clock()), _Clock(),
        )
        due = sched.get_due_items()
        assert len(due) == 1


class TestRecordResult:
    def test_pass_updates_metadata(self) -> None:
        item = _monitored_item()
        store = _mock_store([item])
        sched = RevalidationScheduler(
            store, DeprecateLearningItemUseCase(store, _Clock()), _Clock(),
        )
        result = sched.record_result(item_id="LI-M001", score=0.95)
        assert result.passed is True
        assert result.action_taken == "passed"
        store.save_item.assert_called_once()

    def test_failure_records_without_deprecation(self) -> None:
        item = _monitored_item()
        store = _mock_store([item])
        sched = RevalidationScheduler(
            store, DeprecateLearningItemUseCase(store, _Clock()), _Clock(),
        )
        result = sched.record_result(item_id="LI-M001", score=0.5, threshold=0.9)
        assert result.passed is False
        assert result.action_taken == "failure_recorded"
