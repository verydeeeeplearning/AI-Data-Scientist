"""Playbook candidate for reusable workflow patterns."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlaybookCandidate(BaseModel):
    """A workflow pattern detected as potentially reusable."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(min_length=1)
    entry_id: str = Field(min_length=1)
    pattern_signature: str = Field(min_length=1)
    description: str = ""
    occurrence_count: int = Field(default=1, ge=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    promoted: bool = False
