"""AnthropicProvider tests using mock SDK."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.domain.entities.provider_models import ProviderSDKConfig
from ds_agent.domain.interfaces.llm_provider import LLMProvider


def _make_text_response(text="Hello", input_tokens=100, output_tokens=50):
    """Create a mock Anthropic API response with text content."""
    block = MagicMock()
    block.type = "text"
    block.text = text

    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.cache_read_input_tokens = 0
    usage.cache_creation_input_tokens = 0

    resp = MagicMock()
    resp.content = [block]
    resp.usage = usage
    resp.model = "claude-sonnet-4"
    resp.stop_reason = "end_turn"
    return resp


def _make_tool_use_response():
    """Create a mock Anthropic API response with tool use."""
    block = MagicMock()
    block.type = "tool_use"
    block.id = "toolu_1"
    block.name = "profile_data"
    block.input = {"file": "data.csv"}

    usage = MagicMock()
    usage.input_tokens = 200
    usage.output_tokens = 100
    usage.cache_read_input_tokens = 0
    usage.cache_creation_input_tokens = 0

    resp = MagicMock()
    resp.content = [block]
    resp.usage = usage
    resp.model = "claude-sonnet-4"
    resp.stop_reason = "tool_use"
    return resp


def _make_thinking_response():
    """Create a mock response with thinking block."""
    thinking_block = MagicMock()
    thinking_block.type = "thinking"
    thinking_block.thinking = "Let me analyze step by step..."

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "The answer is 42."

    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 50
    usage.cache_read_input_tokens = 0
    usage.cache_creation_input_tokens = 0

    resp = MagicMock()
    resp.content = [thinking_block, text_block]
    resp.usage = usage
    resp.model = "claude-sonnet-4"
    resp.stop_reason = "end_turn"
    return resp


class TestAnthropicProvider:
    @pytest.fixture
    def mock_anthropic_module(self):
        """Mock the anthropic SDK module."""
        mock_client = AsyncMock()
        mock_module = MagicMock()
        mock_module.AsyncAnthropic.return_value = mock_client
        return mock_module, mock_client

    def _create_provider(self, mock_module):
        with patch.dict("sys.modules", {"anthropic": mock_module}):
            from ds_agent.providers.anthropic import AnthropicProvider

            provider = AnthropicProvider.__new__(AnthropicProvider)
            provider._model = "claude-sonnet-4"
            provider._config = ProviderSDKConfig()
            provider._client = mock_module.AsyncAnthropic()
            return provider

    def test_implements_protocol(self, mock_anthropic_module):
        mock_module, _ = mock_anthropic_module
        provider = self._create_provider(mock_module)
        assert isinstance(provider, LLMProvider)

    @pytest.mark.asyncio
    async def test_chat_text_response(self, mock_anthropic_module):
        mock_module, mock_client = mock_anthropic_module
        provider = self._create_provider(mock_module)
        mock_client.messages.create = AsyncMock(return_value=_make_text_response("Result"))

        messages = [ChatMessage(role=Role.USER, content="Analyze data")]
        resp = await provider.chat(messages)

        assert resp.content == "Result"
        assert resp.tool_calls is None
        assert resp.usage.input_tokens == 100
        assert resp.usage.output_tokens == 50

    @pytest.mark.asyncio
    async def test_chat_tool_calls(self, mock_anthropic_module):
        mock_module, mock_client = mock_anthropic_module
        provider = self._create_provider(mock_module)
        mock_client.messages.create = AsyncMock(return_value=_make_tool_use_response())

        messages = [ChatMessage(role=Role.USER, content="Profile data.csv")]
        resp = await provider.chat(messages)

        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "profile_data"
        assert resp.tool_calls[0].arguments == {"file": "data.csv"}
        assert resp.stop_reason == "tool_use"

    @pytest.mark.asyncio
    async def test_extended_thinking(self, mock_anthropic_module):
        mock_module, mock_client = mock_anthropic_module
        provider = self._create_provider(mock_module)
        mock_client.messages.create = AsyncMock(return_value=_make_thinking_response())

        messages = [ChatMessage(role=Role.USER, content="Complex question")]
        resp = await provider.chat(messages)

        assert resp.thinking == "Let me analyze step by step..."
        assert resp.content == "The answer is 42."

    def test_system_prompt_extraction(self, mock_anthropic_module):
        """System messages should be separated from conversation messages."""
        mock_module, _ = mock_anthropic_module
        provider = self._create_provider(mock_module)

        messages = [
            ChatMessage(role=Role.SYSTEM, content="You are a DS agent."),
            ChatMessage(role=Role.USER, content="Hello"),
        ]
        system, api_msgs = provider._split_system_message(messages)

        assert system == "You are a DS agent."
        assert len(api_msgs) == 1
        assert api_msgs[0]["role"] == "user"

    def test_tool_schema_conversion(self, mock_anthropic_module):
        """OpenAI function calling schema should convert to Anthropic format."""
        mock_module, _ = mock_anthropic_module
        provider = self._create_provider(mock_module)

        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": "profile_data",
                    "description": "Profile a dataset",
                    "parameters": {
                        "type": "object",
                        "properties": {"file": {"type": "string"}},
                    },
                },
            }
        ]
        anthropic_tools = provider._convert_tools_to_anthropic(openai_tools)

        assert len(anthropic_tools) == 1
        assert anthropic_tools[0]["name"] == "profile_data"
        assert "input_schema" in anthropic_tools[0]

    def test_model_normalization(self, mock_anthropic_module):
        mock_module, _ = mock_anthropic_module
        with patch.dict("sys.modules", {"anthropic": mock_module}):
            from ds_agent.providers.anthropic import AnthropicProvider

            p = AnthropicProvider.__new__(AnthropicProvider)
            assert p._normalize_model_id("anthropic/claude-sonnet-4") == "claude-sonnet-4"
            assert p._normalize_model_id("claude-sonnet-4") == "claude-sonnet-4"

    def test_get_model_info(self, mock_anthropic_module):
        mock_module, _ = mock_anthropic_module
        provider = self._create_provider(mock_module)
        info = provider.get_model_info()

        assert info.provider == "anthropic"
        assert info.model_id == "claude-sonnet-4"
        assert info.supports_thinking is True
        assert info.supports_caching is True
        assert info.max_context_tokens == 200_000

    @pytest.mark.asyncio
    async def test_chat_with_system_message(self, mock_anthropic_module):
        """System messages should be extracted to the system parameter."""
        mock_module, mock_client = mock_anthropic_module
        provider = self._create_provider(mock_module)
        mock_client.messages.create = AsyncMock(return_value=_make_text_response("OK"))

        messages = [
            ChatMessage(role=Role.SYSTEM, content="You are a DS agent."),
            ChatMessage(role=Role.USER, content="Analyze data"),
        ]
        resp = await provider.chat(messages)

        assert resp.content == "OK"
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["system"] == "You are a DS agent."

    @pytest.mark.asyncio
    async def test_chat_with_tools(self, mock_anthropic_module):
        """Tools should be converted to Anthropic format."""
        mock_module, mock_client = mock_anthropic_module
        provider = self._create_provider(mock_module)
        mock_client.messages.create = AsyncMock(return_value=_make_text_response("OK"))

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
                },
            }
        ]
        await provider.chat(messages, tools=tools)
        call_kwargs = mock_client.messages.create.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tools"][0]["name"] == "read_file"

    @pytest.mark.asyncio
    async def test_chat_with_temperature_no_thinking(self, mock_anthropic_module):
        """Non-zero temperature is passed to API when thinking is disabled (4.10 fix)."""
        mock_module, mock_client = mock_anthropic_module
        provider = self._create_provider(mock_module)
        mock_client.messages.create = AsyncMock(return_value=_make_text_response("OK"))

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        # Explicitly disable thinking so temperature is not overridden
        await provider.chat(messages, temperature=0.7, thinking=False)
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["temperature"] == 0.7
        assert "thinking" not in call_kwargs

    @pytest.mark.asyncio
    async def test_chat_thinking_forces_temperature_one(self, mock_anthropic_module):
        """When thinking is enabled, temperature must be 1 (Anthropic API requirement)."""
        mock_module, mock_client = mock_anthropic_module
        provider = self._create_provider(mock_module)
        mock_client.messages.create = AsyncMock(return_value=_make_text_response("OK"))

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        await provider.chat(messages, temperature=0.0)  # default — thinking enabled
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["temperature"] == 1
        assert call_kwargs["thinking"]["type"] == "enabled"

    @pytest.mark.asyncio
    async def test_count_tokens_success(self, mock_anthropic_module):
        """Token counting via API should return integer."""
        mock_module, mock_client = mock_anthropic_module
        provider = self._create_provider(mock_module)

        token_result = MagicMock()
        token_result.input_tokens = 42
        mock_client.messages.count_tokens = AsyncMock(return_value=token_result)

        messages = [ChatMessage(role=Role.USER, content="Hello world")]
        count = await provider.count_tokens(messages)
        assert count == 42

    @pytest.mark.asyncio
    async def test_count_tokens_fallback_on_error(self, mock_anthropic_module):
        """Token counting fallback: estimate from content length."""
        mock_module, mock_client = mock_anthropic_module
        provider = self._create_provider(mock_module)
        mock_client.messages.count_tokens = AsyncMock(side_effect=Exception("API error"))

        messages = [ChatMessage(role=Role.USER, content="Hello world, this is a test")]
        count = await provider.count_tokens(messages)
        assert isinstance(count, int)
        assert count > 0

    def test_get_model_info_unknown_model(self, mock_anthropic_module):
        """Unknown model should use default values."""
        mock_module, _ = mock_anthropic_module
        provider = self._create_provider(mock_module)
        provider._model = "claude-unknown-future-model"
        info = provider.get_model_info()
        assert info.model_id == "claude-unknown-future-model"
        assert info.max_context_tokens == 200_000
        assert info.max_output_tokens == 8_192

    def test_get_model_info_opus46(self, mock_anthropic_module):
        """Opus 4.6 should have 1M context."""
        mock_module, _ = mock_anthropic_module
        provider = self._create_provider(mock_module)
        provider._model = "claude-opus-4-6"
        info = provider.get_model_info()
        assert info.max_context_tokens == 1_000_000
        assert info.max_output_tokens == 128_000

    def test_convert_tool_message(self, mock_anthropic_module):
        """Tool result messages should convert to user + tool_result format."""
        mock_module, _ = mock_anthropic_module
        provider = self._create_provider(mock_module)

        msg = ChatMessage(role=Role.TOOL, content="result data", tool_call_id="tc_1")
        converted = provider._convert_message(msg)
        assert converted["role"] == "user"
        assert converted["content"][0]["type"] == "tool_result"
        assert converted["content"][0]["tool_use_id"] == "tc_1"

    def test_convert_assistant_message_with_tool_calls(self, mock_anthropic_module):
        """Assistant messages with tool calls should include tool_use blocks."""
        mock_module, _ = mock_anthropic_module
        provider = self._create_provider(mock_module)

        from ds_agent.domain.entities.messages import ToolCall

        msg = ChatMessage(
            role=Role.ASSISTANT,
            content="Let me check.",
            tool_calls=[ToolCall(id="tc_1", name="read_file", arguments={"path": "a.csv"})],
        )
        converted = provider._convert_message(msg)
        assert converted["role"] == "assistant"
        # Should have text + tool_use blocks
        assert any(b["type"] == "text" for b in converted["content"])
        assert any(b["type"] == "tool_use" for b in converted["content"])

    def test_get_default_max_tokens(self, mock_anthropic_module):
        mock_module, _ = mock_anthropic_module
        provider = self._create_provider(mock_module)
        # claude-sonnet-4 has max_output=16000
        assert provider._get_default_max_tokens() == 16_000

    # --- Streaming tests (4.2) ---

    @pytest.mark.asyncio
    async def test_streaming_calls_on_delta(self, mock_anthropic_module):
        """When on_delta is provided, provider streams text deltas and returns final response."""
        mock_module, mock_client = mock_anthropic_module
        provider = self._create_provider(mock_module)

        final_response = _make_text_response("Streamed result")

        # Build a mock async context manager for messages.stream()
        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)
        mock_stream.text_stream = _async_iter(["Streamed ", "result"])
        mock_stream.get_final_message = AsyncMock(return_value=final_response)
        mock_client.messages.stream = MagicMock(return_value=mock_stream)

        received: list[str] = []

        async def collect(delta: str) -> None:
            received.append(delta)

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        resp = await provider.chat(messages, on_delta=collect, thinking=False)

        assert received == ["Streamed ", "result"]
        assert resp.content == "Streamed result"
        # stream() used, not create()
        mock_client.messages.stream.assert_called_once()
        mock_client.messages.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_streaming_skipped_when_thinking_enabled(self, mock_anthropic_module):
        """When extended thinking is active, on_delta is ignored and create() is used."""
        mock_module, mock_client = mock_anthropic_module
        provider = self._create_provider(mock_module)
        mock_client.messages.create = AsyncMock(return_value=_make_thinking_response())

        received: list[str] = []

        async def collect(delta: str) -> None:
            received.append(delta)

        messages = [ChatMessage(role=Role.USER, content="Think hard")]
        # thinking defaults to True for claude-sonnet-4 which has thinking=True in metadata
        resp = await provider.chat(messages, on_delta=collect)

        assert resp.thinking == "Let me analyze step by step..."
        # on_delta was NOT called — thinking path uses create(), not stream()
        assert received == []
        mock_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_streaming_without_on_delta(self, mock_anthropic_module):
        """When on_delta is None (default), provider uses non-streaming create()."""
        mock_module, mock_client = mock_anthropic_module
        provider = self._create_provider(mock_module)
        mock_client.messages.create = AsyncMock(return_value=_make_text_response("OK"))

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        resp = await provider.chat(messages, thinking=False)

        assert resp.content == "OK"
        mock_client.messages.create.assert_called_once()
        mock_client.messages.stream.assert_not_called()


def _async_iter(items: list[str]):
    """Return an async iterator over a list of strings."""

    async def _gen():
        for item in items:
            yield item

    return _gen()


class TestAnthropicProviderInit:
    def test_init_with_config(self):
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            from ds_agent.providers.anthropic import AnthropicProvider

            provider = AnthropicProvider("claude-sonnet-4", ProviderSDKConfig(api_key="sk-test"))
            assert provider._model == "claude-sonnet-4"
            mock_anthropic.AsyncAnthropic.assert_called_once()

    def test_init_normalizes_prefix(self):
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            from ds_agent.providers.anthropic import AnthropicProvider

            provider = AnthropicProvider("anthropic/claude-sonnet-4")
            assert provider._model == "claude-sonnet-4"

    def test_init_default_config(self):
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            from ds_agent.providers.anthropic import AnthropicProvider

            provider = AnthropicProvider("claude-sonnet-4")
            assert provider._config is not None
