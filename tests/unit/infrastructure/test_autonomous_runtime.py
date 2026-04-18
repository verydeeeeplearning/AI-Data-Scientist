"""Tests for the autonomous coordinator and sensor hub."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from ds_agent.domain.value_objects.budget import BudgetPolicy


async def _wait_for(predicate: object, timeout_seconds: float = 1.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise TimeoutError("condition not satisfied before timeout")


def _seed_decision_os_monitor_fixture(workspace) -> None:
    from ds_agent.domain.entities.experiment import ExperimentRun
    from ds_agent.domain.entities.model import Model
    from ds_agent.infrastructure.persistence.model_registry_store import SqliteModelRegistryStore
    from ds_agent.memory.experiment_log import ExperimentLog

    experiment_log = ExperimentLog(data_dir=str(workspace / "data" / "memory" / "experiment_log"))
    experiment_log.record_extended(
        ExperimentRun.model_validate(
            {
                "run_id": "run-champion",
                "experiment_group": "exp_churn",
                "sequence": 1,
                "hypothesis": {
                    "statement": "Champion baseline",
                    "rationale": "Current production baseline.",
                    "expected_effect": "f1_macro tracked",
                },
                "method": {
                    "model_family": "lightgbm",
                    "hyperparameters": {"learning_rate": 0.05},
                    "random_seed": 42,
                    "code_ref": "git:aaa111",
                },
                "feature_refs": [{"feature_id": "f_user_activity_30d", "version": 1}],
                "data_snapshot_uri": "snapshot://warehouse/churn/2026-04-07",
                "result": {"metrics": {"f1_macro": 0.80, "fp_rate": 0.12}},
                "created_at": datetime(2026, 4, 16, tzinfo=UTC),
                "owner": "growth-ds",
                "status": "succeeded",
            }
        )
    )

    model_store = SqliteModelRegistryStore.for_workspace(str(workspace))
    model_store.save(
        Model.model_validate(
            {
                "model_id": "m_churn_lightgbm",
                "version": 5,
                "alias": "champion",
                "lineage_run_id": "run-champion",
                "artifact": {
                    "uri": "model://churn/lightgbm/v5",
                    "format": "json",
                    "size_bytes": 1024,
                    "checksum": "abc123",
                },
                "serving": {
                    "runtime": "batch",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "feature_refs": [{"feature_id": "f_user_activity_30d", "version": 1}],
                    "latency_budget_ms": 100,
                    "throughput_budget_qps": 40,
                },
                "created_at": datetime(2026, 4, 16, tzinfo=UTC),
                "description": "Champion churn model.",
            }
        )
    )

    reference_path = workspace / "data" / "monitoring" / "post_deploy" / "reference.csv"
    current_path = workspace / "data" / "monitoring" / "post_deploy" / "current.csv"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_text("f_user_activity_30d\n0\n0\n0\n0\n0\n", encoding="utf-8")
    current_path.write_text("f_user_activity_30d\n10\n10\n10\n10\n10\n", encoding="utf-8")
    (workspace / "data" / "monitoring" / "post_deploy" / "m_churn_lightgbm-v5.json").write_text(
        (
            "{\n"
            f'  "reference_path": "{reference_path.as_posix()}",\n'
            f'  "current_path": "{current_path.as_posix()}",\n'
            '  "current_metrics": {"f1_macro": 0.66, "fp_rate": 0.16},\n'
            '  "latency_p95_ms": 140.0,\n'
            '  "qps": 30.0,\n'
            '  "observed_at": "2026-04-16T12:00:00+00:00"\n'
            "}\n"
        ),
        encoding="utf-8",
    )


def _regression_alert_dispatch_report():
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

    return RegressionAlertDispatchReport(
        snapshot=RegressionBoardSnapshot(
            total_records=5,
            recent_window=3,
            baseline_window_days=14,
            domain_filter="retail",
            overall=RegressionOverallSummary(
                recent=RegressionWindowStats(
                    record_count=3,
                    avg_weighted_score=0.42,
                    pass_rate=0.0,
                ),
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
                    message=(
                        "Gold-suite pass rate dropped below the rolling baseline "
                        "by more than 3pp."
                    ),
                    current_value=0.0,
                    baseline_value=1.0,
                    delta=-1.0,
                ),
            ),
        ),
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


class TestSensorHub:
    async def test_publish_and_receive(self):
        from ds_agent.runtime.sensor_hub import SensorHub

        hub = SensorHub()
        published = hub.publish(
            sensor="file_watch",
            kind="file.created",
            session_id="autonomous:inbox",
            surface="daemon",
            message="new file",
        )

        received = await hub.next_event(timeout_seconds=0.1)

        assert received == published
        assert hub.backlog == 0
        hub.task_done()


class TestSensors:
    def test_file_watch_sensor_detects_created_file(self, tmp_path):
        from ds_agent.runtime.sensor_hub import SensorHub
        from ds_agent.runtime.sensors.file_watch import FileWatchSensor

        watch_dir = tmp_path / "workspace" / "inbox"
        hub = SensorHub()
        sensor = FileWatchSensor(watch_dir=watch_dir, sensor_hub=hub)

        sensor.prime()
        (watch_dir / "dataset.csv").write_text("a,b\n1,2\n", encoding="utf-8")

        events = sensor.poll_once()

        assert len(events) == 1
        assert events[0].kind == "file.created"
        assert events[0].metadata["path"] == "dataset.csv"

    def test_user_input_sensor_marks_non_dispatch_event(self):
        from ds_agent.runtime.sensor_hub import SensorHub
        from ds_agent.runtime.sensors.user_input import UserInputSensor

        hub = SensorHub()
        sensor = UserInputSensor(hub)

        event = sensor.record_message(session_id="session-1", surface="ws", message="hello")

        assert event.kind == "user.message"
        assert event.metadata["dispatch"] is False


class TestCoordinator:
    async def test_file_watch_event_dispatches_autonomous_run(self, tmp_path):
        from ds_agent.runtime.coordinator import AutonomousCoordinator
        from ds_agent.runtime.sensor_hub import SensorHub
        from ds_agent.runtime.sensors.file_watch import FileWatchSensor

        hub = SensorHub()
        calls: list[tuple[str, str, str]] = []

        async def dispatch_run(session_id: str, message: str, surface: str) -> dict[str, str]:
            calls.append((session_id, message, surface))
            return {"runId": "run-1"}

        coordinator = AutonomousCoordinator(
            sensor_hub=hub,
            dispatch_run=dispatch_run,
            has_running_run=lambda _session_id: False,
            cooldown_seconds=0.0,
        )
        sensor = FileWatchSensor(watch_dir=tmp_path / "workspace" / "inbox", sensor_hub=hub)

        await coordinator.start()
        sensor.prime()
        (tmp_path / "workspace" / "inbox" / "fresh.csv").write_text("x\n1\n", encoding="utf-8")
        sensor.poll_once()

        await _wait_for(lambda: len(calls) == 1)
        await coordinator.stop()

        assert calls[0][0] == "autonomous:inbox"
        assert "fresh.csv" in calls[0][1]
        assert calls[0][2] == "daemon"

    async def test_capacity_limit_suppresses_dispatch(self):
        from ds_agent.runtime.coordinator import AutonomousCoordinator
        from ds_agent.runtime.sensor_hub import SensorHub

        hub = SensorHub()
        calls: list[tuple[str, str, str]] = []

        async def dispatch_run(session_id: str, message: str, surface: str) -> dict[str, str]:
            calls.append((session_id, message, surface))
            return {"runId": "run-1"}

        coordinator = AutonomousCoordinator(
            sensor_hub=hub,
            dispatch_run=dispatch_run,
            has_running_run=lambda _session_id: False,
            has_dispatch_capacity=lambda: False,
            cooldown_seconds=0.0,
        )

        event = hub.publish(
            sensor="file_watch",
            kind="file.created",
            session_id="autonomous:inbox",
            surface="daemon",
            message="new file",
            metadata={"path": "fresh.csv"},
        )

        result = await coordinator.handle_event(event)

        assert result is None
        assert calls == []


class TestAppStateAutonomousRuntime:
    async def test_start_and_stop_background_runtime(self, tmp_path):
        from ds_agent.api.ws_handler import AppState
        from ds_agent.config.schema import AgentConfig, DSAgentConfig, GatewayConfig
        from ds_agent.runtime.decision_os_scheduler import DecisionOsMonitorScheduler
        from ds_agent.runtime.regression_alert_scheduler import RegressionAlertScheduler

        workspace = tmp_path / "workspace"
        config = DSAgentConfig(
            agent=AgentConfig(workspace_dir=str(workspace)),
            gateway=GatewayConfig(autonomous_runtime_enabled=True),
        )
        state = AppState(config=config)

        await state.start_background_runtime()
        status = state.get_status()

        assert status["autonomousRuntimeEnabled"] is True
        assert status["autonomousRuntimeRunning"] is True
        assert (workspace / "inbox").exists()
        assert "recoveredSessions" in status
        assert "automationProfile" in status
        assert "recurringGoalCount" in status
        assert "standingOrderCount" in status
        assert status["standingOrderCount"] >= 1
        assert "resourcePressure" in status
        assert "authorityOverlay" in status
        assert "effectiveAuthorityMode" in status
        assert (
            state._policy_store.get_standing_order(DecisionOsMonitorScheduler.ORDER_ID) is not None
        )
        assert (
            state._policy_store.get_standing_order(RegressionAlertScheduler.ORDER_ID) is not None
        )

        await state.stop_background_runtime()
        assert state.get_status()["autonomousRuntimeRunning"] is False

    async def test_schedule_tick_executes_registered_decision_os_monitor(self, tmp_path):
        from ds_agent.api.ws_handler import AppState
        from ds_agent.config.schema import AgentConfig, DSAgentConfig, GatewayConfig
        from ds_agent.infrastructure.persistence.deploy_monitor_state_store import (
            SqliteDeployMonitorStateStore,
        )
        from ds_agent.runtime.decision_os_scheduler import DecisionOsMonitorScheduler
        from ds_agent.runtime.regression_alert_scheduler import RegressionAlertScheduler

        workspace = tmp_path / "workspace"
        _seed_decision_os_monitor_fixture(workspace)
        config = DSAgentConfig(
            agent=AgentConfig(workspace_dir=str(workspace)),
            gateway=GatewayConfig(autonomous_runtime_enabled=True),
        )
        state = AppState(config=config)

        with patch.dict("os.environ", {"DS_AGENT_DECISION_OS_MONITOR_CRON": "* * * * *"}):
            await state.start_background_runtime()
            daemon = state._autonomous_daemon
            assert daemon is not None

            order = state._policy_store.get_standing_order(DecisionOsMonitorScheduler.ORDER_ID)
            assert order is not None
            order.next_run_at = 0.0
            state._policy_store.upsert_standing_order(order)
            alert_order = state._policy_store.get_standing_order(RegressionAlertScheduler.ORDER_ID)
            assert alert_order is not None
            alert_order.next_run_at = 0.0
            state._policy_store.upsert_standing_order(alert_order)

            daemon._schedule_sensor.emit_tick()

            await _wait_for(
                lambda: (
                    "completed"
                    in [
                        item["status"]
                        for item in state._policy_store.list_standing_order_history(
                            DecisionOsMonitorScheduler.ORDER_ID,
                            limit=5,
                        )
                    ]
                )
            )

            deploy_state = SqliteDeployMonitorStateStore.for_workspace(str(workspace)).latest(
                "m_churn_lightgbm"
            )
            assert deploy_state is not None
            assert deploy_state.overall_status == "alert"
            assert state.list_runs(session_id="decision_os:monitor", limit=5) == []

            task_events = state.list_runtime_events(limit=20, category="task")
            deployment_events = state.list_runtime_events(limit=20, category="deployment")
            assert any(
                getattr(event, "kind", "") == "standing_order.completed" for event in task_events
            )
            assert any(
                getattr(event, "kind", "") == "post_deploy_alert" for event in deployment_events
            )
            alert_history = state._policy_store.list_standing_order_history(
                RegressionAlertScheduler.ORDER_ID,
                limit=5,
            )
            assert "completed" in [item["status"] for item in alert_history]

            await state.stop_background_runtime()

    async def test_schedule_tick_executes_registered_regression_alert_sweep(self, tmp_path):
        from ds_agent.api.ws_handler import AppState
        from ds_agent.config.schema import AgentConfig, DSAgentConfig, GatewayConfig
        from ds_agent.runtime.regression_alert_scheduler import RegressionAlertScheduler

        workspace = tmp_path / "workspace"
        config = DSAgentConfig(
            agent=AgentConfig(workspace_dir=str(workspace)),
            gateway=GatewayConfig(autonomous_runtime_enabled=True),
        )
        state = AppState(config=config)

        with patch.dict("os.environ", {"DS_AGENT_EVAL_ALERT_CRON": "* * * * *"}):
            await state.start_background_runtime()
            daemon = state._autonomous_daemon
            assert daemon is not None

            order = state._policy_store.get_standing_order(RegressionAlertScheduler.ORDER_ID)
            assert order is not None
            order.next_run_at = 0.0
            state._policy_store.upsert_standing_order(order)

            dispatch_calls: list[dict[str, object]] = []

            def _dispatch(**kwargs):
                dispatch_calls.append(kwargs)
                return _regression_alert_dispatch_report()

            daemon._regression_alert_scheduler._dispatch = _dispatch
            daemon._schedule_sensor.emit_tick()

            await _wait_for(
                lambda: (
                    "completed"
                    in [
                        item["status"]
                        for item in state._policy_store.list_standing_order_history(
                            RegressionAlertScheduler.ORDER_ID,
                            limit=5,
                        )
                    ]
                )
            )

            assert len(dispatch_calls) == 1
            assert dispatch_calls[0]["dispatch_source"] == "schedule"
            assert dispatch_calls[0]["skip_if_unchanged"] is True
            task_events = state.list_runtime_events(limit=20, category="task")
            assert any(
                getattr(event, "kind", "") == "standing_order.completed" for event in task_events
            )

            await state.stop_background_runtime()

    async def test_daemon_run_uses_background_mode_and_budget(self, tmp_path):
        from ds_agent.agent.callbacks import NullCallbacks
        from ds_agent.api.ws_handler import AppState
        from ds_agent.config.schema import AgentConfig, DSAgentConfig, GatewayConfig

        class FakeAgent:
            def __init__(self) -> None:
                self.run_calls: list[tuple[str, dict[str, object]]] = []
                self._budget = MagicMock()
                self._budget.policy = BudgetPolicy(max_iterations=100, max_cost_usd=10.0)
                self._budget.state = MagicMock()
                self._budget.state.total_cost_usd = 0.0

            def set_runtime_context(self, run_id=None, surface=None) -> None:
                return None

            async def run(self, message: str, **kwargs: object) -> str:
                self.run_calls.append((message, kwargs))
                self._budget.state.total_cost_usd = 0.12
                return "Analysis complete."

        workspace = tmp_path / "workspace"
        config = DSAgentConfig(
            agent=AgentConfig(workspace_dir=str(workspace)),
            gateway=GatewayConfig(
                autonomous_runtime_enabled=True,
                autonomous_budget_per_run_usd=0.25,
            ),
        )
        state = AppState(config=config)
        fake_agent = FakeAgent()

        with patch.object(state._sessions, "get_or_create", new=AsyncMock(return_value=fake_agent)):
            run = await state.start_run(
                session_id="autonomous:inbox",
                message="wake up",
                callbacks=NullCallbacks(),
                surface="daemon",
            )
            await state.wait_for_run(run.run_id, timeout_ms=1000)

        assert fake_agent.run_calls[0][1]["execution_mode"] == "background"
        budget_policy = fake_agent.run_calls[0][1]["budget_policy"]
        assert isinstance(budget_policy, BudgetPolicy)
        assert budget_policy.max_cost_usd == 0.25

        events = state.list_runtime_events(limit=10, session_id="autonomous:inbox", category="task")
        assert any(getattr(event, "kind", "") == "task.completed" for event in events)
