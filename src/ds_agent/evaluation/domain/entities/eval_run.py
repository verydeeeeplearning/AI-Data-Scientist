"""Eval run entities representing one autonomous agent execution."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.evaluation.domain.entities.human_rubric import HumanRubric


class EvalArtifact(BaseModel):
    """User-visible or internal artifact produced by a run."""

    model_config = ConfigDict(frozen=True)

    artifact_type: str = Field(min_length=1)
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)


class EvalToolCall(BaseModel):
    """One tool call observed during a run."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: Literal["ok", "error"] = "ok"
    cost_usd: float = Field(default=0.0, ge=0.0)


class EvalApprovalDecision(BaseModel):
    """Approval request emitted by the agent."""

    model_config = ConfigDict(frozen=True)

    action: str = Field(min_length=1)
    requested: bool = True
    approved: bool | None = None


class EvalOperatorFeedback(BaseModel):
    """Operator signals used for satisfaction scoring."""

    model_config = ConfigDict(frozen=True)

    approved_final: bool | None = None
    follow_up_messages: int = Field(default=0, ge=0)
    manual_intervention: bool = False
    human_score: float | None = Field(default=None, ge=0.0, le=5.0)
    comment: str | None = None


class EvalRun(BaseModel):
    """Portable execution trace used by the evaluation harness."""

    model_config = ConfigDict(extra="ignore")

    run_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    mode: Literal["offline", "shadow", "online"] = "offline"
    user_prompt: str = ""
    started_at: float
    finished_at: float | None = None
    decision_ready_at: float | None = None
    cost_usd: float = Field(default=0.0, ge=0.0)
    goal_brief: dict[str, str] = Field(default_factory=dict)
    metric_choices: tuple[str, ...] = Field(default_factory=tuple)
    temporal_violations: tuple[str, ...] = Field(default_factory=tuple)
    tool_calls: tuple[EvalToolCall, ...] = Field(default_factory=tuple)
    approvals: tuple[EvalApprovalDecision, ...] = Field(default_factory=tuple)
    artifacts: tuple[EvalArtifact, ...] = Field(default_factory=tuple)
    underlying_metrics: dict[str, float] = Field(default_factory=dict)
    final_summary: str = ""
    summary_sections: dict[str, str] = Field(default_factory=dict)
    operator_feedback: EvalOperatorFeedback = Field(default_factory=EvalOperatorFeedback)
    human_rubric: HumanRubric | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def artifact_types(self) -> set[str]:
        return {artifact.artifact_type for artifact in self.artifacts}

    def artifacts_for_type(self, artifact_type: str) -> tuple[EvalArtifact, ...]:
        return tuple(
            artifact for artifact in self.artifacts if artifact.artifact_type == artifact_type
        )
