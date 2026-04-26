"""Backend observability and Sentry redaction tests."""

from __future__ import annotations

from typing import Any, cast

import pytest

from ds_agent.config.schema import DSAgentConfig
from ds_agent.infrastructure.observability import sentry_backend


class _FakeSentrySdk:
    def __init__(self) -> None:
        self.init_calls: list[dict[str, Any]] = []
        self.flush_calls: list[float] = []
        self.close_calls: list[float] = []
        self.breadcrumbs: list[dict[str, Any]] = []

    def init(self, **kwargs: Any) -> None:
        self.init_calls.append(kwargs)

    def add_breadcrumb(self, **kwargs: Any) -> None:
        self.breadcrumbs.append(kwargs)

    def flush(self, *, timeout: float) -> None:
        self.flush_calls.append(timeout)

    def get_client(self) -> _FakeSentrySdk:
        return self

    def close(self, *, timeout: float) -> None:
        self.close_calls.append(timeout)


@pytest.fixture(autouse=True)
def reset_backend_observability_state() -> None:
    cast(dict[str, Any], sentry_backend._state).update(
        {
            "initialized": False,
            "dsn": None,
            "environment": "production",
            "error_reporting_enabled": False,
            "telemetry_enabled": False,
        }
    )


def test_configure_backend_observability_initializes_sentry_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_sdk = _FakeSentrySdk()
    monkeypatch.setattr(sentry_backend, "sentry_sdk", fake_sdk)
    monkeypatch.setattr(sentry_backend, "LoggingIntegration", lambda **kwargs: ("logging", kwargs))
    monkeypatch.setattr(sentry_backend, "FastApiIntegration", lambda **kwargs: ("fastapi", kwargs))

    config = DSAgentConfig(
        observability={
            "sentry_dsn": "https://public@example.ingest.sentry.io/1",
            "sentry_environment": "staging",
            "error_reporting_enabled": True,
            "telemetry_enabled": False,
        }
    )

    sentry_backend.configure_backend_observability(config)
    sentry_backend.configure_backend_observability(config)

    assert len(fake_sdk.init_calls) == 1
    init_kwargs = fake_sdk.init_calls[0]
    assert init_kwargs["dsn"] == "https://public@example.ingest.sentry.io/1"
    assert init_kwargs["environment"] == "staging"
    assert callable(init_kwargs["before_send"])
    assert callable(init_kwargs["before_send_transaction"])
    assert init_kwargs["traces_sampler"]({}) == 0.0

    sentry_backend.shutdown_backend_observability(timeout=1.5)

    assert fake_sdk.flush_calls == [1.5]
    assert fake_sdk.close_calls == [1.5]
    assert cast(dict[str, Any], sentry_backend._state)["initialized"] is False


def test_error_event_redaction_respects_opt_in_gate() -> None:
    event = {
        "message": "Request failed with sk-ant-secretvalue",
        "request": {"headers": {"authorization": "Bearer secret"}},
        "extra": {"api_key": "top-secret"},
    }

    assert sentry_backend.redact_backend_sentry_event(event, {}) is None

    cast(dict[str, Any], sentry_backend._state)["error_reporting_enabled"] = True
    redacted = sentry_backend.redact_backend_sentry_event(event, {})

    assert redacted is not None
    assert redacted["message"] == "Request failed with ***REDACTED***"
    assert redacted["request"]["headers"]["authorization"] == "***REDACTED***"
    assert redacted["extra"]["api_key"] == "***REDACTED***"


def test_transaction_redaction_respects_telemetry_gate() -> None:
    event = {
        "transaction": "READY:18790:desktop-handshake-token",
        "contexts": {"trace": {"token": "sensitive"}},
    }

    assert sentry_backend.redact_backend_sentry_transaction(event, {}) is None
    assert sentry_backend._backend_traces_sampler({}) == 0.0

    cast(dict[str, Any], sentry_backend._state)["telemetry_enabled"] = True
    redacted = sentry_backend.redact_backend_sentry_transaction(event, {})

    assert redacted is not None
    assert redacted["transaction"] == "READY:18790:***REDACTED***"
    assert redacted["contexts"]["trace"]["token"] == "***REDACTED***"
    assert sentry_backend._backend_traces_sampler({}) == 0.1


def test_add_backend_breadcrumb_noops_when_sentry_unavailable_or_inactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentry_backend.add_backend_breadcrumb(
        "telegram.bot_supervisor",
        data={"status": "pending"},
    )

    fake_sdk = _FakeSentrySdk()
    monkeypatch.setattr(sentry_backend, "sentry_sdk", fake_sdk)
    cast(dict[str, Any], sentry_backend._state).update(
        {
            "initialized": True,
            "dsn": None,
            "error_reporting_enabled": True,
            "telemetry_enabled": False,
        },
    )
    sentry_backend.add_backend_breadcrumb(
        "telegram.bot_supervisor",
        data={"status": "pending"},
    )

    cast(dict[str, Any], sentry_backend._state).update(
        {
            "initialized": True,
            "dsn": "https://public@example.ingest.sentry.io/1",
            "error_reporting_enabled": False,
            "telemetry_enabled": False,
        },
    )
    sentry_backend.add_backend_breadcrumb(
        "telegram.bot_supervisor",
        data={"status": "pending"},
    )

    assert fake_sdk.breadcrumbs == []


def test_add_backend_breadcrumb_sends_redacted_payload_when_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_sdk = _FakeSentrySdk()
    monkeypatch.setattr(sentry_backend, "sentry_sdk", fake_sdk)
    cast(dict[str, Any], sentry_backend._state).update(
        {
            "initialized": True,
            "dsn": "https://public@example.ingest.sentry.io/1",
            "error_reporting_enabled": True,
            "telemetry_enabled": False,
        },
    )

    sentry_backend.add_backend_breadcrumb(
        "telegram.bot_supervisor",
        message="READY:18790:desktop-token chat_id=987654321",
        data={
            "status": "pending",
            "action": "start",
            "chatId": "987654321",
            "api_token": "123456789:secret-token-value",
            "notes": "chat_id=987654321 sk-ant-secretvalue",
        },
    )

    assert len(fake_sdk.breadcrumbs) == 1
    breadcrumb = fake_sdk.breadcrumbs[0]
    assert breadcrumb["message"] == "READY:18790:***REDACTED*** chat_id=***REDACTED***"
    assert breadcrumb["data"] == {
        "status": "pending",
        "action": "start",
        "chatId": "***REDACTED***",
        "api_token": "***REDACTED***",
        "notes": "chat_id=***REDACTED*** ***REDACTED***",
    }


# --------------------------------------------------------------------------- #
# PII redaction regression tests (Fix Sprint S2 — A02 blocking issue follow-up)
# The payloads below are SYNTHETIC and used only to assert redaction behavior.
# --------------------------------------------------------------------------- #


@pytest.fixture
def _pii_enabled() -> None:
    """Enable error reporting so redact_backend_sentry_event does not drop events."""

    cast(dict[str, Any], sentry_backend._state)["error_reporting_enabled"] = True


def test_message_email_is_redacted(_pii_enabled: None) -> None:
    event = {"message": "Contact jane.doe@example.com for follow up"}
    redacted = sentry_backend.redact_backend_sentry_event(event, {})
    assert redacted is not None
    assert "jane.doe@example.com" not in redacted["message"]
    assert "***EMAIL***" in redacted["message"]


def test_message_phone_is_redacted(_pii_enabled: None) -> None:
    event = {"message": "Call +1-202-555-0199 today"}
    redacted = sentry_backend.redact_backend_sentry_event(event, {})
    assert redacted is not None
    assert "202-555-0199" not in redacted["message"]
    assert "***PHONE***" in redacted["message"]


def test_message_card_with_spaces_is_redacted(_pii_enabled: None) -> None:
    event = {"message": "Card 4111 1111 1111 1111 was declined"}
    redacted = sentry_backend.redact_backend_sentry_event(event, {})
    assert redacted is not None
    assert "4111 1111 1111 1111" not in redacted["message"]
    assert "4111111111111111" not in redacted["message"]
    assert "***CARD***" in redacted["message"]


def test_message_card_no_spaces_is_redacted(_pii_enabled: None) -> None:
    event = {"message": "Card 4111111111111111 was declined"}
    redacted = sentry_backend.redact_backend_sentry_event(event, {})
    assert redacted is not None
    assert "4111111111111111" not in redacted["message"]
    assert "***CARD***" in redacted["message"]


def test_extra_notes_pii_are_redacted(_pii_enabled: None) -> None:
    event = {
        "extra": {
            "notes": ("email=jane.doe@example.com phone=+1-202-555-0199 card=4111111111111111"),
        },
    }
    redacted = sentry_backend.redact_backend_sentry_event(event, {})
    assert redacted is not None
    notes = redacted["extra"]["notes"]
    assert "jane.doe@example.com" not in notes
    assert "202-555-0199" not in notes
    assert "4111111111111111" not in notes
    assert "***EMAIL***" in notes
    assert "***PHONE***" in notes
    assert "***CARD***" in notes


def test_customer_email_field_name_triggers_redaction(_pii_enabled: None) -> None:
    event = {"extra": {"customer_email": "jane.doe@example.com"}}
    redacted = sentry_backend.redact_backend_sentry_event(event, {})
    assert redacted is not None
    assert redacted["extra"]["customer_email"] == "***REDACTED***"


def test_phone_number_field_name_triggers_redaction(_pii_enabled: None) -> None:
    event = {"extra": {"phone_number": "+1-202-555-0199"}}
    redacted = sentry_backend.redact_backend_sentry_event(event, {})
    assert redacted is not None
    assert redacted["extra"]["phone_number"] == "***REDACTED***"


def test_nested_contexts_user_email_is_redacted(_pii_enabled: None) -> None:
    event = {"contexts": {"user": {"email": "jane.doe@example.com"}}}
    redacted = sentry_backend.redact_backend_sentry_event(event, {})
    assert redacted is not None
    # Either field-name redaction (preferred) or value-regex redaction must apply.
    value = redacted["contexts"]["user"]["email"]
    assert "jane.doe@example.com" not in value
    assert value in ("***REDACTED***", "***EMAIL***")


def test_existing_token_redaction_regression(_pii_enabled: None) -> None:
    """Existing token redaction must keep working after PII extensions."""

    event = {
        "message": "Bearer sk-ant-secretvalue in READY:18790:desktop-token",
        "extra": {"api_key": "top-secret"},
    }
    redacted = sentry_backend.redact_backend_sentry_event(event, {})
    assert redacted is not None
    assert "sk-ant-secretvalue" not in redacted["message"]
    assert "desktop-token" not in redacted["message"]
    assert "READY:18790:***REDACTED***" in redacted["message"]
    assert redacted["extra"]["api_key"] == "***REDACTED***"


def test_uuid_and_hash_are_not_false_positively_redacted(_pii_enabled: None) -> None:
    """Regular UUIDs, SHA-256 hashes, and 16+ random digit sequences that are
    not valid credit card numbers must not trigger PII redaction."""

    uuid_str = "550e8400-e29b-41d4-a716-446655440000"
    sha256_hex = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    long_digits = "1234567890123456"  # 16 digits, fails Luhn → not a card
    event = {
        "message": (f"request_id={uuid_str} hash={sha256_hex} counter={long_digits}"),
    }
    redacted = sentry_backend.redact_backend_sentry_event(event, {})
    assert redacted is not None
    msg = redacted["message"]
    assert uuid_str in msg
    assert sha256_hex in msg
    assert long_digits in msg
    assert "***CARD***" not in msg
    assert "***EMAIL***" not in msg
    assert "***PHONE***" not in msg
