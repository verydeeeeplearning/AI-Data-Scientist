"""Score entities produced by evaluation scorers."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType


class EvalScore(BaseModel):
    """One dimension score for an eval run."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    value: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)
    sub_scores: dict[str, float] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    version: str = Field(default="1.0", min_length=1)
    judge_type: JudgeType

    @model_validator(mode="after")
    def _validate_sub_scores(self) -> EvalScore:
        for key, value in self.sub_scores.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"Sub-score {key!r} must be in [0, 1].")
        return self


class EvalDatasetRecord(BaseModel):
    """Append-only record stored in the eval dataset."""

    model_config = ConfigDict(frozen=True)

    recorded_at: float = Field(default_factory=time.time)
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
