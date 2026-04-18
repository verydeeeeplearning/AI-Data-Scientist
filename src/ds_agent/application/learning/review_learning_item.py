"""Use case: review a learning item (approve/modify/reject)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Protocol

from ds_agent.application.ports.learning_store_port import LearningStoreAtomicPort
from ds_agent.domain.interfaces.learning import LearningStore
from ds_agent.domain.learning.learning_item import (
    LearningItem,
    LearningItemStatus,
)
from ds_agent.domain.learning.review_event import (
    ReviewChecklist,
    ReviewDecision,
    ReviewEvent,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class ReviewLearningItemUseCase:
    """Apply a review decision to a learning item.

    - approve: proposed→under_review (first review) or under_review→approved
    - modify: stays under_review, applies content modifications
    - reject: under_review→rejected
    """

    def __init__(self, store: LearningStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def execute(
        self,
        *,
        item_id: str,
        decision: ReviewDecision,
        reviewer: str = "system",
        checklist: ReviewChecklist | None = None,
        comment: str = "",
        modifications: dict[str, Any] | None = None,
    ) -> tuple[LearningItem, ReviewEvent]:
        item = self._store.get_item(item_id)
        if item is None:
            raise ValueError(f"Learning item {item_id} not found")

        now = self._clock.now()

        if decision == ReviewDecision.APPROVE:
            updated = self._handle_approve(item, checklist, now)
        elif decision == ReviewDecision.MODIFY:
            updated = self._handle_modify(item, modifications or {}, now)
        elif decision == ReviewDecision.REJECT:
            updated = self._handle_reject(item, now)
        else:
            raise ValueError(f"Unknown decision: {decision}")

        event = ReviewEvent(
            event_id=f"RE-{uuid.uuid4().hex[:8]}",
            item_id=item_id,
            decision=decision,
            reviewer=reviewer,
            checklist=checklist,
            comment=comment,
            modifications=modifications or {},
            created_at=now,
        )

        # R-3 atomic: co-commit review event with item transition so
        # the audit stream can never record a decision for an item
        # whose state transition was lost.
        atomic: LearningStoreAtomicPort = self._store  # type: ignore[assignment]
        atomic.save_review_event_and_item(event=event, item=updated)
        return updated, event

    def _handle_approve(
        self,
        item: LearningItem,
        checklist: ReviewChecklist | None,
        now: datetime,
    ) -> LearningItem:
        if checklist is not None and not checklist.all_passed:
            raise ValueError(
                "Cannot approve: checklist has unmet requirements",
            )

        new_review_count = item.review_count + 1

        if item.status == LearningItemStatus.PROPOSED:
            # First review: move to under_review
            updated = item.transition_to(
                LearningItemStatus.UNDER_REVIEW,
                now=now,
                review_count=new_review_count,
            )
            # If not requiring second reviewer, approve immediately
            if not item.requires_second_reviewer:
                updated = updated.transition_to(
                    LearningItemStatus.APPROVED,
                    now=now,
                )
            return updated

        if item.status == LearningItemStatus.UNDER_REVIEW:
            # Second (or subsequent) review
            updated = item.model_copy(
                update={
                    "review_count": new_review_count,
                    "updated_at": now,
                },
            )
            if item.requires_second_reviewer and new_review_count < 2:
                return updated  # Still needs more reviews
            return updated.transition_to(
                LearningItemStatus.APPROVED,
                now=now,
            )

        raise ValueError(
            f"Cannot approve item in status {item.status.value}",
        )

    def _handle_modify(
        self,
        item: LearningItem,
        modifications: dict[str, Any],
        now: datetime,
    ) -> LearningItem:
        if item.status == LearningItemStatus.PROPOSED:
            item = item.transition_to(
                LearningItemStatus.UNDER_REVIEW,
                now=now,
            )

        if item.status != LearningItemStatus.UNDER_REVIEW:
            raise ValueError(
                f"Cannot modify item in status {item.status.value}",
            )

        update: dict[str, Any] = {"updated_at": now}
        if "title" in modifications:
            update["title"] = modifications["title"]
        if "content" in modifications:
            update["content"] = modifications["content"]
        if "tags" in modifications:
            update["tags"] = modifications["tags"]
        return item.model_copy(update=update)

    def _handle_reject(
        self,
        item: LearningItem,
        now: datetime,
    ) -> LearningItem:
        if item.status == LearningItemStatus.PROPOSED:
            item = item.transition_to(
                LearningItemStatus.UNDER_REVIEW,
                now=now,
            )
        if item.status != LearningItemStatus.UNDER_REVIEW:
            raise ValueError(
                f"Cannot reject item in status {item.status.value}",
            )
        return item.transition_to(
            LearningItemStatus.REJECTED,
            now=now,
        )
