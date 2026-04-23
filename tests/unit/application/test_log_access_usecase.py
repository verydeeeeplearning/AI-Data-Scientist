from __future__ import annotations

from ds_agent.application.use_cases.log_access_usecase import (
    LogAccessInput,
    LogAccessUseCase,
)


class _FakeAccessLogStore:
    def __init__(self) -> None:
        self.entries = []

    def append(self, entry):
        self.entries.append(entry)
        return entry


def test_log_access_hashes_actor_and_sanitizes_metadata() -> None:
    store = _FakeAccessLogStore()
    use_case = LogAccessUseCase(store)

    entry = use_case.execute(
        LogAccessInput(
            resource_type="run",
            resource_id="run-1",
            action="view",
            allowed=True,
            actor_user_id="alice@example.com",
            role="viewer",
            reason="allowed",
            metadata={
                "surface": "electron",
                "user_email": "alice@example.com",
                "items": ["keep", {"token": "secret", "scope": "run"}],
            },
            occurred_at=123.0,
        )
    )

    assert entry.actor_ref.startswith("user:")
    assert entry.actor_ref != "alice@example.com"
    assert entry.metadata == {
        "surface": "electron",
        "items": ["keep", {"scope": "run"}],
    }
    assert entry.created_at == 123.0
    assert store.entries == [entry]


def test_log_access_records_anonymous_actor() -> None:
    store = _FakeAccessLogStore()
    use_case = LogAccessUseCase(store)

    entry = use_case.execute(
        LogAccessInput(
            resource_type="artifact",
            resource_id="artifact-1",
            action="export",
            allowed=False,
        )
    )

    assert entry.actor_ref == "anonymous"
    assert entry.metadata == {}
