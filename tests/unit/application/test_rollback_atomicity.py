"""Atomicity tests for RollbackPromotionUseCase.

These tests guard the invariant that the two persisted artefacts of a
rollback — the deprecated :class:`LearningItem` and its matching
:class:`DeprecationRecord` — land in storage as a single logical unit.
If the deprecation record cannot be persisted, the item must NOT be left
in the ``deprecated`` status with no audit record (the "audit trail
split" described in the B11 probe evidence).

The suite mocks the store so we can inject a failure into the atomic
persistence call and observe the use case's behaviour in isolation
(no SQLite, no filesystem).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ds_agent.application.learning.rollback_promotion import (
    RollbackPromotionUseCase,
)
from ds_agent.application.ports.learning_store_port import LearningStoreAtomicPort
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
from ds_agent.domain.learning.promotion_record import PromotionRecord
from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore

NOW = datetime(2026, 4, 16, 10, 0, tzinfo=UTC)


@dataclass
class _Clock:
    def now(self) -> datetime:
        return NOW


def _promoted_item() -> LearningItem:
    return LearningItem(
        item_id="LI-A001",
        item_type=LearningItemType.KB_ENTRY,
        status=LearningItemStatus.PROMOTED,
        title="Promoted KB",
        content="Content",
        signature="sig:a001",
        source=SourceInfo(),
        created_at=NOW,
        updated_at=NOW,
    )


def _promotion_record() -> PromotionRecord:
    return PromotionRecord(
        record_id="PR-A01",
        item_id="LI-A001",
        item_type=LearningItemType.KB_ENTRY,
        eval_score=1.0,
        eval_threshold=1.0,
        promoted_asset_ref="domain_kb:a:b",
        rollback_ref="snapshot:A001",
        promoted_at=NOW,
    )


class TestRollbackAtomicity:
    """Regression tests for FAIL-B11-8 (atomicity split)."""

    def test_use_case_uses_atomic_write(self) -> None:
        """Happy path: the atomic port method is invoked with both artefacts.

        This documents the use case's new contract: a single call to
        ``save_item_and_deprecation`` replaces the two independent
        ``save_item`` / ``save_deprecation_record`` calls so the store can
        commit both rows inside one transaction.
        """
        store = MagicMock()
        store.get_item.return_value = _promoted_item()
        store.get_promotion_record.return_value = _promotion_record()

        uc = RollbackPromotionUseCase(store, _Clock())
        updated, dep_record = uc.execute(item_id="LI-A001", reason="unit test")

        # New atomic method is called exactly once with both artefacts.
        assert store.save_item_and_deprecation.call_count == 1
        call_kwargs = store.save_item_and_deprecation.call_args.kwargs
        call_args = store.save_item_and_deprecation.call_args.args
        # Support either positional or keyword passing:
        passed = {**dict(zip(("item", "deprecation"), call_args, strict=False)), **call_kwargs}
        assert isinstance(passed["item"], LearningItem)
        assert isinstance(passed["deprecation"], DeprecationRecord)
        assert passed["item"].status == LearningItemStatus.DEPRECATED
        assert passed["deprecation"].item_id == "LI-A001"

        # The old non-atomic pair must NOT be used directly.
        store.save_item.assert_not_called()
        store.save_deprecation_record.assert_not_called()

        # And the returned tuple is still (updated_item, dep_record).
        assert updated.status == LearningItemStatus.DEPRECATED
        assert dep_record.item_id == "LI-A001"

    def test_atomic_failure_raises_and_does_not_split_writes(self) -> None:
        """If the atomic write fails, the exception propagates and no
        separate partial write (item-only or record-only) has been made.

        Pre-fix, the use case called ``save_item`` then
        ``save_deprecation_record`` as two independent commits. Injecting
        a failure into the second left the item marked ``deprecated``
        without a matching DeprecationRecord (B11 probe evidence).
        """
        store = MagicMock()
        store.get_item.return_value = _promoted_item()
        store.get_promotion_record.return_value = _promotion_record()
        store.save_item_and_deprecation.side_effect = RuntimeError("injected")

        uc = RollbackPromotionUseCase(store, _Clock())

        with pytest.raises(RuntimeError, match="injected"):
            uc.execute(item_id="LI-A001", reason="inject")

        # The atomic method was attempted...
        assert store.save_item_and_deprecation.call_count == 1
        # ...but neither of the legacy single-row writers was called, so
        # there is no way to have produced a half-committed state from
        # the use case's side. (Storage-side atomicity is covered by the
        # integration test against SqliteLearningStore below.)
        store.save_item.assert_not_called()
        store.save_deprecation_record.assert_not_called()


class TestSqliteStoreAtomicity:
    """Storage-layer atomicity for ``save_item_and_deprecation``.

    These tests exercise the real :class:`SqliteLearningStore` adapter
    (against a ``tmp_path`` database — no production ``data/`` access)
    to verify the B11 probe invariant: when either of the two writes
    inside the atomic method fails, neither row is persisted.
    """

    def test_port_is_runtime_checkable_on_sqlite_store(self, tmp_path: Path) -> None:
        store = SqliteLearningStore(tmp_path / "atomic.db")
        assert isinstance(store, LearningStoreAtomicPort)

    def test_atomic_success_persists_both_rows(self, tmp_path: Path) -> None:
        store = SqliteLearningStore(tmp_path / "atomic_ok.db")
        item = LearningItem(
            item_id="LI-ATX",
            item_type=LearningItemType.KB_ENTRY,
            status=LearningItemStatus.DEPRECATED,
            title="Will be deprecated",
            content="c",
            signature="sig:atx",
            source=SourceInfo(),
            created_at=NOW,
            updated_at=NOW,
        )
        dep = DeprecationRecord(
            record_id="DR-ATX",
            item_id="LI-ATX",
            reason=DeprecationReason.MANUAL,
            mode=DeprecationMode.IMMEDIATE,
            deprecated_at=NOW,
        )
        store.save_item_and_deprecation(item=item, deprecation=dep)

        loaded_item = store.get_item("LI-ATX")
        loaded_dep = store.get_deprecation_record("LI-ATX")
        assert loaded_item is not None
        assert loaded_item.status == LearningItemStatus.DEPRECATED
        assert loaded_dep is not None
        assert loaded_dep.record_id == "DR-ATX"

    def test_atomic_failure_rolls_back_both_rows(self, tmp_path: Path) -> None:
        """Simulate a failure during the second INSERT inside the
        atomic method — exactly the scenario the B11 probe reproduced.

        Injection strategy: wrap ``store._conn`` in a thin proxy whose
        ``execute`` raises on any INSERT into ``deprecation_records``.
        Everything else (BEGIN, item INSERT, rollback, subsequent reads)
        delegates to the real connection so we observe the real
        transaction semantics.

        With the fix in place, the surrounding ``BEGIN IMMEDIATE`` ...
        ``ROLLBACK`` must leave the first INSERT uncommitted; both
        ``get_item`` and ``get_deprecation_record`` must return ``None``.
        Pre-fix (separate commits) the item would be persisted alone
        (the audit-trail-split state the probe captured).
        """
        store = SqliteLearningStore(tmp_path / "atomic_fail.db")
        item = LearningItem(
            item_id="LI-ROLLBK",
            item_type=LearningItemType.KB_ENTRY,
            status=LearningItemStatus.DEPRECATED,
            title="Rollback candidate",
            content="c",
            signature="sig:rollbk",
            source=SourceInfo(),
            created_at=NOW,
            updated_at=NOW,
        )
        dep = DeprecationRecord(
            record_id="DR-ROLLBK",
            item_id="LI-ROLLBK",
            reason=DeprecationReason.MANUAL,
            mode=DeprecationMode.IMMEDIATE,
            deprecated_at=NOW,
        )

        real_conn = store._conn

        class _FailingConn:
            """Pass-through proxy that fails the deprecation INSERT only."""

            def execute(self, sql: str, params: object = ()) -> object:
                stripped = sql.lstrip().upper()
                if "DEPRECATION_RECORDS" in sql.upper() and stripped.startswith(
                    ("INSERT", "REPLACE"),
                ):
                    raise RuntimeError("injected storage failure")
                return real_conn.execute(sql, params)

            def commit(self) -> None:
                real_conn.commit()

            def rollback(self) -> None:
                real_conn.rollback()

        try:
            store._conn = _FailingConn()  # type: ignore[assignment]
            with pytest.raises(RuntimeError, match="injected storage failure"):
                store.save_item_and_deprecation(item=item, deprecation=dep)
        finally:
            store._conn = real_conn

        # CRITICAL invariant: neither row must be persisted.
        assert store.get_item("LI-ROLLBK") is None, (
            "Item row leaked past a failed atomic write "
            "(B11 FAIL-B11-8 regression)"
        )
        assert store.get_deprecation_record("LI-ROLLBK") is None
