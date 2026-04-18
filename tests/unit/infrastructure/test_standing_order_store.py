"""Structured standing-order persistence tests."""

from __future__ import annotations

from ds_agent.domain.entities.standing_order import CronTrigger, StandingOrder
from ds_agent.runtime.policy_store import JsonPolicyStore


class TestStandingOrderStore:
    def test_crud_and_history_round_trip(self, tmp_path):
        store = JsonPolicyStore(base_dir=tmp_path)
        order = StandingOrder(
            session_id="session-1",
            name="Weekly KPI scan",
            prompt="Scan KPI drift and summarize anomalies.",
            trigger=CronTrigger("0 9 * * MON"),
        )

        store.upsert_standing_order(order)
        listed = store.list_standing_order_records()
        assert len(listed) == 1
        assert listed[0].order_id == order.order_id

        store.mark_standing_order_triggered(order.order_id, triggered_at=123.0, run_id="run-1")
        store.record_standing_order_result(
            order.order_id,
            status="succeeded",
            summary="No anomaly detected.",
            run_id="run-1",
        )
        history = store.list_standing_order_history(order.order_id)

        assert history[0]["status"] == "succeeded"
        assert history[1]["status"] == "dispatched"
        assert store.delete_standing_order(order.order_id) is True
        assert store.list_standing_order_records() == []
