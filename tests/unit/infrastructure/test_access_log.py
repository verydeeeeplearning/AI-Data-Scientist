from __future__ import annotations

from ds_agent.domain.access.access_log_entry import AccessLogEntry
from ds_agent.infrastructure.persistence.access_log import JsonAccessLogStore


def test_json_access_log_round_trip_returns_newest_first(tmp_path) -> None:
    store = JsonAccessLogStore(base_dir=tmp_path)
    older = AccessLogEntry(
        resource_type="run",
        resource_id="run-1",
        action="view",
        actor_ref="user:111",
        allowed=True,
        created_at=100.0,
    )
    newer = AccessLogEntry(
        resource_type="run",
        resource_id="run-1",
        action="export",
        actor_ref="user:222",
        allowed=True,
        created_at=200.0,
    )

    store.append(older)
    store.append(newer)

    listed = store.list(resource_type="run", resource_id="run-1", now=200.0)
    assert [entry.action for entry in listed] == ["export", "view"]
    assert [entry.actor_ref for entry in listed] == ["user:222", "user:111"]


def test_json_access_log_prunes_entries_outside_retention(tmp_path) -> None:
    store = JsonAccessLogStore(base_dir=tmp_path, retention_seconds=10.0)
    stale = AccessLogEntry(
        resource_type="run",
        resource_id="run-1",
        action="view",
        actor_ref="user:111",
        allowed=True,
        created_at=0.0,
    )
    fresh = AccessLogEntry(
        resource_type="run",
        resource_id="run-1",
        action="export",
        actor_ref="user:222",
        allowed=True,
        created_at=25.0,
    )

    store.append(stale)
    store.append(fresh)

    listed = store.list(now=25.0)
    assert len(listed) == 1
    assert listed[0].action == "export"


def test_json_access_log_filters_by_time_window_and_resource_type(tmp_path) -> None:
    store = JsonAccessLogStore(base_dir=tmp_path)
    entries = [
        AccessLogEntry(
            resource_type="run",
            resource_id="run-1",
            action="view",
            actor_ref="user:111",
            allowed=True,
            created_at=100.0,
        ),
        AccessLogEntry(
            resource_type="artifact",
            resource_id="artifact-1",
            action="export",
            actor_ref="user:222",
            allowed=False,
            created_at=200.0,
        ),
        AccessLogEntry(
            resource_type="run",
            resource_id="run-2",
            action="share",
            actor_ref="user:333",
            allowed=True,
            created_at=300.0,
        ),
    ]

    for entry in entries:
        store.append(entry)

    listed = store.list(resource_type="run", since=150.0, until=350.0, now=300.0)
    assert [entry.resource_id for entry in listed] == ["run-2"]


def test_json_access_log_recreates_parent_directory_before_write(tmp_path) -> None:
    store = JsonAccessLogStore(base_dir=tmp_path)
    entry = AccessLogEntry(
        resource_type="run",
        resource_id="run-1",
        action="view",
        actor_ref="user:111",
        allowed=True,
        created_at=100.0,
    )

    store._file_path.parent.rmdir()
    store.append(entry)

    listed = store.list(now=100.0)
    assert [item.resource_id for item in listed] == ["run-1"]
