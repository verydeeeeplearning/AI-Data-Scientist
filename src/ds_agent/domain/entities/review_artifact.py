"""Structured review artifacts surfaced by Decision OS shared skills."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ReviewSkillName = Literal[
    "backtesting",
    "causal-assumption-check",
    "uncertainty-quantification",
    "retrain-vs-rollback",
]
ReviewArtifactStatus = Literal["pass", "warn", "fail"]
RollbackRecommendation = Literal["retrain", "rollback", "monitor", "hold"]


class FoldResult(BaseModel):
    """One fold-level backtest result."""

    model_config = ConfigDict(frozen=True)

    fold_label: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    score: float
    baseline_score: float | None = None
    status: ReviewArtifactStatus = "pass"


class BacktestResult(BaseModel):
    """Structured backtesting output for one experiment."""

    model_config = ConfigDict(frozen=True)

    artifact_type: Literal["backtesting"] = "backtesting"
    folds: list[FoldResult] = Field(default_factory=list)
    consistency_score: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


class CausalRisk(BaseModel):
    """One causal assumption risk."""

    model_config = ConfigDict(frozen=True)

    assumption: str = Field(min_length=1)
    severity: ReviewArtifactStatus = "warn"
    detail: str = Field(min_length=1)


class CausalReview(BaseModel):
    """Structured causal review output."""

    model_config = ConfigDict(frozen=True)

    artifact_type: Literal["causal-assumption-check"] = "causal-assumption-check"
    risks: list[CausalRisk] = Field(default_factory=list)
    confounders: list[str] = Field(default_factory=list)
    is_causal: bool = False


class UncertaintyInterval(BaseModel):
    """One uncertainty interval for a reported metric."""

    model_config = ConfigDict(frozen=True)

    metric: str = Field(min_length=1)
    lower: float
    upper: float
    confidence_level: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_bounds(self) -> UncertaintyInterval:
        if self.lower > self.upper:
            raise ValueError("lower must be <= upper")
        return self


class UncertaintyReport(BaseModel):
    """Structured uncertainty quantification output."""

    model_config = ConfigDict(frozen=True)

    artifact_type: Literal["uncertainty-quantification"] = "uncertainty-quantification"
    methodology: str = Field(min_length=1)
    intervals: list[UncertaintyInterval] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RetrainVsRollback(BaseModel):
    """Structured remediation recommendation output."""

    model_config = ConfigDict(frozen=True)

    artifact_type: Literal["retrain-vs-rollback"] = "retrain-vs-rollback"
    recommendation: RollbackRecommendation
    rationale: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)


ReviewArtifactPayload = Annotated[
    BacktestResult | CausalReview | UncertaintyReport | RetrainVsRollback,
    Field(discriminator="artifact_type"),
]


class ReviewArtifact(BaseModel):
    """Persisted review artifact rendered by the Review tab."""

    model_config = ConfigDict(frozen=True)

    artifact_id: str = Field(min_length=1)
    skill_name: ReviewSkillName
    summary: str = Field(min_length=1)
    narrative: str | None = None
    created_at: datetime
    artifact: ReviewArtifactPayload

    @model_validator(mode="after")
    def _validate_skill_name(self) -> ReviewArtifact:
        if self.skill_name != self.artifact.artifact_type:
            raise ValueError("skill_name must match artifact.artifact_type")
        return self


def build_review_artifact(
    *,
    skill_name: ReviewSkillName,
    summary: str,
    artifact: dict[str, object],
    narrative: str | None = None,
    artifact_id: str | None = None,
    created_at: datetime | None = None,
) -> ReviewArtifact:
    """Build one typed review artifact from a raw payload."""

    normalized = dict(artifact)
    normalized["artifact_type"] = skill_name
    payload_model: ReviewArtifactPayload
    if skill_name == "backtesting":
        payload_model = BacktestResult.model_validate(normalized)
    elif skill_name == "causal-assumption-check":
        payload_model = CausalReview.model_validate(normalized)
    elif skill_name == "uncertainty-quantification":
        payload_model = UncertaintyReport.model_validate(normalized)
    else:
        payload_model = RetrainVsRollback.model_validate(normalized)
    return ReviewArtifact(
        artifact_id=artifact_id or f"review-{uuid.uuid4().hex[:12]}",
        skill_name=skill_name,
        summary=summary,
        narrative=narrative,
        created_at=created_at or datetime.now(UTC),
        artifact=payload_model,
    )
