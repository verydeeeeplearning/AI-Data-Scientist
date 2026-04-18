"""Promotion record for learning item governance."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.domain.learning.learning_item import LearningItemType


class PromotionRecord(BaseModel):
    """Record of a learning item being promoted to organization assets."""

    model_config = ConfigDict(frozen=True)

    record_id: str = Field(min_length=1)
    item_id: str = Field(min_length=1)
    item_type: LearningItemType
    eval_score: float = Field(ge=0.0)
    eval_threshold: float = Field(ge=0.0)
    promoted_asset_ref: str = ""
    rollback_ref: str = ""
    promoted_at: datetime
    promoted_by: str = "system"
    metadata: dict[str, Any] = Field(default_factory=dict)
