"""Telegram bot lifecycle supervisor."""

from __future__ import annotations

import asyncio
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import structlog

from ds_agent.application.ports.telegram_transport_port import BotIdentity, TelegramTransportPort
from ds_agent.application.use_cases.pair_telegram_chat_usecase import PairingHandle
from ds_agent.config.schema import DSAgentConfig
from ds_agent.domain.errors.telegram_errors import (
    PairingCodeMismatchError,
    PairingError,
    TelegramAuthError,
    TelegramError,
)
from ds_agent.domain.notification.pairing_state import (
    PairingState,
    PairingStatus,
)
from ds_agent.infrastructure.observability import add_backend_breadcrumb
from ds_agent.infrastructure.telegram.telegram_api_client import TelegramApiClient

logger = structlog.get_logger()

BotRuntimeState = Literal["disabled", "starting", "running", "stopping", "error"]


@dataclass(frozen=True, slots=True)
class PairedChat:
    """One paired Telegram chat."""

    chat_id: str
    first_active_at: datetime | None = None
    last_active_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class BotStatus:
    """Serializable supervisor status."""

    enabled: bool
    status: BotRuntimeState
    bot_username: str | None = None
    paired: tuple[PairedChat, ...] = ()
    last_error: str | None = None

    def to_payload(self) -> dict[str, object]:
        """Return renderer-friendly JSON data."""

        return {
            "enabled": self.enabled,
            "status": self.status,
            "botUsername": self.bot_username,
            "paired": [
                {
                    "chatId": chat.chat_id,
                    "firstActiveAt": _iso_or_none(chat.first_active_at),
                    "lastActiveAt": _iso_or_none(chat.last_active_at),
                }
                for chat in self.paired
            ],
            "lastError": self.last_error,
        }


RunnerFactory = Callable[..., Any]
TransportFactory = Callable[[str], TelegramTransportPort]
Clock = Callable[[], datetime]
CodeGenerator = Callable[[], str]


class BotSupervisor:
    """Own the lifecycle of one TelegramGatewayRunner instance."""

    def __init__(
        self,
        config: DSAgentConfig,
        *,
        app_state: Any,
        runner_factory: RunnerFactory | None = None,
        transport_factory: TransportFactory | None = None,
        clock: Clock | None = None,
        code_generator: CodeGenerator | None = None,
        ttl_seconds: int = 60,
    ) -> None:
        self._config = config
        self._app_state = app_state
        self._runner_factory = runner_factory or _default_runner_factory
        self._transport_factory = transport_factory or (lambda token: TelegramApiClient(token))
        self._clock = clock or (lambda: datetime.now(UTC))
        self._code_generator = code_generator or _generate_otp_code
        self._ttl_seconds = ttl_seconds
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._runner: Any | None = None
        self._state: BotRuntimeState = "disabled"
        self._last_error: str | None = None
        self._bot_identity: BotIdentity | None = None
        self._token_override: str | None = None
        self._pending_by_handle: dict[str, PairingState] = {}
        self._pending_tokens: dict[str, str] = {}
        self._pending_identities: dict[str, BotIdentity] = {}
        self._handle_by_code: dict[str, str] = {}
        self._paired_chats: dict[str, PairedChat] = {
            str(chat_id): PairedChat(str(chat_id))
            for chat_id in getattr(config.channels.telegram, "allow_from", [])
        }

    @property
    def status(self) -> BotStatus:
        """Return the current runtime status."""

        self._refresh_finished_task()
        return BotStatus(
            enabled=bool(getattr(self._config.channels.telegram, "enabled", False)),
            status=self._state,
            bot_username=None if self._bot_identity is None else self._bot_identity.username,
            paired=tuple(self._paired_chats.values()),
            last_error=self._last_error,
        )

    async def start(self) -> None:
        """Start the bot if enabled and configured."""

        await self._start(token_override=None)

    async def start_with_token(self, token: str) -> None:
        """Start the bot using an in-memory token override."""

        await self._start(token_override=token)

    async def stop(self, *, timeout: float = 5.0) -> None:
        """Stop the running bot task, if any."""

        async with self._lock:
            if self._task is None:
                self._runner = None
                self._set_state("disabled")
                return

            self._set_state("stopping")
            task = self._task
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=timeout)
            except (asyncio.CancelledError, TimeoutError):
                pass
            finally:
                self._task = None
                self._runner = None
                self._set_state("disabled")

    async def restart(self) -> None:
        """Restart the bot using current config/token state."""

        await self.stop()
        await self.start()

    async def begin_pairing(self, token: str) -> PairingHandle:
        """Validate *token*, start the bot with it, and create an OTP handle."""

        normalized = token.strip()
        if not normalized:
            self._add_pairing_breadcrumb(
                action="start",
                status="error",
                reason="missing_credential",
                level="warning",
            )
            raise ValueError("token is required")

        self._add_pairing_breadcrumb(
            action="start",
            status="validating",
            credential_present=True,
        )
        transport = self._transport_factory(normalized)
        try:
            identity = await transport.get_me(normalized)
        except TelegramError as exc:
            self._add_pairing_breadcrumb(
                action="start",
                status="error",
                reason=_reason_from_exception(exc),
                credential_present=True,
                level="warning",
            )
            raise
        finally:
            await _close_transport(transport)

        now = _coerce_utc(self._clock())
        state = PairingState(
            handle_id=uuid.uuid4().hex,
            code=self._code_generator(),
            created_at=now,
            expires_at=now + timedelta(seconds=self._ttl_seconds),
        )

        async with self._lock:
            self._bot_identity = identity
            self._token_override = normalized
            self._pending_by_handle[state.handle_id] = state
            self._pending_tokens[state.handle_id] = normalized
            self._pending_identities[state.handle_id] = identity
            self._handle_by_code[state.code] = state.handle_id

        self._add_pairing_breadcrumb(
            action="start",
            status=PairingStatus.PENDING,
            credential_present=True,
        )
        await self.start_with_token(normalized)
        self._emit_status_changed()
        return PairingHandle(
            handle_id=state.handle_id,
            code=state.code,
            expires_at=state.expires_at,
            bot_username=identity.username,
            bot_id=identity.id,
            first_name=identity.first_name,
        )

    def pairing_status(self, handle_id: str) -> PairingStatus:
        """Return effective status for a pairing handle."""

        state = self._pending_by_handle.get(handle_id)
        if state is None:
            self._add_pairing_breadcrumb(
                action="status",
                status="error",
                reason="not_found",
                level="warning",
            )
            raise PairingError(
                f"Pairing handle not found: {handle_id}",
                metadata={"handle_id": handle_id},
            )
        status = state.expire_if_needed(now=self._clock()).status
        self._add_pairing_breadcrumb(action="status", status=status)
        return status

    async def cancel_pairing(self, handle_id: str) -> None:
        """Cancel a pending pairing attempt."""

        async with self._lock:
            state = self._pending_by_handle.get(handle_id)
            if state is None:
                self._add_pairing_breadcrumb(
                    action="cancel",
                    status="error",
                    reason="not_found",
                    level="warning",
                )
                raise PairingError(
                    f"Pairing handle not found: {handle_id}",
                    metadata={"handle_id": handle_id},
                )
            try:
                cancelled = state.cancel(now=self._clock())
            except PairingError as exc:
                self._add_pairing_breadcrumb(
                    action="cancel",
                    status="error",
                    reason=_reason_from_exception(exc),
                    level="warning",
                )
                raise
            self._pending_by_handle[handle_id] = cancelled
            self._handle_by_code.pop(state.code, None)
        self._add_pairing_breadcrumb(action="cancel", status=PairingStatus.CANCELLED)
        self._emit_status_changed()

    async def confirm_pairing_by_code(self, code: str, chat_id: str) -> PairingState:
        """Confirm the pending pairing matching *code*."""

        handle_id = self._handle_by_code.get(code.strip())
        if handle_id is None:
            self._add_pairing_breadcrumb(
                action="confirm",
                status="error",
                reason="code_mismatch",
                level="warning",
            )
            raise PairingCodeMismatchError("Pairing code is invalid or expired")
        return await self.confirm_pairing(handle_id, chat_id)

    async def confirm_pairing(self, handle_id: str, chat_id: str) -> PairingState:
        """Confirm a pairing attempt and persist non-secret config state."""

        async with self._lock:
            state = self._pending_by_handle.get(handle_id)
            if state is None:
                self._add_pairing_breadcrumb(
                    action="confirm",
                    status="error",
                    reason="not_found",
                    level="warning",
                )
                raise PairingError(
                    f"Pairing handle not found: {handle_id}",
                    metadata={"handle_id": handle_id},
                )
            try:
                paired = state.confirm(code=state.code, chat_id=chat_id, now=self._clock())
            except PairingError as exc:
                self._add_pairing_breadcrumb(
                    action="confirm",
                    status="error",
                    reason=_reason_from_exception(exc),
                    level="warning",
                )
                raise
            self._pending_by_handle[handle_id] = paired
            self._handle_by_code.pop(state.code, None)
            self._paired_chats[paired.chat_id or chat_id] = PairedChat(
                chat_id=paired.chat_id or chat_id,
                first_active_at=paired.paired_at,
                last_active_at=paired.paired_at,
            )
            identity = self._pending_identities.get(handle_id)
            if identity is not None:
                self._bot_identity = identity
            token = self._pending_tokens.get(handle_id)
            if token is not None:
                self._token_override = token
            self._set_config("channels.telegram.allow_from", list(self._paired_chats))
            self._set_config("channels.telegram.enabled", True)

        self._add_pairing_breadcrumb(action="confirm", status=PairingStatus.PAIRED)
        self._emit_event(
            "telegram.paired",
            {
                "handleId": handle_id,
                "chatId": chat_id,
                "persistToken": True,
            },
        )
        self._emit_status_changed()
        return paired

    def has_pairing_code(self, code: str) -> bool:
        """Return whether *code* currently maps to a pending handle."""

        handle_id = self._handle_by_code.get(code.strip())
        if handle_id is None:
            return False
        state = self._pending_by_handle.get(handle_id)
        return (
            state is not None
            and state.expire_if_needed(now=self._clock()).status == PairingStatus.PENDING
        )

    async def send_test_message(self, chat_id: str, text: str) -> None:
        """Send a one-off test message through a thin API client."""

        token = self._effective_token()
        if not token:
            raise TelegramAuthError("Telegram bot token is required")
        transport = self._transport_factory(token)
        try:
            await transport.send_message(token=token, chat_id=chat_id, text=text)
        finally:
            await _close_transport(transport)

    async def _start(self, *, token_override: str | None) -> None:
        async with self._lock:
            self._refresh_finished_task()
            if self._task is not None and not self._task.done():
                return

            token = (token_override or self._effective_token()).strip()
            enabled = bool(getattr(self._config.channels.telegram, "enabled", False))
            if not enabled and token_override is None:
                self._set_state("disabled")
                return
            if not token:
                self._set_error("missing_token")
                return

            transport = self._transport_factory(token)
            try:
                identity = await transport.get_me(token)
            except TelegramError as exc:
                self._set_error(_reason_from_exception(exc))
                return
            finally:
                await _close_transport(transport)

            self._bot_identity = identity
            self._token_override = token_override
            self._set_state("starting")
            self._runner = self._runner_factory(
                self._config,
                supervisor=self,
                token_override=token_override,
            )
            self._task = asyncio.create_task(self._run_runner(self._runner))
            self._set_state("running")

    async def _run_runner(self, runner: Any) -> None:
        try:
            await runner.run()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._set_error(_reason_from_exception(exc))
            logger.exception("telegram_bot_runner_failed", error=str(exc))
        finally:
            if self._state != "stopping":
                self._task = None
                self._runner = None
                if self._state == "running":
                    self._set_state("disabled")

    def _effective_token(self) -> str:
        return self._token_override or str(getattr(self._config.channels.telegram, "bot_token", ""))

    def _refresh_finished_task(self) -> None:
        task = self._task
        if task is None or not task.done():
            return
        self._task = None
        self._runner = None
        if task.cancelled():
            self._set_state("disabled")
            return
        exc = task.exception()
        if exc is not None:
            self._set_error(_reason_from_exception(exc))

    def _set_config(self, path: str, value: object) -> None:
        setter = getattr(self._app_state, "set_config", None)
        if callable(setter):
            setter(path, value)
            return
        parts = path.split(".")
        obj: Any = self._config
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], value)

    def _set_state(self, state: BotRuntimeState) -> None:
        self._state = state
        if state != "error":
            self._last_error = None
        self._add_pairing_breadcrumb(action="runtime_status", status=state)
        logger.info("telegram_bot_status_changed", status=state)
        self._emit_status_changed()

    def _set_error(self, reason: str) -> None:
        self._state = "error"
        self._last_error = reason
        self._add_pairing_breadcrumb(
            action="runtime_status",
            status="error",
            reason=reason,
            level="warning",
        )
        logger.warning("telegram_bot_status_changed", status="error", reason=reason)
        self._emit_status_changed()

    def _emit_status_changed(self) -> None:
        self._emit_event("telegram.statusChanged", self.status.to_payload())

    def _emit_event(self, event: str, payload: dict[str, object]) -> None:
        broadcaster = getattr(self._app_state, "broadcast_event", None)
        if callable(broadcaster):
            broadcaster(event, payload)

    def _add_pairing_breadcrumb(
        self,
        *,
        action: str,
        status: str | PairingStatus | BotRuntimeState,
        reason: str | None = None,
        credential_present: bool | None = None,
        level: str = "info",
    ) -> None:
        data: dict[str, object] = {
            "action": action,
            "status": str(status),
            "pending_count": len(self._pending_by_handle),
            "paired_count": len(self._paired_chats),
            "runner_active": self._task is not None and not self._task.done(),
        }
        if reason is not None:
            data["reason"] = reason
        if credential_present is not None:
            data["credential_present"] = credential_present
        add_backend_breadcrumb(
            "telegram.bot_supervisor",
            message="telegram_pairing_transition",
            data=data,
            level=level,
        )


def _default_runner_factory(config: DSAgentConfig, **kwargs: Any) -> Any:
    from ds_agent.gateway.telegram_runner import TelegramGatewayRunner

    return TelegramGatewayRunner(config, **kwargs)


def _generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _reason_from_exception(exc: BaseException) -> str:
    if isinstance(exc, TelegramAuthError):
        return "unauthorized"
    if isinstance(exc, TelegramError):
        return str(exc) or exc.__class__.__name__
    return exc.__class__.__name__


async def _close_transport(transport: TelegramTransportPort) -> None:
    closer = getattr(transport, "aclose", None)
    if callable(closer):
        await closer()


def _iso_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _coerce_utc(value).isoformat()
