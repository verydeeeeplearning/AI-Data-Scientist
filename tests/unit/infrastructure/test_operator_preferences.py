"""Tests for ds_agent.runtime.operator_preferences_store."""

from __future__ import annotations

from ds_agent.runtime.operator_preferences_store import (
    ChatPreference,
    JsonOperatorPreferencesStore,
    digest_cadence_label,
)


class TestChatPreferenceDefaults:
    def test_default_enabled(self) -> None:
        pref = ChatPreference(chat_id="123")
        assert pref.enabled is True
        assert pref.min_severity == "warning"
        assert pref.approvals_only is False
        assert pref.digest_mode is False
        assert pref.digest_cadence == "interval"
        assert pref.timezone == "UTC"
        assert "recovery" in pref.subscribed_categories

    def test_default_categories_are_independent(self) -> None:
        p1 = ChatPreference(chat_id="a")
        p2 = ChatPreference(chat_id="b")
        p1.subscribed_categories.add("custom")
        assert "custom" not in p2.subscribed_categories


class TestJsonOperatorPreferencesStore:
    def test_get_creates_default(self, tmp_path) -> None:
        store = JsonOperatorPreferencesStore(tmp_path)
        pref = store.get("chat1")
        assert pref.chat_id == "chat1"
        assert pref.enabled is True

    def test_set_min_severity(self, tmp_path) -> None:
        store = JsonOperatorPreferencesStore(tmp_path)
        pref = store.set_min_severity("chat1", "info")
        assert pref.min_severity == "info"
        reloaded = JsonOperatorPreferencesStore(tmp_path).get("chat1")
        assert reloaded.min_severity == "info"

    def test_set_muted_and_unmute(self, tmp_path) -> None:
        store = JsonOperatorPreferencesStore(tmp_path)
        store.set_muted("chat1", 3600)
        assert store.is_muted("chat1")
        store.unmute("chat1")
        assert not store.is_muted("chat1")

    def test_set_approvals_only(self, tmp_path) -> None:
        store = JsonOperatorPreferencesStore(tmp_path)
        store.set_approvals_only("chat1", True)
        pref = store.get("chat1")
        assert pref.approvals_only is True

    def test_set_digest_mode(self, tmp_path) -> None:
        store = JsonOperatorPreferencesStore(tmp_path)
        store.set_digest_mode("chat1", True, interval_seconds=300)
        pref = store.get("chat1")
        assert pref.digest_mode is True
        assert pref.digest_interval_seconds == 300.0

    def test_set_named_digest_cadence(self, tmp_path) -> None:
        store = JsonOperatorPreferencesStore(tmp_path)
        pref = store.set_digest_mode("chat1", True, cadence="morning")
        assert pref.digest_cadence == "morning"

    def test_set_timezone(self, tmp_path) -> None:
        store = JsonOperatorPreferencesStore(tmp_path)
        pref = store.set_timezone("chat1", "Asia/Seoul")
        assert pref.timezone == "Asia/Seoul"

    def test_should_push_respects_severity(self, tmp_path) -> None:
        store = JsonOperatorPreferencesStore(tmp_path)
        store.set_min_severity("chat1", "error")
        assert not store.should_push("chat1", "health", "warning")
        assert store.should_push("chat1", "health", "error")
        assert store.should_push("chat1", "health", "critical")

    def test_should_push_respects_approvals_only(self, tmp_path) -> None:
        store = JsonOperatorPreferencesStore(tmp_path)
        store.set_approvals_only("chat1", True)
        assert not store.should_push("chat1", "health", "critical")
        assert store.should_push("chat1", "approval", "warning")

    def test_should_push_critical_bypasses_mute(self, tmp_path) -> None:
        store = JsonOperatorPreferencesStore(tmp_path)
        store.set_muted("chat1", 3600)
        assert not store.should_push("chat1", "health", "warning")
        assert store.should_push("chat1", "health", "critical")

    def test_should_push_respects_category(self, tmp_path) -> None:
        store = JsonOperatorPreferencesStore(tmp_path)
        store.set_subscribed_categories("chat1", {"approval"})
        assert not store.should_push("chat1", "health", "critical")
        assert store.should_push("chat1", "approval", "warning")

    def test_persistence_roundtrip(self, tmp_path) -> None:
        store = JsonOperatorPreferencesStore(tmp_path)
        store.set_min_severity("chat1", "info")
        store.set_approvals_only("chat2", True)
        store.set_digest_mode("chat1", True, cadence="hourly")
        store.set_timezone("chat1", "Asia/Seoul")

        store2 = JsonOperatorPreferencesStore(tmp_path)
        assert store2.get("chat1").min_severity == "info"
        assert store2.get("chat1").digest_cadence == "hourly"
        assert store2.get("chat1").timezone == "Asia/Seoul"
        assert store2.get("chat2").approvals_only is True

    def test_list_all(self, tmp_path) -> None:
        store = JsonOperatorPreferencesStore(tmp_path)
        store.get("a")
        store.get("b")
        assert len(store.list_all()) == 2

    def test_digest_cadence_label_for_named_schedule(self) -> None:
        assert digest_cadence_label("morning", 900.0) == "morning 09:00"
