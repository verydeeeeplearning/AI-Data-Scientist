"""Digest aggregation domain logic.

PLAN_04 §5.4: daily/weekly digest with top metric, milestones, top
artifacts.  Pure aggregation — no I/O, no formatting (formatting belongs
to the adapter / presenter).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from ds_agent.domain.notification.notification import (
    Notification,
    NotificationCategory,
)


class DigestCadence(StrEnum):
    OFF = "off"
    DAILY = "daily"
    WEEKLY = "weekly"

    @property
    def window(self) -> timedelta:
        if self is DigestCadence.DAILY:
            return timedelta(days=1)
        if self is DigestCadence.WEEKLY:
            return timedelta(days=7)
        return timedelta(0)


@dataclass(frozen=True, slots=True)
class DigestEntry:
    """One source notification considered for digest aggregation."""

    category: NotificationCategory
    title: str
    occurred_at: datetime
    workspace_id: str | None = None
    run_id: str | None = None
    deep_link: str | None = None


@dataclass(frozen=True, slots=True)
class Digest:
    """Aggregated digest summary.

    Fields are deliberately minimal so the adapter can render however it
    likes (Telegram text, e-mail HTML, renderer card).
    """

    cadence: DigestCadence
    window_start: datetime
    window_end: datetime
    total_count: int
    by_category: dict[NotificationCategory, int]
    top_milestones: tuple[DigestEntry, ...] = field(default_factory=tuple)
    top_errors: tuple[DigestEntry, ...] = field(default_factory=tuple)
    top_approvals: tuple[DigestEntry, ...] = field(default_factory=tuple)
    deep_links: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        return self.total_count == 0


def aggregate_digest(
    entries: list[DigestEntry],
    *,
    cadence: DigestCadence,
    now: datetime | None = None,
    top_n: int = 3,
) -> Digest:
    """Build a :class:`Digest` from raw entries.

    Filters *entries* to the cadence window ending at *now*, counts by
    category, and selects the most recent ``top_n`` entries per priority
    bucket (milestones, errors, approvals).
    """
    if cadence is DigestCadence.OFF:
        moment = now or datetime.now(tz=UTC)
        return Digest(
            cadence=cadence,
            window_start=moment,
            window_end=moment,
            total_count=0,
            by_category={},
        )

    moment = now or datetime.now(tz=UTC)
    if moment.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    window_start = moment - cadence.window

    in_window = [
        e
        for e in entries
        if _ensure_aware(e.occurred_at) >= window_start
        and _ensure_aware(e.occurred_at) <= moment
    ]
    counts: Counter[NotificationCategory] = Counter(e.category for e in in_window)

    def _top(category: NotificationCategory) -> tuple[DigestEntry, ...]:
        bucket = [e for e in in_window if e.category is category]
        bucket.sort(key=lambda e: _ensure_aware(e.occurred_at), reverse=True)
        return tuple(bucket[:top_n])

    deep_links = tuple(
        dict.fromkeys(  # preserve order, dedupe
            e.deep_link for e in in_window if e.deep_link
        )
    )

    return Digest(
        cadence=cadence,
        window_start=window_start,
        window_end=moment,
        total_count=len(in_window),
        by_category=dict(counts),
        top_milestones=_top(NotificationCategory.MILESTONE),
        top_errors=_top(NotificationCategory.ERROR),
        top_approvals=_top(NotificationCategory.APPROVAL),
        deep_links=deep_links,
    )


def _ensure_aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("DigestEntry.occurred_at must be timezone-aware")
    return moment


# Re-export Notification for adapters that want to round-trip.
__all__ = [
    "Digest",
    "DigestCadence",
    "DigestEntry",
    "Notification",
    "aggregate_digest",
]
