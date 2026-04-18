"""SchedulerService tests for structured standing orders."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from ds_agent.application.services.scheduler_service import SchedulerService
from ds_agent.domain.entities.standing_order import CronTrigger, EventTrigger, StandingOrder
from ds_agent.infrastructure.cron_runner import CronRunner
from ds_agent.runtime.policy_store import JsonPolicyStore


class TestSchedulerService:
    def test_evaluate_due_cron_order(self, tmp_path):
        store = JsonPolicyStore(base_dir=tmp_path)
        service = SchedulerService(store=store, cron_runner=CronRunner())
        created = datetime(2026, 4, 13, 8, 0, tzinfo=ZoneInfo("Asia/Seoul")).timestamp()
        order = StandingOrder(
            session_id="session-1",
            name="Weekly KPI scan",
            prompt="Scan KPI drift and summarize anomalies.",
            trigger=CronTrigger("0 9 * * MON", timezone="Asia/Seoul"),
            created_at=created,
            updated_at=created,
        )
        service.register(order)

        due = service.evaluate_triggers(
            now=datetime(2026, 4, 13, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")),
            event_kind="schedule.tick",
        )

        assert len(due) == 1
        assert due[0].order_id == order.order_id

    def test_evaluate_event_order(self, tmp_path):
        store = JsonPolicyStore(base_dir=tmp_path)
        service = SchedulerService(store=store, cron_runner=CronRunner())
        order = StandingOrder(
            session_id="session-2",
            name="Inbox CSV review",
            prompt="Inspect the incoming CSV and decide whether to ingest it.",
            trigger=EventTrigger("file.created", filters={"path_suffix": ".csv"}),
        )
        service.register(order)

        due = service.evaluate_triggers(
            event_kind="file.created",
            event_metadata={"path": "fresh.csv"},
        )

        assert len(due) == 1
        assert due[0].order_id == order.order_id

    def test_record_result_appends_history(self, tmp_path):
        store = JsonPolicyStore(base_dir=tmp_path)
        service = SchedulerService(store=store, cron_runner=CronRunner())
        order = StandingOrder(
            session_id="session-3",
            name="Nightly drift",
            prompt="Check drift metrics and summarize anomalies.",
            trigger=CronTrigger("0 1 * * *"),
        )
        service.register(order)
        service.mark_dispatched(order.order_id, triggered_at=1_700_000_000.0, run_id="run-1")
        service.record_result(
            order.order_id,
            status="succeeded",
            summary="No anomaly detected.",
            run_id="run-1",
        )

        history = service.list_history(order.order_id)

        assert history[0]["status"] == "succeeded"
        assert history[1]["status"] == "dispatched"
