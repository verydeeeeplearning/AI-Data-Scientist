"""Tests for learning inbox use case (priority scoring, filtering, dedup)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from ds_agent.application.learning.learning_inbox import (
    LearningInboxUseCase,
)
from ds_agent.domain.learning.learning_item import (
    ConflictRef,
    Evidence,
    LearningItem,
    LearningItemStatus,
    LearningItemType,
    SourceInfo,
)

NOW = datetime(2026, 4, 16, 10, 0, tzinfo=UTC)


@dataclass
class _MockClock:
    now_value: datetime = NOW

    def now(self) -> datetime:
        return self.now_value


def _make_item(
    item_id: str = "LI-001",
    *,
    evidence_count: int = 0,
    has_conflict: bool = False,
    scope: str = "project",
    age_days: float = 0,
) -> LearningItem:
    evidence = [
        Evidence(
            metric_name="acc",
            metric_value=0.9,
            project_id="p1",
            recorded_at=NOW,
        )
        for _ in range(evidence_count)
    ]
    conflicts = (
        [ConflictRef(conflicting_item_id="LI-other", resolved=False)]
        if has_conflict
        else []
    )
    created = NOW - timedelta(days=age_days)
    return LearningItem(
        item_id=item_id,
        item_type=LearningItemType.KB_ENTRY,
        status=LearningItemStatus.PROPOSED,
        title=f"Item {item_id}",
        content="content",
        signature=f"sig:{item_id}",
        source=SourceInfo(),
        evidence=evidence,
        conflict_refs=conflicts,
        scope=scope,
        created_at=created,
        updated_at=created,
    )


def _mock_store(items: list[LearningItem]) -> MagicMock:
    store = MagicMock()

    def list_items(*, status=None, item_type=None, limit=50):
        return [
            i
            for i in items
            if (status is None or i.status == status)
            and (item_type is None or i.item_type == item_type)
        ][:limit]

    store.list_items = list_items
    return store


class TestPriorityScoring:
    def test_max_score_item(self) -> None:
        """3+ evidence, conflict, global scope, 30+ days old -> max."""
        item = _make_item(
            "LI-MAX",
            evidence_count=3,
            has_conflict=True,
            scope="global",
            age_days=30,
        )
        uc = LearningInboxUseCase(_mock_store([item]), _MockClock())
        result = uc.execute()
        assert len(result) == 1
        assert result[0].priority_score == pytest.approx(1.0, abs=0.01)

    def test_min_score_item(self) -> None:
        """0 evidence, no conflict, project scope, 0 days old."""
        item = _make_item("LI-MIN", evidence_count=0, scope="project", age_days=0)
        uc = LearningInboxUseCase(_mock_store([item]), _MockClock())
        result = uc.execute()
        assert len(result) == 1
        assert result[0].priority_score < 0.1

    def test_sorting_descending(self) -> None:
        high = _make_item("LI-H", evidence_count=3, has_conflict=True, scope="global", age_days=30)
        low = _make_item("LI-L", evidence_count=0, scope="project", age_days=0)
        uc = LearningInboxUseCase(_mock_store([low, high]), _MockClock())
        result = uc.execute()
        assert result[0].item.item_id == "LI-H"
        assert result[1].item.item_id == "LI-L"

    def test_deterministic(self) -> None:
        """Same input always produces same score."""
        item = _make_item("LI-DET", evidence_count=2, scope="domain", age_days=15)
        uc = LearningInboxUseCase(_mock_store([item]), _MockClock())
        r1 = uc.execute()
        r2 = uc.execute()
        assert r1[0].priority_score == r2[0].priority_score


class TestFiltering:
    def test_default_statuses(self) -> None:
        proposed = _make_item("LI-P")
        approved = LearningItem(
            item_id="LI-A",
            item_type=LearningItemType.KB_ENTRY,
            status=LearningItemStatus.APPROVED,
            title="Approved",
            content="c",
            signature="sig:A",
            created_at=NOW,
            updated_at=NOW,
        )
        uc = LearningInboxUseCase(_mock_store([proposed, approved]), _MockClock())
        result = uc.execute()
        ids = {s.item.item_id for s in result}
        assert "LI-P" in ids
        assert "LI-A" not in ids

    def test_type_filter(self) -> None:
        kb = _make_item("LI-KB")
        uc = LearningInboxUseCase(_mock_store([kb]), _MockClock())
        result = uc.execute(item_type_filter=LearningItemType.CUSTOM_SKILL)
        assert len(result) == 0
