"""Notification domain layer for Telegram Mini Control Plane (PLAN_04).

Pure business rules for cross-channel notifications: categorisation,
quiet-hours suppression, and digest aggregation.  Has zero dependencies
on external packages, frameworks, or I/O.
"""

from __future__ import annotations

from ds_agent.domain.notification.digest import (
    Digest,
    DigestCadence,
    DigestEntry,
    aggregate_digest,
)
from ds_agent.domain.notification.notification import (
    InlineButton,
    Notification,
    NotificationCategory,
)
from ds_agent.domain.notification.push_policy import (
    PUSH_ELIGIBLE_CATEGORIES,
    is_push_eligible,
)
from ds_agent.domain.notification.quiet_hours import (
    QuietHours,
    QuietHoursPolicy,
    is_quiet_now,
)

__all__ = [
    "PUSH_ELIGIBLE_CATEGORIES",
    "Digest",
    "DigestCadence",
    "DigestEntry",
    "InlineButton",
    "Notification",
    "NotificationCategory",
    "QuietHours",
    "QuietHoursPolicy",
    "aggregate_digest",
    "is_push_eligible",
    "is_quiet_now",
]
