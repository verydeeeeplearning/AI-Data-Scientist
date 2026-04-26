from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ds_agent.application.ports.telegram_transport_port import BotIdentity
from ds_agent.application.use_cases.pair_telegram_chat_usecase import (
    PairTelegramChatUseCase,
)


class FakeTransport:
    def __init__(self) -> None:
        self.tokens: list[str] = []

    async def get_me(self, token: str) -> BotIdentity:
        self.tokens.append(token)
        return BotIdentity(id=42, username="demo_bot", first_name="Demo")

    async def send_message(self, *, token: str, chat_id: str, text: str) -> None:
        del token, chat_id, text


@pytest.mark.asyncio
async def test_begin_pairing_validates_token_and_returns_handle() -> None:
    now = datetime(2026, 4, 26, 1, 0, tzinfo=UTC)
    transport = FakeTransport()

    usecase = PairTelegramChatUseCase(
        transport=transport,
        handle_id_generator=lambda: "handle-1",
        code_generator=lambda: "428193",
        clock=lambda: now,
    )

    result = await usecase.start_pairing(token=" 123456:ABCDEFGHIJKLMNOPQRST ")

    assert result.state.handle_id == "handle-1"
    assert result.state.code == "428193"
    assert result.state.created_at == now
    assert result.state.expires_at == now + timedelta(seconds=60)
    assert result.handle.bot_username == "demo_bot"
    assert transport.tokens == ["123456:ABCDEFGHIJKLMNOPQRST"]
