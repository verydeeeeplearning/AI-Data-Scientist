"""Entities for production-vs-shadow evaluation comparisons."""

from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.evaluation.domain.entities.eval_score import EvalScore


class ShadowDimensionComparison(BaseModel):
    """Per-dimension delta between production and shadow scores."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    baseline_value: float = Field(ge=0.0, le=1.0)
    shadow_value: float = Field(ge=0.0, le=1.0)
    delta: float = Field(ge=-1.0, le=1.0)
    baseline_rationale: str = ""
    shadow_rationale: str = ""


class ShadowComparisonRecord(BaseModel):
    """Append-only persisted comparison between one production run and one shadow run."""

    model_config = ConfigDict(frozen=True)

    comparison_id: str = Field(default_factory=lambda: f"shadow-{uuid.uuid4().hex[:12]}")
    created_at: float = Field(default_factory=time.time, ge=0.0)
    session_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    baseline_run_id: str = Field(min_length=1)
    shadow_run_id: str = Field(min_length=1)
    baseline_mode: str = Field(default="online", min_length=1)
    shadow_mode: str = Field(default="shadow", min_length=1)
    baseline_weighted_score: float = Field(ge=0.0, le=1.0)
    shadow_weighted_score: float = Field(ge=0.0, le=1.0)
    weighted_score_delta: float = Field(ge=-1.0, le=1.0)
    baseline_passed: bool
    shadow_passed: bool
    baseline_scores: dict[str, EvalScore]
    shadow_scores: dict[str, EvalScore]
    dimension_deltas: tuple[ShadowDimensionComparison, ...] = Field(default_factory=tuple)
    baseline_metadata: dict[str, Any] = Field(default_factory=dict)
    shadow_metadata: dict[str, Any] = Field(default_factory=dict)
    baseline_model: str | None = None
    shadow_model: str | None = None
    shadow_budget_factor: float = Field(default=0.5, ge=0.0)

