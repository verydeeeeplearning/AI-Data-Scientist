"""Scheduler adapter for automatic regression-board alert dispatch."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from ds_agent.application.services.scheduler_service import SchedulerService
from ds_agent.domain.entities.standing_order import CronTrigger, StandingOrder
from ds_agent.evaluation.application.dtos.regression_alert_dto import (
    RegressionAlertDispatchReport,
)


class RegressionAlertScheduler:
    """Register and execute one periodic regression-alert dispatch sweep."""

    ORDER_ID = "evaluation_regression_alerts"

    def __init__(
        self,
        *,
        scheduler_service: SchedulerService,
        dispatch: Callable[..., RegressionAlertDispatchReport],
        cron: str = "*/30 * * * *",
        session_id: str = "evaluation:regression_alerts",
        channels: Sequence[str] = (),
        mode: str | None = None,
        domain: str | None = None,
        recent_window: int = 3,
        baseline_window_days: int = 14,
    ) -> None:
        self._scheduler_service = scheduler_service
        self._dispatch = dispatch
        self._cron = cron
        self._session_id = session_id
        self._channels = tuple(channel.strip().lower() for channel in channels if channel.strip())
        self._mode = None if mode is None else mode.strip() or None
        self._domain = None if domain is None else domain.strip() or None
        self._recent_window = max(1, int(recent_window))
        self._baseline_window_days = max(1, int(baseline_window_days))

    def register(self) -> StandingOrder:
        """Create or update the standing order used for alert sweeps."""

        existing = self._scheduler_service.get_order(self.ORDER_ID)
        created_at = existing.created_at if existing is not None else datetime.now(UTC).timestamp()
        updated_at = datetime.now(UTC).timestamp()
        filters = [f"mode={self._mode or 'all'}", f"domain={self._domain or 'all'}"]
        if self._channels:
            filters.append(f"channels={','.join(self._channels)}")
        order = StandingOrder(
            order_id=self.ORDER_ID,
            session_id=self._session_id,
            name="Evaluation Regression Alert Sweep",
            description=(
                "Builds the latest regression board snapshot and dispatches configured "
                "Slack/Teams alerts when active regressions remain unresolved."
            ),
            prompt=(
                "Run the evaluation regression-alert sweep and notify configured "
                "operator channels when the board still has active alerts."
            ),
            trigger=CronTrigger(self._cron, timezone="UTC"),
            scope={
                "system": "evaluation",
                "job": "regression_alert_dispatch",
                "filters": filters,
            },
            approval_gate="notify_only",
            created_at=created_at,
            updated_at=updated_at,
        )
        return self._scheduler_service.register(order)

    def run_due(self, *, now: datetime | None = None) -> RegressionAlertDispatchReport | None:
        """Execute the alert sweep when the registered cron trigger is due."""

        current = datetime.now(UTC) if now is None else _ensure_utc(now)
        due_orders = self._scheduler_service.evaluate_triggers(
            now=current,
            event_kind="schedule.tick",
        )
        if not any(order.order_id == self.ORDER_ID for order in due_orders):
            return None

        self._scheduler_service.mark_dispatched(
            self.ORDER_ID,
            triggered_at=current.timestamp(),
        )
        report = self._dispatch(
            channels=self._channels or None,
            mode=self._mode,
            domain=self._domain,
            recent_window=self._recent_window,
            baseline_window_days=self._baseline_window_days,
            skip_if_unchanged=True,
            dispatch_source="schedule",
        )
        self._scheduler_service.record_result(
            self.ORDER_ID,
            status="completed",
            summary=_summary_for_report(report),
            metadata={
                "mode": self._mode,
                "domain": self._domain,
                "channels": list(self._channels),
                "alertCount": report.alert_count,
                "deliveryCount": len(report.deliveries),
                "skipped": report.skipped,
                "skipReason": report.skip_reason,
                "fingerprint": report.fingerprint,
            },
        )
        return report


def _summary_for_report(report: RegressionAlertDispatchReport) -> str:
    if report.skipped:
        return "Regression alert sweep skipped because the alert fingerprint is unchanged."
    if report.alert_count == 0:
        return "Regression alert sweep found no active board alerts."
    if report.deliveries:
        return (
            "Regression alert sweep dispatched "
            f"{report.alert_count} alert(s) across {len(report.deliveries)} channel(s)."
        )
    return "Regression alert sweep found active alerts but no configured webhook matched."


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
