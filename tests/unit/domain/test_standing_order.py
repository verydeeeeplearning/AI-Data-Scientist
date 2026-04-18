"""Standing-order domain entity tests."""

from __future__ import annotations

import pytest

from ds_agent.domain.entities.standing_order import (
    CronTrigger,
    EscalationRule,
    EventTrigger,
    StandingOrder,
)


class TestStandingOrder:
    def test_cron_order_is_valid(self):
        order = StandingOrder(
            session_id="session-1",
            name="Weekly KPI scan",
            prompt="Scan KPI drift and summarize anomalies.",
            trigger=CronTrigger("0 9 * * MON", timezone="Asia/Seoul"),
            scope={"kpis": ["revenue", "retention"]},
        )

        assert order.trigger_type == "cron"
        assert "Weekly KPI scan" in order.build_prompt()
        assert "retention" in order.build_prompt()

    def test_event_trigger_matches_suffix_filter(self):
        trigger = EventTrigger(
            event_type="file.created",
            filters={"path_suffix": ".csv"},
        )

        assert trigger.matches("file.created", {"path": "fresh.csv"}) is True
        assert trigger.matches("file.created", {"path": "fresh.parquet"}) is False

    def test_escalation_rule_triggers(self):
        order = StandingOrder(
            session_id="session-1",
            name="Drift watch",
            prompt="Inspect the current KPI spread.",
            trigger=CronTrigger("0 9 * * *"),
            escalation=EscalationRule(
                metric_key="z_score",
                operator=">=",
                threshold=3.0,
                target="manager",
                channel="telegram",
            ),
        )

        assert order.should_escalate({"z_score": 3.2}) is True
        assert order.should_escalate({"z_score": 2.1}) is False

    def test_invalid_order_requires_prompt(self):
        with pytest.raises(ValueError):
            StandingOrder(
                session_id="session-1",
                name="Broken order",
                prompt="",
                trigger=CronTrigger("0 9 * * *"),
            )
