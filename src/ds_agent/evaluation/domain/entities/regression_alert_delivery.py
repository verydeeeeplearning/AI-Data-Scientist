"""Delivery records for regression-board alert notifications."""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RegressionAlertDelivery(BaseModel):
    """One webhook delivery attempt for regression alerts."""

    model_config = ConfigDict(frozen=True)

    channel: Literal["slack", "teams"]
    alert_count: int = Field(ge=0)
    delivered_at: float = Field(default_factory=time.time, ge=0.0)
    target: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    alert_kinds: tuple[str, ...] = Field(default_factory=tuple)
    response: str | None = None
