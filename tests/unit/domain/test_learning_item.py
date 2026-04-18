"""Tests for learning item domain entity and state machine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ds_agent.domain.learning.learning_item import (
    ConflictRef,
    Evidence,
    LearningItem,
    LearningItemStatus,
    LearningItemType,
    SourceInfo,
    can_transition,
)

NOW = datetime(2026, 4, 16, 10, 0, tzinfo=UTC)


def _make_item(
    *,
    status: LearningItemStatus = LearningItemStatus.PROPOSED,
    item_type: LearningItemType = LearningItemType.KB_ENTRY,
    review_count: int = 0,
    conflict_refs: list[ConflictRef] | None = None,
) -> LearningItem:
    return LearningItem(
        item_id="LI-test001",
        item_type=item_type,
        status=status,
        title="Test learning item",
        content="Some extracted knowledge",
        signature="test:sig:001",
        source=SourceInfo(source_type="manual"),
        review_count=review_count,
        conflict_refs=conflict_refs or [],
        created_at=NOW,
        updated_at=NOW,
    )


class TestStateMachine:
    """Test all valid and forbidden transitions."""

    @pytest.mark.parametrize(
        ("from_s", "to_s", "allowed"),
        [
            # proposed
            ("proposed", "under_review", True),
            ("proposed", "archived", True),
            ("proposed", "approved", False),
            ("proposed", "promoted", False),
            ("proposed", "rejected", False),
            ("proposed", "monitored", False),
            # under_review
            ("under_review", "approved", True),
            ("under_review", "rejected", True),
            ("under_review", "proposed", False),
            ("under_review", "promoted", False),
            # approved
            ("approved", "promoted", True),
            ("approved", "archived", True),
            ("approved", "proposed", False),
            ("approved", "rejected", False),
            # rejected
            ("rejected", "proposed", True),
            ("rejected", "archived", True),
            ("rejected", "approved", False),
            ("rejected", "promoted", False),
            # promoted
            ("promoted", "monitored", True),
            ("promoted", "deprecated", True),
            ("promoted", "archived", True),
            ("promoted", "proposed", False),
            # monitored
            ("monitored", "promoted", True),
            ("monitored", "deprecated", True),
            ("monitored", "archived", True),
            ("monitored", "proposed", False),
            # deprecated
            ("deprecated", "archived", True),
            ("deprecated", "proposed", False),
            ("deprecated", "promoted", False),
            # archived (terminal)
            ("archived", "proposed", False),
            ("archived", "under_review", False),
            ("archived", "approved", False),
            ("archived", "promoted", False),
        ],
    )
    def test_transition_table(self, from_s: str, to_s: str, allowed: bool) -> None:
        result = can_transition(
            LearningItemStatus(from_s),
            LearningItemStatus(to_s),
        )
        expected = "allowed" if allowed else "forbidden"
        assert result == allowed, f"{from_s} -> {to_s} should be {expected}"

    def test_valid_transition_returns_new_item(self) -> None:
        item = _make_item()
        updated = item.transition_to(LearningItemStatus.UNDER_REVIEW, now=NOW + timedelta(hours=1))
        assert updated.status == LearningItemStatus.UNDER_REVIEW
        assert updated.updated_at == NOW + timedelta(hours=1)

    def test_forbidden_transition_raises(self) -> None:
        item = _make_item()
        with pytest.raises(ValueError, match="not allowed"):
            item.transition_to(LearningItemStatus.PROMOTED, now=NOW)

    def test_archived_is_terminal(self) -> None:
        item = _make_item(status=LearningItemStatus.ARCHIVED)
        for target in LearningItemStatus:
            if target == LearningItemStatus.ARCHIVED:
                continue
            with pytest.raises(ValueError, match="not allowed"):
                item.transition_to(target, now=NOW)


class TestInvariants:
    def test_frozen_model(self) -> None:
        item = _make_item()
        with pytest.raises(ValidationError):
            item.status = LearningItemStatus.APPROVED  # type: ignore[misc]

    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            LearningItem(
                item_id="",
                item_type=LearningItemType.KB_ENTRY,
                title="t",
                content="c",
                signature="s",
                created_at=NOW,
                updated_at=NOW,
            )

    def test_has_unresolved_conflicts(self) -> None:
        item = _make_item(
            conflict_refs=[
                ConflictRef(conflicting_item_id="LI-other", resolved=False),
            ],
        )
        assert item.has_unresolved_conflicts

    def test_no_unresolved_conflicts(self) -> None:
        item = _make_item(
            conflict_refs=[
                ConflictRef(conflicting_item_id="LI-other", resolved=True),
            ],
        )
        assert not item.has_unresolved_conflicts


class TestSecondReviewer:
    def test_custom_skill_requires_second_reviewer(self) -> None:
        item = _make_item(item_type=LearningItemType.CUSTOM_SKILL)
        assert item.requires_second_reviewer

    def test_kb_entry_no_second_reviewer(self) -> None:
        item = _make_item(item_type=LearningItemType.KB_ENTRY)
        assert not item.requires_second_reviewer

    def test_unresolved_conflict_requires_second_reviewer(self) -> None:
        item = _make_item(
            conflict_refs=[
                ConflictRef(conflicting_item_id="LI-other", resolved=False),
            ],
        )
        assert item.requires_second_reviewer


class TestEvidence:
    def test_evidence_creation(self) -> None:
        e = Evidence(
            metric_name="accuracy",
            metric_value=0.95,
            project_id="proj-1",
            recorded_at=NOW,
        )
        assert e.metric_value == 0.95

    def test_source_info_defaults(self) -> None:
        s = SourceInfo()
        assert s.source_type == "manual"
        assert s.project_id is None
