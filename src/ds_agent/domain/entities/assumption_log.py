"""Assumption log entities for task contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ds_agent.domain.entities._id_patterns import (
    ASSUMPTION_ENTRY_ID_PATTERN,
    ASSUMPTION_LOG_ID_PATTERN,
)


class AssumptionEntry(BaseModel):
    """One explicit assumption taken during execution."""

    entry_id: str = Field(pattern=ASSUMPTION_ENTRY_ID_PATTERN)
    statement: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    risk_level: Literal["low", "medium", "high"]
    verified: bool = False
    verification_note: str | None = None
    asked_user: bool = False
    created_at: datetime


class AssumptionLog(BaseModel):
    """Container for all assumptions for a task contract."""

    log_id: str = Field(pattern=ASSUMPTION_LOG_ID_PATTERN)
    task_id: str = Field(min_length=1)
    entries: list[AssumptionEntry] = Field(default_factory=list)
