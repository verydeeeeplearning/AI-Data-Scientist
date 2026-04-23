from __future__ import annotations

from ds_agent.application.use_cases.list_access_log_usecase import (
    ListAccessLogInput,
    ListAccessLogUseCase,
)
from ds_agent.domain.access.access_log_entry import AccessLogEntry


class _RecordingAccessLogStore:
    def __init__(self, entries: list[AccessLogEntry] | None = None) -> None:
        self.entries = entries or []
        self.calls: list[dict[str, object]] = []

    def list(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        return list(self.entries)


def _entry(action: str, *, actor_ref: str = "user:abc", created_at: float = 100.0) -> AccessLogEntry:
    return AccessLogEntry(
        resource_type="run",
        resource_id="run-1",
        action=action,
        actor_ref=actor_ref,
        allowed=True,
        reason="allowed",
        created_at=created_at,
    )


def test_owner_receives_entries_and_filters_are_forwarded() -> None:
    store = _RecordingAccessLogStore(entries=[_entry("export", created_at=200.0), _entry("view")])
    use_case = ListAccessLogUseCase(store)

    listed = use_case.execute(
        ListAccessLogInput(
            operator_id="local-user",
            resource_type=" run ",
            since=50.0,
            until=250.0,
            limit=25,
        )
    )

    assert listed == store.entries
    assert store.calls == [
        {
            "resource_type": "run",
            "since": 50.0,
            "until": 250.0,
            "limit": 25,
        }
    ]


def test_non_owner_gets_empty_result_without_querying_store() -> None:
    store = _RecordingAccessLogStore(entries=[_entry("view")])
    use_case = ListAccessLogUseCase(store)

    listed = use_case.execute(
        ListAccessLogInput(
            operator_id="viewer-1",
            resource_type="run",
            limit=25,
        )
    )

    assert listed == []
    assert store.calls == []


def test_blank_operator_gets_empty_result_without_querying_store() -> None:
    store = _RecordingAccessLogStore(entries=[_entry("view")])
    use_case = ListAccessLogUseCase(store)

    listed = use_case.execute(
        ListAccessLogInput(
            operator_id="   ",
            limit=25,
        )
    )

    assert listed == []
    assert store.calls == []


def test_limit_is_capped_at_two_hundred() -> None:
    store = _RecordingAccessLogStore(entries=[_entry("view")])
    use_case = ListAccessLogUseCase(store)

    listed = use_case.execute(
        ListAccessLogInput(
            operator_id="local-user",
            limit=999,
        )
    )

    assert listed == store.entries
    assert store.calls[0]["limit"] == 200


def test_zero_limit_returns_empty_without_querying_store() -> None:
    store = _RecordingAccessLogStore(entries=[_entry("view")])
    use_case = ListAccessLogUseCase(store)

    listed = use_case.execute(
        ListAccessLogInput(
            operator_id="local-user",
            limit=0,
        )
    )

    assert listed == []
    assert store.calls == []
