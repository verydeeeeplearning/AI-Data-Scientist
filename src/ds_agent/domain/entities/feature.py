"""Feature registry domain entities for Decision OS."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FeatureAlias = Literal["stable", "experimental", "deprecated"]


def _normalize_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = [value]
    else:
        try:
            raw_items = list(value)  # type: ignore[call-overload]
        except TypeError as exc:  # pragma: no cover - defensive branch
            raise TypeError("expected a sequence of strings") from exc

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = str(item).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized


class FeatureStatistics(BaseModel):
    """Basic distribution metadata attached to a feature version."""

    model_config = ConfigDict(frozen=True)

    mean: float | None = None
    median: float | None = None
    p95: float | None = None
    null_rate: float | None = Field(default=None, ge=0, le=1)
    distinct_count: int | None = Field(default=None, ge=0)
    last_computed_at: datetime


class FeatureRef(BaseModel):
    """Reference to a specific feature version locked at experiment start."""

    model_config = ConfigDict(frozen=True)

    feature_id: str = Field(min_length=1)
    version: int = Field(ge=1)


class Feature(BaseModel):
    """Canonical feature definition stored by the Decision OS registry."""

    model_config = ConfigDict(frozen=True)

    feature_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    version: int = Field(ge=1)
    description: str = Field(min_length=1)
    transformation_logic: str = Field(min_length=1)
    source_tables: list[str] = Field(default_factory=list, min_length=1)
    owner: str = Field(min_length=1)
    created_at: datetime
    statistics: FeatureStatistics
    point_in_time_safe: bool
    alias: FeatureAlias = "experimental"
    used_in_experiments: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("source_tables", "used_in_experiments", "tags", mode="before")
    @classmethod
    def _normalize_lists(cls, value: object) -> list[str]:
        return _normalize_string_list(value)

    def ref(self) -> FeatureRef:
        """Return the immutable reference used by experiment runs."""

        return FeatureRef(feature_id=self.feature_id, version=self.version)
