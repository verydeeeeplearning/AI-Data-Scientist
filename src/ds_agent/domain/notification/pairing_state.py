"""Pure Telegram pairing state machine.

The domain owns only the lifecycle rules for a one-time pairing code. Token
validation, Telegram API calls, persistence, and notification delivery all live
outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from hmac import compare_digest

from ds_agent.domain.errors.telegram_errors import (
    PairingAlreadyPairedError,
    PairingCancelledError,
    PairingCodeMismatchError,
    PairingExpiredError,
)


class PairingStatus(StrEnum):
    """Lifecycle states exposed to the API layer."""

    PENDING = "pending"
    PAIRED = "paired"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class PairingState:
    """Immutable state for a single Telegram OTP pairing attempt."""

    handle_id: str
    code: str
    created_at: datetime
    expires_at: datetime
    status: PairingStatus = PairingStatus.PENDING
    chat_id: str | None = None
    paired_at: datetime | None = None
    cancelled_at: datetime | None = None
    expired_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.handle_id.strip():
            raise ValueError("handle_id must be non-empty")
        if not (len(self.code) == 6 and self.code.isdecimal()):
            raise ValueError("code must be exactly 6 digits")
        if not isinstance(self.status, PairingStatus):
            raise TypeError("status must be PairingStatus")
        _require_aware(self.created_at, "created_at")
        _require_aware(self.expires_at, "expires_at")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")

        if self.status is PairingStatus.PENDING:
            self._validate_pending()
        elif self.status is PairingStatus.PAIRED:
            if not _non_empty(self.chat_id):
                raise ValueError("paired state requires chat_id")
            _require_aware(self.paired_at, "paired_at")
        elif self.status is PairingStatus.CANCELLED:
            _require_aware(self.cancelled_at, "cancelled_at")
        elif self.status is PairingStatus.EXPIRED:
            _require_aware(self.expired_at, "expired_at")

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            PairingStatus.PAIRED,
            PairingStatus.EXPIRED,
            PairingStatus.CANCELLED,
        }

    def is_expired(self, *, now: datetime) -> bool:
        _require_aware(now, "now")
        return now >= self.expires_at

    def expire(self, *, now: datetime) -> PairingState:
        """Return this state marked expired."""
        _require_aware(now, "now")
        if self.status is PairingStatus.EXPIRED:
            return self
        if self.status is PairingStatus.PAIRED:
            raise PairingAlreadyPairedError(
                "Pairing has already completed",
                metadata={"handle_id": self.handle_id},
            )
        if self.status is PairingStatus.CANCELLED:
            raise PairingCancelledError(
                "Pairing has been cancelled",
                metadata={"handle_id": self.handle_id},
            )
        return replace(self, status=PairingStatus.EXPIRED, expired_at=now)

    def expire_if_needed(self, *, now: datetime) -> PairingState:
        """Return expired state when the pending code has passed its deadline."""
        if self.status is not PairingStatus.PENDING:
            return self
        if not self.is_expired(now=now):
            return self
        return self.expire(now=now)

    def confirm(self, *, code: str, chat_id: str, now: datetime) -> PairingState:
        """Confirm this pairing with a matching OTP and Telegram chat id."""
        _require_aware(now, "now")
        self._raise_if_terminal_for_confirm()
        if self.is_expired(now=now):
            raise PairingExpiredError(
                "Pairing code is invalid or expired",
                metadata={"handle_id": self.handle_id},
            )
        normalized_code = code.strip()
        if not compare_digest(normalized_code, self.code):
            raise PairingCodeMismatchError(
                "Pairing code does not match",
                metadata={"handle_id": self.handle_id},
            )
        normalized_chat_id = chat_id.strip()
        if not normalized_chat_id:
            raise ValueError("chat_id must be non-empty")
        return replace(
            self,
            status=PairingStatus.PAIRED,
            chat_id=normalized_chat_id,
            paired_at=now,
        )

    def cancel(self, *, now: datetime) -> PairingState:
        """Cancel this pending pairing attempt."""
        _require_aware(now, "now")
        if self.status is PairingStatus.CANCELLED:
            return self
        if self.status is PairingStatus.PAIRED:
            raise PairingAlreadyPairedError(
                "Pairing has already completed",
                metadata={"handle_id": self.handle_id},
            )
        if self.status is PairingStatus.EXPIRED:
            raise PairingExpiredError(
                "Pairing code is invalid or expired",
                metadata={"handle_id": self.handle_id},
            )
        return replace(self, status=PairingStatus.CANCELLED, cancelled_at=now)

    def _validate_pending(self) -> None:
        if self.chat_id is not None:
            raise ValueError("pending state cannot have chat_id")
        if self.paired_at is not None:
            raise ValueError("pending state cannot have paired_at")
        if self.cancelled_at is not None:
            raise ValueError("pending state cannot have cancelled_at")
        if self.expired_at is not None:
            raise ValueError("pending state cannot have expired_at")

    def _raise_if_terminal_for_confirm(self) -> None:
        if self.status is PairingStatus.PAIRED:
            raise PairingAlreadyPairedError(
                "Pairing has already completed",
                metadata={"handle_id": self.handle_id},
            )
        if self.status is PairingStatus.CANCELLED:
            raise PairingCancelledError(
                "Pairing has been cancelled",
                metadata={"handle_id": self.handle_id},
            )
        if self.status is PairingStatus.EXPIRED:
            raise PairingExpiredError(
                "Pairing code is invalid or expired",
                metadata={"handle_id": self.handle_id},
            )


def _require_aware(value: datetime | None, field_name: str) -> None:
    if value is None or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _non_empty(value: str | None) -> bool:
    return value is not None and bool(value.strip())

