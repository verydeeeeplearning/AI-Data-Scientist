"""Domain/application errors for Telegram channel setup and pairing."""

from __future__ import annotations

from collections.abc import Mapping


class TelegramError(Exception):
    """Base class for Telegram-related failures."""

    error_code = "TELEGRAM_ERROR"

    def __init__(
        self,
        message: str = "",
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.metadata = dict(metadata or {})

    def to_api_detail(self) -> dict[str, object]:
        detail: dict[str, object] = {
            "message": str(self),
            "error_code": self.error_code,
        }
        if self.metadata:
            detail["metadata"] = self.metadata
        return detail


class TelegramInvalidTokenError(TelegramError):
    """Raised before transport I/O when a bot token is visibly malformed."""

    error_code = "TELEGRAM_INVALID_TOKEN"


class TelegramApiError(TelegramError):
    """Raised for non-auth Telegram API errors."""

    error_code = "TELEGRAM_API_ERROR"

    def __init__(
        self,
        message: str = "",
        *,
        telegram_error_code: int | None = None,
        description: str | None = None,
        status_code: int | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        merged = dict(metadata or {})
        if telegram_error_code is not None:
            merged["telegram_error_code"] = telegram_error_code
        if description:
            merged["description"] = description
        if status_code is not None:
            merged["status_code"] = status_code
        super().__init__(message, metadata=merged)
        self.telegram_error_code = telegram_error_code
        self.description = description
        self.status_code = status_code


class TelegramAuthError(TelegramError):
    """Raised when Telegram rejects the bot token."""

    error_code = "TELEGRAM_AUTH_ERROR"

    def __init__(
        self,
        message: str = "",
        *,
        telegram_error_code: int | None = None,
        description: str | None = None,
        status_code: int | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        merged = dict(metadata or {})
        if telegram_error_code is not None:
            merged["telegram_error_code"] = telegram_error_code
        if description:
            merged["description"] = description
        if status_code is not None:
            merged["status_code"] = status_code
        super().__init__(message, metadata=merged)
        self.telegram_error_code = telegram_error_code
        self.description = description
        self.status_code = status_code


class TelegramNetworkError(TelegramError):
    """Raised when Telegram cannot be reached."""

    error_code = "TELEGRAM_NETWORK_ERROR"


class PairingError(TelegramError):
    """Base class for Telegram chat pairing failures."""

    error_code = "TELEGRAM_PAIRING_ERROR"


class PairingStateError(PairingError):
    """Raised when a pairing transition is invalid for the current state."""

    error_code = "TELEGRAM_PAIRING_STATE_ERROR"


class PairingExpiredError(PairingStateError):
    """Raised when a pairing code is used after its expiry."""

    error_code = "TELEGRAM_PAIRING_EXPIRED"


class PairingCancelledError(PairingStateError):
    """Raised when a cancelled pairing is used."""

    error_code = "TELEGRAM_PAIRING_CANCELLED"


class PairingAlreadyPairedError(PairingStateError):
    """Raised when a terminal paired handle is reused."""

    error_code = "TELEGRAM_PAIRING_ALREADY_PAIRED"


class PairingCodeMismatchError(PairingError):
    """Raised when a supplied OTP does not match the pending pairing."""

    error_code = "TELEGRAM_PAIRING_CODE_MISMATCH"
