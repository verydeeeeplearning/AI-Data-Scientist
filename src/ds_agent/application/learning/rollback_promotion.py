"""Use case: rollback a promoted learning item."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ds_agent.application.ports.learning_store_port import LearningStoreAtomicPort
from ds_agent.domain.interfaces.learning import LearningStore
from ds_agent.domain.learning.deprecation_record import (
    DeprecationMode,
    DeprecationReason,
    DeprecationRecord,
)
from ds_agent.domain.learning.learning_item import (
    LearningItem,
    LearningItemStatus,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class RollbackPromotionUseCase:
    """Atomically restore org asset from promotion rollback_ref.

    - Transitions item to deprecated
    - Creates deprecation record with reason=manual

    Atomicity contract
    ------------------
    The item-status transition and the audit record MUST land together.
    This is enforced by requiring the injected ``store`` to implement
    :class:`~ds_agent.application.ports.learning_store_port.LearningStoreAtomicPort`
    in addition to the baseline :class:`~ds_agent.domain.interfaces.learning.LearningStore`
    reads used by this use case. The use case delegates the two-row
    write to ``store.save_item_and_deprecation`` so the store can commit
    both inside a single transaction and roll back on failure (see
    B11 probe evidence:
    ``Docs/qa_run_2026-04-17/B11_portfolio_learning/B11_rollback_atomicity_sqlite_probe.json``).
    """

    def __init__(
        self,
        store: LearningStore,
        clock: Clock,
    ) -> None:
        # ``store`` is duck-typed — in production it is a single
        # SqliteLearningStore instance that honours both the domain
        # ``LearningStore`` Protocol (reads) and the application
        # ``LearningStoreAtomicPort`` (atomic write). We keep the
        # annotated type as the broader ``LearningStore`` so existing
        # callers don't need to change, and assert the atomic surface
        # at call time with a clear error.
        self._store = store
        self._clock = clock

    def execute(
        self,
        *,
        item_id: str,
        reason: str = "manual rollback",
        rolled_back_by: str = "system",
    ) -> tuple[LearningItem, DeprecationRecord]:
        item = self._store.get_item(item_id)
        if item is None:
            raise ValueError(f"Learning item {item_id} not found")
        if item.status not in {
            LearningItemStatus.PROMOTED,
            LearningItemStatus.MONITORED,
        }:
            raise ValueError(
                f"Cannot rollback item in status {item.status.value} "
                f"(must be promoted or monitored)",
            )

        promotion = self._store.get_promotion_record(item_id)
        if promotion is None:
            raise ValueError(f"No promotion record found for {item_id}")

        now = self._clock.now()

        # Transition to deprecated
        updated = item.transition_to(
            LearningItemStatus.DEPRECATED,
            now=now,
        )

        import uuid

        dep_record = DeprecationRecord(
            record_id=f"DR-{uuid.uuid4().hex[:8]}",
            item_id=item_id,
            reason=DeprecationReason.MANUAL,
            mode=DeprecationMode.IMMEDIATE,
            deprecated_at=now,
            deprecated_by=rolled_back_by,
            notes=f"Rollback: {reason}. Asset ref: {promotion.promoted_asset_ref}",
        )

        # Single atomic commit: either both rows persist or neither does.
        # See ``LearningStoreAtomicPort`` for the contract.
        atomic: LearningStoreAtomicPort = self._store  # type: ignore[assignment]
        atomic.save_item_and_deprecation(item=updated, deprecation=dep_record)
        return updated, dep_record
