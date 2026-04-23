"""Use case: decide whether a notification should be suppressed.

Thin wrapper over the domain :func:`is_quiet_now` predicate so that
adapters depend on the use case (port) rather than the domain function
directly.  This keeps the dependency arrow flowing inward.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ds_agent.domain.notification import (
    Notification,
    QuietHoursPolicy,
    is_quiet_now,
)


class QuietHoursPolicyPort(Protocol):
    """Repository port for loading the operator's current quiet-hours policy."""

    def load(self, *, operator_id: str) -> QuietHoursPolicy: ...


@dataclass(slots=True)
class QuietHoursDecision:
    suppress: bool
    reason: str


class CheckQuietHoursUseCase:
    """Decides whether *notification* should be deferred at *now*."""

    def __init__(self, policy_port: QuietHoursPolicyPort) -> None:
        self._policy_port = policy_port

    def execute(
        self,
        *,
        operator_id: str,
        notification: Notification,
        now: datetime | None = None,
    ) -> QuietHoursDecision:
        policy = self._policy_port.load(operator_id=operator_id)
        suppress = is_quiet_now(notification, policy=policy, now=now)
        if suppress:
            return QuietHoursDecision(suppress=True, reason="quiet_hours_active")
        if notification.category.bypasses_quiet_hours:
            return QuietHoursDecision(suppress=False, reason="bypass_category")
        return QuietHoursDecision(suppress=False, reason="outside_window")
