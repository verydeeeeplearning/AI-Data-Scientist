"""Policy engine for autonomous automation decisions and throttling."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from ds_agent.application.services.scheduler_service import SchedulerService
from ds_agent.runtime.policy_store import JsonPolicyStore, RecurringGoal
from ds_agent.runtime.sensor_hub import SensorEvent

AutomationProfile = Literal["manual", "balanced", "aggressive"]


@dataclass(slots=True)
class PolicyDecision:
    """Decision returned by the policy engine for one sensor event."""

    dispatch: bool
    prompt: str | None = None
    session_id: str | None = None
    reason: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class PolicyEngine:
    """Evaluate sensor events against automation profile, rules, and throttles."""

    def __init__(
        self,
        *,
        policy_store: JsonPolicyStore,
        scheduler_service: SchedulerService | None = None,
        automation_profile: AutomationProfile = "balanced",
        max_dispatches_per_window: int = 3,
        dispatch_window_seconds: float = 600.0,
    ) -> None:
        self._store = policy_store
        self._scheduler_service = scheduler_service
        self._automation_profile = automation_profile
        self._max_dispatches_per_window = max_dispatches_per_window
        self._dispatch_window_seconds = dispatch_window_seconds
        self._recent_dispatches: list[float] = []
        self._resource_pressure = False

    @property
    def automation_profile(self) -> AutomationProfile:
        return self._automation_profile

    @property
    def resource_pressure(self) -> bool:
        """Return whether runtime pressure suppression is currently active."""
        return self._resource_pressure

    def set_automation_profile(self, profile: AutomationProfile) -> None:
        """Update the active automation profile."""
        self._automation_profile = profile

    def evaluate(self, event: SensorEvent) -> PolicyDecision:
        """Evaluate one sensor event and decide whether to dispatch."""
        if event.kind == "system.resource.pressure":
            self._resource_pressure = True
            return PolicyDecision(dispatch=False, reason="resource_pressure")

        if event.kind == "system.resource.normal":
            self._resource_pressure = False
            return PolicyDecision(dispatch=False, reason="resource_normal")

        profile = self._automation_profile
        if profile == "manual":
            return PolicyDecision(dispatch=False, reason="manual_profile")

        if event.kind == "recovery.resume":
            return PolicyDecision(dispatch=True, reason="direct_runtime_event")

        if self._resource_pressure:
            return PolicyDecision(dispatch=False, reason="resource_pressure")

        if self._scheduler_service is not None:
            due_orders = self._scheduler_service.evaluate_triggers(
                now=datetime.fromtimestamp(event.created_at, tz=UTC),
                event_kind=event.kind,
                event_metadata=event.metadata,
            )
            if due_orders:
                if not self._allow_dispatch():
                    return PolicyDecision(dispatch=False, reason="dispatch_throttled")
                order = due_orders[0]
                return PolicyDecision(
                    dispatch=True,
                    session_id=order.session_id,
                    prompt=self._scheduler_service.build_prompt(order),
                    reason="standing_order",
                    metadata={
                        "policyKind": "standing_order",
                        "standingOrderId": order.order_id,
                    },
                )

        if event.kind == "schedule.tick":
            due_goals = self._store.get_due_recurring_goals(now=event.created_at)
            if due_goals:
                if not self._allow_dispatch():
                    return PolicyDecision(dispatch=False, reason="dispatch_throttled")
                goal = due_goals[0]
                return PolicyDecision(
                    dispatch=True,
                    session_id=goal.session_id,
                    prompt=self._build_recurring_goal_prompt(goal),
                    reason="recurring_goal",
                    metadata={"policyKind": "recurring_goal", "goalId": goal.goal_id},
                )

            if profile == "aggressive" and bool(event.metadata.get("dispatch", False)):
                if not self._allow_dispatch():
                    return PolicyDecision(dispatch=False, reason="dispatch_throttled")
                return PolicyDecision(dispatch=True, reason="schedule_review")

            return PolicyDecision(dispatch=False, reason="no_due_recurring_goal")

        if event.kind in {"file.created", "file.updated", "recovery.resume"}:
            if not self._allow_dispatch():
                return PolicyDecision(dispatch=False, reason="dispatch_throttled")
            return PolicyDecision(dispatch=True, reason="direct_runtime_event")

        if event.kind in {"pipeline.health.degraded", "model.monitor.degraded"}:
            if profile != "aggressive":
                return PolicyDecision(dispatch=False, reason="profile_not_aggressive")
            if not self._allow_dispatch():
                return PolicyDecision(dispatch=False, reason="dispatch_throttled")
            return PolicyDecision(
                dispatch=True,
                session_id=event.session_id,
                prompt=self._build_monitoring_prompt(event),
                reason="monitoring_alert",
                metadata={"policyKind": event.kind},
            )

        return PolicyDecision(dispatch=False, reason="unhandled_event")

    def note_dispatch(self, decision: PolicyDecision, *, event: SensorEvent) -> None:
        """Record one successful autonomous dispatch."""
        if not decision.dispatch:
            return
        self._record_dispatch()
        if decision.metadata.get("policyKind") == "standing_order":
            order_id = decision.metadata.get("standingOrderId")
            if (
                self._scheduler_service is not None
                and isinstance(order_id, str)
                and order_id
            ):
                self._scheduler_service.mark_dispatched(order_id, triggered_at=event.created_at)
            return
        if decision.metadata.get("policyKind") != "recurring_goal":
            return
        goal_id = decision.metadata.get("goalId")
        if isinstance(goal_id, str) and goal_id:
            self._store.mark_recurring_goal_triggered(goal_id, triggered_at=event.created_at)

    def _allow_dispatch(self) -> bool:
        now = time.monotonic()
        self._recent_dispatches = [
            ts for ts in self._recent_dispatches if (now - ts) < self._dispatch_window_seconds
        ]
        return len(self._recent_dispatches) < self._max_dispatches_per_window

    def _record_dispatch(self) -> None:
        self._recent_dispatches.append(time.monotonic())

    def _build_recurring_goal_prompt(self, goal: RecurringGoal) -> str:
        standing_orders = self._store.get_standing_orders()
        parts = [
            "Autonomous recurring goal wake-up.",
            f"Recurring goal: {goal.prompt}",
        ]
        if standing_orders:
            parts.append("Standing orders:")
            parts.extend(f"- {item}" for item in standing_orders[:5])
        parts.append(
            "Review the current workspace state and execute the recurring check only if it is "
            "still relevant."
        )
        return "\n".join(parts)

    @staticmethod
    def _build_monitoring_prompt(event: SensorEvent) -> str:
        return (
            "Autonomous monitoring alert.\n"
            f"Sensor: {event.sensor}\n"
            f"Alert: {event.message}\n"
            "Inspect the current workflow health and decide whether corrective action is needed."
        )
