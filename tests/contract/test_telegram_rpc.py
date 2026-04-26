from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import pytest

from ds_agent.api.ws_handler import WsRpcHandler
from ds_agent.application.ports.telegram_transport_port import BotIdentity
from ds_agent.config.schema import AgentConfig, DSAgentConfig
from ds_agent.domain.errors.telegram_errors import TelegramAuthError, TelegramNetworkError
from ds_agent.domain.notification.pairing_state import PairingStatus


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.sent.append(payload)


@dataclass(frozen=True, slots=True)
class FakeStatus:
    def to_payload(self) -> dict[str, object]:
        return {
            "enabled": True,
            "status": "running",
            "botUsername": "demo_bot",
            "paired": [
                {
                    "chatId": "chat-1",
                    "firstActiveAt": 1_766_666_000,
                    "lastActiveAt": 1_766_666_600,
                }
            ],
            "lastError": None,
        }


@dataclass(frozen=True, slots=True)
class FakeHandle:
    def to_dict(self) -> dict[str, object]:
        return {
            "handleId": "handle-1",
            "code": "428193",
            "expiresAt": 1_766_666_666,
            "botUsername": "demo_bot",
            "botId": 123,
            "firstName": "Demo",
        }


class FakeSupervisor:
    status = FakeStatus()

    def __init__(self) -> None:
        self.started_tokens: list[str] = []
        self.cancelled: list[str] = []
        self.sent_messages: list[tuple[str, str]] = []

    async def begin_pairing(self, token: str) -> FakeHandle:
        self.started_tokens.append(token)
        return FakeHandle()

    def pairing_status(self, handle_id: str) -> PairingStatus:
        assert handle_id == "handle-1"
        return PairingStatus.PAIRED

    async def cancel_pairing(self, handle_id: str) -> None:
        self.cancelled.append(handle_id)

    async def send_test_message(self, chat_id: str, text: str) -> None:
        self.sent_messages.append((chat_id, text))


class FakeState:
    def __init__(self) -> None:
        self.config = DSAgentConfig(agent=AgentConfig(workspace_dir="."))
        self.config.channels.telegram.allow_from = ["chat-1", "chat-2"]
        self.supervisor = FakeSupervisor()
        self.set_config_calls: list[tuple[str, object]] = []
        self.started_forces: list[bool] = []
        self.stop_count = 0
        self.broadcasts: list[tuple[str, dict[str, object]]] = []

    def get_telegram_supervisor(self) -> FakeSupervisor:
        return self.supervisor

    def set_config(self, path: str, value: object) -> None:
        self.set_config_calls.append((path, value))
        if path == "channels.telegram.allow_from":
            self.config.channels.telegram.allow_from = list(value)  # type: ignore[arg-type]
        elif path == "channels.telegram.enabled":
            self.config.channels.telegram.enabled = bool(value)

    async def start_telegram_gateway(self, *, force: bool = False) -> None:
        self.started_forces.append(force)

    async def stop_telegram_gateway(self) -> None:
        self.stop_count += 1

    def broadcast_event(self, event: str, payload: dict[str, object]) -> None:
        self.broadcasts.append((event, payload))


async def _rpc(
    state: FakeState,
    method: str,
    params: dict[str, object] | None = None,
) -> dict[str, Any]:
    ws = FakeWebSocket()
    handler = WsRpcHandler(state=state, websocket=ws)  # type: ignore[arg-type]
    await handler.handle_message(
        {"type": "req", "id": "req-1", "method": method, "params": params or {}}
    )
    assert len(ws.sent) == 1
    return ws.sent[0]


@pytest.mark.asyncio
async def test_telegram_rpc_happy_path_contract() -> None:
    state = FakeState()

    start = await _rpc(
        state,
        "telegram.startPairing",
        {"token": "123456:ABCDEFGHIJKLMNOPQRST"},
    )
    assert start["ok"] is True
    assert start["payload"]["handleId"] == "handle-1"
    assert start["payload"]["code"] == "428193"
    assert state.supervisor.started_tokens == ["123456:ABCDEFGHIJKLMNOPQRST"]

    pairing = await _rpc(state, "telegram.pairingStatus", {"handleId": "handle-1"})
    assert pairing["payload"] == {"state": "paired"}

    cancel = await _rpc(state, "telegram.cancelPairing", {"handleId": "handle-1"})
    assert cancel["payload"] == {"ok": True}
    assert state.supervisor.cancelled == ["handle-1"]

    status = await _rpc(state, "telegram.status")
    assert status["payload"] == FakeStatus().to_payload()

    send_test = await _rpc(state, "telegram.sendTestMessage", {"chatId": "chat-1"})
    assert send_test["payload"] == {"ok": True}
    assert state.supervisor.sent_messages == [
        ("chat-1", "DS Agent Telegram test message.")
    ]

    disconnect_chat = await _rpc(state, "telegram.disconnect", {"chatId": "chat-1"})
    assert disconnect_chat["payload"] == {"ok": True}
    assert state.config.channels.telegram.allow_from == ["chat-2"]
    assert state.broadcasts[-1][0] == "telegram.statusChanged"

    disconnect_all = await _rpc(state, "telegram.disconnect")
    assert disconnect_all["payload"] == {"ok": True}
    assert state.stop_count == 1
    assert state.set_config_calls[-1] == ("channels.telegram.enabled", False)

    reconnect = await _rpc(state, "telegram.reconnect")
    assert reconnect["payload"] == {"ok": True}
    assert state.set_config_calls[-1] == ("channels.telegram.enabled", True)
    assert state.started_forces == [True]


@pytest.mark.asyncio
async def test_telegram_rpc_invalid_params_contract() -> None:
    state = FakeState()

    for method, params in [
        ("telegram.startPairing", {}),
        ("telegram.pairingStatus", {}),
        ("telegram.cancelPairing", {}),
        ("telegram.sendTestMessage", {}),
    ]:
        response = await _rpc(state, method, params)
        assert response["ok"] is False
        assert response["error"]["code"] == "INVALID_PARAMS"


@pytest.mark.asyncio
async def test_telegram_test_rpc_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    from ds_agent.infrastructure.telegram import telegram_api_client

    class FakeClient:
        instances: ClassVar[list[FakeClient]] = []
        error: ClassVar[Exception | None] = None

        def __init__(self) -> None:
            self.closed = False
            FakeClient.instances.append(self)

        async def get_me(self, token: str) -> BotIdentity:
            assert token == "123456:ABCDEFGHIJKLMNOPQRST"
            if FakeClient.error is not None:
                raise FakeClient.error
            return BotIdentity(id=123, username="demo_bot", first_name="Demo")

        async def aclose(self) -> None:
            self.closed = True

    monkeypatch.setattr(telegram_api_client, "TelegramApiClient", FakeClient)

    success = await _rpc(
        FakeState(),
        "telegram.test",
        {"token": "123456:ABCDEFGHIJKLMNOPQRST"},
    )
    assert success["payload"] == {
        "ok": True,
        "username": "demo_bot",
        "firstName": "Demo",
        "botId": 123,
    }
    assert FakeClient.instances[-1].closed is True

    FakeClient.error = TelegramAuthError("unauthorized")
    auth_failure = await _rpc(
        FakeState(),
        "telegram.test",
        {"token": "123456:ABCDEFGHIJKLMNOPQRST"},
    )
    assert auth_failure["payload"] == {"ok": False, "reason": "unauthorized"}
    assert FakeClient.instances[-1].closed is True

    FakeClient.error = TelegramNetworkError("offline")
    network_failure = await _rpc(
        FakeState(),
        "telegram.test",
        {"token": "123456:ABCDEFGHIJKLMNOPQRST"},
    )
    assert network_failure["payload"] == {"ok": False, "reason": "network_error"}

    invalid_format = await _rpc(FakeState(), "telegram.test", {"token": ""})
    assert invalid_format["payload"] == {"ok": False, "reason": "invalid_format"}
