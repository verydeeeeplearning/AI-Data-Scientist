"""Tests for the Telegram pairing domain state machine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ds_agent.domain.errors.telegram_errors import (
    PairingAlreadyPairedError,
    PairingCancelledError,
    PairingCodeMismatchError,
    PairingExpiredError,
)
from ds_agent.domain.notification.pairing_state import PairingState, PairingStatus

NOW = datetime(2026, 4, 26, 12, 0, tzinfo=UTC)


def _pending(
    *,
    code: str = "428193",
    expires_at: datetime = NOW + timedelta(seconds=60),
) -> PairingState:
    return PairingState(
        handle_id="pair-1",
        code=code,
        created_at=NOW,
        expires_at=expires_at,
    )


def test_pending_pairing_requires_six_digit_code() -> None:
    assert _pending(code="000001").code == "000001"

    with pytest.raises(ValueError, match="code must be exactly 6 digits"):
        _pending(code="12345")
    with pytest.raises(ValueError, match="code must be exactly 6 digits"):
        _pending(code="12345a")


def test_pending_pairing_requires_timezone_aware_expiry() -> None:
    with pytest.raises(ValueError, match="expires_at must be timezone-aware"):
        PairingState(
            handle_id="pair-1",
            code="428193",
            created_at=NOW,
            expires_at=datetime(2026, 4, 26, 12, 1),
        )


def test_confirm_matching_code_before_expiry_pairs_chat() -> None:
    paired = _pending().confirm(code="428193", chat_id="987654321", now=NOW)

    assert paired.status is PairingStatus.PAIRED
    assert paired.chat_id == "987654321"
    assert paired.paired_at == NOW


def test_confirm_rejects_wrong_code() -> None:
    with pytest.raises(PairingCodeMismatchError):
        _pending().confirm(code="111111", chat_id="987654321", now=NOW)


def test_confirm_rejects_expired_pairing() -> None:
    expired_time = NOW + timedelta(seconds=61)

    with pytest.raises(PairingExpiredError):
        _pending().confirm(code="428193", chat_id="987654321", now=expired_time)


def test_expire_if_needed_marks_pending_state_expired() -> None:
    expired_time = NOW + timedelta(seconds=60)

    expired = _pending().expire_if_needed(now=expired_time)

    assert expired.status is PairingStatus.EXPIRED
    assert expired.expired_at == expired_time


def test_cancelled_pairing_cannot_be_confirmed() -> None:
    cancelled = _pending().cancel(now=NOW + timedelta(seconds=10))

    assert cancelled.status is PairingStatus.CANCELLED
    with pytest.raises(PairingCancelledError):
        cancelled.confirm(code="428193", chat_id="987654321", now=NOW)


def test_paired_pairing_cannot_be_cancelled() -> None:
    paired = _pending().confirm(code="428193", chat_id="987654321", now=NOW)

    with pytest.raises(PairingAlreadyPairedError):
        paired.cancel(now=NOW + timedelta(seconds=10))

