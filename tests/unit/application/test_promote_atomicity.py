"""Atomicity tests for PromoteLearningItemUseCase (S9 / R-1).

Guards the invariant that a ``PromotionRecord`` is never durably
persisted while the referenced ``LearningItem`` still sits in the
``approved`` state. Pre-fix, the use case called
``save_promotion_record`` and ``save_item`` as two independent commits;
if the second failed, a reader could observe a PromotionRecord pointing
to a still-``approved`` item (the "phantom-promotion audit split"
described in S6 RECOMMENDATIONS §R-1).

Two layers of coverage:
- ``TestPromoteAtomicity``: use-case level (mocked store).
- ``TestSqlitePromoteAtomicity``: storage-level rollback against the
  real ``SqliteLearningStore`` on a ``tmp_path`` database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ds_agent.application.learning.promote_learning_item import (
    PromoteLearningItemUseCase,
)
from ds_agent.application.ports.learning_store_port import LearningStoreAtomicPort
from ds_agent.domain.learning.learning_item import (
    LearningItem,
    LearningItemStatus,
    LearningItemType,
    SourceInfo,
)
from ds_agent.domain.learning.promotion_record import PromotionRecord
from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore

NOW = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)


@dataclass
class _Clock:
    def now(self) -> datetime:
        return NOW


def _approved_item() -> LearningItem:
    return LearningItem(
        item_id="LI-P001",
        item_type=LearningItemType.KB_ENTRY,
        status=LearningItemStatus.APPROVED,
        title="Approved KB",
        content="Content",
        signature="sig:p001",
        source=SourceInfo(),
        created_at=NOW,
        updated_at=NOW,
    )


class TestPromoteAtomicity:
    """Use-case-level atomicity guard for R-1."""

    def test_use_case_calls_atomic_port(self) -> None:
        """Promote path must dispatch to save_promotion_and_item."""
        store = MagicMock()
        store.get_item.return_value = _approved_item()

        uc = PromoteLearningItemUseCase(store, _Clock())
        record = uc.execute(item_id="LI-P001", eval_score=1.0)

        assert store.save_promotion_and_item.call_count == 1
        kwargs = store.save_promotion_and_item.call_args.kwargs
        assert isinstance(kwargs["promotion"], PromotionRecord)
        assert isinstance(kwargs["item"], LearningItem)
        assert kwargs["item"].status == LearningItemStatus.PROMOTED
        assert kwargs["promotion"].item_id == "LI-P001"

        # The old non-atomic pair must NOT be used.
        store.save_promotion_record.assert_not_called()
        store.save_item.assert_not_called()

        # Return value preserved.
        assert record.item_id == "LI-P001"

    def test_atomic_failure_propagates_without_split_writes(self) -> None:
        """Injected failure must raise; no legacy single-row writer was used."""
        store = MagicMock()
        store.get_item.return_value = _approved_item()
        store.save_promotion_and_item.side_effect = RuntimeError("injected")

        uc = PromoteLearningItemUseCase(store, _Clock())

        with pytest.raises(RuntimeError, match="injected"):
            uc.execute(item_id="LI-P001", eval_score=1.0)

        assert store.save_promotion_and_item.call_count == 1
        store.save_promotion_record.assert_not_called()
        store.save_item.assert_not_called()


class TestSqlitePromoteAtomicity:
    """Storage-level atomicity for save_promotion_and_item."""

    def test_port_is_runtime_checkable_on_sqlite_store(self, tmp_path: Path) -> None:
        store = SqliteLearningStore(tmp_path / "promote_atomic.db")
        assert isinstance(store, LearningStoreAtomicPort)

    def test_atomic_success_persists_both_rows(self, tmp_path: Path) -> None:
        store = SqliteLearningStore(tmp_path / "promote_ok.db")
        item = LearningItem(
            item_id="LI-SP1",
            item_type=LearningItemType.KB_ENTRY,
            status=LearningItemStatus.PROMOTED,
            title="Promoted now",
            content="c",
            signature="sig:sp1",
            source=SourceInfo(),
            created_at=NOW,
            updated_at=NOW,
        )
        promotion = PromotionRecord(
            record_id="PR-SP1",
            item_id="LI-SP1",
            item_type=LearningItemType.KB_ENTRY,
            eval_score=1.0,
            eval_threshold=1.0,
            promoted_at=NOW,
        )
        store.save_promotion_and_item(promotion=promotion, item=item)

        loaded_item = store.get_item("LI-SP1")
        loaded_promotion = store.get_promotion_record("LI-SP1")
        assert loaded_item is not None
        assert loaded_item.status == LearningItemStatus.PROMOTED
        assert loaded_promotion is not None
        assert loaded_promotion.record_id == "PR-SP1"

    def test_atomic_failure_rolls_back_both_rows(self, tmp_path: Path) -> None:
        """Simulate failure on the second INSERT (learning_items).

        The surrounding BEGIN IMMEDIATE ... ROLLBACK must leave the first
        INSERT uncommitted; neither row is observable post-failure.
        """
        store = SqliteLearningStore(tmp_path / "promote_fail.db")

        item = LearningItem(
            item_id="LI-SP2",
            item_type=LearningItemType.KB_ENTRY,
            status=LearningItemStatus.PROMOTED,
            title="Would-be promoted",
            content="c",
            signature="sig:sp2",
            source=SourceInfo(),
            created_at=NOW,
            updated_at=NOW,
        )
        promotion = PromotionRecord(
            record_id="PR-SP2",
            item_id="LI-SP2",
            item_type=LearningItemType.KB_ENTRY,
            eval_score=1.0,
            eval_threshold=1.0,
            promoted_at=NOW,
        )

        real_conn = store._conn

        class _FailingConn:
            """Proxy connection that fails the learning_items INSERT only.

            Mirrors the S6 ``test_rollback_atomicity._FailingConn`` pattern —
            `sqlite3.Connection.execute` is read-only so we swap the whole
            connection with a passthrough proxy for the duration of the test.
            """

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
                store.save_promotion_and_item(promotion=promotion, item=item)
        finally:
            store._conn = real_conn

        # CRITICAL invariant: neither row must be persisted.
        assert store.get_item("LI-SP2") is None, (
            "Item row leaked past a failed atomic write (R-1 regression)"
        )
        assert store.get_promotion_record("LI-SP2") is None, (
            "Promotion row leaked past a failed atomic write (R-1 regression)"
        )
