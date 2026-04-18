"""Standing order domain entities for scheduled and event-driven autonomy."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

ApprovalGate = Literal["auto_report", "approval_required", "notify_only"]
EscalationOperator = Literal[">", ">=", "<", "<=", "==", "!="]
_APPROVAL_GATES = frozenset({"auto_report", "approval_required", "notify_only"})


@dataclass(slots=True)
class CronTrigger:
    """Cron-style trigger for scheduled autonomous work."""

    cron: str
    timezone: str = "UTC"

    def __post_init__(self) -> None:
        if len(self.cron.split()) != 5:
            raise ValueError("Cron trigger requires a 5-field cron expression")
        if not self.timezone.strip():
            raise ValueError("Cron trigger requires a timezone")


@dataclass(slots=True)
class EventTrigger:
    """Event-driven trigger for autonomous work."""

    event_type: str
    filters: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_type.strip():
            raise ValueError("Event trigger requires an event_type")

    def matches(self, event_type: str, metadata: dict[str, object] | None = None) -> bool:
        """Return whether the trigger matches one runtime event."""
        if event_type != self.event_type:
            return False

        payload = metadata or {}
        for key, expected in self.filters.items():
            if key.endswith("_suffix"):
                field_name = key.removesuffix("_suffix")
                actual = str(payload.get(field_name, ""))
                if not actual.endswith(expected):
                    return False
                continue

            if key.endswith("_prefix"):
                field_name = key.removesuffix("_prefix")
                actual = str(payload.get(field_name, ""))
                if not actual.startswith(expected):
                    return False
                continue

            if str(payload.get(key, "")) != expected:
                return False

        return True


@dataclass(slots=True)
class EscalationRule:
    """Metric-based escalation rule for standing orders."""

    metric_key: str
    operator: EscalationOperator
    threshold: float
    target: str
    channel: str = "runtime"

    def __post_init__(self) -> None:
        if not self.metric_key.strip():
            raise ValueError("Escalation rule requires metric_key")
        if not self.target.strip():
            raise ValueError("Escalation rule requires target")

    def is_triggered(self, metrics: dict[str, object] | None) -> bool:
        """Return whether the rule should escalate for the given metrics."""
        if not metrics:
            return False
        raw_value = metrics.get(self.metric_key)
        if raw_value is None:
            return False
        try:
            value = float(raw_value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False

        if self.operator == ">":
            return value > self.threshold
        if self.operator == ">=":
            return value >= self.threshold
        if self.operator == "<":
            return value < self.threshold
        if self.operator == "<=":
            return value <= self.threshold
        if self.operator == "==":
            return value == self.threshold
        return value != self.threshold


@dataclass(slots=True)
class StandingOrder:
    """Structured autonomous order evaluated by the runtime scheduler."""

    session_id: str
    name: str
    prompt: str
    trigger: CronTrigger | EventTrigger
    order_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    description: str = ""
    scope: dict[str, object] = field(default_factory=dict)
    approval_gate: ApprovalGate = "notify_only"
    escalation: EscalationRule | None = None
    budget_limit_usd: float = 5.0
    enabled: bool = True
    last_run_at: float | None = None
    next_run_at: float | None = None
    run_count: int = 0
    failure_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("Standing order requires session_id")
        if not self.name.strip():
            raise ValueError("Standing order requires name")
        if not self.prompt.strip():
            raise ValueError("Standing order requires prompt")
        if self.approval_gate not in _APPROVAL_GATES:
            raise ValueError(f"Unsupported approval gate: {self.approval_gate}")
        if self.budget_limit_usd <= 0:
            raise ValueError("Standing order budget_limit_usd must be > 0")

    @property
    def trigger_type(self) -> str:
        return "cron" if isinstance(self.trigger, CronTrigger) else "event"

    def build_prompt(self) -> str:
        """Build the background prompt dispatched for this order."""
        parts = [
            "Standing order wake-up.",
            f"Order: {self.name}",
        ]
        if self.description.strip():
            parts.append(f"Description: {self.description.strip()}")
        if self.scope:
            parts.append(f"Scope: {self.scope}")
        parts.append(self.prompt.strip())
        if self.approval_gate != "notify_only":
            parts.append(f"Approval gate: {self.approval_gate}")
        return "\n".join(parts)

    def should_escalate(self, metrics: dict[str, object] | None) -> bool:
        """Return whether the order should escalate for the given metrics."""
        return self.escalation is not None and self.escalation.is_triggered(metrics)
