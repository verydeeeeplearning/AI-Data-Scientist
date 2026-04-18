"""Data trust registry domain models."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ds_agent.memory.semantic.domain._normalization import normalize_string_list

RefreshCadence = Literal["realtime", "hourly", "daily", "weekly", "adhoc"]
PiiClass = Literal["none", "low", "medium", "high"]
JoinType = Literal["inner", "left", "right", "full"]
JoinCardinality = Literal["one_to_one", "one_to_many", "many_to_many"]


class TrustGrade(StrEnum):
    """Ordered trust levels for data assets."""

    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    UNTRUSTED = "untrusted"

    def can_transition_to(self, target: TrustGrade) -> bool:
        """Allow same-grade moves, one-step promotions, and any downgrade."""

        if self == target:
            return True
        order = {
            TrustGrade.UNTRUSTED.value: 0,
            TrustGrade.BRONZE.value: 1,
            TrustGrade.SILVER.value: 2,
            TrustGrade.GOLD.value: 3,
        }
        current_rank = order[self.value]
        target_rank = order[target.value]
        return target_rank <= current_rank or target_rank == current_rank + 1

    def validate_transition(self, target: TrustGrade) -> None:
        if not self.can_transition_to(target):
            raise ValueError(
                f"trust grade transition from {self.value} to {target.value} is not allowed"
            )


class RefreshSLA(BaseModel):
    """Expected freshness contract for a table."""

    model_config = ConfigDict(frozen=True)

    cadence: RefreshCadence
    max_staleness_minutes: int = Field(ge=0)
    last_refreshed_at: datetime | None = None


class ColumnTrust(BaseModel):
    """Column-level lineage and classification."""

    model_config = ConfigDict(frozen=True)

    column: str = Field(min_length=1)
    pii_class: PiiClass
    lineage_upstream: list[str] = Field(default_factory=list)
    nullable_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    data_type: str = Field(min_length=1)

    @field_validator("lineage_upstream", mode="before")
    @classmethod
    def _normalize_lineage(cls, value: object) -> list[str]:
        return normalize_string_list(value)


class ApprovedJoin(BaseModel):
    """Pre-approved join path for query synthesis."""

    model_config = ConfigDict(frozen=True)

    target_fqtn: str = Field(min_length=1)
    left_keys: list[str] = Field(default_factory=list)
    right_keys: list[str] = Field(default_factory=list)
    join_type: JoinType
    cardinality: JoinCardinality
    caveat: str | None = None

    @field_validator("left_keys", "right_keys", mode="before")
    @classmethod
    def _normalize_keys(cls, value: object) -> list[str]:
        return normalize_string_list(value)


class TableTrust(BaseModel):
    """Trust metadata for one fully-qualified table name."""

    model_config = ConfigDict(frozen=True)

    fqtn: str = Field(min_length=1)
    grade: TrustGrade
    owner: str = Field(min_length=1)
    description: str = Field(min_length=1)
    refresh: RefreshSLA
    columns: list[ColumnTrust] = Field(default_factory=list)
    approved_joins: list[ApprovedJoin] = Field(default_factory=list)
    grade_rationale: str = Field(min_length=1)
    last_audited: date

    def transition_grade(self, target: TrustGrade) -> TableTrust:
        """Return a new instance with a validated target grade."""

        self.grade.validate_transition(target)
        return self.model_copy(update={"grade": target})
