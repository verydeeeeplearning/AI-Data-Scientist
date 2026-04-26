"""Use case for starting and confirming Telegram chat pairing."""

from __future__ import annotations

import re
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ds_agent.application.ports.telegram_transport_port import (
    BotIdentity,
    TelegramTransportPort,
)
from ds_agent.domain.errors.telegram_errors import TelegramInvalidTokenError
from ds_agent.domain.notification.pairing_state import PairingState, PairingStatus

_TOKEN_PATTERN = re.compile(r"^\d+:[A-Za-z0-9_-]{20,}$")
_DEFAULT_TTL_SECONDS = 60

Clock = Callable[[], datetime]
IdGenerator = Callable[[], str]
CodeGenerator = Callable[[], str]


@dataclass(frozen=True, slots=True)
class PairingHandle:
    """Public pairing handle returned to API/UI callers."""

    handle_id: str
    code: str
    expires_at: datetime
    bot_username: str
    bot_id: int
    first_name: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "handleId": self.handle_id,
            "code": self.code,
            "expiresAt": self.expires_at.timestamp(),
            "botUsername": self.bot_username,
            "botId": self.bot_id,
            "firstName": self.first_name,
        }


@dataclass(frozen=True, slots=True)
class StartPairingResult:
    """Pairing start result for a validated Telegram bot token."""

    state: PairingState
    handle: PairingHandle
    bot_identity: BotIdentity


class PairTelegramChatUseCase:
    """Validate a bot token, issue an OTP, and confirm chat pairing."""

    def __init__(
        self,
        *,
        transport: TelegramTransportPort,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
        clock: Clock | None = None,
        handle_id_generator: IdGenerator | None = None,
        code_generator: CodeGenerator | None = None,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._transport = transport
        self._ttl_seconds = ttl_seconds
        self._clock = clock or _utc_now
        self._handle_id_generator = handle_id_generator or _default_handle_id
        self._code_generator = code_generator or _default_otp_code

    async def start_pairing(self, *, token: str) -> StartPairingResult:
        """Validate *token* via Telegram and return a pending pairing state."""
        normalized_token = self._normalize_token(token)
        bot_identity = await self._transport.get_me(normalized_token)
        now = self._clock()
        state = self.create_pending_state(
            handle_id=self._handle_id_generator(),
            code=self._code_generator(),
            created_at=now,
        )
        handle = PairingHandle(
            handle_id=state.handle_id,
            code=state.code,
            expires_at=state.expires_at,
            bot_username=bot_identity.username,
            bot_id=bot_identity.id,
            first_name=bot_identity.first_name,
        )
        return StartPairingResult(
            state=state,
            handle=handle,
            bot_identity=bot_identity,
        )

    def create_pending_state(
        self,
        *,
        handle_id: str,
        code: str,
        created_at: datetime,
    ) -> PairingState:
        """Build a pending state using this use case's configured TTL."""
        return PairingState(
            handle_id=handle_id,
            code=code,
            created_at=created_at,
            expires_at=created_at + timedelta(seconds=self._ttl_seconds),
        )

    def confirm_pairing(
        self,
        state: PairingState,
        *,
        code: str,
        chat_id: str,
        now: datetime | None = None,
    ) -> PairingState:
        """Confirm a pending pairing for *chat_id*."""
        return state.confirm(code=code, chat_id=chat_id, now=now or self._clock())

    def cancel_pairing(
        self,
        state: PairingState,
        *,
        now: datetime | None = None,
    ) -> PairingState:
        """Cancel a pending pairing."""
        return state.cancel(now=now or self._clock())

    def pairing_status(
        self,
        state: PairingState,
        *,
        now: datetime | None = None,
    ) -> PairingStatus:
        """Return current status, accounting for expiry."""
        return state.expire_if_needed(now=now or self._clock()).status

    @staticmethod
    def _normalize_token(token: str) -> str:
        normalized = token.strip()
        if not _TOKEN_PATTERN.fullmatch(normalized):
            raise TelegramInvalidTokenError(
                "Telegram bot token format is invalid",
                metadata={"reason": "invalid_format"},
            )
        return normalized


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _default_handle_id() -> str:
    return f"tg-pair-{uuid.uuid4().hex}"


def _default_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"

