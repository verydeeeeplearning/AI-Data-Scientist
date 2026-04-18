"""Tests for ds_agent.runtime.channel_identity."""

from __future__ import annotations

from ds_agent.runtime.channel_identity import (
    parse_telegram_session_id,
    telegram_legacy_session_id,
    telegram_session_id,
)


class TestTelegramSessionId:
    """telegram_session_id builds canonical identity strings."""

    def test_dm_no_thread(self) -> None:
        assert telegram_session_id("12345") == "telegram:12345"

    def test_dm_explicit_none_thread(self) -> None:
        assert telegram_session_id("12345", thread_id=None) == "telegram:12345"

    def test_forum_topic(self) -> None:
        assert telegram_session_id("12345", thread_id="67890") == "telegram:12345:67890"

    def test_numeric_string_ids(self) -> None:
        result = telegram_session_id("999", thread_id="111")
        assert result == "telegram:999:111"


class TestParseTelegramSessionId:
    """parse_telegram_session_id recovers components from canonical strings."""

    def test_chat_only_legacy(self) -> None:
        conv_id, thread_id = parse_telegram_session_id("telegram:12345")
        assert conv_id == "12345"
        assert thread_id is None

    def test_chat_with_thread(self) -> None:
        conv_id, thread_id = parse_telegram_session_id("telegram:12345:67890")
        assert conv_id == "12345"
        assert thread_id == "67890"

    def test_roundtrip_no_thread(self) -> None:
        original = telegram_session_id("42")
        conv_id, thread_id = parse_telegram_session_id(original)
        assert telegram_session_id(conv_id, thread_id) == original

    def test_roundtrip_with_thread(self) -> None:
        original = telegram_session_id("42", thread_id="99")
        conv_id, thread_id = parse_telegram_session_id(original)
        assert telegram_session_id(conv_id, thread_id) == original


class TestTelegramLegacySessionId:
    def test_thread_session_maps_to_legacy_chat_scope(self) -> None:
        assert telegram_legacy_session_id("telegram:12345:67890") == "telegram:12345"

    def test_chat_scoped_session_has_no_legacy_fallback(self) -> None:
        assert telegram_legacy_session_id("telegram:12345") is None
