"""Review verdict entities for verifier orchestration and task contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ds_agent.domain.entities._id_patterns import REVIEW_VERDICT_ID_PATTERN

CheckStatus = Literal["pass", "warn", "fail", "skipped", "error"]
LayerName = Literal["statistical", "data", "policy", "narrative"]
LayerStatus = Literal["pass", "warn", "fail", "error"]
VerdictCategory = Literal[
    "statistical",
    "data",
    "data_quality",
    "policy",
    "narrative",
    "orchestrator",
]
VerdictResult = Literal["pass", "warn", "fail"]
ConfidenceGrade = Literal["high", "medium", "low", "insufficient"]
IssueSeverity = Literal["low", "medium", "high", "critical"]
ActionPriority = Literal["low", "medium", "high"]
VerifierScope = Literal["all", "statistical", "data", "policy", "narrative"]

_CHECK_STATUS_PRIORITY: dict[CheckStatus, int] = {
    "error": 4,
    "fail": 3,
    "warn": 2,
    "pass": 1,
    "skipped": 0,
}
_LAYER_STATUS_TO_RESULT: dict[LayerStatus, VerdictResult] = {
    "error": "fail",
    "fail": "fail",
    "warn": "warn",
    "pass": "pass",
}
_RESULT_PRIORITY: dict[VerdictResult, int] = {
    "fail": 3,
    "warn": 2,
    "pass": 1,
}


def _derive_confidence_grade(score: float) -> ConfidenceGrade:
    if score >= 0.80:
        return "high"
    if score >= 0.50:
        return "medium"
    if score >= 0.20:
        return "low"
    return "insufficient"


def _pick_worst_check_status(statuses: list[CheckStatus]) -> LayerStatus:
    if not statuses:
        return "pass"
    worst = max(statuses, key=_CHECK_STATUS_PRIORITY.__getitem__)
    if worst == "skipped":
        return "pass"
    return "error" if worst == "error" else worst


def _pick_worst_result(results: list[VerdictResult]) -> VerdictResult:
    if not results:
        return "pass"
    return max(results, key=_RESULT_PRIORITY.__getitem__)


class CheckResult(BaseModel):
    """Outcome of one deterministic verifier check."""

    model_config = ConfigDict(validate_assignment=True)

    check_id: str = Field(min_length=1)
    status: CheckStatus
    score: float = Field(ge=0.0, le=1.0)
    evidence: dict[str, Any] = Field(default_factory=dict)
    message: str = Field(min_length=1)
    remediation_hint: str | None = None
    duration_ms: int = Field(default=0, ge=0)


class LayerResult(BaseModel):
    """Aggregated result of one verifier layer."""

    model_config = ConfigDict(validate_assignment=True)

    layer: LayerName
    overall: LayerStatus | None = None
    checks: list[CheckResult] = Field(default_factory=list)
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    summary: str | None = None
    partial_failure: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _normalize(self) -> LayerResult:
        if self.overall is None:
            object.__setattr__(
                self,
                "overall",
                _pick_worst_check_status([check.status for check in self.checks]),
            )
        if self.score is None:
            scored_checks = [
                check.score for check in self.checks if check.status not in {"skipped", "error"}
            ]
            object.__setattr__(
                self,
                "score",
                sum(scored_checks) / len(scored_checks) if scored_checks else 1.0,
            )
        return self


class Issue(BaseModel):
    """Blocking or advisory issue emitted by the verifier."""

    model_config = ConfigDict(validate_assignment=True)

    issue_id: str | None = None
    layer: LayerName | None = None
    check_id: str | None = None
    severity: IssueSeverity = "medium"
    message: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    blocking: bool = True


class ActionHint(BaseModel):
    """LLM-facing remediation suggestion derived from a verdict."""

    model_config = ConfigDict(validate_assignment=True)

    action_id: str | None = None
    title: str = Field(min_length=1)
    description: str | None = None
    priority: ActionPriority = "medium"
    scope: VerifierScope | None = None
    related_issue_ids: list[str] = Field(default_factory=list)


class ConfidenceBand(BaseModel):
    """Confidence score, grade, and a short rationale."""

    model_config = ConfigDict(validate_assignment=True)

    score: float = Field(ge=0.0, le=1.0)
    grade: ConfidenceGrade | None = None
    rationale: str = ""

    @model_validator(mode="after")
    def _normalize(self) -> ConfidenceBand:
        derived_grade = _derive_confidence_grade(self.score)
        if self.grade is None:
            object.__setattr__(self, "grade", derived_grade)
            return self
        if self.grade != derived_grade:
            raise ValueError(
                f"confidence grade '{self.grade}' does not match score bucket '{derived_grade}'"
            )
        return self


class ReviewVerdict(BaseModel):
    """Typed verifier verdict stored with task contracts and orchestration logs."""

    model_config = ConfigDict(validate_assignment=True)

    verdict_id: str = Field(pattern=REVIEW_VERDICT_ID_PATTERN)
    task_id: str = Field(min_length=1)
    category: VerdictCategory = "orchestrator"
    result: VerdictResult | None = None
    reviewer: str = Field(default="verifier", min_length=1)
    summary: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime

    run_id: str | None = None
    overall: VerdictResult | None = None
    layers: list[LayerResult] = Field(default_factory=list)
    blocking_issues: list[Issue] = Field(default_factory=list)
    confidence: ConfidenceBand | None = None
    recommended_actions: list[ActionHint] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _normalize(self) -> ReviewVerdict:
        derived_results: list[VerdictResult] = []
        if self.result is not None:
            derived_results.append(self.result)
        if self.overall is not None:
            derived_results.append(self.overall)
        if self.layers:
            derived_results.extend(
                _LAYER_STATUS_TO_RESULT[layer.overall or "pass"] for layer in self.layers
            )

        final_result = _pick_worst_result(derived_results)
        object.__setattr__(self, "result", final_result)
        object.__setattr__(self, "overall", final_result)

        if self.summary is None or not self.summary.strip():
            object.__setattr__(self, "summary", self._derive_summary())
        return self

    def _derive_summary(self) -> str:
        if self.confidence is not None and self.confidence.rationale.strip():
            return self.confidence.rationale.strip()
        if self.blocking_issues:
            return self.blocking_issues[0].message
        if self.layers:
            parts = [
                f"{layer.layer}={_LAYER_STATUS_TO_RESULT[layer.overall or 'pass']}"
                for layer in self.layers
            ]
            return ", ".join(parts[:4])
        return f"{self.category} review {self.result}"
