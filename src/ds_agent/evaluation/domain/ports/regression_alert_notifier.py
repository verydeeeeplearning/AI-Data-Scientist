"""Notification contract for regression-board alert delivery."""

from __future__ import annotations

from typing import Protocol

from ds_agent.evaluation.domain.entities.regression_alert_delivery import (
    RegressionAlertDelivery,
)
from ds_agent.evaluation.domain.entities.regression_board import (
    RegressionAlert,
    RegressionBoardSnapshot,
)


class RegressionAlertNotifier(Protocol):
    """Send regression-board alerts to an external channel."""

    channel: str

    def notify(
        self,
        *,
        snapshot: RegressionBoardSnapshot,
        alerts: tuple[RegressionAlert, ...],
    ) -> RegressionAlertDelivery:
        """Deliver the selected regression alerts."""
