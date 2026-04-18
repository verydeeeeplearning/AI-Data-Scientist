"""LLM judge protocol used by heuristic scorers when available."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.evaluation.domain.entities.eval_score import EvalScore


class JudgeRequest(BaseModel):
    """Generic prompt contract passed to judge models."""

    model_config = ConfigDict(frozen=True)

    scorer_name: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    fallback_score: float = Field(ge=0.0, le=1.0)
    fallback_rationale: str = Field(min_length=1)


class JudgeLLM(Protocol):
    """Optional adapter used by LLM-judge scorers."""

    def judge(self, request: JudgeRequest) -> EvalScore:
        """Return a normalized score for the judge request."""

