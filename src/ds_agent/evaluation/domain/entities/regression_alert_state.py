"""Persistent state used to dedupe automatic regression-alert dispatches."""

from __future__ import annotations

import time

from pydantic import BaseModel, ConfigDict, Field


class RegressionAlertDispatchState(BaseModel):
    """Last delivered regression-alert fingerprint for one dispatch scope."""

    model_config = ConfigDict(frozen=True)

    dedupe_key: str = Field(min_length=1)
    fingerprint: str = Field(min_length=1)
    channels: tuple[str, ...] = Field(default_factory=tuple)
    dispatch_source: str = Field(min_length=1)
    alert_count: int = Field(ge=0)
    summary: str = Field(min_length=1)
    delivered_at: float = Field(default_factory=time.time, ge=0.0)
