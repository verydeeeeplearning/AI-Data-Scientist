"""Tests for ds_agent.runtime.operator_alert_state_store."""

from __future__ import annotations

import time
from datetime import datetime

from ds_agent.runtime.operator_alert_state_store import JsonOperatorAlertStateStore


class TestJsonOperatorAlertStateStore:
    def test_acknowledge_roundtrip(self, tmp_path) -> None:
        store = JsonOperatorAlertStateStore(base_dir=tmp_path)
        store.acknowledge("chat1", "evt-1")

        reloaded = JsonOperatorAlertStateStore(base_dir=tmp_path)
        assert reloaded.is_acknowledged("chat1", "evt-1")

    def test_set_muted_and_unmute(self, tmp_path) -> None:
        store = JsonOperatorAlertStateStore(base_dir=tmp_path)
        store.set_muted("chat1", 60.0)
        assert store.is_muted("chat1")

        store.unmute("chat1")
        assert not store.is_muted("chat1")

    def test_record_suppressed_and_clear_after_digest(self, tmp_path) -> None:
        store = JsonOperatorAlertStateStore(base_dir=tmp_path)
        store.record_suppressed("chat1", "evt-1", "muted")
        store.record_suppressed("chat1", "evt-2", "digest")

        items = store.list_suppressed("chat1")
        assert [item.event_id for item in items] == ["evt-1", "evt-2"]
        assert store.suppression_reason("chat1", "evt-2") == "digest"

        store.mark_digest_sent("chat1", delivered_event_ids=["evt-1"])
        remaining = store.list_suppressed("chat1")
        assert [item.event_id for item in remaining] == ["evt-2"]

    def test_should_send_digest_uses_oldest_suppressed_when_no_previous_digest(
        self,
        tmp_path,
    ) -> None:
        store = JsonOperatorAlertStateStore(base_dir=tmp_path)
        state = store.record_suppressed("chat1", "evt-1", "muted")
        state.suppressed_alerts[0].created_at = time.time() - 601.0
        store.update(state)

        assert store.should_send_digest("chat1", 600.0) is True

    def test_should_send_morning_digest_in_chat_timezone(self, tmp_path) -> None:
        from zoneinfo import ZoneInfo

        store = JsonOperatorAlertStateStore(base_dir=tmp_path)
        state = store.record_suppressed("chat1", "evt-1", "digest")
        seoul = ZoneInfo("Asia/Seoul")
        state.suppressed_alerts[0].created_at = datetime(
            2026,
            4,
            13,
            8,
            30,
            tzinfo=seoul,
        ).timestamp()
        store.update(state)

        due_at = datetime(2026, 4, 13, 9, 15, tzinfo=seoul).timestamp()
        assert (
            store.should_send_digest(
                "chat1",
                600.0,
                cadence="morning",
                timezone="Asia/Seoul",
                now=due_at,
            )
            is True
        )

    def test_morning_digest_waits_for_next_slot_when_alert_is_newer_than_slot(
        self,
        tmp_path,
    ) -> None:
        from zoneinfo import ZoneInfo

        store = JsonOperatorAlertStateStore(base_dir=tmp_path)
        state = store.record_suppressed("chat1", "evt-1", "digest")
        seoul = ZoneInfo("Asia/Seoul")
        state.suppressed_alerts[0].created_at = datetime(
            2026,
            4,
            13,
            9,
            5,
            tzinfo=seoul,
        ).timestamp()
        store.update(state)

        due_at = datetime(2026, 4, 13, 9, 15, tzinfo=seoul).timestamp()
        assert (
            store.should_send_digest(
                "chat1",
                600.0,
                cadence="morning",
                timezone="Asia/Seoul",
                now=due_at,
            )
            is False
        )
