"""Decision OS post-deploy monitoring entities."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.domain.entities.model import ModelAlias

MonitorStatus = Literal["ok", "warning", "alert", "skipped"]
TriggerMode = Literal["manual_only", "auto_retrain", "auto_rollback"]


class DriftMetricObservation(BaseModel):
    """One persisted drift metric for one feature."""

    model_config = ConfigDict(frozen=True)

    feature_name: str = Field(min_length=1)
    metric_type: str = Field(min_length=1)
    value: float
    threshold: float
    level: str = Field(min_length=1)


class DriftSummary(BaseModel):
    """Aggregated post-deploy drift status for one model sweep."""

    model_config = ConfigDict(frozen=True)

    overall_status: str = Field(min_length=1)
    max_psi: float | None = None
    max_ks: float | None = None
    top_drifting_features: list[str] = Field(default_factory=list)
    metrics: list[DriftMetricObservation] = Field(default_factory=list)


class MetricChangeObservation(BaseModel):
    """Observed production-metric change versus the model baseline."""

    model_config = ConfigDict(frozen=True)

    metric: str = Field(min_length=1)
    baseline_value: float
    current_value: float
    delta: float
    direction: Literal["better", "worse", "neutral"]
    status: MonitorStatus


class ServiceLevelSummary(BaseModel):
    """Observed latency and throughput against serving budgets."""

    model_config = ConfigDict(frozen=True)

    latency_p95_ms: float | None = None
    latency_budget_ms: int | None = Field(default=None, ge=0)
    qps: float | None = None
    throughput_budget_qps: int | None = Field(default=None, ge=0)
    status: MonitorStatus = "skipped"


class RemediationSummary(BaseModel):
    """Recommended remediation after one monitoring sweep."""

    model_config = ConfigDict(frozen=True)

    decision: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    should_alert: bool
    recommended_steps: list[str] = Field(default_factory=list)


class PostDeploySnapshot(BaseModel):
    """One external monitoring snapshot consumed by the runtime adapter."""

    model_config = ConfigDict(frozen=True)

    reference_path: str = Field(min_length=1)
    current_path: str = Field(min_length=1)
    current_metrics: dict[str, float] = Field(default_factory=dict)
    latency_p95_ms: float | None = None
    qps: float | None = None
    observed_at: datetime


class PostDeployMonitorState(BaseModel):
    """Persisted state for one model/window monitoring sweep."""

    model_config = ConfigDict(frozen=True)

    state_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_version: int = Field(ge=1)
    alias: ModelAlias
    window: str = Field(min_length=1)
    observed_at: datetime
    drift: DriftSummary
    metrics: list[MetricChangeObservation] = Field(default_factory=list)
    service_level: ServiceLevelSummary
    remediation: RemediationSummary
    overall_status: Literal["ok", "warning", "alert"]
    alerts: list[str] = Field(default_factory=list)
    trigger_mode: TriggerMode = "manual_only"
    trigger_payload: dict[str, object] = Field(default_factory=dict)
