"""Quiet-hours policy for notification suppression.

PLAN_04 §5.5: per-user timezone + start/end hour.  ERROR & APPROVAL
categories bypass quiet hours; INFO / MILESTONE / DIGEST are deferred.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ds_agent.domain.notification.notification import (
    Notification,
    NotificationCategory,
)


@dataclass(frozen=True, slots=True)
class QuietHours:
    """Per-user quiet-hours window.

    *start_hour* and *end_hour* are 0..23 in local time of *timezone_name*.
    Window may wrap midnight (e.g. 22..7); equality of start and end means
    "always quiet" (kept simple - operator can disable via ``enabled=False``).
    """

    timezone_name: str = "UTC"
    start_hour: int = 22
    end_hour: int = 7
    enabled: bool = True

    def __post_init__(self) -> None:
        if not (0 <= self.start_hour <= 23):
            raise ValueError("start_hour must be in 0..23")
        if not (0 <= self.end_hour <= 23):
            raise ValueError("end_hour must be in 0..23")
        # Validate timezone name early; raises before runtime delivery.
        _resolve_tz(self.timezone_name)

    def contains(self, moment: datetime) -> bool:
        """True if *moment* (any tz-aware datetime) falls inside the window."""
        if not self.enabled:
            return False
        if moment.tzinfo is None:
            raise ValueError("moment must be timezone-aware")
        local = moment.astimezone(_resolve_tz(self.timezone_name))
        hour = local.hour
        if self.start_hour == self.end_hour:
            # Treat start == end as "always quiet" only when enabled.
            return True
        if self.start_hour < self.end_hour:
            return self.start_hour <= hour < self.end_hour
        # Wraps midnight, e.g. 22..7  → quiet if hour >= 22 or hour < 7.
        return hour >= self.start_hour or hour < self.end_hour


@dataclass(frozen=True, slots=True)
class QuietHoursPolicy:
    """Combination of a window plus the categories it suppresses.

    By default, suppresses INFO / MILESTONE / DIGEST.  ERROR and APPROVAL
    always bypass via :pymeth:`NotificationCategory.bypasses_quiet_hours`.
    """

    window: QuietHours = field(default_factory=QuietHours)
    suppressed_categories: frozenset[NotificationCategory] = field(
        default_factory=lambda: frozenset(
            {
                NotificationCategory.INFO,
                NotificationCategory.MILESTONE,
                NotificationCategory.DIGEST,
            }
        )
    )


def is_quiet_now(
    notification: Notification,
    *,
    policy: QuietHoursPolicy,
    now: datetime | None = None,
) -> bool:
    """Decide whether *notification* should be suppressed at *now*.

    ERROR / APPROVAL bypass quiet hours unconditionally.  Other categories
    are suppressed only if (a) they are in ``policy.suppressed_categories``
    and (b) ``policy.window`` contains *now*.
    """
    if notification.category.bypasses_quiet_hours:
        return False
    if notification.category not in policy.suppressed_categories:
        return False
    moment = now or datetime.now(tz=UTC)
    return policy.window.contains(moment)


def _resolve_tz(name: str) -> tzinfo:
    if name in ("UTC", "utc"):
        return UTC
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:  # pragma: no cover
        raise ValueError(f"unknown timezone: {name}") from exc
