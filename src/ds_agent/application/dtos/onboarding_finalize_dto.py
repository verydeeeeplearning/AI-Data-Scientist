"""DTOs for the onboarding finalize backend handoff."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ds_agent.application.dtos.mission_context_dto import MissionContextDTO


class OnboardingFinalizeRequestDTO(BaseModel):
    """Thin onboarding finalize payload used to bootstrap one session."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    session_id: str | None = Field(default=None, alias="sessionId")
    goal: str | None = None
    use_case_id: str | None = Field(default=None, alias="useCaseId")
    starter_prompt: str | None = Field(default=None, alias="starterPrompt")
    responses: dict[str, Any] | None = None

    @field_validator("session_id", "goal", "use_case_id", "starter_prompt", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class OnboardingFinalizeResultDTO(BaseModel):
    """Backend response returned after onboarding finalize bootstraps a session."""

    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId", min_length=1)
    created_session: bool = Field(alias="createdSession")
    goal_seeded: bool = Field(alias="goalSeeded")
    task_id: str | None = Field(default=None, alias="taskId")
    mission: MissionContextDTO
