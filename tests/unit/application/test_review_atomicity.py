"""Atomicity tests for ReviewLearningItemUseCase (S10 / R-3).

Guards the invariant that a ``ReviewEvent`` is never durably persisted
while the corresponding ``LearningItem`` state transition is lost. The
review-event stream is append-only evidence; losing the item transition
would leave readers unable to reconstruct "why is this item in state X
even though reviewer decided Y" from storage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ds_agent.application.learning.review_learning_item import (
    ReviewLearningItemUseCase,
)
from ds_agent.application.ports.learning_store_port import LearningStoreAtomicPort
from ds_agent.domain.learning.learning_item import (
    LearningItem,
    LearningItemStatus,
    LearningItemType,
    SourceInfo,
)
from ds_agent.domain.learning.review_event import (
    ReviewDecision,
    ReviewEvent,
)
from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore

NOW = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)


@dataclass
class _Clock:
    def now(self) -> datetime:
        return NOW


def _proposed_item() -> LearningItem:
    return LearningItem(
        item_id="LI-R001",
        item_type=LearningItemType.KB_ENTRY,
        status=LearningItemStatus.PROPOSED,
        title="Proposed KB",
        content="Content",
        signature="sig:r001",
        source=SourceInfo(),
        requires_second_reviewer=False,
        created_at=NOW,
        updated_at=NOW,
    )


class TestReviewAtomicity:
    """Use-case-level atomicity guard for R-3."""

    def test_use_case_uses_atomic_port(self) -> None:
        store = MagicMock()
        store.get_item.return_value = _proposed_item()

        uc = ReviewLearningItemUseCase(store, _Clock())
        updated, event = uc.execute(
            item_id="LI-R001",
            decision=ReviewDecision.APPROVE,
            reviewer="alice",
        )

        assert store.save_review_event_and_item.call_count == 1
        kwargs = store.save_review_event_and_item.call_args.kwargs
        assert isinstance(kwargs["event"], ReviewEvent)
        assert isinstance(kwargs["item"], LearningItem)
        assert kwargs["item"].item_id == "LI-R001"
        assert kwargs["event"].decision == ReviewDecision.APPROVE

        # Legacy single-row writers must NOT fire.
        store.save_review_event.assert_not_called()
        store.save_item.assert_not_called()

        assert updated.item_id == "LI-R001"
        assert event.reviewer == "alice"

    def test_atomic_failure_propagates_without_split_writes(self) -> None:
        store = MagicMock()
        store.get_item.return_value = _proposed_item()
        store.save_review_event_and_item.side_effect = RuntimeError("injected")

        uc = ReviewLearningItemUseCase(store, _Clock())

        with pytest.raises(RuntimeError, match="injected"):
            uc.execute(
                item_id="LI-R001",
                decision=ReviewDecision.APPROVE,
                reviewer="alice",
            )

        assert store.save_review_event_and_item.call_count == 1
        store.save_review_event.assert_not_called()
        store.save_item.assert_not_called()


class TestSqliteReviewAtomicity:
    """Storage-level atomicity for save_review_event_and_item."""

    def test_port_is_runtime_checkable_on_sqlite_store(self, tmp_path: Path) -> None:
        store = SqliteLearningStore(tmp_path / "review_atomic.db")
        assert isinstance(store, LearningStoreAtomicPort)

    def test_atomic_success_persists_both_rows(self, tmp_path: Path) -> None:
        store = SqliteLearningStore(tmp_path / "review_ok.db")

        # Pre-seed the item (ReviewLearningItemUseCase reads by id first).
        seed_item = _proposed_item()
        store.save_item(seed_item)

        transitioned = seed_item.transition_to(
            LearningItemStatus.UNDER_REVIEW,
            now=NOW,
        ).transition_to(
            LearningItemStatus.APPROVED,
            now=NOW,
        )
        event = ReviewEvent(
            event_id="RE-SR1",
            item_id=seed_item.item_id,
            decision=ReviewDecision.APPROVE,
            reviewer="alice",
            created_at=NOW,
        )
        store.save_review_event_and_item(event=event, item=transitioned)

        loaded = store.get_item(seed_item.item_id)
        assert loaded is not None
        assert loaded.status == LearningItemStatus.APPROVED
        events = store.list_review_events(seed_item.item_id)
        assert len(events) == 1
        assert events[0].event_id == "RE-SR1"

    def test_atomic_failure_rolls_back_both_rows(self, tmp_path: Path) -> None:
        """Inject failure on the second INSERT (learning_items)."""
        store = SqliteLearningStore(tmp_path / "review_fail.db")
        seed = _proposed_item()
        store.save_item(seed)

        transitioned = seed.transition_to(
            LearningItemStatus.UNDER_REVIEW,
            now=NOW,
        ).transition_to(
            LearningItemStatus.APPROVED,
            now=NOW,
        )
        event = ReviewEvent(
            event_id="RE-SR2",
            item_id=seed.item_id,
            decision=ReviewDecision.APPROVE,
            reviewer="alice",
            created_at=NOW,
        )

        real_conn = store._conn

        class _FailingConn:
            """Fail the learning_items upsert only (S6 proxy pattern)."""

            def execute(self, sql: str, params: object = ()) -> object:
                stripped = sql.lstrip().upper()
                if "LEARNING_ITEMS" in sql.upper() and stripped.startswith(
                    ("INSERT", "REPLACE"),
                ):
                    raise RuntimeError("injected on item insert")
                return real_conn.execute(sql, params)

            def commit(self) -> None:
                real_conn.commit()

            def rollback(self) -> None:
                real_conn.rollback()

        try:
            store._conn = _FailingConn()  # type: ignore[assignment]
            with pytest.raises(RuntimeError, match="injected on item insert"):
                store.save_review_event_and_item(event=event, item=transitioned)
        finally:
            store._conn = real_conn

        # Pre-seeded item must remain in its original PROPOSED state,
        # and the injected review event must NOT be persisted.
        loaded = store.get_item(seed.item_id)
        assert loaded is not None
        assert loaded.status == LearningItemStatus.PROPOSED, (
            "Item status leaked from a failed atomic review write (R-3 regression)"
        )
        events = store.list_review_events(seed.item_id)
        assert not events, (
            "ReviewEvent row leaked past a failed atomic write (R-3 regression)"
        )
