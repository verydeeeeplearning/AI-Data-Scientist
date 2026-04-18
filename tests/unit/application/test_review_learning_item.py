"""Tests for review learning item use case."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from ds_agent.application.learning.review_learning_item import (
    ReviewLearningItemUseCase,
)
from ds_agent.domain.learning.learning_item import (
    ConflictRef,
    LearningItem,
    LearningItemStatus,
    LearningItemType,
    SourceInfo,
)
from ds_agent.domain.learning.review_event import (
    ReviewChecklist,
    ReviewDecision,
)

NOW = datetime(2026, 4, 16, 10, 0, tzinfo=UTC)


@dataclass
class _MockClock:
    now_value: datetime = NOW

    def now(self) -> datetime:
        return self.now_value


def _make_item(
    status: LearningItemStatus = LearningItemStatus.PROPOSED,
    item_type: LearningItemType = LearningItemType.KB_ENTRY,
    review_count: int = 0,
    conflict_refs: list[ConflictRef] | None = None,
) -> LearningItem:
    return LearningItem(
        item_id="LI-review-001",
        item_type=item_type,
        status=status,
        title="Test item",
        content="Test content",
        signature="test:review:001",
        source=SourceInfo(),
        review_count=review_count,
        conflict_refs=conflict_refs or [],
        created_at=NOW,
        updated_at=NOW,
    )


def _mock_store(item: LearningItem | None) -> MagicMock:
    store = MagicMock()
    store.get_item.return_value = item
    return store


FULL_CHECKLIST = ReviewChecklist(
    evidence_sufficient=True,
    no_unresolved_conflicts=True,
    scope_appropriate=True,
    content_accurate=True,
    second_reviewer_if_required=True,
)


class TestApproveFlow:
    def test_approve_kb_entry_proposed(self) -> None:
        """KB entry (no second reviewer needed) goes proposed→approved."""
        item = _make_item()
        store = _mock_store(item)
        uc = ReviewLearningItemUseCase(store, _MockClock())
        updated, event = uc.execute(
            item_id="LI-review-001",
            decision=ReviewDecision.APPROVE,
            reviewer="operator",
            checklist=FULL_CHECKLIST,
        )
        assert updated.status == LearningItemStatus.APPROVED
        assert updated.review_count >= 1
        assert event.decision == ReviewDecision.APPROVE

    def test_approve_custom_skill_needs_second_review(self) -> None:
        """Custom skill stays under_review after first approve."""
        item = _make_item(item_type=LearningItemType.CUSTOM_SKILL)
        store = _mock_store(item)
        uc = ReviewLearningItemUseCase(store, _MockClock())
        updated, _ = uc.execute(
            item_id="LI-review-001",
            decision=ReviewDecision.APPROVE,
            reviewer="reviewer1",
            checklist=FULL_CHECKLIST,
        )
        assert updated.status == LearningItemStatus.UNDER_REVIEW

    def test_second_approve_promotes_custom_skill(self) -> None:
        """Custom skill with review_count=1 goes to approved on second review."""
        item = _make_item(
            status=LearningItemStatus.UNDER_REVIEW,
            item_type=LearningItemType.CUSTOM_SKILL,
            review_count=1,
        )
        store = _mock_store(item)
        uc = ReviewLearningItemUseCase(store, _MockClock())
        updated, _ = uc.execute(
            item_id="LI-review-001",
            decision=ReviewDecision.APPROVE,
            reviewer="reviewer2",
            checklist=FULL_CHECKLIST,
        )
        assert updated.status == LearningItemStatus.APPROVED

    def test_approve_with_incomplete_checklist_fails(self) -> None:
        item = _make_item()
        store = _mock_store(item)
        uc = ReviewLearningItemUseCase(store, _MockClock())
        bad_checklist = ReviewChecklist(evidence_sufficient=False)
        with pytest.raises(ValueError, match="checklist"):
            uc.execute(
                item_id="LI-review-001",
                decision=ReviewDecision.APPROVE,
                checklist=bad_checklist,
            )


class TestModifyFlow:
    def test_modify_keeps_under_review(self) -> None:
        item = _make_item(status=LearningItemStatus.PROPOSED)
        store = _mock_store(item)
        uc = ReviewLearningItemUseCase(store, _MockClock())
        updated, event = uc.execute(
            item_id="LI-review-001",
            decision=ReviewDecision.MODIFY,
            modifications={"title": "Updated title"},
        )
        assert updated.status == LearningItemStatus.UNDER_REVIEW
        assert updated.title == "Updated title"
        assert event.decision == ReviewDecision.MODIFY


class TestRejectFlow:
    def test_reject_proposed(self) -> None:
        item = _make_item()
        store = _mock_store(item)
        uc = ReviewLearningItemUseCase(store, _MockClock())
        updated, event = uc.execute(
            item_id="LI-review-001",
            decision=ReviewDecision.REJECT,
            comment="Not useful",
        )
        assert updated.status == LearningItemStatus.REJECTED
        assert event.comment == "Not useful"

    def test_reject_approved_fails(self) -> None:
        item = _make_item(status=LearningItemStatus.APPROVED)
        store = _mock_store(item)
        uc = ReviewLearningItemUseCase(store, _MockClock())
        with pytest.raises(ValueError, match="Cannot reject"):
            uc.execute(
                item_id="LI-review-001",
                decision=ReviewDecision.REJECT,
            )


class TestNotFound:
    def test_item_not_found(self) -> None:
        store = _mock_store(None)
        uc = ReviewLearningItemUseCase(store, _MockClock())
        with pytest.raises(ValueError, match="not found"):
            uc.execute(item_id="LI-NOPE", decision=ReviewDecision.APPROVE)
