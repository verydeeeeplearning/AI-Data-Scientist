"""Gold task entities and validation rules."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType


class GoldDataset(BaseModel):
    """Dataset reference attached to a gold task."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    schema_ref: str | None = None


class GoldTaskInput(BaseModel):
    """Input constraints for a gold task."""

    model_config = ConfigDict(frozen=True)

    datasets: tuple[GoldDataset, ...] = Field(default_factory=tuple)
    snapshot_date: date | None = None
    budget_usd: float = Field(default=0.0, ge=0.0)
    time_budget_min: int = Field(default=0, ge=0)


class ExpectedDeliverable(BaseModel):
    """Deliverable expected from a run."""

    model_config = ConfigDict(frozen=True)

    type: str = Field(min_length=1)
    must_contain: tuple[str, ...] = Field(default_factory=tuple)
    must_cover: tuple[str, ...] = Field(default_factory=tuple)
    kind: str | None = None
    target: str | None = None
    top_k: int | None = Field(default=None, ge=1)


class TemporalValidation(BaseModel):
    """Temporal validation points for leakage detection."""

    model_config = ConfigDict(frozen=True)

    snapshot_date: date | None = None
    features_cutoff_before_days: int = Field(default=0, ge=0)
    forbid_future_leakage: bool = True


class MetricSelectionValidation(BaseModel):
    """Primary metric allow/deny lists."""

    model_config = ConfigDict(frozen=True)

    acceptable_primary: tuple[str, ...] = Field(default_factory=tuple)
    forbidden_primary: tuple[str, ...] = Field(default_factory=tuple)


class SegmentValidation(BaseModel):
    """Segment-level validation rules."""

    model_config = ConfigDict(frozen=True)

    must_exclude: tuple[str, ...] = Field(default_factory=tuple)


class ValidationPoints(BaseModel):
    """Deterministic validation anchors for scorers."""

    model_config = ConfigDict(frozen=True)

    temporal: TemporalValidation | None = None
    metric_selection: MetricSelectionValidation | None = None
    segment: SegmentValidation | None = None
    approval_required: dict[str, bool] = Field(default_factory=dict)


class Baseline(BaseModel):
    """Human or historical baseline for a task."""

    model_config = ConfigDict(frozen=True)

    human_expert_time_min: int | None = Field(default=None, ge=0)
    human_expert_rubric: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_rubric(self) -> Baseline:
        for key, value in self.human_expert_rubric.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"Baseline rubric score for {key!r} must be in [0, 1].")
        return self


class ScoringRubricEntry(BaseModel):
    """Weight and judge configuration for one dimension."""

    model_config = ConfigDict(frozen=True)

    weight: float = Field(ge=0.0, le=1.0)
    judge: JudgeType
    prompt_ref: str | None = None


class GoldTask(BaseModel):
    """Typed representation of a YAML gold task."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=3)
    task_version: int = Field(ge=1)
    domain: str = Field(min_length=1)
    difficulty: Literal["easy", "medium", "hard"]
    tags: tuple[str, ...] = Field(default_factory=tuple)
    prompt: str = Field(min_length=1)
    input: GoldTaskInput
    expected_deliverables: tuple[ExpectedDeliverable, ...] = Field(default_factory=tuple)
    validation_points: ValidationPoints = Field(default_factory=ValidationPoints)
    baseline: Baseline = Field(default_factory=Baseline)
    scoring_rubric: dict[str, ScoringRubricEntry]
    pass_threshold: float = Field(ge=0.0, le=1.0)
    alert_on_drop_below: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_invariants(self) -> GoldTask:
        expected_suffix = f".v{self.task_version}"
        if not self.id.endswith(expected_suffix):
            raise ValueError(
                f"GoldTask id must end with {expected_suffix!r}; got {self.id!r}."
            )
        total_weight = sum(item.weight for item in self.scoring_rubric.values())
        if abs(total_weight - 1.0) > 1e-6:
            raise ValueError("GoldTask scoring rubric weights must sum to 1.0.")
        if self.pass_threshold < self.alert_on_drop_below:
            raise ValueError("pass_threshold must be >= alert_on_drop_below.")
        return self

