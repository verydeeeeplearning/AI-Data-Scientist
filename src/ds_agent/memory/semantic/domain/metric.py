"""Metric catalog domain models."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ds_agent.memory.semantic.domain._normalization import normalize_string_list

MetricGrain = Literal["hourly", "daily", "weekly", "monthly", "quarterly", "yearly"]
MetricUnit = Literal["ratio", "count", "amount", "duration_seconds", "percentage"]
MetricDirection = Literal["higher_is_better", "lower_is_better", "neutral"]


class MetricCalculationComponent(BaseModel):
    """One side of a metric calculation."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(min_length=1)
    filter: str = Field(min_length=1)
    aggregation: str = Field(min_length=1)


class MetricCalculation(BaseModel):
    """Structured metric calculation."""

    model_config = ConfigDict(frozen=True)

    numerator: MetricCalculationComponent
    denominator: MetricCalculationComponent | None = None
    formula: str | None = None


class MetricApproval(BaseModel):
    """Human approval metadata for a metric definition."""

    model_config = ConfigDict(frozen=True)

    team: str = Field(min_length=1)
    decision_date: date
    decision_id: str = Field(min_length=1)


class Metric(BaseModel):
    """Typed metric definition used by semantic retrieval."""

    model_config = ConfigDict(frozen=True)

    metric_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    owner_contact: str | None = Field(default=None, min_length=1)
    definition: str = Field(min_length=1)
    synonyms: list[str] = Field(default_factory=list)
    grain: MetricGrain
    unit: MetricUnit
    direction: MetricDirection
    typical_range: tuple[float, float] | None = None
    calculation: MetricCalculation
    related_metrics: list[str] = Field(default_factory=list)
    approved_by: list[MetricApproval] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    verified_query_ids: list[str] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    last_reviewed: date | None = None

    @field_validator("synonyms", "related_metrics", "caveats", "verified_query_ids", mode="before")
    @classmethod
    def _normalize_lists(cls, value: object) -> list[str]:
        return normalize_string_list(value)

    @model_validator(mode="after")
    def _validate_typical_range(self) -> Metric:
        if self.typical_range is not None and self.typical_range[0] > self.typical_range[1]:
            raise ValueError("typical_range must be ascending")
        return self

