"""Integration tests for SqliteLearningStore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ds_agent.domain.learning.deprecation_record import (
    DeprecationMode,
    DeprecationReason,
    DeprecationRecord,
)
from ds_agent.domain.learning.learning_item import (
    Evidence,
    LearningItem,
    LearningItemStatus,
    LearningItemType,
    SourceInfo,
)
from ds_agent.domain.learning.promotion_record import PromotionRecord
from ds_agent.domain.learning.review_event import (
    ReviewChecklist,
    ReviewDecision,
    ReviewEvent,
)
from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore

NOW = datetime(2026, 4, 16, 10, 0, tzinfo=UTC)


@pytest.fixture()
def store(tmp_path: Path) -> SqliteLearningStore:
    return SqliteLearningStore(tmp_path / "test_learning.db")


def _kb_item(item_id: str = "LI-001", signature: str = "sig:001") -> LearningItem:
    return LearningItem(
        item_id=item_id,
        item_type=LearningItemType.KB_ENTRY,
        status=LearningItemStatus.PROPOSED,
        title="Test KB entry",
        content="Some knowledge",
        signature=signature,
        source=SourceInfo(source_type="post_project", project_id="proj-1"),
        evidence=[
            Evidence(metric_name="acc", metric_value=0.9, project_id="proj-1", recorded_at=NOW),
        ],
        tags=["churn"],
        scope="domain",
        created_at=NOW,
        updated_at=NOW,
    )


class TestLearningItemCRUD:
    def test_save_and_get(self, store: SqliteLearningStore) -> None:
        item = _kb_item()
        store.save_item(item)
        loaded = store.get_item("LI-001")
        assert loaded is not None
        assert loaded.item_id == "LI-001"
        assert loaded.item_type == LearningItemType.KB_ENTRY
        assert loaded.status == LearningItemStatus.PROPOSED
        assert loaded.tags == ["churn"]
        assert loaded.scope == "domain"
        assert len(loaded.evidence) == 1

    def test_get_nonexistent(self, store: SqliteLearningStore) -> None:
        assert store.get_item("LI-NOPE") is None

    def test_find_by_signature(self, store: SqliteLearningStore) -> None:
        store.save_item(_kb_item())
        found = store.find_by_signature("sig:001")
        assert found is not None
        assert found.item_id == "LI-001"

    def test_find_by_signature_not_found(self, store: SqliteLearningStore) -> None:
        assert store.find_by_signature("nope") is None

    def test_list_by_status(self, store: SqliteLearningStore) -> None:
        store.save_item(_kb_item("LI-A", "sig:A"))
        store.save_item(
            LearningItem(
                item_id="LI-B",
                item_type=LearningItemType.PATTERN,
                status=LearningItemStatus.APPROVED,
                title="Approved",
                content="c",
                signature="sig:B",
                created_at=NOW,
                updated_at=NOW,
            ),
        )
        proposed = store.list_items(status=LearningItemStatus.PROPOSED)
        assert len(proposed) == 1
        assert proposed[0].item_id == "LI-A"

    def test_list_by_type(self, store: SqliteLearningStore) -> None:
        store.save_item(_kb_item("LI-KB", "sig:KB"))
        items = store.list_items(item_type=LearningItemType.KB_ENTRY)
        assert len(items) == 1

    def test_update_item(self, store: SqliteLearningStore) -> None:
        item = _kb_item()
        store.save_item(item)
        updated = item.model_copy(
            update={"status": LearningItemStatus.UNDER_REVIEW, "review_count": 1},
        )
        store.save_item(updated)
        loaded = store.get_item("LI-001")
        assert loaded is not None
        assert loaded.status == LearningItemStatus.UNDER_REVIEW
        assert loaded.review_count == 1


class TestReviewEvents:
    def test_save_and_list(self, store: SqliteLearningStore) -> None:
        event = ReviewEvent(
            event_id="RE-001",
            item_id="LI-001",
            decision=ReviewDecision.APPROVE,
            reviewer="operator",
            checklist=ReviewChecklist(
                evidence_sufficient=True,
                no_unresolved_conflicts=True,
                scope_appropriate=True,
                content_accurate=True,
            ),
            comment="LGTM",
            created_at=NOW,
        )
        store.save_review_event(event)
        events = store.list_review_events("LI-001")
        assert len(events) == 1
        assert events[0].decision == ReviewDecision.APPROVE
        assert events[0].checklist is not None
        assert events[0].checklist.evidence_sufficient is True


class TestPromotionRecords:
    def test_save_and_get(self, store: SqliteLearningStore) -> None:
        record = PromotionRecord(
            record_id="PR-001",
            item_id="LI-001",
            item_type=LearningItemType.KB_ENTRY,
            eval_score=0.95,
            eval_threshold=1.0,
            promoted_asset_ref="domain_kb:churn:ltv",
            rollback_ref="snapshot:001",
            promoted_at=NOW,
        )
        store.save_promotion_record(record)
        loaded = store.get_promotion_record("LI-001")
        assert loaded is not None
        assert loaded.eval_score == 0.95
        assert loaded.rollback_ref == "snapshot:001"

    def test_list_records(self, store: SqliteLearningStore) -> None:
        store.save_promotion_record(
            PromotionRecord(
                record_id="PR-A",
                item_id="LI-A",
                item_type=LearningItemType.PATTERN,
                eval_score=1.0,
                eval_threshold=1.0,
                promoted_at=NOW,
            ),
        )
        records = store.list_promotion_records()
        assert len(records) == 1


class TestDeprecationRecords:
    def test_save_and_get(self, store: SqliteLearningStore) -> None:
        record = DeprecationRecord(
            record_id="DR-001",
            item_id="LI-001",
            reason=DeprecationReason.EVAL_FAILURE,
            mode=DeprecationMode.IMMEDIATE,
            failure_count=2,
            deprecated_at=NOW,
            notes="2 consecutive failures",
        )
        store.save_deprecation_record(record)
        loaded = store.get_deprecation_record("LI-001")
        assert loaded is not None
        assert loaded.reason == DeprecationReason.EVAL_FAILURE
        assert loaded.failure_count == 2

    def test_grace_mode(self, store: SqliteLearningStore) -> None:
        grace_until = NOW + timedelta(days=14)
        record = DeprecationRecord(
            record_id="DR-G",
            item_id="LI-G",
            reason=DeprecationReason.MANUAL,
            mode=DeprecationMode.GRACE,
            grace_until=grace_until,
            deprecated_at=NOW,
        )
        store.save_deprecation_record(record)
        loaded = store.get_deprecation_record("LI-G")
        assert loaded is not None
        assert loaded.mode == DeprecationMode.GRACE
        assert loaded.grace_until == grace_until


class TestMigrationIdempotency:
    def test_double_init(self, tmp_path: Path) -> None:
        db_path = tmp_path / "idempotent.db"
        store1 = SqliteLearningStore(db_path)
        store1.save_item(_kb_item())
        store2 = SqliteLearningStore(db_path)
        loaded = store2.get_item("LI-001")
        assert loaded is not None
