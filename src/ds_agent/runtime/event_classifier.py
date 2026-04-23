"""Event classification and subscription engine.

Replaces the hard-coded ``_PUSH_ALERT_KINDS`` set with a policy-driven
classifier that evaluates severity, category, urgency, actionability,
and suppressibility for each runtime event.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ds_agent.runtime.runtime_event_log import RuntimeEventRecord


class DeliveryDecision(StrEnum):
    LIVE_PUSH = "live_push"
    DIGEST_ONLY = "digest_only"
    SUPPRESS = "suppress"
    ESCALATE = "escalate"


@dataclass(frozen=True, slots=True)
class ClassifiedEvent:
    """Enriched event with classification metadata."""

    event: RuntimeEventRecord
    category: str
    severity: str
    urgency: str  # "immediate", "normal", "low"
    actionable: bool
    suppressible: bool


# Default urgency mapping by event kind.
_URGENCY_MAP: dict[str, str] = {
    "recovery.awaiting_approval": "immediate",
    "recovery.resume_recommended": "normal",
    "pipeline.health.degraded": "immediate",
    "model.monitor.degraded": "immediate",
    "run.outcome.failed": "immediate",
    "run.outcome.cancelled": "normal",
    "run.outcome.succeeded": "low",
    "system.resource.pressure": "normal",
    "system.resource.normal": "low",
    "policy.dispatch_failed": "normal",
    "policy.suppressed": "low",
}

_ACTIONABLE_KINDS: frozenset[str] = frozenset(
    {
        "recovery.awaiting_approval",
        "recovery.resume_recommended",
        "pipeline.health.degraded",
        "run.outcome.failed",
        "policy.dispatch_failed",
    }
)


def classify_event(event: RuntimeEventRecord) -> ClassifiedEvent:
    """Classify a runtime event for delivery routing."""
    category = event.category or "health"
    severity = event.severity or "info"
    urgency = _URGENCY_MAP.get(event.kind, "normal")
    actionable = event.kind in _ACTIONABLE_KINDS
    suppressible = urgency == "low" and severity in {"info", "warning"}

    return ClassifiedEvent(
        event=event,
        category=category,
        severity=severity,
        urgency=urgency,
        actionable=actionable,
        suppressible=suppressible,
    )


def _should_buffer_in_digest(classified: ClassifiedEvent) -> bool:
    """Return True when chat digest mode should buffer the event."""
    if classified.category == "approval":
        return False
    if classified.severity == "critical":
        return False
    return classified.urgency != "immediate"


def evaluate_delivery(
    classified: ClassifiedEvent,
    *,
    chat_enabled: bool = True,
    chat_min_severity: str = "warning",
    chat_subscribed_categories: set[str] | None = None,
    chat_muted: bool = False,
    chat_approvals_only: bool = False,
    chat_digest_mode: bool = False,
) -> DeliveryDecision:
    """Evaluate delivery decision for one classified event and one chat."""
    if not chat_enabled:
        return DeliveryDecision.SUPPRESS

    severity_order = ("info", "warning", "error", "critical")
    sev_idx = (
        severity_order.index(classified.severity) if classified.severity in severity_order else 0
    )
    min_idx = severity_order.index(chat_min_severity) if chat_min_severity in severity_order else 0

    if chat_approvals_only and classified.category != "approval":
        return DeliveryDecision.SUPPRESS

    if (
        chat_subscribed_categories is not None
        and classified.category not in chat_subscribed_categories
    ):
        return DeliveryDecision.SUPPRESS

    if sev_idx < min_idx:
        return DeliveryDecision.SUPPRESS

    if classified.severity == "critical" and classified.urgency == "immediate":
        return DeliveryDecision.ESCALATE

    if chat_muted and classified.severity != "critical":
        return DeliveryDecision.SUPPRESS

    if chat_digest_mode and _should_buffer_in_digest(classified):
        return DeliveryDecision.DIGEST_ONLY

    return DeliveryDecision.LIVE_PUSH
