from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ds_agent.application.services.scheduler_service import SchedulerService
from ds_agent.domain.entities.post_deploy import (
    PostDeployMonitorState,
    RemediationSummary,
    ServiceLevelSummary,
)
from ds_agent.infrastructure.cron_runner import CronRunner
from ds_agent.runtime.decision_os_scheduler import DecisionOsMonitorScheduler
from ds_agent.runtime.policy_store import JsonPolicyStore


@dataclass
class StubMonitor:
    states: list[PostDeployMonitorState]
    call_count: int = 0

    def periodic_sweep(self) -> list[PostDeployMonitorState]:
        self.call_count += 1
        return list(self.states)


def _state() -> PostDeployMonitorState:
    return PostDeployMonitorState.model_validate(
        {
            "state_id": "deploy-001",
            "model_id": "m_churn_lightgbm",
            "model_version": 5,
            "alias": "champion",
            "window": "24h",
            "observed_at": datetime(2026, 4, 16, 15, tzinfo=UTC),
            "drift": {
                "overall_status": "warning",
                "max_psi": 0.25,
                "max_ks": 0.4,
                "top_drifting_features": ["f_user_activity_30d"],
                "metrics": [],
            },
            "metrics": [],
            "service_level": ServiceLevelSummary(status="ok"),
            "remediation": RemediationSummary(
                decision="monitor",
                severity="low",
                rationale="Watch the next batch.",
                should_alert=False,
                recommended_steps=["Monitor."],
            ),
            "overall_status": "warning",
            "alerts": ["Feature drift warning"],
            "trigger_mode": "manual_only",
            "trigger_payload": {"trigger": "monitor"},
        }
    )


def test_registers_decision_os_post_deploy_order(tmp_path) -> None:
    scheduler = SchedulerService(
        store=JsonPolicyStore(base_dir=tmp_path),
        cron_runner=CronRunner(),
    )
    adapter = DecisionOsMonitorScheduler(
        scheduler_service=scheduler,
        monitor=StubMonitor([]),
        cron="*/15 * * * *",
    )

    order = adapter.register()

    assert order.order_id == DecisionOsMonitorScheduler.ORDER_ID
    assert order.trigger.cron == "*/15 * * * *"
    assert order.scope["job"] == "deploy_monitor_sweep"


def test_run_due_executes_monitor_and_records_history(tmp_path) -> None:
    scheduler = SchedulerService(
        store=JsonPolicyStore(base_dir=tmp_path),
        cron_runner=CronRunner(),
    )
    monitor = StubMonitor([_state()])
    adapter = DecisionOsMonitorScheduler(
        scheduler_service=scheduler,
        monitor=monitor,
        cron="*/15 * * * *",
    )
    adapter.register()

    states = adapter.run_due(now=datetime(2026, 4, 16, 15, 0, tzinfo=UTC))

    assert len(states) == 1
    assert monitor.call_count == 1
    history = scheduler.list_history(DecisionOsMonitorScheduler.ORDER_ID, limit=5)
    statuses = [item["status"] for item in history]
    assert "completed" in statuses
    assert "dispatched" in statuses
