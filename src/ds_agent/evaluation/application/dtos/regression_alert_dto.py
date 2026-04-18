"""DTOs for regression-alert dispatch flows."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.evaluation.domain.entities.regression_alert_delivery import (
    RegressionAlertDelivery,
)
from ds_agent.evaluation.domain.entities.regression_board import RegressionBoardSnapshot


class RegressionAlertDispatchReport(BaseModel):
    """Dispatch summary for one regression-board alert send."""

    model_config = ConfigDict(frozen=True)

    snapshot: RegressionBoardSnapshot
    deliveries: tuple[RegressionAlertDelivery, ...] = Field(default_factory=tuple)
    fingerprint: str | None = None
    skipped: bool = False
    skip_reason: str | None = None

    @property
    def alert_count(self) -> int:
        return len(self.snapshot.alerts)

    @property
    def delivered_channels(self) -> tuple[str, ...]:
        return tuple(delivery.channel for delivery in self.deliveries)
