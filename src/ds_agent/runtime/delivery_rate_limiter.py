"""Policy-aware delivery rate limiter and escalation engine.

This module implements Tier 2 (policy-level) rate limiting:
- Quiet-hours enforcement
- Per-kind throttling
- Escalation after repeated failures
- Priority queue for escalation messages

Tier 1 (Telegram transport 429 handling) is handled by
``TelegramPlugin._send_with_retry()``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class QuietHoursWindow:
    """A quiet-hours window definition."""

    start_hour: int = 0  # 0-23
    end_hour: int = 0  # 0-23
    timezone: str = "UTC"
    enabled: bool = False


@dataclass
class EscalationState:
    """Tracks repeated failures for escalation decisions."""

    failure_counts: dict[str, int] = field(default_factory=dict)
    last_escalation: dict[str, float] = field(default_factory=dict)

    def record_failure(self, key: str) -> int:
        self.failure_counts[key] = self.failure_counts.get(key, 0) + 1
        return self.failure_counts[key]

    def should_escalate(self, key: str, threshold: int = 3) -> bool:
        return self.failure_counts.get(key, 0) >= threshold

    def mark_escalated(self, key: str) -> None:
        self.last_escalation[key] = time.time()
        self.failure_counts[key] = 0

    def reset(self, key: str) -> None:
        self.failure_counts.pop(key, None)


class DeliveryRateLimiter:
    """Policy-aware delivery rate limiter (Tier 2)."""

    def __init__(
        self,
        quiet_hours: QuietHoursWindow | None = None,
        escalation_threshold: int = 3,
    ) -> None:
        self._quiet_hours = quiet_hours or QuietHoursWindow()
        self._escalation_threshold = escalation_threshold
        self._escalation = EscalationState()
        self._kind_cooldowns: dict[str, float] = {}
        self._default_cooldown_seconds = 60.0

    def is_in_quiet_hours(self, now: float | None = None) -> bool:
        return self.is_in_quiet_hours_for(now=now)

    def is_in_quiet_hours_for(
        self,
        *,
        now: float | None = None,
        quiet_hours: QuietHoursWindow | None = None,
    ) -> bool:
        """Check if current time falls within the quiet-hours window."""
        window = quiet_hours or self._quiet_hours
        if not window.enabled:
            return False
        if now is None:
            now = time.time()
        try:
            import datetime
            import zoneinfo

            tz = zoneinfo.ZoneInfo(window.timezone)
        except (ImportError, KeyError):
            import datetime

            tz = datetime.UTC
        dt = datetime.datetime.fromtimestamp(now, tz=tz)
        hour = dt.hour
        start = window.start_hour
        end = window.end_hour
        if start <= end:
            return start <= hour < end
        return hour >= start or hour < end

    def should_deliver(
        self,
        kind: str,
        severity: str,
        *,
        is_escalation: bool = False,
        quiet_hours: QuietHoursWindow | None = None,
    ) -> bool:
        """Return True if delivery should proceed under current policy."""
        if is_escalation:
            return True

        if self.is_in_quiet_hours_for(quiet_hours=quiet_hours) and severity != "critical":
            return False

        now = time.monotonic()
        cooldown = self._cooldown_for_kind(kind)
        last = self._kind_cooldowns.get(kind)
        if last is not None and (now - last) < cooldown:
            return False
        self._kind_cooldowns[kind] = now
        return True

    def record_failure(self, failure_key: str) -> bool:
        """Record a failure and return True if escalation threshold is reached."""
        self._escalation.record_failure(failure_key)
        if self._escalation.should_escalate(failure_key, self._escalation_threshold):
            self._escalation.mark_escalated(failure_key)
            return True
        return False

    def reset_failure(self, failure_key: str) -> None:
        self._escalation.reset(failure_key)

    def _cooldown_for_kind(self, kind: str) -> float:
        if kind in {"system.resource.pressure", "system.resource.normal"}:
            return 300.0
        if kind == "policy.suppressed":
            return 180.0
        return self._default_cooldown_seconds
