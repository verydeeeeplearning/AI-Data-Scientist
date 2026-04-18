"""Deprecation record for learning item governance."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DeprecationReason(StrEnum):
    """Why a learning item was deprecated."""

    EVAL_FAILURE = "eval_failure"
    MANUAL = "manual"
    SUPERSEDED = "superseded"
    STALE = "stale"


class DeprecationMode(StrEnum):
    """How quickly the deprecation takes effect."""

    IMMEDIATE = "immediate"
    GRACE = "grace"


class DeprecationRecord(BaseModel):
    """Record of a learning item being deprecated."""

    model_config = ConfigDict(frozen=True)

    record_id: str = Field(min_length=1)
    item_id: str = Field(min_length=1)
    reason: DeprecationReason
    mode: DeprecationMode = DeprecationMode.IMMEDIATE
    failure_count: int = Field(default=0, ge=0)
    grace_until: datetime | None = None
    deprecated_at: datetime
    deprecated_by: str = "system"
    notes: str = ""
