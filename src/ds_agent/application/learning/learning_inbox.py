"""Use case: query and rank learning items for the review surface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Protocol

from ds_agent.domain.interfaces.learning import LearningStore
from ds_agent.domain.learning.learning_item import (
    LearningItem,
    LearningItemStatus,
    LearningItemType,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


@dataclass(frozen=True)
class ScoredLearningItem:
    """Learning item with computed priority score."""

    item: LearningItem
    priority_score: float


class LearningInboxUseCase:
    """Query and rank proposed/under_review items for review.

    Priority scoring formula:
      evidence * 0.4 + conflict * 0.3 + scope * 0.2 + staleness * 0.1
    """

    WEIGHTS: ClassVar[dict[str, float]] = {
        "evidence": 0.4,
        "conflict": 0.3,
        "scope": 0.2,
        "staleness": 0.1,
    }

    _SCOPE_SCORES: ClassVar[dict[str, float]] = {
        "global": 1.0,
        "domain": 0.6,
        "project": 0.3,
    }

    def __init__(self, store: LearningStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def execute(
        self,
        *,
        status_filter: list[LearningItemStatus] | None = None,
        item_type_filter: LearningItemType | None = None,
        limit: int = 50,
    ) -> list[ScoredLearningItem]:
        statuses = status_filter or [
            LearningItemStatus.PROPOSED,
            LearningItemStatus.UNDER_REVIEW,
        ]
        items: list[LearningItem] = []
        for status in statuses:
            items.extend(
                self._store.list_items(
                    status=status,
                    item_type=item_type_filter,
                    limit=limit,
                ),
            )

        scored = [
            ScoredLearningItem(item=item, priority_score=self._compute_priority(item))
            for item in items
        ]
        scored.sort(key=lambda s: s.priority_score, reverse=True)
        return scored[:limit]

    def _compute_priority(self, item: LearningItem) -> float:
        evidence_score = (
            min(len(item.evidence) / 3.0, 1.0) * self.WEIGHTS["evidence"]
        )
        conflict_score = (
            (1.0 if item.has_unresolved_conflicts else 0.0)
            * self.WEIGHTS["conflict"]
        )
        scope_score = (
            self._SCOPE_SCORES.get(item.scope, 0.3)
            * self.WEIGHTS["scope"]
        )
        now = self._clock.now()
        age_days = (now - item.created_at).total_seconds() / 86400
        staleness_score = min(age_days / 30.0, 1.0) * self.WEIGHTS["staleness"]

        return round(
            evidence_score + conflict_score + scope_score + staleness_score,
            4,
        )
