"""Monitoring state for post-execution metric tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MonitoringState(BaseModel):
    """Tracks ongoing metric monitoring for a portfolio entry."""

    model_config = ConfigDict(frozen=True)

    monitoring_id: str = Field(min_length=1)
    entry_id: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    target_value: float | None = None
    current_value: float | None = None
    threshold: float | None = None
    check_interval_s: int = 3600
    last_checked_at: datetime | None = None
    status: str = "active"  # active | passed | failed
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
