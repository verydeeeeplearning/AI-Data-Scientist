"""Tests for policy automation, recurring goals, and monitoring sensors."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest


def _make_event(*, sensor: str, kind: str, session_id: str, metadata: dict | None = None):
    from ds_agent.runtime.sensor_hub import SensorHub

    hub = SensorHub()
    return hub.publish(
        sensor=sensor,
        kind=kind,
        session_id=session_id,
        surface="daemon",
        message=f"{kind} message",
        metadata=metadata,
    )


class TestJsonPolicyStore:
    def test_recurring_goal_round_trip(self, tmp_path):
        from ds_agent.runtime.policy_store import JsonPolicyStore

        store = JsonPolicyStore(base_dir=tmp_path)

        goal = store.upsert_recurring_goal(
            session_id="session-1",
            prompt="Review weekly drift",
            interval_seconds=3600,
        )
        store.set_standing_orders(["Prefer safe automation", "Escalate destructive actions"])

        goals = store.list_recurring_goals()

        assert len(goals) == 1
        assert goals[0].goal_id == goal.goal_id
        assert goals[0].prompt == "Review weekly drift"
        assert store.get_standing_orders() == [
            "Prefer safe automation",
            "Escalate destructive actions",
        ]

    def test_action_matrix_overrides_round_trip(self, tmp_path):
        from ds_agent.runtime.policy_store import JsonPolicyStore

        store = JsonPolicyStore(base_dir=tmp_path)
        stored = store.set_action_matrix_overrides(
            {
                "jira_create": {"delegate": "auto"},
                "prod_deploy": {"supervised": "approve"},
            }
        )

        reloaded = JsonPolicyStore(base_dir=tmp_path)

        assert stored == {
            "jira_create": {"delegate": "auto"},
            "prod_deploy": {"supervised": "approve"},
        }
        assert reloaded.get_action_matrix_overrides() == stored
        assert reloaded.build_action_matrix().lookup("jira_create", "delegate").value == "auto"
        assert reloaded.build_action_matrix().lookup("prod_deploy", "supervised").value == "approve"

    def test_action_matrix_overrides_reject_unknown_action_classes(self, tmp_path):
        from ds_agent.runtime.policy_store import JsonPolicyStore

        store = JsonPolicyStore(base_dir=tmp_path)

        with pytest.raises(ValueError, match="Unknown action class override"):
            store.set_action_matrix_overrides({"not_real": {"delegate": "auto"}})


class TestPolicyEngine:
    def test_manual_profile_suppresses_file_events(self, tmp_path):
        from ds_agent.runtime.policy_engine import PolicyEngine
        from ds_agent.runtime.policy_store import JsonPolicyStore

        store = JsonPolicyStore(base_dir=tmp_path)
        engine = PolicyEngine(policy_store=store, automation_profile="manual")
        event = _make_event(
            sensor="file_watch",
            kind="file.created",
            session_id="autonomous:inbox",
            metadata={"path": "fresh.csv"},
        )

        decision = engine.evaluate(event)

        assert decision.dispatch is False
        assert decision.reason == "manual_profile"

    def test_schedule_tick_dispatches_due_standing_order(self, tmp_path):
        from ds_agent.application.services.scheduler_service import SchedulerService
        from ds_agent.domain.entities.standing_order import CronTrigger, StandingOrder
        from ds_agent.infrastructure.cron_runner import CronRunner
        from ds_agent.runtime.policy_engine import PolicyEngine
        from ds_agent.runtime.policy_store import JsonPolicyStore

        store = JsonPolicyStore(base_dir=tmp_path)
        created = datetime(2026, 4, 13, 8, 0, tzinfo=ZoneInfo("Asia/Seoul")).timestamp()
        order = StandingOrder(
            session_id="session-9",
            name="Weekly KPI scan",
            prompt="Review KPI drift and summarize anomalies.",
            trigger=CronTrigger("0 9 * * MON", timezone="Asia/Seoul"),
            created_at=created,
            updated_at=created,
        )
        scheduler = SchedulerService(store=store, cron_runner=CronRunner())
        scheduler.register(order)
        engine = PolicyEngine(
            policy_store=store,
            scheduler_service=scheduler,
            automation_profile="balanced",
        )
        event = _make_event(
            sensor="schedule",
            kind="schedule.tick",
            session_id="autonomous:schedule",
            metadata={"dispatch": False},
        )
        event.created_at = datetime(
            2026, 4, 13, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")
        ).timestamp()

        decision = engine.evaluate(event)
        engine.note_dispatch(decision, event=event)

        assert decision.dispatch is True
        assert decision.reason == "standing_order"
        assert decision.session_id == "session-9"
        assert decision.metadata["standingOrderId"] == order.order_id
        assert store.list_standing_order_history(order.order_id)[0]["status"] == "dispatched"

    def test_schedule_tick_dispatches_due_recurring_goal(self, tmp_path):
        from ds_agent.runtime.policy_engine import PolicyEngine
        from ds_agent.runtime.policy_store import JsonPolicyStore

        store = JsonPolicyStore(base_dir=tmp_path)
        goal = store.upsert_recurring_goal(
            session_id="session-1",
            prompt="Check training backlog",
            interval_seconds=300,
        )
        engine = PolicyEngine(policy_store=store, automation_profile="balanced")
        event = _make_event(
            sensor="schedule",
            kind="schedule.tick",
            session_id="autonomous:schedule",
            metadata={"dispatch": False},
        )

        decision = engine.evaluate(event)
        engine.note_dispatch(decision, event=event)

        assert decision.dispatch is True
        assert decision.reason == "recurring_goal"
        assert decision.session_id == "session-1"
        assert decision.metadata["goalId"] == goal.goal_id
        assert store.get_due_recurring_goals(now=event.created_at) == []

    def test_aggressive_profile_dispatches_monitoring_alerts(self, tmp_path):
        from ds_agent.runtime.policy_engine import PolicyEngine
        from ds_agent.runtime.policy_store import JsonPolicyStore

        store = JsonPolicyStore(base_dir=tmp_path)
        engine = PolicyEngine(policy_store=store, automation_profile="aggressive")
        event = _make_event(
            sensor="pipeline_health",
            kind="pipeline.health.degraded",
            session_id="session-1",
        )

        decision = engine.evaluate(event)

        assert decision.dispatch is True
        assert decision.reason == "monitoring_alert"
        assert "corrective action" in (decision.prompt or "")

    def test_resource_pressure_suppresses_dispatch_until_normal(self, tmp_path):
        from ds_agent.runtime.policy_engine import PolicyEngine
        from ds_agent.runtime.policy_store import JsonPolicyStore

        store = JsonPolicyStore(base_dir=tmp_path)
        engine = PolicyEngine(policy_store=store, automation_profile="balanced")

        pressure_event = _make_event(
            sensor="system_resource",
            kind="system.resource.pressure",
            session_id="autonomous:system",
        )
        file_event = _make_event(
            sensor="file_watch",
            kind="file.updated",
            session_id="autonomous:inbox",
            metadata={"path": "fresh.csv"},
        )
        normal_event = _make_event(
            sensor="system_resource",
            kind="system.resource.normal",
            session_id="autonomous:system",
        )

        assert engine.evaluate(pressure_event).reason == "resource_pressure"
        assert engine.evaluate(file_event).dispatch is False
        assert engine.evaluate(file_event).reason == "resource_pressure"
        assert engine.evaluate(normal_event).reason == "resource_normal"
        assert engine.evaluate(file_event).dispatch is True

    def test_throttle_blocks_runaway_automation(self, tmp_path):
        from ds_agent.runtime.policy_engine import PolicyEngine
        from ds_agent.runtime.policy_store import JsonPolicyStore

        store = JsonPolicyStore(base_dir=tmp_path)
        engine = PolicyEngine(
            policy_store=store,
            automation_profile="balanced",
            max_dispatches_per_window=1,
            dispatch_window_seconds=300,
        )
        first_event = _make_event(
            sensor="file_watch",
            kind="file.created",
            session_id="autonomous:inbox",
            metadata={"path": "a.csv"},
        )
        second_event = _make_event(
            sensor="file_watch",
            kind="file.created",
            session_id="autonomous:inbox",
            metadata={"path": "b.csv"},
        )

        first_decision = engine.evaluate(first_event)
        engine.note_dispatch(first_decision, event=first_event)
        second_decision = engine.evaluate(second_event)

        assert first_decision.dispatch is True
        assert second_decision.dispatch is False
        assert second_decision.reason == "dispatch_throttled"


class TestMonitoringSensors:
    def test_model_monitor_emits_degraded_event(self, tmp_path):
        from ds_agent.memory.experiment_log import ExperimentLog
        from ds_agent.runtime.sensor_hub import SensorHub
        from ds_agent.runtime.sensors.model_monitor import ModelMonitorSensor

        experiment_log = ExperimentLog(data_dir=str(tmp_path / "exp"))
        experiment_log.log_experiment(
            "project-1",
            "xgboost",
            "classification",
            {"f1": 0.42},
        )
        sensor = ModelMonitorSensor(sensor_hub=SensorHub(), experiment_log=experiment_log)

        events = sensor.poll_once()

        assert len(events) == 1
        assert events[0].kind == "model.monitor.degraded"
        assert events[0].metadata["metricName"] == "f1"

    def test_pipeline_health_emits_failed_run_once(self):
        from ds_agent.domain.entities.runtime_state import RuntimeStatus
        from ds_agent.runtime.sensor_hub import SensorHub
        from ds_agent.runtime.sensors.pipeline_health import PipelineHealthSensor

        runs = [
            SimpleNamespace(
                run_id="run-1",
                session_id="session-1",
                status=RuntimeStatus.FAILED,
            )
        ]
        sensor = PipelineHealthSensor(
            sensor_hub=SensorHub(),
            list_recent_runs=lambda: runs,
        )

        first = sensor.poll_once()
        second = sensor.poll_once()

        assert len(first) == 1
        assert first[0].kind == "pipeline.health.degraded"
        assert second == []

    def test_system_resource_sensor_emits_pressure_and_normal(self):
        from ds_agent.runtime.sensor_hub import SensorHub
        from ds_agent.runtime.sensors.system_resource import SystemResourceSensor

        state = {"activeRuns": 0, "sensorBacklog": 0}
        sensor = SystemResourceSensor(
            sensor_hub=SensorHub(),
            status_provider=lambda: dict(state),
            backlog_threshold=2,
            active_run_threshold=2,
        )

        assert sensor.poll_once() is None

        state["sensorBacklog"] = 2
        pressure = sensor.poll_once()

        state["sensorBacklog"] = 0
        normal = sensor.poll_once()

        assert pressure is not None
        assert pressure.kind == "system.resource.pressure"
        assert normal is not None
        assert normal.kind == "system.resource.normal"


class TestCoordinatorPolicyIntegration:
    async def test_schedule_tick_dispatches_recurring_goal_session(self, tmp_path):
        from ds_agent.runtime.coordinator import AutonomousCoordinator
        from ds_agent.runtime.policy_engine import PolicyEngine
        from ds_agent.runtime.policy_store import JsonPolicyStore
        from ds_agent.runtime.sensor_hub import SensorHub

        hub = SensorHub()
        store = JsonPolicyStore(base_dir=tmp_path)
        store.upsert_recurring_goal(
            session_id="session-42",
            prompt="Review active modeling results",
            interval_seconds=300,
        )
        engine = PolicyEngine(policy_store=store, automation_profile="balanced")
        calls: list[tuple[str, str, str]] = []

        async def dispatch_run(session_id: str, message: str, surface: str) -> dict[str, str]:
            calls.append((session_id, message, surface))
            return {"runId": "run-1"}

        coordinator = AutonomousCoordinator(
            sensor_hub=hub,
            dispatch_run=dispatch_run,
            has_running_run=lambda _session_id: False,
            policy_engine=engine,
            cooldown_seconds=0.0,
        )
        event = hub.publish(
            sensor="schedule",
            kind="schedule.tick",
            session_id="autonomous:schedule",
            surface="daemon",
            message="tick",
            metadata={"dispatch": False},
        )

        await coordinator.handle_event(event)

        assert len(calls) == 1
        assert calls[0][0] == "session-42"
        assert "Review active modeling results" in calls[0][1]


class TestAppStatePolicyStatus:
    def test_status_exposes_policy_counts(self, tmp_path):
        from ds_agent.api.ws_handler import AppState
        from ds_agent.config.schema import AgentConfig, DSAgentConfig, GatewayConfig

        state = AppState(
            config=DSAgentConfig(
                agent=AgentConfig(workspace_dir=str(tmp_path / "workspace")),
                gateway=GatewayConfig(automation_profile="aggressive"),
            )
        )
        state.upsert_recurring_goal(
            session_id="session-1",
            prompt="Check nightly experiments",
            interval_seconds=600,
        )
        state.set_standing_orders(["Prefer review before destructive actions"])

        status = state.get_status()

        assert status["automationProfile"] == "aggressive"
        assert status["recurringGoalCount"] == 1
        assert status["standingOrderCount"] == 1
        assert status["resourcePressure"] is False
        assert status["authorityOverlay"] is None
        assert status["effectiveAuthorityMode"] == "delegate"

    def test_status_clears_expired_incident_overlay(self, tmp_path):
        from ds_agent.api.ws_handler import AppState
        from ds_agent.config.schema import AgentConfig, DSAgentConfig, GatewayConfig

        state = AppState(
            config=DSAgentConfig(
                agent=AgentConfig(workspace_dir=str(tmp_path / "workspace")),
                gateway=GatewayConfig(
                    authority_overlay="incident",
                    authority_overlay_started_at="2026-04-14T00:00:00+00:00",
                ),
            )
        )

        status = state.get_status()

        assert status["authorityOverlay"] is None
        assert status["effectiveAuthorityMode"] == "delegate"
        assert state.config.gateway.authority_overlay is None
        assert state.config.gateway.authority_overlay_started_at is None
