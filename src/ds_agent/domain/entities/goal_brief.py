"""GoalBrief entity for task contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ds_agent.domain.entities._id_patterns import GOAL_BRIEF_ID_PATTERN


class GoalBrief(BaseModel):
    """Business request translated into a concrete DS problem."""

    brief_id: str = Field(pattern=GOAL_BRIEF_ID_PATTERN)
    task_id: str = Field(min_length=1)
    business_question: str = Field(min_length=1)
    ds_problem_statement: str = Field(min_length=1)
    hypothesis: str | None = None
    comparison_baseline: str = Field(min_length=1)
    decision_to_make: str = Field(min_length=1)
    expected_effort: Literal["S", "M", "L", "XL"]
    created_at: datetime
    updated_at: datetime
