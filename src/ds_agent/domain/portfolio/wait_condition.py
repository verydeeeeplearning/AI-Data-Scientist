"""Wait condition types for the waiting quadrant."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WaitConditionKind(StrEnum):
    """Kinds of conditions that block task resumption."""

    DATA_FRESHNESS = "data_freshness"
    APPROVAL = "approval"
    EXTERNAL_RESOURCE = "external_resource"
    TIMER = "timer"


_DEFAULT_POLL_INTERVALS: dict[WaitConditionKind, int] = {
    WaitConditionKind.DATA_FRESHNESS: 300,
    WaitConditionKind.APPROVAL: 30,
    WaitConditionKind.EXTERNAL_RESOURCE: 60,
    WaitConditionKind.TIMER: 60,
}


class WaitCondition(BaseModel):
    """One wait condition attached to a waiting portfolio entry."""

    model_config = ConfigDict(frozen=True)

    condition_id: str = Field(min_length=1)
    kind: WaitConditionKind
    spec: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    deadline: datetime | None = None
    last_checked_at: datetime | None = None
    last_check_result: str | None = None  # "pending" | "satisfied" | "failed"
    poll_interval_s: int = 60

    @classmethod
    def create(
        cls,
        *,
        condition_id: str,
        kind: WaitConditionKind,
        spec: dict[str, Any],
        now: datetime,
        deadline: datetime | None = None,
        poll_interval_s: int | None = None,
    ) -> WaitCondition:
        """Factory with kind-specific defaults."""
        return cls(
            condition_id=condition_id,
            kind=kind,
            spec=spec,
            created_at=now,
            deadline=deadline,
            poll_interval_s=poll_interval_s or _DEFAULT_POLL_INTERVALS.get(kind, 60),
        )

    @property
    def is_satisfied(self) -> bool:
        return self.last_check_result == "satisfied"

    @property
    def is_overdue(self) -> bool:
        if self.deadline is None or self.last_checked_at is None:
            return False
        return self.last_checked_at > self.deadline and not self.is_satisfied

    def with_check_result(
        self,
        result: str,
        checked_at: datetime,
    ) -> WaitCondition:
        """Return a copy with updated check result."""
        return self.model_copy(
            update={
                "last_checked_at": checked_at,
                "last_check_result": result,
            },
        )
