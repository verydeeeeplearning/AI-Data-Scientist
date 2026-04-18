"""Human rubric entity for operator-review overrides."""

from __future__ import annotations

import time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HumanRubric(BaseModel):
    """Normalized human review payload."""

    model_config = ConfigDict(frozen=True)

    reviewer_id: str = Field(min_length=1)
    dimensions: dict[str, float]
    comment: str | None = None

    @model_validator(mode="after")
    def _validate_dimensions(self) -> HumanRubric:
        for key, value in self.dimensions.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"Rubric value for {key!r} must be in [0, 1].")
        return self


class HumanRubricRecord(BaseModel):
    """Persisted human rubric bound to one run/session."""

    model_config = ConfigDict(frozen=True)

    recorded_at: float = Field(default_factory=time.time)
    session_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_id: str | None = None
    rubric: HumanRubric
