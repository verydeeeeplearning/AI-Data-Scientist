"""Domain entities for long-lived session goals."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class GoalStatus(StrEnum):
    """Lifecycle states for one session goal."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class GoalRecord:
    """A user-visible goal tracked across multiple runs."""

    goal_id: str
    session_id: str
    summary: str
    detail: str
    status: GoalStatus = GoalStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    last_run_id: str | None = None
    blocked_reason: str | None = None
    completed_at: float | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def is_terminal(self) -> bool:
        return self.status in {GoalStatus.COMPLETED, GoalStatus.CANCELLED}
