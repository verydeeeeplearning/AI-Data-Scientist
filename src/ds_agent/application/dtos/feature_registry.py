"""DTOs for Decision OS feature-registry boundaries."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ds_agent.domain.entities.feature import FeatureAlias


class FeatureRegistrationResultDTO(BaseModel):
    """Response returned after a feature definition is registered."""

    feature_id: str
    version: int
    alias: FeatureAlias
    validation_warnings: list[str] = Field(default_factory=list)
