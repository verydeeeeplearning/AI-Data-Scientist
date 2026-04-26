from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ds_agent.channels.base import InboundMessage
from ds_agent.channels.bundled.telegram.plugin import TelegramPlugin
from ds_agent.config.schema import AgentConfig, DSAgentConfig
from ds_agent.domain.errors.telegram_errors import PairingCodeMismatchError
from ds_agent.gateway.telegram_runner import TelegramGatewayRunner


class FakeSupervisor:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    async def confirm_pairing_by_code(self, code: str, chat_id: str) -> None:
        self.calls.append((code, chat_id))
        if self.fail:
            raise PairingCodeMismatchError("invalid")


def _runner(supervisor: FakeSupervisor) -> TelegramGatewayRunner:
    runner = TelegramGatewayRunner.__new__(TelegramGatewayRunner)
    runner._config = DSAgentConfig(agent=AgentConfig(language="en"))
    runner._supervisor = supervisor
    runner._operator_chats = set()
    runner._delivery_targets = {}
    runner._send_text = AsyncMock()
    return runner


@pytest.mark.asyncio
async def test_pair_command_confirms_before_normal_command_dispatch() -> None:
    supervisor = FakeSupervisor()
    runner = _runner(supervisor)
    msg = InboundMessage(
        text="/pair 428193",
        sender_id="987654321",
        conversation_id="987654321",
        channel_id="telegram",
        account_id="bot1",
    )

    await runner._handle_message(msg)

    assert supervisor.calls == [("428193", "987654321")]
    runner._send_text.assert_awaited_once()
    assert "Connected" in runner._send_text.await_args.args[0]


@pytest.mark.asyncio
async def test_pair_command_sends_invalid_reply_on_bad_code() -> None:
    supervisor = FakeSupervisor(fail=True)
    runner = _runner(supervisor)
    msg = InboundMessage(
        text="/pair 000000",
        sender_id="987654321",
        conversation_id="987654321",
        channel_id="telegram",
        account_id="bot1",
    )

    await runner._handle_message(msg)

    runner._send_text.assert_awaited_once()
    assert "invalid or expired" in runner._send_text.await_args.args[0]


class _FakeUser:
    id = 987654321


class _FakeChat:
    id = 987654321


class _FakeMessage:
    text = "/pair 428193"
    from_user = _FakeUser()
    chat = _FakeChat()


class _FakeUpdate:
    message = _FakeMessage()

    def to_dict(self) -> dict[str, object]:
        return {}


@pytest.mark.asyncio
async def test_plugin_allows_pair_command_from_unpaired_sender() -> None:
    plugin = TelegramPlugin(bot_token="123:abc", allow_from=["111"])

    await plugin._on_text(_FakeUpdate(), object())

    inbound = await plugin.get_next_message()
    assert inbound.text == "/pair 428193"
    assert inbound.sender_id == "987654321"
