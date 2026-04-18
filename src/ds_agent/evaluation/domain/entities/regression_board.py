"""Entities for evaluation regression-board snapshots."""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class RegressionWindowStats(BaseModel):
    """Aggregate score statistics for one rolling window."""

    model_config = ConfigDict(frozen=True)

    record_count: int = Field(ge=0)
    avg_weighted_score: float | None = Field(default=None, ge=0.0, le=1.0)
    pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class RegressionOverallSummary(BaseModel):
    """Overall recent-vs-baseline comparison."""

    model_config = ConfigDict(frozen=True)

    recent: RegressionWindowStats
    baseline: RegressionWindowStats
    delta_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    delta_pass_rate: float | None = Field(default=None, ge=-1.0, le=1.0)


class RegressionModeSummary(BaseModel):
    """Aggregate metrics for one evaluation mode."""

    model_config = ConfigDict(frozen=True)

    mode: str = Field(min_length=1)
    record_count: int = Field(ge=0)
    avg_weighted_score: float | None = Field(default=None, ge=0.0, le=1.0)
    pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class RegressionDimensionSummary(BaseModel):
    """Recent-vs-baseline comparison for one scoring dimension."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    recent_record_count: int = Field(ge=0)
    baseline_record_count: int = Field(ge=0)
    recent_mean_score: float | None = Field(default=None, ge=0.0, le=1.0)
    baseline_mean_score: float | None = Field(default=None, ge=0.0, le=1.0)
    delta_score: float | None = Field(default=None, ge=-1.0, le=1.0)


class RegressionBoardPoint(BaseModel):
    """One grouped time/commit point on the regression board."""

    model_config = ConfigDict(frozen=True)

    axis_key: str = Field(min_length=1)
    axis_label: str = Field(min_length=1)
    run_count: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    weighted_score_mean: float = Field(ge=0.0, le=1.0)
    per_dimension_means: dict[str, float] = Field(default_factory=dict)
    per_mode_weighted_scores: dict[str, float] = Field(default_factory=dict)


class RegressionTaskSummary(BaseModel):
    """Recent-vs-baseline comparison for one task."""

    model_config = ConfigDict(frozen=True)

    task_id: str = Field(min_length=1)
    domain: str | None = None
    difficulty: str | None = None
    latest_run_id: str = Field(min_length=1)
    latest_mode: str = Field(min_length=1)
    latest_recorded_at: float = Field(ge=0.0)
    latest_weighted_score: float = Field(ge=0.0, le=1.0)
    latest_passed: bool
    pass_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    alert_on_drop_below: float | None = Field(default=None, ge=0.0, le=1.0)
    recent_record_count: int = Field(ge=0)
    baseline_record_count: int = Field(ge=0)
    recent_mean_score: float | None = Field(default=None, ge=0.0, le=1.0)
    baseline_mean_score: float | None = Field(default=None, ge=0.0, le=1.0)
    delta_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    status: Literal["healthy", "regressed", "failing", "insufficient_baseline"]


class RegressionAlert(BaseModel):
    """One surfaced regression alert."""

    model_config = ConfigDict(frozen=True)

    kind: Literal[
        "pass_rate_drop",
        "dimension_regression",
        "single_task_hard_fail",
        "online_mode_drift",
    ]
    severity: Literal["high", "medium", "low"]
    scope: Literal["overall", "dimension", "task", "mode"]
    scope_key: str | None = None
    dimension: str | None = None
    task_id: str | None = None
    message: str = Field(min_length=1)
    delta: float | None = Field(default=None, ge=-1.0, le=1.0)
    current_value: float | None = Field(default=None, ge=0.0, le=1.0)
    baseline_value: float | None = Field(default=None, ge=0.0, le=1.0)


class RegressionBoardBaseline(BaseModel):
    """Frozen baseline summary reserved for future board pinning."""

    model_config = ConfigDict(frozen=True)

    baseline_id: str = Field(min_length=1)
    commit_sha: str = Field(min_length=1)
    axis_kind: Literal["commit", "date"] = "commit"
    mode: str | None = None
    domain: str | None = None
    task_id: str | None = None
    pass_rate: float = Field(ge=0.0, le=1.0)
    weighted_score_mean: float = Field(ge=0.0, le=1.0)
    baseline_window_days: int = Field(default=14, ge=1)
    source_point_count: int = Field(ge=0)
    dimension_mean_scores: dict[str, float] = Field(default_factory=dict)
    task_mean_scores: dict[str, float] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time, ge=0.0)

    @property
    def per_dimension_means(self) -> dict[str, float]:
        return self.dimension_mean_scores

    @property
    def task_weighted_scores(self) -> dict[str, float]:
        return self.task_mean_scores


class RegressionBoardSnapshot(BaseModel):
    """Read-only regression-board snapshot for CLI and Electron surfaces."""

    model_config = ConfigDict(frozen=True)

    generated_at: float = Field(default_factory=time.time, ge=0.0)
    total_records: int = Field(ge=0)
    recent_window: int = Field(ge=1)
    baseline_window_days: int = Field(ge=1)
    axis_kind: Literal["commit", "date"] = "commit"
    mode_filter: str | None = None
    domain_filter: str | None = None
    baseline_source: Literal["rolling", "frozen"] = "rolling"
    available_domains: tuple[str, ...] = Field(default_factory=tuple)
    overall: RegressionOverallSummary
    points: tuple[RegressionBoardPoint, ...] = Field(default_factory=tuple)
    mode_summaries: tuple[RegressionModeSummary, ...] = Field(default_factory=tuple)
    task_summaries: tuple[RegressionTaskSummary, ...] = Field(default_factory=tuple)
    dimension_summaries: tuple[RegressionDimensionSummary, ...] = Field(default_factory=tuple)
    alerts: tuple[RegressionAlert, ...] = Field(default_factory=tuple)
    frozen_baseline: RegressionBoardBaseline | None = None

    @computed_field
    def point_count(self) -> int:
        return len(self.points)

    @computed_field
    def active_alerts(self) -> tuple[RegressionAlert, ...]:
        return self.alerts

    @computed_field
    def baseline(self) -> RegressionBoardBaseline | None:
        return self.frozen_baseline
