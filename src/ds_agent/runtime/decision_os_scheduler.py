"""Scheduler adapter for Decision OS post-deploy monitoring."""

from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.application.services.scheduler_service import SchedulerService
from ds_agent.domain.entities.standing_order import CronTrigger, StandingOrder
from ds_agent.runtime.post_deploy_monitor import PostDeployMonitor


class DecisionOsMonitorScheduler:
    """Register and execute the periodic post-deploy sweep as one standing order."""

    ORDER_ID = "decision_os_post_deploy_monitor"

    def __init__(
        self,
        *,
        scheduler_service: SchedulerService,
        monitor: PostDeployMonitor,
        cron: str = "*/15 * * * *",
        session_id: str = "decision_os:monitor",
    ) -> None:
        self._scheduler_service = scheduler_service
        self._monitor = monitor
        self._cron = cron
        self._session_id = session_id

    def register(self) -> StandingOrder:
        """Create or update the standing order used for periodic sweeps."""

        existing = self._scheduler_service.get_order(self.ORDER_ID)
        created_at = existing.created_at if existing is not None else datetime.now(UTC).timestamp()
        updated_at = datetime.now(UTC).timestamp()
        order = StandingOrder(
            order_id=self.ORDER_ID,
            session_id=self._session_id,
            name="Decision OS Post-Deploy Sweep",
            description=(
                "Runs the built-in Decision OS deploy monitor over active champion/canary models."
            ),
            prompt=(
                "Run the Decision OS post-deploy monitor sweep and execute configured "
                "automatic remediation actions."
            ),
            trigger=CronTrigger(self._cron, timezone="UTC"),
            scope={"system": "decision_os", "job": "deploy_monitor_sweep"},
            approval_gate="notify_only",
            created_at=created_at,
            updated_at=updated_at,
        )
        return self._scheduler_service.register(order)

    def run_due(self, *, now: datetime | None = None) -> list:
        """Execute the monitor when the registered cron trigger is due."""

        current = datetime.now(UTC) if now is None else _ensure_utc(now)
        due_orders = self._scheduler_service.evaluate_triggers(
            now=current,
            event_kind="schedule.tick",
        )
        if not any(order.order_id == self.ORDER_ID for order in due_orders):
            return []

        self._scheduler_service.mark_dispatched(
            self.ORDER_ID,
            triggered_at=current.timestamp(),
        )
        states = self._monitor.periodic_sweep()
        alert_count = sum(1 for state in states if state.alerts)
        self._scheduler_service.record_result(
            self.ORDER_ID,
            status="completed",
            summary=(
                "Decision OS post-deploy sweep completed for "
                f"{len(states)} model(s) with {alert_count} alerting result(s)."
            ),
            metadata={
                "stateCount": len(states),
                "alertCount": alert_count,
            },
        )
        return states


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
