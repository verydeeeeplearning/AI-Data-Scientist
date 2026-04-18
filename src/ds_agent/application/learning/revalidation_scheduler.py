"""Revalidation scheduler: periodic eval on monitored items.

The scheduler evaluates due items and records results.
2 consecutive failures trigger auto-deprecation.
It does NOT auto-promote — the LLM decides whether to act on results.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import ClassVar, Protocol

from ds_agent.application.learning.deprecate_learning_item import (
    DeprecateLearningItemUseCase,
)
from ds_agent.domain.interfaces.learning import LearningStore
from ds_agent.domain.learning.learning_item import LearningItem, LearningItemType


class Clock(Protocol):
    def now(self) -> datetime: ...


@dataclass(frozen=True)
class RevalidationResult:
    """Result of evaluating one monitored item."""

    item_id: str
    passed: bool
    score: float
    action_taken: str  # "passed", "failure_recorded", "deprecated"


class RevalidationScheduler:
    """Periodic revalidation of monitored learning items.

    Intervals by type:
      - pattern: 30 days
      - kb_entry: 60 days
      - custom_skill: 14 days
    """

    INTERVALS: ClassVar[dict[LearningItemType, timedelta]] = {
        LearningItemType.PATTERN: timedelta(days=30),
        LearningItemType.KB_ENTRY: timedelta(days=60),
        LearningItemType.CUSTOM_SKILL: timedelta(days=14),
    }

    def __init__(
        self,
        store: LearningStore,
        deprecation_uc: DeprecateLearningItemUseCase,
        clock: Clock,
    ) -> None:
        self._store = store
        self._deprecation_uc = deprecation_uc
        self._clock = clock

    def get_due_items(self) -> list[LearningItem]:
        """Return monitored items that are due for revalidation."""
        now = self._clock.now()
        monitored = self._store.list_monitored_items(limit=100)
        due: list[LearningItem] = []
        for item in monitored:
            interval = self.INTERVALS.get(item.item_type, timedelta(days=30))
            last_eval = item.metadata.get("last_revalidation_at")
            if last_eval is None:
                # Never evaluated since promotion — due immediately
                due.append(item)
                continue
            try:
                last_dt = datetime.fromisoformat(str(last_eval))
            except (ValueError, TypeError):
                due.append(item)
                continue
            if now - last_dt >= interval:
                due.append(item)
        return due

    def record_result(
        self,
        *,
        item_id: str,
        score: float,
        threshold: float = 0.9,
    ) -> RevalidationResult:
        """Record one revalidation result and handle failure logic.

        If score >= threshold: passed.
        If score < threshold: record failure, auto-deprecate on 2nd.
        """
        now = self._clock.now()
        item = self._store.get_item(item_id)
        if item is None:
            raise ValueError(f"Learning item {item_id} not found")

        passed = score >= threshold

        if passed:
            updated = item.model_copy(
                update={
                    "metadata": {
                        **item.metadata,
                        "last_revalidation_at": now.isoformat(),
                        "last_revalidation_score": score,
                    },
                    "updated_at": now,
                },
            )
            self._store.save_item(updated)
            return RevalidationResult(
                item_id=item_id,
                passed=True,
                score=score,
                action_taken="passed",
            )

        # Failure path
        record = self._deprecation_uc.auto_deprecate_on_failure(item_id=item_id)
        action = "deprecated" if record is not None else "failure_recorded"
        return RevalidationResult(
            item_id=item_id,
            passed=False,
            score=score,
            action_taken=action,
        )
