from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.application.services.scheduler_service import SchedulerService
from ds_agent.evaluation.application.dtos.regression_alert_dto import (
    RegressionAlertDispatchReport,
)
from ds_agent.evaluation.domain.entities.regression_alert_delivery import (
    RegressionAlertDelivery,
)
from ds_agent.evaluation.domain.entities.regression_board import (
    RegressionAlert,
    RegressionBoardSnapshot,
    RegressionOverallSummary,
    RegressionWindowStats,
)
from ds_agent.infrastructure.cron_runner import CronRunner
from ds_agent.runtime.policy_store import JsonPolicyStore
from ds_agent.runtime.regression_alert_scheduler import RegressionAlertScheduler


class StubDispatch:
    def __init__(self, report: RegressionAlertDispatchReport) -> None:
        self.report = report
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs) -> RegressionAlertDispatchReport:
        self.calls.append(kwargs)
        return self.report


def _report() -> RegressionAlertDispatchReport:
    snapshot = RegressionBoardSnapshot(
        total_records=5,
        recent_window=3,
        baseline_window_days=14,
        mode_filter=None,
        domain_filter="retail",
        overall=RegressionOverallSummary(
            recent=RegressionWindowStats(record_count=3, avg_weighted_score=0.42, pass_rate=0.0),
            baseline=RegressionWindowStats(
                record_count=2,
                avg_weighted_score=0.85,
                pass_rate=1.0,
            ),
            delta_score=-0.43,
            delta_pass_rate=-1.0,
        ),
        alerts=(
            RegressionAlert(
                kind="pass_rate_drop",
                severity="high",
                scope="overall",
                message="Gold-suite pass rate dropped below the rolling baseline by more than 3pp.",
                current_value=0.0,
                baseline_value=1.0,
                delta=-1.0,
            ),
        ),
    )
    return RegressionAlertDispatchReport(
        snapshot=snapshot,
        deliveries=(
            RegressionAlertDelivery(
                channel="slack",
                alert_count=1,
                target="hooks.slack.test",
                summary="sent",
            ),
        ),
        fingerprint="fp-1",
    )


def test_registers_regression_alert_order(tmp_path) -> None:
    store = JsonPolicyStore(base_dir=tmp_path)
    scheduler = SchedulerService(store=store, cron_runner=CronRunner())
    adapter = RegressionAlertScheduler(
        scheduler_service=scheduler,
        dispatch=StubDispatch(_report()),
        cron="*/30 * * * *",
        channels=("slack", "teams"),
        mode="online",
        domain="retail",
    )

    order = adapter.register()

    assert order.order_id == RegressionAlertScheduler.ORDER_ID
    assert order.trigger.cron == "*/30 * * * *"
    assert order.scope["job"] == "regression_alert_dispatch"


def test_run_due_executes_dispatch_and_records_history(tmp_path) -> None:
    store = JsonPolicyStore(base_dir=tmp_path)
    scheduler = SchedulerService(store=store, cron_runner=CronRunner())
    dispatch = StubDispatch(_report())
    adapter = RegressionAlertScheduler(
        scheduler_service=scheduler,
        dispatch=dispatch,
        cron="*/30 * * * *",
        channels=("slack",),
        domain="retail",
    )
    order = adapter.register()
    order.next_run_at = 0.0
    store.upsert_standing_order(order)

    report = adapter.run_due(now=datetime(2026, 4, 16, 15, 0, tzinfo=UTC))

    assert report is not None
    assert len(dispatch.calls) == 1
    assert dispatch.calls[0]["channels"] == ("slack",)
    assert dispatch.calls[0]["domain"] == "retail"
    assert dispatch.calls[0]["dispatch_source"] == "schedule"
    assert dispatch.calls[0]["skip_if_unchanged"] is True
    history = scheduler.list_history(RegressionAlertScheduler.ORDER_ID, limit=5)
    statuses = [item["status"] for item in history]
    assert "completed" in statuses
    assert "dispatched" in statuses
