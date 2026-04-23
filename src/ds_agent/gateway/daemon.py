"""Background autonomous runtime daemon."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from ds_agent.agent.callbacks import NullCallbacks
from ds_agent.application.learning.harness_warning_ingestor import HarnessWarningIngestor
from ds_agent.application.services.scheduler_service import SchedulerService
from ds_agent.config.loader import get_default_config_path, load_config
from ds_agent.domain.entities.runtime_state import RuntimeStatus
from ds_agent.infrastructure.cron_runner import CronRunner
from ds_agent.infrastructure.decision_os_container import build_decision_os_container
from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore
from ds_agent.memory.experiment_log import ExperimentLog
from ds_agent.runtime.coordinator import AutonomousCoordinator
from ds_agent.runtime.decision_os_scheduler import DecisionOsMonitorScheduler
from ds_agent.runtime.goal_store import JsonGoalStore
from ds_agent.runtime.learning_governance_scheduler import LearningGovernanceScheduler
from ds_agent.runtime.policy_engine import PolicyEngine
from ds_agent.runtime.policy_store import JsonPolicyStore
from ds_agent.runtime.regression_alert_scheduler import RegressionAlertScheduler
from ds_agent.runtime.sensor_hub import SensorHub
from ds_agent.runtime.sensors.file_watch import FileWatchSensor
from ds_agent.runtime.sensors.model_monitor import ModelMonitorSensor
from ds_agent.runtime.sensors.pipeline_health import PipelineHealthSensor
from ds_agent.runtime.sensors.schedule import ScheduleSensor
from ds_agent.runtime.sensors.system_resource import SystemResourceSensor
from ds_agent.runtime.sensors.user_input import UserInputSensor
from ds_agent.runtime.startup_recovery import RecoveryRecord, StartupRecovery
from ds_agent.runtime.working_memory import JsonWorkingMemoryStore

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState
    from ds_agent.domain.interfaces.llm_provider import AgentCallbacks

logger = structlog.get_logger()


class _RuntimeEventRecorderAdapter:
    """Proxy Decision OS runtime events through AppState broadcasting."""

    def __init__(self, state: AppState) -> None:
        self._state = state

    def record(
        self,
        *,
        category: str,
        kind: str,
        severity: str,
        message: str,
        session_id: str | None = None,
        run_id: str | None = None,
        surface: str = "daemon",
        source: str = "runtime",
        metadata: dict[str, object] | None = None,
        created_at: float | None = None,
    ) -> object:
        return self._state.record_runtime_event(
            category=category,
            kind=kind,
            severity=severity,
            message=message,
            session_id=session_id,
            run_id=run_id,
            surface=surface,
            source=source,
            metadata=metadata,
            created_at=created_at,
        )


class AutonomousCallbacks(NullCallbacks):
    """Low-noise callbacks for autonomous background runs."""

    def __init__(
        self,
        surface: str,
        *,
        workspace_dir: str | None = None,
        warning_ingestor: HarnessWarningIngestor | None = None,
    ) -> None:
        self._surface = surface
        self._warning_ingestor = warning_ingestor
        if self._warning_ingestor is None and workspace_dir is not None:
            self._warning_ingestor = HarnessWarningIngestor(
                SqliteLearningStore.for_workspace(workspace_dir)
            )
        self._current_session_id: str | None = None
        self._current_run_id: str | None = None

    def emit_event(self, event: str, payload: dict) -> None:
        self._remember_runtime_context(payload)
        self._ingest_warning_if_needed(event, payload)
        logger.debug(
            "autonomous_emit",
            surface=self._surface,
            event_name=event,
            payload_keys=sorted(payload.keys()),
        )

    async def on_status(self, status: str, detail: str) -> None:
        logger.info("autonomous_status", surface=self._surface, status=status, detail=detail)

    async def emit_stream_done(
        self,
        content: str,
        cost: float,
        message_id: str | None = None,
    ) -> None:
        logger.info(
            "autonomous_run_done",
            surface=self._surface,
            cost_usd=cost,
            preview=content[:200],
        )

    def _remember_runtime_context(self, payload: dict) -> None:
        session_id = payload.get("sessionId")
        run_id = payload.get("runId")
        if isinstance(session_id, str) and session_id.strip():
            self._current_session_id = session_id
        if isinstance(run_id, str) and run_id.strip():
            self._current_run_id = run_id
        surface = payload.get("surface")
        if isinstance(surface, str) and surface.strip():
            self._surface = surface

    def _ingest_warning_if_needed(self, event: str, payload: dict) -> None:
        if event != "harness.warning" or self._warning_ingestor is None:
            return
        try:
            self._warning_ingestor.ingest(
                payload,
                session_id=_first_non_empty_string(
                    payload.get("sessionId"),
                    self._current_session_id,
                ),
                run_id=_first_non_empty_string(payload.get("runId"), self._current_run_id),
                surface=_first_non_empty_string(payload.get("surface"), self._surface) or "daemon",
            )
        except Exception as exc:
            logger.warning("daemon_harness_warning_ingest_failed", error=str(exc))


class AutonomousDaemon:
    """Own the coordinator and sensors for one shared AppState instance."""

    def __init__(
        self,
        state: AppState,
        *,
        file_poll_interval_seconds: float = 2.0,
        schedule_interval_seconds: float = 300.0,
    ) -> None:
        self._state = state
        self._workspace_dir = str(state.config.agent.workspace_dir)
        inbox_dir = Path(self._workspace_dir).expanduser().resolve() / "inbox"
        self._sensor_hub = SensorHub()
        self._user_input_sensor = UserInputSensor(self._sensor_hub)
        self._goal_store = JsonGoalStore(self._workspace_dir)
        self._policy_store: JsonPolicyStore = state.policy_store
        self._record_runtime_event = state.record_runtime_event
        self._scheduler_service = SchedulerService(
            store=self._policy_store,
            cron_runner=CronRunner(),
            record_runtime_event=self._record_runtime_event,
        )
        self._policy_engine = PolicyEngine(
            policy_store=self._policy_store,
            scheduler_service=self._scheduler_service,
            automation_profile=str(state.config.gateway.automation_profile),
        )
        self._decision_os = build_decision_os_container(
            self._workspace_dir,
            runtime_event_log=_RuntimeEventRecorderAdapter(state),
        )
        self._decision_os_scheduler = DecisionOsMonitorScheduler(
            scheduler_service=self._scheduler_service,
            monitor=self._decision_os.post_deploy_monitor,
            cron=self._decision_os.post_deploy_policy.schedule_cron(),
        )
        self._learning_store = SqliteLearningStore.for_workspace(self._workspace_dir)
        self._learning_governance_scheduler = LearningGovernanceScheduler(
            scheduler_service=self._scheduler_service,
            store=self._learning_store,
            workspace_dir=self._workspace_dir,
            cron=os.getenv("DS_AGENT_GC_LOOP_CRON", "0 9 * * MON"),
            promotion_threshold=_int_env("DS_AGENT_GC_PROMOTION_THRESHOLD", default=3),
            limit=_int_env("DS_AGENT_GC_LOOP_LIMIT", default=200),
        )
        self._regression_alert_scheduler = RegressionAlertScheduler(
            scheduler_service=self._scheduler_service,
            dispatch=state.dispatch_regression_alerts,
            cron=os.getenv("DS_AGENT_EVAL_ALERT_CRON", "*/30 * * * *"),
            channels=_parse_channels(os.getenv("DS_AGENT_EVAL_ALERT_CHANNELS")),
            mode=_optional_env(os.getenv("DS_AGENT_EVAL_ALERT_MODE")),
            domain=_optional_env(os.getenv("DS_AGENT_EVAL_ALERT_DOMAIN")),
            recent_window=_int_env("DS_AGENT_EVAL_ALERT_RECENT_WINDOW", default=3),
            baseline_window_days=_int_env(
                "DS_AGENT_EVAL_ALERT_BASELINE_WINDOW_DAYS",
                default=14,
            ),
        )
        self._working_memory_store = JsonWorkingMemoryStore(self._workspace_dir)
        self._startup_recovery = StartupRecovery(
            checkpoint_store=state.checkpoint_store,
            goal_store=self._goal_store,
            working_memory_store=self._working_memory_store,
            approval_store=state.approval_store,
            sensor_hub=self._sensor_hub,
        )
        self._recovery_records: list[RecoveryRecord] = []
        self._file_watch_sensor = FileWatchSensor(
            watch_dir=inbox_dir,
            sensor_hub=self._sensor_hub,
            poll_interval_seconds=file_poll_interval_seconds,
        )
        self._schedule_sensor = ScheduleSensor(
            sensor_hub=self._sensor_hub,
            interval_seconds=schedule_interval_seconds,
            dispatch=self._policy_engine.automation_profile == "aggressive",
            on_tick=self._handle_schedule_tick,
        )
        self._max_concurrent_runs = max(
            int(getattr(state.config.gateway, "autonomous_max_concurrent_runs", 1)),
            1,
        )
        self._model_monitor_sensor = ModelMonitorSensor(
            sensor_hub=self._sensor_hub,
            experiment_log=ExperimentLog(),
        )
        self._pipeline_health_sensor = PipelineHealthSensor(
            sensor_hub=self._sensor_hub,
            list_recent_runs=lambda: state.list_runs(limit=20),
        )
        self._system_resource_sensor = SystemResourceSensor(
            sensor_hub=self._sensor_hub,
            status_provider=state.get_status,
        )
        self._coordinator = AutonomousCoordinator(
            sensor_hub=self._sensor_hub,
            dispatch_run=self._dispatch_run,
            has_running_run=self._has_running_run,
            has_dispatch_capacity=self._has_dispatch_capacity,
            policy_engine=self._policy_engine,
            record_runtime_event=self._record_runtime_event,
            cooldown_seconds=float(
                getattr(state.config.gateway, "autonomous_cooldown_seconds", 15.0)
            ),
        )

    async def start(self) -> None:
        """Start the autonomous runtime."""
        order = self._decision_os_scheduler.register()
        learning_gc_order = self._learning_governance_scheduler.register()
        alert_order = self._regression_alert_scheduler.register()
        await self._coordinator.start()
        await self._file_watch_sensor.start()
        await self._schedule_sensor.start()
        await self._model_monitor_sensor.start()
        await self._pipeline_health_sensor.start()
        await self._system_resource_sensor.start()
        self._recovery_records = self._startup_recovery.recover()
        self._record_runtime_event(
            category="lifecycle",
            kind="runtime.started",
            severity="success",
            message="Autonomous runtime started.",
            session_id="autonomous:system",
            surface="daemon",
            source="autonomous_runtime",
            metadata={
                "automationProfile": self._policy_engine.automation_profile,
                "watchDir": str(self._file_watch_sensor._watch_dir),
                "decisionOsOrderId": order.order_id,
                "decisionOsCron": order.trigger.cron,
                "learningGovernanceOrderId": learning_gc_order.order_id,
                "learningGovernanceCron": learning_gc_order.trigger.cron,
                "regressionAlertOrderId": alert_order.order_id,
                "regressionAlertCron": alert_order.trigger.cron,
            },
        )
        self._record_runtime_event(
            category="deployment",
            kind="decision_os.monitor_registered",
            severity="info",
            message="Decision OS post-deploy monitor standing order registered.",
            session_id="decision_os:monitor",
            surface="daemon",
            source="decision_os",
            metadata={
                "standingOrderId": order.order_id,
                "cron": order.trigger.cron,
            },
        )
        self._record_runtime_event(
            category="learning",
            kind="learning_governance.gc_registered",
            severity="info",
            message="Learning governance weekly GC standing order registered.",
            session_id="learning:gc",
            surface="daemon",
            source="learning_governance",
            metadata={
                "standingOrderId": learning_gc_order.order_id,
                "cron": learning_gc_order.trigger.cron,
            },
        )
        self._record_runtime_event(
            category="evaluation",
            kind="regression_alert.monitor_registered",
            severity="info",
            message="Regression alert standing order registered.",
            session_id="evaluation:regression_alerts",
            surface="daemon",
            source="evaluation_harness",
            metadata={
                "standingOrderId": alert_order.order_id,
                "cron": alert_order.trigger.cron,
            },
        )
        for record in self._recovery_records:
            self._record_recovery_event(record)
        logger.info("autonomous_runtime_started", watch_dir=str(self._file_watch_sensor._watch_dir))

    async def stop(self) -> None:
        """Stop the autonomous runtime."""
        await self._system_resource_sensor.stop()
        await self._pipeline_health_sensor.stop()
        await self._model_monitor_sensor.stop()
        await self._schedule_sensor.stop()
        await self._file_watch_sensor.stop()
        await self._coordinator.stop()
        self._record_runtime_event(
            category="lifecycle",
            kind="runtime.stopped",
            severity="info",
            message="Autonomous runtime stopped.",
            session_id="autonomous:system",
            surface="daemon",
            source="autonomous_runtime",
        )
        logger.info("autonomous_runtime_stopped")

    @property
    def running(self) -> bool:
        return (
            self._coordinator.running
            and self._file_watch_sensor.running
            and self._schedule_sensor.running
            and self._model_monitor_sensor.running
            and self._pipeline_health_sensor.running
            and self._system_resource_sensor.running
        )

    @property
    def sensor_backlog(self) -> int:
        return self._sensor_hub.backlog

    @property
    def recovered_count(self) -> int:
        return len(self._recovery_records)

    @property
    def automation_profile(self) -> str:
        return self._policy_engine.automation_profile

    @property
    def recurring_goal_count(self) -> int:
        return len(self._policy_store.list_recurring_goals())

    @property
    def standing_order_count(self) -> int:
        return len(self._policy_store.get_standing_orders()) + len(
            self._policy_store.list_standing_order_records()
        )

    @property
    def resource_pressure(self) -> bool:
        return self._policy_engine.resource_pressure

    def publish_user_input(
        self,
        *,
        session_id: str,
        surface: str,
        message: str,
        run_id: str | None = None,
    ) -> None:
        """Publish one foreground user-input event into the shared hub."""
        self._user_input_sensor.record_message(
            session_id=session_id,
            surface=surface,
            message=message,
            run_id=run_id,
        )

    def _has_running_run(self, session_id: str) -> bool:
        runs = self._state.list_runs(session_id=session_id, status=None, limit=1)
        return bool(runs) and runs[0].status.value == "running"

    def _has_dispatch_capacity(self) -> bool:
        runs = self._state.list_runs(
            status=RuntimeStatus.RUNNING,
            limit=self._max_concurrent_runs,
        )
        return len(runs) < self._max_concurrent_runs

    async def _dispatch_run(self, session_id: str, message: str, surface: str) -> object | None:
        callbacks: AgentCallbacks = AutonomousCallbacks(
            surface,
            workspace_dir=self._workspace_dir,
        )
        return await self._state.start_run(
            session_id=session_id,
            message=message,
            callbacks=callbacks,
            surface=surface,
        )

    def _record_recovery_event(self, record: RecoveryRecord) -> None:
        if record.action == "awaiting_approval":
            kind = "recovery.awaiting_approval"
            severity = "warning"
            message = (
                f"Recovered session {record.session_id} is blocked by "
                f"{record.pending_approval_count} pending approval(s)."
            )
        else:
            kind = "recovery.resume_recommended"
            severity = "info"
            message = (
                f"Recovered session {record.session_id} can resume from "
                f"checkpoint step {record.checkpoint_step}."
            )

        self._record_runtime_event(
            category="recovery",
            kind=kind,
            severity=severity,
            message=message,
            session_id=record.session_id,
            surface="daemon",
            source="startup_recovery",
            metadata={
                "action": record.action,
                "checkpointStep": record.checkpoint_step,
                "pendingApprovalCount": record.pending_approval_count,
                "goalStatus": record.goal_status,
                "notes": list(record.notes),
            },
        )

    def _handle_schedule_tick(self, event: object) -> None:
        created_at = getattr(event, "created_at", None)
        now = None
        if created_at is not None:
            now = datetime.fromtimestamp(float(created_at), tz=UTC)
        try:
            self._decision_os_scheduler.run_due(now=now)
        except Exception as exc:
            self._record_runtime_event(
                category="deployment",
                kind="decision_os.monitor_failed",
                severity="error",
                message="Decision OS post-deploy monitor sweep failed.",
                session_id="decision_os:monitor",
                surface="daemon",
                source="decision_os",
                metadata={"error": str(exc)},
                created_at=created_at,
            )
            logger.warning("decision_os_monitor_failed", error=str(exc))
        try:
            learning_gc_result = self._learning_governance_scheduler.run_due(now=now)
            if learning_gc_result is not None:
                self._record_runtime_event(
                    category="learning",
                    kind="learning_governance.gc_completed",
                    severity="success",
                    message=(
                        "Learning governance weekly GC classified "
                        f"{learning_gc_result.total_items} item(s) across "
                        f"{learning_gc_result.total_recurrences} recurrence(s)."
                    ),
                    session_id="learning:gc",
                    surface="daemon",
                    source="learning_governance",
                    metadata={
                        "totalItems": learning_gc_result.total_items,
                        "totalRecurrences": learning_gc_result.total_recurrences,
                        "promotionThreshold": learning_gc_result.promotion_threshold,
                        "promotionCandidateClasses": [
                            failure_class.value
                            for failure_class in learning_gc_result.promotion_candidate_classes
                        ],
                        "reportPath": learning_gc_result.report_path,
                    },
                    created_at=created_at,
                )
        except Exception as exc:
            self._record_runtime_event(
                category="learning",
                kind="learning_governance.gc_failed",
                severity="error",
                message="Learning governance weekly GC sweep failed.",
                session_id="learning:gc",
                surface="daemon",
                source="learning_governance",
                metadata={"error": str(exc)},
                created_at=created_at,
            )
            logger.warning("learning_governance_gc_failed", error=str(exc))
        try:
            self._regression_alert_scheduler.run_due(now=now)
        except Exception as exc:
            self._record_runtime_event(
                category="evaluation",
                kind="regression_alert.monitor_failed",
                severity="error",
                message="Regression alert standing order sweep failed.",
                session_id="evaluation:regression_alerts",
                surface="daemon",
                source="evaluation_harness",
                metadata={"error": str(exc)},
                created_at=created_at,
            )
            logger.warning("regression_alert_monitor_failed", error=str(exc))


def _first_non_empty_string(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return None


async def _run_forever() -> None:
    from ds_agent.api.ws_handler import AppState

    config = load_config(get_default_config_path())
    state = AppState(config=config)
    daemon = AutonomousDaemon(state)
    await daemon.start()
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await daemon.stop()


def main() -> None:
    """CLI entry point for the background autonomous runtime."""
    asyncio.run(_run_forever())


def _optional_env(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _parse_channels(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(part.strip().lower() for part in value.split(",") if part.strip())


def _int_env(name: str, *, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default
