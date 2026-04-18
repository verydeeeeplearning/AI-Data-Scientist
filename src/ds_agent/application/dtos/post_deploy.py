"""DTOs for Decision OS post-deploy status queries."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.domain.entities.post_deploy import PostDeployMonitorState


class PostDeployStatusResultDTO(BaseModel):
    """Returned status summary for a model's recent post-deploy observations."""

    model_config = ConfigDict(frozen=True)

    model_id: str = Field(min_length=1)
    model_version: int = Field(ge=1)
    window: str = Field(min_length=1)
    summary: PostDeployMonitorState
    alerts: list[str] = Field(default_factory=list)
    observations: int = Field(ge=1)
