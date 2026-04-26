from __future__ import annotations

from dataclasses import dataclass

import pytest

from ds_agent.api.ws_handler import WsRpcHandler
from ds_agent.config.schema import AgentConfig, DSAgentConfig
from ds_agent.domain.notification.pairing_state import PairingStatus


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


@dataclass(frozen=True, slots=True)
class FakeStatus:
    def to_payload(self) -> dict[str, object]:
        return {
            "enabled": True,
            "status": "running",
            "botUsername": "demo_bot",
            "paired": [],
            "lastError": None,
        }


@dataclass(frozen=True, slots=True)
class FakeHandle:
    handle_id: str = "handle-1"
    code: str = "428193"

    def to_dict(self) -> dict[str, object]:
        return {
            "handleId": self.handle_id,
            "code": self.code,
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

    async def begin_pairing(self, token: str) -> FakeHandle:
        self.started_tokens.append(token)
        return FakeHandle()

    def pairing_status(self, handle_id: str) -> PairingStatus:
        assert handle_id == "handle-1"
        return PairingStatus.PENDING

    async def cancel_pairing(self, handle_id: str) -> None:
        self.cancelled.append(handle_id)


class FakeState:
    def __init__(self) -> None:
        self.config = DSAgentConfig(agent=AgentConfig(workspace_dir="."))
        self.supervisor = FakeSupervisor()

    def get_telegram_supervisor(self) -> FakeSupervisor:
        return self.supervisor


@pytest.mark.asyncio
async def test_telegram_status_rpc_returns_supervisor_payload() -> None:
    ws = FakeWebSocket()
    handler = WsRpcHandler(state=FakeState(), websocket=ws)  # type: ignore[arg-type]

    await handler.handle_message(
        {"type": "req", "id": "1", "method": "telegram.status", "params": {}}
    )

    assert ws.sent == [
        {
            "type": "res",
            "id": "1",
            "ok": True,
            "payload": {
                "enabled": True,
                "status": "running",
                "botUsername": "demo_bot",
                "paired": [],
                "lastError": None,
            },
        }
    ]


@pytest.mark.asyncio
async def test_telegram_start_pairing_rpc_returns_handle() -> None:
    state = FakeState()
    ws = FakeWebSocket()
    handler = WsRpcHandler(state=state, websocket=ws)  # type: ignore[arg-type]

    await handler.handle_message(
        {
            "type": "req",
            "id": "2",
            "method": "telegram.startPairing",
            "params": {"token": "123456:ABCDEFGHIJKLMNOPQRST"},
        }
    )

    assert state.supervisor.started_tokens == ["123456:ABCDEFGHIJKLMNOPQRST"]
    assert ws.sent[0]["ok"] is True
    assert ws.sent[0]["payload"]["handleId"] == "handle-1"
    assert ws.sent[0]["payload"]["code"] == "428193"
