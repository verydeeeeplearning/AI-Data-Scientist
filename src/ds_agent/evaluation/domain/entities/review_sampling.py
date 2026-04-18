"""Entities for deterministic human-review sampling decisions."""

from __future__ import annotations

import time

from pydantic import BaseModel, ConfigDict, Field


class ReviewSamplingDecision(BaseModel):
    """Persisted decision describing whether one run should collect human review."""

    model_config = ConfigDict(frozen=True)

    recorded_at: float = Field(default_factory=time.time)
    session_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_id: str | None = None
    domain: str = Field(default="generic", min_length=1)
    surface: str | None = None
    target_rate: float = Field(ge=0.0, le=1.0)
    bucket: float = Field(ge=0.0, lt=1.0)
    sampled: bool
    stratum: str = Field(min_length=1)
    policy_version: str = Field(default="domain_hash_v1", min_length=1)

