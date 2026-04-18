"""Output DTOs for evaluation use cases."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.evaluation.domain.entities.eval_score import EvalDatasetRecord, EvalScore


class ScoredRunReport(BaseModel):
    """Scored report for a single task/run pair."""

    model_config = ConfigDict(frozen=True)

    task_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    mode: str = Field(min_length=1)
    weighted_score: float = Field(ge=0.0, le=1.0)
    passed: bool
    scores: dict[str, EvalScore]
    session_id: str | None = None
    cost_usd: float = Field(default=0.0, ge=0.0)
    decision_latency_seconds: float | None = Field(default=None, ge=0.0)
    metric_choices: tuple[str, ...] = Field(default_factory=tuple)
    artifact_types: tuple[str, ...] = Field(default_factory=tuple)
    run_metadata: dict[str, Any] = Field(default_factory=dict)

    def to_record(self) -> EvalDatasetRecord:
        return EvalDatasetRecord(
            task_id=self.task_id,
            run_id=self.run_id,
            mode=self.mode,
            weighted_score=self.weighted_score,
            passed=self.passed,
            scores=self.scores,
            session_id=self.session_id,
            cost_usd=self.cost_usd,
            decision_latency_seconds=self.decision_latency_seconds,
            metric_choices=self.metric_choices,
            artifact_types=self.artifact_types,
            run_metadata=self.run_metadata,
        )


class EvalBatchReport(BaseModel):
    """Aggregated report for a batch of task evaluations."""

    model_config = ConfigDict(frozen=True)

    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    per_task_scores: dict[str, float]
    per_dimension_means: dict[str, float]
    task_reports: tuple[ScoredRunReport, ...]
