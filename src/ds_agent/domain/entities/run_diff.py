"""Run-diff entities for Decision OS experiment comparison."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.domain.entities.feature import FeatureRef

DiffDirection = Literal["better", "worse", "neutral"]
ArtifactDiffStatus = Literal["added", "removed", "changed", "shared"]
ArtifactKind = Literal["plot", "review_artifact"]
DecisionDiffKind = Literal[
    "hypothesis",
    "feature_strategy",
    "model_strategy",
    "verifier",
    "review_artifact",
]


class FeatureSetDiff(BaseModel):
    """Feature-level delta between two experiment runs."""

    model_config = ConfigDict(frozen=True)

    added: list[FeatureRef] = Field(default_factory=list)
    removed: list[FeatureRef] = Field(default_factory=list)
    version_changed: list[tuple[str, int, int]] = Field(default_factory=list)


class ConfigDiff(BaseModel):
    """Config-level delta between two experiment runs."""

    model_config = ConfigDict(frozen=True)

    changed: dict[str, tuple[object, object]] = Field(default_factory=dict)
    added: dict[str, object] = Field(default_factory=dict)
    removed: dict[str, object] = Field(default_factory=dict)


class MetricDelta(BaseModel):
    """Metric delta between two experiment runs."""

    model_config = ConfigDict(frozen=True)

    metric: str
    from_value: float
    to_value: float
    delta: float
    direction: DiffDirection
    highlighted: bool = False
    significance_note: str | None = None


class VerifierDiff(BaseModel):
    """Verifier-summary delta between two experiment runs."""

    model_config = ConfigDict(frozen=True)

    statistical: tuple[str, str] = ("UNKNOWN", "UNKNOWN")
    data: tuple[str, str] = ("UNKNOWN", "UNKNOWN")
    policy: tuple[str, str] = ("UNKNOWN", "UNKNOWN")
    new_findings: list[str] = Field(default_factory=list)
    resolved_findings: list[str] = Field(default_factory=list)


class ArtifactDiffEntry(BaseModel):
    """Artifact-level delta surfaced on the compare board."""

    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    artifact_kind: ArtifactKind
    status: ArtifactDiffStatus
    run_a_value: str | None = None
    run_b_value: str | None = None
    summary: str


class DecisionTraceDiffEntry(BaseModel):
    """Decision-trace divergence marker between two runs."""

    model_config = ConfigDict(frozen=True)

    key: str
    decision_kind: DecisionDiffKind
    divergence_point: str
    run_a_summary: str | None = None
    run_b_summary: str | None = None


class RunDiff(BaseModel):
    """Deterministic diff artifact returned by the Decision OS."""

    model_config = ConfigDict(frozen=True)

    run_a_id: str
    run_b_id: str
    feature_set: FeatureSetDiff
    config: ConfigDiff
    metrics: list[MetricDelta] = Field(default_factory=list)
    artifacts: list[ArtifactDiffEntry] = Field(default_factory=list)
    decisions: list[DecisionTraceDiffEntry] = Field(default_factory=list)
    verifier: VerifierDiff
    code_ref: tuple[str, str]
    data_snapshot: tuple[str, str]
    summary_markdown: str
