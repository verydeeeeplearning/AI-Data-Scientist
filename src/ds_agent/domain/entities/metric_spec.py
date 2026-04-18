"""Metric definition entity for task contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ds_agent.domain.entities._id_patterns import METRIC_SPEC_ID_PATTERN


class MetricSpec(BaseModel):
    """Organization-level KPI definition used by a contract."""

    metric_id: str = Field(pattern=METRIC_SPEC_ID_PATTERN)
    task_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    formula: str = Field(min_length=1)
    source_tables: list[str] = Field(default_factory=list)
    grain: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    direction: Literal["higher_is_better", "lower_is_better", "target"]
    baseline_value: float | None = None
    target_value: float | None = None
    measurement_window: str | None = None
    owner: str | None = None
    refresh_cadence: str | None = None
    confidence_grade: Literal["A", "B", "C"] = "B"
    is_primary_kpi: bool = False
    created_at: datetime
