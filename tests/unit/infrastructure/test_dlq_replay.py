"""Tests for DLQ event listing, status update, and replay dispatch."""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ds_agent.domain.entities.integration_event import (
    IntegrationEvent,
    IntegrationEventStatus,
)
from ds_agent.infrastructure.persistence.work_object_store import (
    SqliteWorkObjectStore,
)


def _make_store() -> SqliteWorkObjectStore:
    """Create a fresh temp store."""
    tmp = tempfile.mkdtemp()
    return SqliteWorkObjectStore(Path(tmp) / "test.db")


def _seed_event(
    store: SqliteWorkObjectStore,
    *,
    event_id: str = "IE-001",
    status: IntegrationEventStatus = IntegrationEventStatus.FAILED,
    system: str = "slack",
    attempt: int = 1,
    payload_json: str | None = '{"webhook_url":"https://x","text_fallback":"hi"}',
) -> IntegrationEvent:
    now = datetime.now(UTC)
    # Bypass FK constraints by inserting directly with FK checks off.
    conn = sqlite3.connect(store._db_path)
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        """
        INSERT OR IGNORE INTO integration_event_log(
            event_id, work_object_id, system, action, idempotency_key,
            request_payload_hash, status, external_ref_json, attempt,
            error_code, error_message, policy_decision_id, started_at,
            finished_at, latency_ms, request_payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            "WO-2026-001",
            system,
            "post_message",
            f"wo_WO-2026-001:{system}:post_message:{event_id}",
            "abc123",
            status.value,
            None,
            attempt,
            "CONNECTION_FAILED",
            "Timeout",
            None,
            now.isoformat(),
            now.isoformat(),
            0,
            payload_json,
        ),
    )
    conn.commit()
    conn.close()

    return IntegrationEvent(
        event_id=event_id,
        work_object_id="WO-2026-001",
        system=system,
        action="post_message",
        request_payload_hash="abc123",
        idempotency_key=f"wo_WO-2026-001:{system}:post_message:{event_id}",
        status=status,
        attempt=attempt,
        started_at=now,
        finished_at=now,
        error_code="CONNECTION_FAILED",
        error_message="Timeout",
        request_payload_json=payload_json,
    )


def test_list_events_by_status_returns_failed() -> None:
    store = _make_store()
    _seed_event(store, event_id="IE-F1", status=IntegrationEventStatus.FAILED)
    _seed_event(store, event_id="IE-S1", status=IntegrationEventStatus.SUCCESS)

    failed = store.list_events_by_status(IntegrationEventStatus.FAILED)
    assert len(failed) == 1
    assert failed[0].event_id == "IE-F1"


def test_list_events_by_status_filters_by_system() -> None:
    store = _make_store()
    _seed_event(store, event_id="IE-S1", system="slack")
    _seed_event(store, event_id="IE-J1", system="jira")

    slack_only = store.list_events_by_status(
        IntegrationEventStatus.FAILED,
        system="slack",
    )
    assert len(slack_only) == 1
    assert slack_only[0].system == "slack"


def test_update_event_status_transitions_to_dlq() -> None:
    store = _make_store()
    _seed_event(store, event_id="IE-T1")

    store.update_event_status(
        "IE-T1",
        IntegrationEventStatus.DLQ,
        error_code="MAX_RETRIES",
        error_message="Moved to DLQ",
    )

    event = store.get_event("IE-T1")
    assert event is not None
    assert event.status == IntegrationEventStatus.DLQ
    assert event.error_code == "MAX_RETRIES"


def test_get_event_returns_stored_payload() -> None:
    store = _make_store()
    _seed_event(
        store,
        event_id="IE-P1",
        payload_json='{"webhook_url":"https://test","text_fallback":"hello"}',
    )

    event = store.get_event("IE-P1")
    assert event is not None
    assert event.request_payload_json is not None
    assert "webhook_url" in event.request_payload_json


def test_get_event_returns_none_for_missing() -> None:
    store = _make_store()
    assert store.get_event("nonexistent") is None
