"""Autonomous coordinator loop for sensor-driven agent runs."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress

import structlog

from ds_agent.runtime.policy_engine import PolicyDecision, PolicyEngine
from ds_agent.runtime.sensor_hub import SensorEvent, SensorHub

logger = structlog.get_logger()

DispatchRunFn = Callable[[str, str, str], Awaitable[object | None]]
HasRunningRunFn = Callable[[str], bool]
HasDispatchCapacityFn = Callable[[], bool]
RuntimeEventRecorderFn = Callable[..., object]


class AutonomousCoordinator:
    """Consume sensor events and dispatch autonomous agent runs."""

    def __init__(
        self,
        *,
        sensor_hub: SensorHub,
        dispatch_run: DispatchRunFn,
        has_running_run: HasRunningRunFn,
        has_dispatch_capacity: HasDispatchCapacityFn | None = None,
        policy_engine: PolicyEngine | None = None,
        record_runtime_event: RuntimeEventRecorderFn | None = None,
        cooldown_seconds: float = 15.0,
    ) -> None:
        self._hub = sensor_hub
        self._dispatch_run = dispatch_run
        self._has_running_run = has_running_run
        self._has_dispatch_capacity = has_dispatch_capacity
        self._policy_engine = policy_engine
        self._record_runtime_event = record_runtime_event
        self._cooldown_seconds = cooldown_seconds
        self._last_dispatch_at: dict[str, float] = {}
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the background coordinator loop."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop(), name="runtime:coordinator")

    async def stop(self) -> None:
        """Stop the background coordinator loop."""
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def handle_event(self, event: SensorEvent) -> object | None:
        """Process one event and dispatch an autonomous run when appropriate."""
        self._record_sensor_event(event)
        decision = self._evaluate(event)
        if not decision.dispatch:
            self._record_policy_decision(event, decision, dispatched=False)
            return None

        session_id = decision.session_id or event.session_id
        if self._has_dispatch_capacity is not None and not self._has_dispatch_capacity():
            self._record_policy_decision(
                event,
                PolicyDecision(
                    dispatch=False,
                    reason="max_concurrent_runs",
                    session_id=session_id,
                ),
                dispatched=False,
            )
            return None

        if self._has_running_run(session_id):
            self._record_policy_decision(
                event,
                PolicyDecision(dispatch=False, reason="run_already_active", session_id=session_id),
                dispatched=False,
            )
            return None

        dedupe_key = self._dedupe_key(event, session_id=session_id, decision=decision)
        now = time.monotonic()
        last_dispatch = self._last_dispatch_at.get(dedupe_key)
        if last_dispatch is not None and (now - last_dispatch) < self._cooldown_seconds:
            self._record_policy_decision(
                event,
                PolicyDecision(dispatch=False, reason="cooldown_active", session_id=session_id),
                dispatched=False,
            )
            return None

        prompt = decision.prompt or self._build_prompt(event)
        if prompt is None:
            self._record_policy_decision(
                event,
                PolicyDecision(dispatch=False, reason="no_prompt_available", session_id=session_id),
                dispatched=False,
            )
            return None

        self._last_dispatch_at[dedupe_key] = now
        logger.info(
            "autonomous_dispatch",
            session_id=session_id,
            sensor=event.sensor,
            kind=event.kind,
            reason=decision.reason,
        )
        try:
            result = await self._dispatch_run(session_id, prompt, event.surface)
        except Exception as exc:
            self._record_runtime_event_entry(
                category="policy",
                kind="policy.dispatch_failed",
                severity="error",
                message=(
                    f"Autonomous dispatch failed for {event.kind}: "
                    f"{decision.reason or 'unknown_reason'}."
                ),
                session_id=session_id,
                surface=event.surface,
                source=event.sensor,
                metadata={
                    "sensorKind": event.kind,
                    "policyReason": decision.reason or "unknown",
                    "error": str(exc),
                },
                created_at=event.created_at,
            )
            raise

        run_id = getattr(result, "run_id", None)
        self._record_policy_decision(
            event,
            decision,
            dispatched=True,
            session_id=session_id,
            run_id=run_id if isinstance(run_id, str) else None,
        )
        if self._policy_engine is not None and result is not None:
            self._policy_engine.note_dispatch(decision, event=event)
        return result

    async def _loop(self) -> None:
        while True:
            event = await self._hub.next_event()
            try:
                if event is not None:
                    await self.handle_event(event)
            except Exception as exc:
                logger.warning(
                    "autonomous_event_failed",
                    sensor=getattr(event, "sensor", "unknown"),
                    kind=getattr(event, "kind", "unknown"),
                    error=str(exc),
                )
            finally:
                if event is not None:
                    self._hub.task_done()

    def _evaluate(self, event: SensorEvent) -> PolicyDecision:
        if self._policy_engine is not None:
            return self._policy_engine.evaluate(event)
        if not self._should_dispatch(event):
            return PolicyDecision(dispatch=False, reason="legacy_filtered")
        return PolicyDecision(dispatch=True, reason="legacy_dispatch")

    @staticmethod
    def _should_dispatch(event: SensorEvent) -> bool:
        if event.kind in {"file.created", "file.updated", "recovery.resume"}:
            return True
        if event.kind == "schedule.tick":
            return bool(event.metadata.get("dispatch", False))
        return False

    @staticmethod
    def _dedupe_key(
        event: SensorEvent,
        *,
        session_id: str,
        decision: PolicyDecision,
    ) -> str:
        goal_id = decision.metadata.get("goalId")
        if isinstance(goal_id, str) and goal_id:
            return f"{session_id}:{event.kind}:{goal_id}"
        path = str(event.metadata.get("path", ""))
        return f"{session_id}:{event.kind}:{path}"

    @staticmethod
    def _build_prompt(event: SensorEvent) -> str | None:
        if event.kind not in {"file.created", "file.updated", "schedule.tick", "recovery.resume"}:
            return None

        if event.kind in {"file.created", "file.updated"}:
            rel_path = str(event.metadata.get("path", "")).strip() or "unknown"
            action = "appeared" if event.kind == "file.created" else "changed"
            return (
                "Autonomous runtime wake-up.\n"
                f"Sensor: {event.sensor}\n"
                f"Inbox file {action}: {rel_path}\n"
                "Inspect the new inbox artifact inside the workspace. "
                "Decide whether it affects the current data-science workflow. "
                "If action is needed, take the next concrete step. "
                "If no action is needed, explain why and stop."
            )

        if event.kind == "recovery.resume":
            checkpoint_step = event.metadata.get("checkpointStep", "unknown")
            return (
                "Autonomous runtime recovery wake-up.\n"
                f"Recovered session: {event.session_id}\n"
                f"Checkpoint step: {checkpoint_step}\n"
                "Resume the interrupted work from the recovered checkpoint and active goal. "
                "First verify what was already completed, then continue with the next "
                "concrete step."
            )

        if not bool(event.metadata.get("dispatch", False)):
            return None
        return (
            "Autonomous runtime wake-up.\n"
            "Sensor: schedule\n"
            "Perform a low-frequency review of active work in the workspace. "
            "Only continue if there is a concrete next step; otherwise stop."
        )

    def _record_sensor_event(self, event: SensorEvent) -> None:
        category_map = {
            "recovery.resume": "recovery",
            "pipeline.health.degraded": "health",
            "model.monitor.degraded": "health",
            "system.resource.pressure": "pressure",
            "system.resource.normal": "pressure",
        }
        category = category_map.get(event.kind)
        if category is None:
            return

        severity = "info"
        if event.kind in {
            "pipeline.health.degraded",
            "model.monitor.degraded",
            "system.resource.pressure",
        }:
            severity = "warning"
        elif event.kind == "system.resource.normal":
            severity = "success"

        self._record_runtime_event_entry(
            category=category,
            kind=event.kind,
            severity=severity,
            message=event.message,
            session_id=event.session_id,
            run_id=(
                str(event.metadata.get("runId"))
                if event.metadata.get("runId") is not None
                else None
            ),
            surface=event.surface,
            source=event.sensor,
            metadata=event.metadata,
            created_at=event.created_at,
        )

    def _record_policy_decision(
        self,
        event: SensorEvent,
        decision: PolicyDecision,
        *,
        dispatched: bool,
        session_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        interesting_reasons = {
            "manual_profile",
            "resource_pressure",
            "dispatch_throttled",
            "profile_not_aggressive",
            "run_already_active",
            "max_concurrent_runs",
            "cooldown_active",
            "recurring_goal",
            "standing_order",
            "schedule_review",
            "monitoring_alert",
            "direct_runtime_event",
        }
        reason = decision.reason or "unknown"
        if reason not in interesting_reasons:
            return

        category = "policy"
        kind = "policy.dispatch" if dispatched else "policy.suppressed"
        if reason == "manual_profile":
            severity = "info"
        elif dispatched:
            severity = "success"
        else:
            severity = "warning"

        if dispatched:
            message = (
                f"Autonomous dispatch started from {event.kind} "
                f"({reason.replace('_', ' ')})."
            )
        else:
            message = (
                f"Autonomous action for {event.kind} was suppressed "
                f"({reason.replace('_', ' ')})."
            )

        metadata = {
            **event.metadata,
            "sensorKind": event.kind,
            "policyReason": reason,
        }
        if decision.metadata:
            metadata.update(decision.metadata)

        self._record_runtime_event_entry(
            category=category,
            kind=kind,
            severity=severity,
            message=message,
            session_id=session_id or decision.session_id or event.session_id,
            run_id=run_id,
            surface=event.surface,
            source=event.sensor,
            metadata=metadata,
            created_at=event.created_at,
        )

    def _record_runtime_event_entry(
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
    ) -> None:
        if self._record_runtime_event is None:
            return
        self._record_runtime_event(
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
