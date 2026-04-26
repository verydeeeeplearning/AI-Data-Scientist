from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from ds_agent.application.ports.telegram_transport_port import BotIdentity
from ds_agent.config.schema import DSAgentConfig
from ds_agent.domain.errors.telegram_errors import PairingExpiredError, TelegramAuthError
from ds_agent.domain.notification.pairing_state import PairingStatus
from ds_agent.gateway.bot_supervisor import BotSupervisor


class FakeTransport:
    def __init__(self, token: str, *, fail_auth: bool = False) -> None:
        self.token = token
        self.fail_auth = fail_auth
        self.closed = False

    async def get_me(self, token: str) -> BotIdentity:
        del token
        if self.fail_auth:
            raise TelegramAuthError("Unauthorized")
        return BotIdentity(id=123, username="demo_bot", first_name="Demo")

    async def send_message(self, *, token: str, chat_id: str, text: str) -> None:
        del token, chat_id, text

    async def aclose(self) -> None:
        self.closed = True


class WaitingRunner:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        self.started = asyncio.Event()

    async def run(self) -> None:
        self.started.set()
        await asyncio.Event().wait()


class FakeAppState:
    def __init__(self, config: DSAgentConfig) -> None:
        self.config = config
        self.events: list[tuple[str, dict[str, object]]] = []
        self.set_calls: list[tuple[str, object]] = []

    def set_config(self, path: str, value: object) -> None:
        self.set_calls.append((path, value))
        parts = path.split(".")
        obj: Any = self.config
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], value)

    def broadcast_event(self, event: str, payload: dict[str, object]) -> None:
        self.events.append((event, payload))


def _supervisor(
    config: DSAgentConfig,
    *,
    now_ref: list[datetime] | None = None,
    fail_auth: bool = False,
) -> BotSupervisor:
    app_state = FakeAppState(config)
    now_ref = now_ref or [datetime(2026, 4, 26, 1, 0, tzinfo=UTC)]
    return BotSupervisor(
        config,
        app_state=app_state,
        runner_factory=lambda *args, **kwargs: WaitingRunner(*args, **kwargs),
        transport_factory=lambda token: FakeTransport(token, fail_auth=fail_auth),
        clock=lambda: now_ref[0],
        code_generator=lambda: "428193",
    )


def _capture_breadcrumbs(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    breadcrumbs: list[dict[str, Any]] = []

    def fake_add_backend_breadcrumb(
        category: str,
        *,
        message: str | None = None,
        data: dict[str, Any] | None = None,
        level: str = "info",
    ) -> None:
        breadcrumbs.append(
            {
                "category": category,
                "message": message,
                "data": data or {},
                "level": level,
            },
        )

    monkeypatch.setattr(
        "ds_agent.gateway.bot_supervisor.add_backend_breadcrumb",
        fake_add_backend_breadcrumb,
    )
    return breadcrumbs


@pytest.mark.asyncio
async def test_start_when_disabled_is_noop() -> None:
    config = DSAgentConfig()
    config.channels.telegram.bot_token = "123:abc"
    supervisor = _supervisor(config)

    await supervisor.start()

    assert supervisor.status.status == "disabled"


@pytest.mark.asyncio
async def test_start_when_enabled_with_token_runs() -> None:
    config = DSAgentConfig()
    config.channels.telegram.enabled = True
    config.channels.telegram.bot_token = "123:abc"
    supervisor = _supervisor(config)

    await supervisor.start()

    assert supervisor.status.status == "running"
    assert supervisor.status.bot_username == "demo_bot"
    await supervisor.stop()


@pytest.mark.asyncio
async def test_stop_while_running_returns_disabled() -> None:
    config = DSAgentConfig()
    config.channels.telegram.enabled = True
    config.channels.telegram.bot_token = "123:abc"
    supervisor = _supervisor(config)

    await supervisor.start()
    await supervisor.stop()

    assert supervisor.status.status == "disabled"


@pytest.mark.asyncio
async def test_begin_pairing_returns_six_digit_code_and_expiry() -> None:
    now_ref = [datetime(2026, 4, 26, 1, 0, tzinfo=UTC)]
    config = DSAgentConfig()
    supervisor = _supervisor(config, now_ref=now_ref)

    handle = await supervisor.begin_pairing("123:abc")

    assert handle.code == "428193"
    assert handle.expires_at == now_ref[0] + timedelta(seconds=60)
    assert handle.bot_username == "demo_bot"
    assert supervisor.pairing_status(handle.handle_id) == PairingStatus.PENDING
    await supervisor.stop()


@pytest.mark.asyncio
async def test_confirm_pairing_adds_chat_and_enables_telegram() -> None:
    config = DSAgentConfig()
    app_state = FakeAppState(config)
    supervisor = BotSupervisor(
        config,
        app_state=app_state,
        runner_factory=lambda *args, **kwargs: WaitingRunner(*args, **kwargs),
        transport_factory=lambda token: FakeTransport(token),
        clock=lambda: datetime(2026, 4, 26, 1, 0, tzinfo=UTC),
        code_generator=lambda: "428193",
    )
    handle = await supervisor.begin_pairing("123:abc")

    paired = await supervisor.confirm_pairing(handle.handle_id, "987654321")

    assert paired.chat_id == "987654321"
    assert config.channels.telegram.enabled is True
    assert config.channels.telegram.allow_from == ["987654321"]
    assert (
        "telegram.paired",
        {"handleId": handle.handle_id, "chatId": "987654321", "persistToken": True},
    ) in app_state.events
    await supervisor.stop()


@pytest.mark.asyncio
async def test_pairing_transitions_emit_low_sensitivity_breadcrumbs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    breadcrumbs = _capture_breadcrumbs(monkeypatch)
    config = DSAgentConfig()
    supervisor = _supervisor(config)

    handle = await supervisor.begin_pairing("123:abc")
    assert supervisor.pairing_status(handle.handle_id) == PairingStatus.PENDING
    await supervisor.confirm_pairing(handle.handle_id, "987654321")
    second_handle = await supervisor.begin_pairing("123:abc")
    await supervisor.cancel_pairing(second_handle.handle_id)

    pairing_breadcrumbs = [
        item
        for item in breadcrumbs
        if item["category"] == "telegram.bot_supervisor"
        and item["message"] == "telegram_pairing_transition"
    ]
    actions = [item["data"]["action"] for item in pairing_breadcrumbs]
    assert "start" in actions
    assert "status" in actions
    assert "cancel" in actions
    assert "confirm" in actions
    assert "runtime_status" in actions

    for item in pairing_breadcrumbs:
        data = item["data"]
        assert "handle_id" not in data
        assert "handleId" not in data
        assert "chat_id" not in data
        assert "chatId" not in data
        assert "token" not in data
        assert "code" not in data
        assert "pending_count" in data
        assert "paired_count" in data

    await supervisor.stop()


@pytest.mark.asyncio
async def test_pairing_error_transitions_emit_breadcrumbs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    breadcrumbs = _capture_breadcrumbs(monkeypatch)
    config = DSAgentConfig()
    supervisor = _supervisor(config, fail_auth=True)

    with pytest.raises(TelegramAuthError):
        await supervisor.begin_pairing("bad")

    assert {
        "action": "start",
        "status": "error",
        "reason": "unauthorized",
        "pending_count": 0,
        "paired_count": 0,
        "runner_active": False,
        "credential_present": True,
    } in [item["data"] for item in breadcrumbs]


@pytest.mark.asyncio
async def test_confirm_pairing_with_expired_handle_raises() -> None:
    now_ref = [datetime(2026, 4, 26, 1, 0, tzinfo=UTC)]
    config = DSAgentConfig()
    supervisor = _supervisor(config, now_ref=now_ref)
    handle = await supervisor.begin_pairing("123:abc")
    now_ref[0] = now_ref[0] + timedelta(seconds=61)

    with pytest.raises(PairingExpiredError):
        await supervisor.confirm_pairing(handle.handle_id, "987654321")

    await supervisor.stop()


@pytest.mark.asyncio
async def test_start_with_bad_token_records_unauthorized_error() -> None:
    config = DSAgentConfig()
    config.channels.telegram.enabled = True
    config.channels.telegram.bot_token = "bad"
    supervisor = _supervisor(config, fail_auth=True)

    await supervisor.start()

    assert supervisor.status.status == "error"
    assert supervisor.status.last_error == "unauthorized"
