"""DTOs for the Mission Header pause-agent action."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PauseAgentRequestDTO(BaseModel):
    """Pause-agent request initiated from the Mission Header."""

    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId", min_length=1)
    reason: Literal["budget_warning", "manual"] = "manual"


class PauseAgentResultDTO(BaseModel):
    """Result of one pause-agent action."""

    model_config = ConfigDict(populate_by_name=True)

    paused: bool
    previous_status: Literal["running", "idle", "paused"] = Field(alias="previousStatus")
