"""Decision OS experiment entities for reproducible experiment tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.domain.entities.feature import FeatureRef
from ds_agent.domain.entities.review_artifact import ReviewArtifact

VerifierStatus = Literal["PASS", "WARN", "FAIL"]
ExperimentStatus = Literal["running", "succeeded", "failed", "archived"]
PromotionState = Literal["none", "candidate", "staging", "production", "retired"]
ReproducibilityStatus = Literal["unknown", "reproduced", "diverged"]


class Hypothesis(BaseModel):
    """Structured hypothesis for one experiment run."""

    model_config = ConfigDict(frozen=True)

    statement: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    expected_effect: str = Field(min_length=1)


class Method(BaseModel):
    """Methodology and execution contract for one experiment run."""

    model_config = ConfigDict(frozen=True)

    model_family: str = Field(min_length=1)
    hyperparameters: dict[str, object] = Field(default_factory=dict)
    train_window: tuple[datetime, datetime] | None = None
    eval_window: tuple[datetime, datetime] | None = None
    random_seed: int | None = None
    code_ref: str = Field(min_length=1)
    nondeterminism_notes: str | None = None


class RunResult(BaseModel):
    """Outcome payload captured after an experiment run finishes."""

    model_config = ConfigDict(frozen=True)

    metrics: dict[str, float] = Field(default_factory=dict)
    confusion_matrix: dict[str, object] | None = None
    plots: list[str] = Field(default_factory=list)


class DiffableRun(BaseModel):
    """Comparison-friendly projection of an experiment run."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    feature_set: dict[str, int] = Field(default_factory=dict)
    config: dict[str, object] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    verifier_summary: dict[str, VerifierStatus] | None = None
    code_ref: str = Field(min_length=1)
    data_snapshot_uri: str = Field(min_length=1)


class ExperimentRun(BaseModel):
    """Typed Decision OS experiment run."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    experiment_group: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    hypothesis: Hypothesis
    method: Method
    feature_refs: list[FeatureRef] = Field(default_factory=list)
    data_snapshot_uri: str = Field(min_length=1)
    result: RunResult
    verifier_report_id: str | None = None
    verifier_summary: dict[str, VerifierStatus] | None = None
    verifier_findings: list[str] = Field(default_factory=list)
    created_at: datetime
    owner: str = Field(min_length=1)
    status: ExperimentStatus = "succeeded"
    parent_run_id: str | None = None
    promotion_state: PromotionState = "none"
    reproducibility_status: ReproducibilityStatus = "unknown"
    review_artifacts: list[ReviewArtifact] = Field(default_factory=list)

    def to_diffable(self) -> DiffableRun:
        """Project the run into the normalized shape used by run-diff logic."""

        config: dict[str, object] = {
            "model_family": self.method.model_family,
            "hyperparameters": self.method.hyperparameters,
            "random_seed": self.method.random_seed,
        }
        if self.method.train_window is not None:
            config["train_window"] = [
                self.method.train_window[0].isoformat(),
                self.method.train_window[1].isoformat(),
            ]
        if self.method.eval_window is not None:
            config["eval_window"] = [
                self.method.eval_window[0].isoformat(),
                self.method.eval_window[1].isoformat(),
            ]
        if self.method.nondeterminism_notes is not None:
            config["nondeterminism_notes"] = self.method.nondeterminism_notes

        return DiffableRun(
            run_id=self.run_id,
            feature_set={ref.feature_id: ref.version for ref in self.feature_refs},
            config=config,
            metrics=self.result.metrics,
            verifier_summary=self.verifier_summary,
            code_ref=self.method.code_ref,
            data_snapshot_uri=self.data_snapshot_uri,
        )
