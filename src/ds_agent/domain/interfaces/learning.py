"""Post-learning and governance store interfaces (Domain layer)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ds_agent.domain.learning.deprecation_record import DeprecationRecord
from ds_agent.domain.learning.learning_item import (
    LearningItem,
    LearningItemStatus,
    LearningItemType,
)
from ds_agent.domain.learning.promotion_record import PromotionRecord
from ds_agent.domain.learning.review_event import ReviewEvent


@runtime_checkable
class PostLearningPort(Protocol):
    """Triggered after successful tool execution to record learnings."""

    def learn_from_tool_result(
        self, session_id: str, tool_name: str, arguments: dict, result: str
    ) -> None: ...

    def learn_from_session_outcome(self, session_id: str, outcome: dict[str, object]) -> None: ...


@runtime_checkable
class LearningStore(Protocol):
    """Storage contract for learning governance entities."""

    # ── Learning items ───────────────────────────────────────────────

    def save_item(self, item: LearningItem) -> None: ...

    def get_item(self, item_id: str) -> LearningItem | None: ...

    def list_items(
        self,
        *,
        status: LearningItemStatus | None = None,
        item_type: LearningItemType | None = None,
        limit: int = 50,
    ) -> list[LearningItem]: ...

    def find_by_signature(self, signature: str) -> LearningItem | None: ...

    # ── Review events ────────────────────────────────────────────────

    def save_review_event(self, event: ReviewEvent) -> None: ...

    def list_review_events(
        self,
        item_id: str,
        *,
        limit: int = 20,
    ) -> list[ReviewEvent]: ...

    # ── Promotion records ────────────────────────────────────────────

    def save_promotion_record(self, record: PromotionRecord) -> None: ...

    def get_promotion_record(self, item_id: str) -> PromotionRecord | None: ...

    def list_promotion_records(self, *, limit: int = 50) -> list[PromotionRecord]: ...

    # ── Deprecation records ──────────────────────────────────────────

    def save_deprecation_record(self, record: DeprecationRecord) -> None: ...

    def get_deprecation_record(self, item_id: str) -> DeprecationRecord | None: ...

    def list_deprecation_records(self, *, limit: int = 50) -> list[DeprecationRecord]: ...

    # ── Queries ──────────────────────────────────────────────────────

    def list_monitored_items(
        self,
        *,
        item_type: LearningItemType | None = None,
        limit: int = 50,
    ) -> list[LearningItem]: ...
