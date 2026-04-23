"""Tests for ds_agent.domain.notification.digest."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ds_agent.domain.notification import (
    DigestCadence,
    DigestEntry,
    NotificationCategory,
    aggregate_digest,
)

_NOW = datetime(2026, 4, 20, 12, 0, 0, tzinfo=UTC)


def _entry(
    category: NotificationCategory,
    title: str,
    *,
    minutes_ago: int = 0,
    deep_link: str | None = None,
) -> DigestEntry:
    return DigestEntry(
        category=category,
        title=title,
        occurred_at=_NOW - timedelta(minutes=minutes_ago),
        workspace_id="ws-1",
        run_id="r-" + title.replace(" ", "_"),
        deep_link=deep_link,
    )


def test_off_cadence_returns_empty() -> None:
    digest = aggregate_digest(
        [_entry(NotificationCategory.INFO, "x")],
        cadence=DigestCadence.OFF,
        now=_NOW,
    )
    assert digest.is_empty
    assert digest.total_count == 0


def test_daily_window_filters_out_older_entries() -> None:
    entries = [
        _entry(NotificationCategory.INFO, "fresh", minutes_ago=10),
        _entry(NotificationCategory.INFO, "old", minutes_ago=60 * 30),  # 30h ago
    ]
    digest = aggregate_digest(entries, cadence=DigestCadence.DAILY, now=_NOW)
    assert digest.total_count == 1
    assert digest.by_category[NotificationCategory.INFO] == 1


def test_weekly_window_includes_six_days_old() -> None:
    entries = [
        _entry(NotificationCategory.INFO, "fresh", minutes_ago=10),
        _entry(NotificationCategory.INFO, "six_days", minutes_ago=60 * 24 * 6),
        _entry(NotificationCategory.INFO, "eight_days", minutes_ago=60 * 24 * 8),
    ]
    digest = aggregate_digest(entries, cadence=DigestCadence.WEEKLY, now=_NOW)
    assert digest.total_count == 2


def test_top_milestones_errors_approvals_separated() -> None:
    entries = [
        _entry(NotificationCategory.MILESTONE, "feature_done"),
        _entry(NotificationCategory.MILESTONE, "experiment_done", minutes_ago=5),
        _entry(NotificationCategory.ERROR, "boom1"),
        _entry(NotificationCategory.APPROVAL, "deploy_v2"),
    ]
    digest = aggregate_digest(entries, cadence=DigestCadence.DAILY, now=_NOW)
    assert digest.by_category[NotificationCategory.MILESTONE] == 2
    assert digest.by_category[NotificationCategory.ERROR] == 1
    assert len(digest.top_milestones) == 2
    # Most-recent first.
    assert digest.top_milestones[0].title == "feature_done"
    assert len(digest.top_errors) == 1
    assert len(digest.top_approvals) == 1


def test_top_n_caps_per_bucket() -> None:
    entries = [
        _entry(NotificationCategory.MILESTONE, f"m{i}", minutes_ago=i)
        for i in range(10)
    ]
    digest = aggregate_digest(
        entries, cadence=DigestCadence.DAILY, now=_NOW, top_n=3
    )
    assert len(digest.top_milestones) == 3
    assert digest.top_milestones[0].title == "m0"
    assert digest.top_milestones[2].title == "m2"


def test_deep_links_deduped_in_order() -> None:
    entries = [
        _entry(NotificationCategory.INFO, "a", deep_link="ds-agent://x"),
        _entry(NotificationCategory.INFO, "b", deep_link="ds-agent://y"),
        _entry(NotificationCategory.INFO, "c", deep_link="ds-agent://x"),
    ]
    digest = aggregate_digest(entries, cadence=DigestCadence.DAILY, now=_NOW)
    assert digest.deep_links == ("ds-agent://x", "ds-agent://y")


def test_naive_now_is_rejected() -> None:
    with pytest.raises(ValueError):
        aggregate_digest([], cadence=DigestCadence.DAILY, now=datetime(2026, 4, 20))


def test_naive_entry_occurred_at_is_rejected() -> None:
    bad_entry = DigestEntry(
        category=NotificationCategory.INFO,
        title="bad",
        occurred_at=datetime(2026, 4, 20, 12, 0, 0),
    )
    with pytest.raises(ValueError):
        aggregate_digest([bad_entry], cadence=DigestCadence.DAILY, now=_NOW)


def test_empty_entries_yields_empty_digest_with_window() -> None:
    digest = aggregate_digest([], cadence=DigestCadence.DAILY, now=_NOW)
    assert digest.is_empty
    assert digest.window_end == _NOW
    assert digest.window_start == _NOW - timedelta(days=1)
