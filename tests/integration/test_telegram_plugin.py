"""Telegram channel plugin tests with mock bot API."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ds_agent.channels.base import OutboundMessage
from ds_agent.channels.bundled.telegram.plugin import TelegramPlugin


def _inject_mock_bot(plugin: TelegramPlugin) -> AsyncMock:
    """Create a mock Application-like object with a .bot attribute."""
    mock_bot = AsyncMock()
    mock_app = MagicMock()
    mock_app.bot = mock_bot
    plugin._app = mock_app
    return mock_bot


class TestTelegramPlugin:
    def test_meta(self):
        plugin = TelegramPlugin(bot_token="fake:token")
        assert plugin.meta.id == "telegram"
        assert plugin.meta.name == "Telegram"

    def test_capabilities(self):
        plugin = TelegramPlugin(bot_token="fake:token")
        assert plugin.capabilities.max_message_length == 4096
        assert plugin.capabilities.markdown is True

    def test_chunk_text_within_limit(self):
        plugin = TelegramPlugin(bot_token="fake:token")
        chunks = plugin.chunk_text("Short message")
        assert len(chunks) == 1

    def test_chunk_text_exceeds_limit(self):
        plugin = TelegramPlugin(bot_token="fake:token")
        text = "Hello world. " * 500  # ~6500 chars
        chunks = plugin.chunk_text(text)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= 4096

    @pytest.mark.asyncio
    async def test_send_text_calls_bot_api(self):
        plugin = TelegramPlugin(bot_token="fake:token")
        mock_bot = _inject_mock_bot(plugin)
        mock_result = MagicMock()
        mock_result.message_id = 42
        mock_bot.send_message = AsyncMock(return_value=mock_result)

        msg = OutboundMessage(text="Hello", conversation_id="12345")
        result = await plugin.send_text(msg)

        assert result.success
        assert result.message_id == "42"
        mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_text_passes_thread_context(self):
        plugin = TelegramPlugin(bot_token="fake:token")
        mock_bot = _inject_mock_bot(plugin)
        mock_result = MagicMock()
        mock_result.message_id = 7
        mock_bot.send_message = AsyncMock(return_value=mock_result)

        msg = OutboundMessage(
            text="Hello",
            conversation_id="12345",
            thread_id="99",
            reply_to_id="1001",
        )
        result = await plugin.send_text(msg)

        assert result.success
        _, kwargs = mock_bot.send_message.await_args
        assert kwargs["message_thread_id"] == 99
        assert kwargs["reply_to_message_id"] == 1001

    @pytest.mark.asyncio
    async def test_send_text_error_handling(self):
        plugin = TelegramPlugin(bot_token="fake:token")
        mock_bot = _inject_mock_bot(plugin)
        mock_bot.send_message = AsyncMock(side_effect=Exception("API error"))

        msg = OutboundMessage(text="Hello", conversation_id="12345")
        result = await plugin.send_text(msg)

        assert not result.success
        assert "API error" in result.error

    @pytest.mark.asyncio
    async def test_send_long_text_chunked(self):
        plugin = TelegramPlugin(bot_token="fake:token")
        mock_bot = _inject_mock_bot(plugin)
        mock_result = MagicMock()
        mock_result.message_id = 1
        mock_bot.send_message = AsyncMock(return_value=mock_result)

        long_text = "Word " * 2000  # ~10000 chars → multiple chunks
        msg = OutboundMessage(text=long_text, conversation_id="12345")
        result = await plugin.send_text(msg)

        assert result.success
        assert mock_bot.send_message.call_count >= 2

    @pytest.mark.asyncio
    async def test_send_file_uses_workspace_and_thread_context(self, tmp_path):
        plugin = TelegramPlugin(bot_token="fake:token", workspace_dir=str(tmp_path))
        mock_bot = _inject_mock_bot(plugin)
        mock_result = MagicMock()
        mock_result.message_id = 88
        mock_bot.send_document = AsyncMock(return_value=mock_result)

        artifact = Path(tmp_path) / "artifacts" / "report.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("# Report", encoding="utf-8")

        result = await plugin.send_file(
            "12345",
            str(artifact),
            thread_id="55",
            reply_to_id="77",
            caption="Key report",
        )

        assert result.success
        _, kwargs = mock_bot.send_document.await_args
        assert kwargs["message_thread_id"] == 55
        assert kwargs["reply_to_message_id"] == 77
        assert kwargs["caption"] == "Key report"

    def test_chunk_text_prefers_paragraph_boundaries(self):
        plugin = TelegramPlugin(bot_token="fake:token")
        paragraph = "Paragraph " * 200
        text = f"{paragraph}\n\n{paragraph}\n\n{paragraph}"

        chunks = plugin.chunk_text(text)

        assert len(chunks) >= 2
        assert all(len(chunk) <= 4096 for chunk in chunks)
        assert any("\n\n" in chunk for chunk in chunks[:-1])

    @pytest.mark.asyncio
    async def test_send_text_retries_on_rate_limit(self):
        """429 with retry_after triggers retry, then succeeds."""
        plugin = TelegramPlugin(bot_token="fake:token")
        mock_bot = _inject_mock_bot(plugin)

        rate_exc = Exception("flood")
        rate_exc.retry_after = 0.01  # type: ignore[attr-defined]
        mock_result = MagicMock()
        mock_result.message_id = 99
        mock_bot.send_message = AsyncMock(
            side_effect=[rate_exc, mock_result],
        )

        msg = OutboundMessage(text="Retry me", conversation_id="12345")
        result = await plugin.send_text(msg)

        assert result.success
        assert mock_bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_answer_callback_query(self):
        plugin = TelegramPlugin(bot_token="fake:token")
        mock_bot = _inject_mock_bot(plugin)
        mock_bot.answer_callback_query = AsyncMock(return_value=True)

        ok = await plugin.answer_callback_query("query-123", text="Done")
        assert ok
        mock_bot.answer_callback_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_edit_message_text(self):
        plugin = TelegramPlugin(bot_token="fake:token")
        mock_bot = _inject_mock_bot(plugin)
        mock_result = MagicMock()
        mock_result.message_id = 55
        mock_bot.edit_message_text = AsyncMock(return_value=mock_result)

        result = await plugin.edit_message_text("12345", "55", "Updated text")
        assert result.success
        mock_bot.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_my_commands(self):
        plugin = TelegramPlugin(bot_token="fake:token")
        mock_bot = _inject_mock_bot(plugin)
        mock_bot.set_my_commands = AsyncMock(return_value=True)

        ok = await plugin.set_my_commands([("status", "Runtime summary"), ("stop", "Stop run")])
        assert ok
        mock_bot.set_my_commands.assert_called_once()
