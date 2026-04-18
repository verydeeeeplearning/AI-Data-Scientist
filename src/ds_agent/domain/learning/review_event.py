"""Review event for learning item governance."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReviewDecision(StrEnum):
    """Possible review decisions."""

    APPROVE = "approve"
    MODIFY = "modify"
    REJECT = "reject"


class ReviewChecklist(BaseModel):
    """Mandatory checklist for review approval."""

    model_config = ConfigDict(frozen=True)

    evidence_sufficient: bool = False
    no_unresolved_conflicts: bool = False
    scope_appropriate: bool = False
    content_accurate: bool = False
    second_reviewer_if_required: bool = True

    @property
    def all_passed(self) -> bool:
        return (
            self.evidence_sufficient
            and self.no_unresolved_conflicts
            and self.scope_appropriate
            and self.content_accurate
            and self.second_reviewer_if_required
        )


class ReviewEvent(BaseModel):
    """One review action on a learning item."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1)
    item_id: str = Field(min_length=1)
    decision: ReviewDecision
    reviewer: str = "system"
    checklist: ReviewChecklist | None = None
    comment: str = ""
    modifications: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
