"""DTOs for Mission Header context snapshots."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MissionGoalDTO(BaseModel):
    """Primary mission goal and completion criteria."""

    model_config = ConfigDict(populate_by_name=True)

    title: str
    success_criteria: list[str] = Field(default_factory=list, alias="successCriteria")


class MissionDataSourceDTO(BaseModel):
    """One mission-relevant data source."""

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["file", "database", "api"]
    label: str
    row_count: int | None = Field(default=None, alias="rowCount")


class MissionConstraintsDTO(BaseModel):
    """Execution constraints surfaced to the Mission Header."""

    model_config = ConfigDict(populate_by_name=True)

    language: str
    requires_approval: bool = Field(alias="requiresApproval")
    local_only_model: bool = Field(alias="localOnlyModel")


class MissionStageDTO(BaseModel):
    """Current mission stage summary."""

    current: int
    total: int
    label: str


class MissionModelDTO(BaseModel):
    """Current model selection summary."""

    model_config = ConfigDict(populate_by_name=True)

    primary: str
    fallbacks: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)


class MissionBudgetDTO(BaseModel):
    """Budget summary for the active or latest run."""

    model_config = ConfigDict(populate_by_name=True)

    spent_usd: float = Field(alias="spentUsd")
    limit_usd: float = Field(alias="limitUsd")
    elapsed_sec: float = Field(alias="elapsedSec")
    near_limit: bool = Field(alias="nearLimit")


class MissionConnectionDTO(BaseModel):
    """Connection status summary exposed to the Mission Header."""

    model_config = ConfigDict(populate_by_name=True)

    state: Literal["connected", "reconnecting", "disconnected"]
    latency_ms: float | None = Field(default=None, alias="latencyMs")


class MissionContextDTO(BaseModel):
    """Full Mission Header context snapshot."""

    model_config = ConfigDict(populate_by_name=True)

    goal: MissionGoalDTO
    data_sources: list[MissionDataSourceDTO] = Field(default_factory=list, alias="dataSources")
    deliverables: list[str] = Field(default_factory=list)
    constraints: MissionConstraintsDTO
    stage: MissionStageDTO
    mode: str
    model: MissionModelDTO
    budget: MissionBudgetDTO
    connection: MissionConnectionDTO
