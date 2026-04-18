"""Checkpoint state for paused portfolio entries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PortfolioCheckpoint(BaseModel):
    """Snapshot of execution state when a task moves to waiting."""

    model_config = ConfigDict(frozen=True)

    checkpoint_id: str = Field(min_length=1)
    entry_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    step_index: int = Field(ge=0)
    state_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
