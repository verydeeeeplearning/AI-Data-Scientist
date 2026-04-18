"""Domain event model for task contract changes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskContractEvent(BaseModel):
    """Serializable task-contract event persisted for audit and testing."""

    event_type: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    occurred_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
