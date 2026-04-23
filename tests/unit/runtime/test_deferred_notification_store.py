from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ds_agent.domain.notification import InlineButton, Notification, NotificationCategory
from ds_agent.runtime.deferred_notification_store import JsonDeferredNotificationStore


def _notification(title: str) -> Notification:
    return Notification(
        category=NotificationCategory.INFO,
        title=title,
        body="summary",
        deep_link="ds-agent://workspace/demo/run/run-1",
        inline_keyboard=(InlineButton(text="Inspect", url="https://example.com/run-1"),),
        sensitive=True,
        workspace_id="workspace-1",
        run_id="run-1",
    )


def test_park_round_trip_persists_full_notification_payload(tmp_path) -> None:
    store = JsonDeferredNotificationStore(base_dir=tmp_path)
    deferred_at = datetime(2026, 4, 20, 23, 0, tzinfo=UTC)

    store.park(
        operator_id="telegram:1234",
        notification=_notification("nightly update"),
        deferred_at=deferred_at,
    )

    reloaded = JsonDeferredNotificationStore(base_dir=tmp_path)
    parked = reloaded.list_parked("telegram:1234")

    assert len(parked) == 1
    record = parked[0]
    assert record.operator_id == "telegram:1234"
    assert record.deferred_at == deferred_at
    assert record.notification.title == "nightly update"
    assert record.notification.deep_link == "ds-agent://workspace/demo/run/run-1"
    assert record.notification.inline_keyboard[0].text == "Inspect"
    assert record.notification.inline_keyboard[0].url == "https://example.com/run-1"
    assert record.notification.sensitive is True
    assert record.notification.workspace_id == "workspace-1"
    assert record.notification.run_id == "run-1"


def test_list_entries_filters_by_operator_and_time_window(tmp_path) -> None:
    store = JsonDeferredNotificationStore(base_dir=tmp_path)
    now = datetime(2026, 4, 21, 6, 0, tzinfo=UTC)

    store.park(
        operator_id="op-1",
        notification=_notification("inside-window"),
        deferred_at=now - timedelta(hours=2),
    )
    store.park(
        operator_id="op-1",
        notification=_notification("too-old"),
        deferred_at=now - timedelta(days=2),
    )
    store.park(
        operator_id="op-2",
        notification=_notification("other-operator"),
        deferred_at=now - timedelta(hours=1),
    )

    reloaded = JsonDeferredNotificationStore(base_dir=tmp_path)
    entries = reloaded.list_entries(
        operator_id="op-1",
        since=now - timedelta(days=1),
        until=now,
    )

    assert [entry.title for entry in entries] == ["inside-window"]
    assert entries[0].category is NotificationCategory.INFO
    assert entries[0].workspace_id == "workspace-1"
    assert entries[0].run_id == "run-1"
    assert entries[0].deep_link == "ds-agent://workspace/demo/run/run-1"
