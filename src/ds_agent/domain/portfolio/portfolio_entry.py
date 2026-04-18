"""Portfolio entry aggregate and supporting types."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PortfolioQuadrant(StrEnum):
    """Four-quadrant portfolio lifecycle states."""

    ACTIVE = "active"
    WAITING = "waiting"
    MONITORING = "monitoring"
    PLAYBOOK_CANDIDATE = "playbook_candidate"


class TerminalQuadrant(StrEnum):
    """Terminal states that cannot transition out."""

    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class BusinessPriority(StrEnum):
    """Business priority with associated SLA windows."""

    P0 = "P0"  # SLA 4h
    P1 = "P1"  # SLA 1 business day
    P2 = "P2"  # SLA 3 business days
    P3 = "P3"  # best-effort

    @property
    def sla_hours(self) -> int | None:
        return {"P0": 4, "P1": 24, "P2": 72, "P3": None}.get(self.value)


# All valid quadrant values for database constraints.
ALL_QUADRANTS: frozenset[str] = frozenset(
    [q.value for q in PortfolioQuadrant] + [q.value for q in TerminalQuadrant],
)


class PortfolioTransition(BaseModel):
    """One recorded lifecycle transition."""

    model_config = ConfigDict(frozen=True)

    from_quadrant: str | None = None
    to_quadrant: str
    reason: str = Field(min_length=1)
    actor: Literal["scheduler", "llm", "user", "system"] = "system"
    at: datetime


# Allowed transitions.  Keys are source quadrants, values are sets of
# allowed target quadrants.
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    PortfolioQuadrant.ACTIVE: {
        PortfolioQuadrant.WAITING,
        PortfolioQuadrant.MONITORING,
        TerminalQuadrant.COMPLETED,
        TerminalQuadrant.CANCELLED,
    },
    PortfolioQuadrant.WAITING: {
        PortfolioQuadrant.ACTIVE,
        TerminalQuadrant.CANCELLED,
    },
    PortfolioQuadrant.MONITORING: {
        PortfolioQuadrant.ACTIVE,
        PortfolioQuadrant.PLAYBOOK_CANDIDATE,
        TerminalQuadrant.COMPLETED,
        TerminalQuadrant.ARCHIVED,
    },
    PortfolioQuadrant.PLAYBOOK_CANDIDATE: {
        TerminalQuadrant.ARCHIVED,
    },
    TerminalQuadrant.COMPLETED: set(),
    TerminalQuadrant.CANCELLED: set(),
    TerminalQuadrant.ARCHIVED: set(),
}


def can_transition(from_q: str, to_q: str) -> bool:
    """Check if a quadrant transition is valid."""
    return to_q in _ALLOWED_TRANSITIONS.get(from_q, set())


class PortfolioEntry(BaseModel):
    """One task in the async portfolio manager."""

    model_config = ConfigDict(validate_assignment=True)

    entry_id: str = Field(min_length=1)
    task_contract_id: str = Field(min_length=1)
    quadrant: str  # PortfolioQuadrant or TerminalQuadrant value
    business_priority: BusinessPriority = BusinessPriority.P2
    sla_deadline: datetime | None = None
    parent_run_id: str | None = None
    wait_condition_id: str | None = None
    monitoring_metric_ref: str | None = None
    playbook_candidate_ref: str | None = None
    created_at: datetime
    updated_at: datetime
    last_transition_at: datetime
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_quadrant_invariants(self) -> PortfolioEntry:
        q = self.quadrant
        if q == PortfolioQuadrant.ACTIVE and not self.parent_run_id:
            raise ValueError("active quadrant requires parent_run_id")
        if q == PortfolioQuadrant.WAITING and not self.wait_condition_id:
            raise ValueError("waiting quadrant requires wait_condition_id")
        if q == PortfolioQuadrant.WAITING and self.parent_run_id:
            raise ValueError("waiting quadrant must not have parent_run_id")
        if q == PortfolioQuadrant.MONITORING and not self.monitoring_metric_ref:
            raise ValueError("monitoring quadrant requires monitoring_metric_ref")
        if q == PortfolioQuadrant.PLAYBOOK_CANDIDATE and not self.playbook_candidate_ref:
            raise ValueError(
                "playbook_candidate quadrant requires playbook_candidate_ref",
            )
        return self

    def transition_to(
        self,
        target: str,
        *,
        reason: str,
        actor: Literal["scheduler", "llm", "user", "system"] = "system",
        now: datetime,
        run_id: str | None = None,
        wait_condition_id: str | None = None,
        monitoring_metric_ref: str | None = None,
        playbook_candidate_ref: str | None = None,
    ) -> PortfolioEntry:
        """Create a transitioned copy with validated state."""
        if not can_transition(self.quadrant, target):
            raise ValueError(
                f"transition from {self.quadrant} to {target} is not allowed",
            )
        return self.model_copy(
            update={
                "quadrant": target,
                "parent_run_id": run_id,
                "wait_condition_id": wait_condition_id,
                "monitoring_metric_ref": monitoring_metric_ref,
                "playbook_candidate_ref": playbook_candidate_ref,
                "updated_at": now,
                "last_transition_at": now,
            },
        )
