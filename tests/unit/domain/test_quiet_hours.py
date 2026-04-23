"""Tests for ds_agent.domain.notification.quiet_hours."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ds_agent.domain.notification import (
    Notification,
    NotificationCategory,
    QuietHours,
    QuietHoursPolicy,
    is_quiet_now,
)


def _utc(year: int, month: int, day: int, hour: int) -> datetime:
    return datetime(year, month, day, hour, 0, 0, tzinfo=UTC)


def test_window_does_not_wrap_midnight() -> None:
    qh = QuietHours(timezone_name="UTC", start_hour=9, end_hour=17)
    assert qh.contains(_utc(2026, 4, 20, 10)) is True
    assert qh.contains(_utc(2026, 4, 20, 17)) is False
    assert qh.contains(_utc(2026, 4, 20, 8)) is False


def test_window_wraps_midnight() -> None:
    qh = QuietHours(timezone_name="UTC", start_hour=22, end_hour=7)
    assert qh.contains(_utc(2026, 4, 20, 23)) is True
    assert qh.contains(_utc(2026, 4, 20, 6)) is True
    assert qh.contains(_utc(2026, 4, 20, 7)) is False
    assert qh.contains(_utc(2026, 4, 20, 12)) is False


def test_window_disabled_returns_false() -> None:
    qh = QuietHours(start_hour=22, end_hour=7, enabled=False)
    assert qh.contains(_utc(2026, 4, 20, 23)) is False


def test_window_invalid_hours_rejected() -> None:
    with pytest.raises(ValueError):
        QuietHours(start_hour=24, end_hour=7)
    with pytest.raises(ValueError):
        QuietHours(start_hour=0, end_hour=-1)


def test_window_naive_datetime_rejected() -> None:
    qh = QuietHours()
    with pytest.raises(ValueError):
        qh.contains(datetime(2026, 4, 20, 23, 0, 0))


def test_window_respects_local_timezone() -> None:
    qh = QuietHours(timezone_name="Asia/Seoul", start_hour=22, end_hour=7)
    # 13:00 UTC == 22:00 KST → quiet
    assert qh.contains(_utc(2026, 4, 20, 13)) is True
    # 03:00 UTC == 12:00 KST → not quiet
    assert qh.contains(_utc(2026, 4, 20, 3)) is False


def _info(title: str = "stage done") -> Notification:
    return Notification(
        category=NotificationCategory.INFO,
        title=title,
        body="b",
    )


def _approval() -> Notification:
    return Notification(
        category=NotificationCategory.APPROVAL,
        title="approve?",
        body="b",
    )


def _error() -> Notification:
    return Notification(
        category=NotificationCategory.ERROR,
        title="boom",
        body="b",
    )


def test_is_quiet_now_suppresses_info_inside_window() -> None:
    policy = QuietHoursPolicy(window=QuietHours(start_hour=22, end_hour=7))
    assert is_quiet_now(_info(), policy=policy, now=_utc(2026, 4, 20, 23)) is True


def test_is_quiet_now_does_not_suppress_outside_window() -> None:
    policy = QuietHoursPolicy(window=QuietHours(start_hour=22, end_hour=7))
    assert is_quiet_now(_info(), policy=policy, now=_utc(2026, 4, 20, 12)) is False


def test_is_quiet_now_approval_always_passes() -> None:
    policy = QuietHoursPolicy(window=QuietHours(start_hour=0, end_hour=23))
    assert is_quiet_now(_approval(), policy=policy, now=_utc(2026, 4, 20, 12)) is False


def test_is_quiet_now_error_always_passes() -> None:
    policy = QuietHoursPolicy(window=QuietHours(start_hour=0, end_hour=23))
    assert is_quiet_now(_error(), policy=policy, now=_utc(2026, 4, 20, 12)) is False


def test_is_quiet_now_uses_default_now_when_omitted() -> None:
    # Disabled policy → never quiet, regardless of clock.
    policy = QuietHoursPolicy(window=QuietHours(enabled=False))
    assert is_quiet_now(_info(), policy=policy) is False
