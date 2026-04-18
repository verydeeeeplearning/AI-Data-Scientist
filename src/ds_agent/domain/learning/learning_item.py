"""LearningItem aggregate — knowledge quality gate entity."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LearningItemType(StrEnum):
    """Kinds of extractable knowledge."""

    PATTERN = "pattern"
    KB_ENTRY = "kb_entry"
    CUSTOM_SKILL = "custom_skill"


class LearningItemStatus(StrEnum):
    """Lifecycle states for a learning item."""

    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROMOTED = "promoted"
    MONITORED = "monitored"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class SourceInfo(BaseModel):
    """Where this learning item was extracted from."""

    model_config = ConfigDict(frozen=True)

    source_type: Literal[
        "pattern_learner", "skill_extractor", "post_project", "manual",
    ] = "manual"
    project_id: str | None = None
    session_id: str | None = None
    extractor_version: str = "1.0"


class Evidence(BaseModel):
    """One piece of evidence supporting the learning item."""

    model_config = ConfigDict(frozen=True)

    metric_name: str = Field(min_length=1)
    metric_value: float
    project_id: str = ""
    recorded_at: datetime


class ConflictRef(BaseModel):
    """Reference to a conflicting learning item."""

    model_config = ConfigDict(frozen=True)

    conflicting_item_id: str = Field(min_length=1)
    conflict_type: Literal["supersedes", "contradicts", "overlaps"] = "overlaps"
    resolved: bool = False
    resolution_note: str | None = None


# ── State machine ────────────────────────────────────────────────────

_ALLOWED_TRANSITIONS: dict[LearningItemStatus, set[LearningItemStatus]] = {
    LearningItemStatus.PROPOSED: {
        LearningItemStatus.UNDER_REVIEW,
        LearningItemStatus.ARCHIVED,
    },
    LearningItemStatus.UNDER_REVIEW: {
        LearningItemStatus.APPROVED,
        LearningItemStatus.REJECTED,
    },
    LearningItemStatus.APPROVED: {
        LearningItemStatus.PROMOTED,
        LearningItemStatus.ARCHIVED,
    },
    LearningItemStatus.REJECTED: {
        LearningItemStatus.PROPOSED,  # re-submission
        LearningItemStatus.ARCHIVED,
    },
    LearningItemStatus.PROMOTED: {
        LearningItemStatus.MONITORED,
        LearningItemStatus.DEPRECATED,
        LearningItemStatus.ARCHIVED,
    },
    LearningItemStatus.MONITORED: {
        LearningItemStatus.PROMOTED,  # re-promotion after revalidation
        LearningItemStatus.DEPRECATED,
        LearningItemStatus.ARCHIVED,
    },
    LearningItemStatus.DEPRECATED: {
        LearningItemStatus.ARCHIVED,
    },
    LearningItemStatus.ARCHIVED: set(),  # terminal
}


def can_transition(from_s: LearningItemStatus, to_s: LearningItemStatus) -> bool:
    """Check if a status transition is valid."""
    return to_s in _ALLOWED_TRANSITIONS.get(from_s, set())


class LearningItem(BaseModel):
    """One piece of extractable knowledge under governance."""

    model_config = ConfigDict(frozen=True)

    item_id: str = Field(min_length=1)
    item_type: LearningItemType
    status: LearningItemStatus = LearningItemStatus.PROPOSED
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    signature: str = Field(min_length=1)  # dedup key
    source: SourceInfo = Field(default_factory=SourceInfo)
    evidence: list[Evidence] = Field(default_factory=list)
    conflict_refs: list[ConflictRef] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    scope: Literal["project", "domain", "global"] = "project"
    review_count: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def has_unresolved_conflicts(self) -> bool:
        return any(not c.resolved for c in self.conflict_refs)

    @property
    def requires_second_reviewer(self) -> bool:
        """Custom skills or unresolved conflicts need a second reviewer."""
        if self.item_type == LearningItemType.CUSTOM_SKILL:
            return True
        return self.has_unresolved_conflicts

    def transition_to(
        self,
        target: LearningItemStatus,
        *,
        now: datetime,
        **kwargs: Any,
    ) -> LearningItem:
        """Return a validated copy in the new status."""
        if not can_transition(self.status, target):
            raise ValueError(
                f"transition from {self.status.value} to {target.value} "
                f"is not allowed",
            )
        update: dict[str, Any] = {
            "status": target,
            "updated_at": now,
            **kwargs,
        }
        return self.model_copy(update=update)
