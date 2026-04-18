"""Use case: deprecate a promoted/monitored learning item."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Protocol

from ds_agent.application.ports.learning_store_port import LearningStoreAtomicPort
from ds_agent.domain.interfaces.learning import LearningStore
from ds_agent.domain.learning.deprecation_record import (
    DeprecationMode,
    DeprecationReason,
    DeprecationRecord,
)
from ds_agent.domain.learning.learning_item import (
    LearningItemStatus,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class DeprecateLearningItemUseCase:
    """Deprecate a promoted or monitored learning item.

    Immediate mode: transitions to deprecated right away.
    Grace mode: sets grace_until, keeps current status until grace expires.
    Auto-deprecation: 2 consecutive eval failures trigger immediate deprecation.
    """

    def __init__(self, store: LearningStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def execute(
        self,
        *,
        item_id: str,
        reason: DeprecationReason,
        mode: DeprecationMode = DeprecationMode.IMMEDIATE,
        grace_days: int = 14,
        notes: str = "",
        deprecated_by: str = "system",
    ) -> DeprecationRecord:
        item = self._store.get_item(item_id)
        if item is None:
            raise ValueError(f"Learning item {item_id} not found")
        if item.status not in {
            LearningItemStatus.PROMOTED,
            LearningItemStatus.MONITORED,
        }:
            raise ValueError(
                f"Cannot deprecate item in status {item.status.value} "
                f"(must be promoted or monitored)",
            )

        now = self._clock.now()
        grace_until = (
            now + timedelta(days=grace_days)
            if mode == DeprecationMode.GRACE
            else None
        )

        record = DeprecationRecord(
            record_id=f"DR-{uuid.uuid4().hex[:8]}",
            item_id=item_id,
            reason=reason,
            mode=mode,
            grace_until=grace_until,
            deprecated_at=now,
            deprecated_by=deprecated_by,
            notes=notes,
        )

        if mode == DeprecationMode.IMMEDIATE:
            updated = item.transition_to(
                LearningItemStatus.DEPRECATED,
                now=now,
            )
            # R-2 atomic: co-commit item transition and deprecation record
            # in one transaction so no reader can observe
            # `item.status == deprecated` without the matching record.
            # Reuses the S6 atomic method (signature matches).
            atomic: LearningStoreAtomicPort = self._store  # type: ignore[assignment]
            atomic.save_item_and_deprecation(item=updated, deprecation=record)
        else:
            # GRACE mode: only the deprecation record is written (no item
            # transition yet). A single-row write remains atomic by
            # definition of the underlying connection ``commit``.
            self._store.save_deprecation_record(record)

        return record

    def auto_deprecate_on_failure(
        self,
        *,
        item_id: str,
    ) -> DeprecationRecord | None:
        """Increment failure count; deprecate on 2nd consecutive failure.

        Returns the deprecation record if deprecated, None otherwise.
        """
        existing = self._store.get_deprecation_record(item_id)
        current_failures = existing.failure_count + 1 if existing else 1

        if current_failures >= 2:
            return self.execute(
                item_id=item_id,
                reason=DeprecationReason.EVAL_FAILURE,
                mode=DeprecationMode.IMMEDIATE,
                notes=f"Auto-deprecated after {current_failures} consecutive failures",
            )

        # Record failure without deprecating
        now = self._clock.now()
        record = DeprecationRecord(
            record_id=f"DR-{uuid.uuid4().hex[:8]}",
            item_id=item_id,
            reason=DeprecationReason.EVAL_FAILURE,
            mode=DeprecationMode.GRACE,
            failure_count=current_failures,
            deprecated_at=now,
            notes=f"Failure {current_failures}/2 recorded",
        )
        self._store.save_deprecation_record(record)
        return None
