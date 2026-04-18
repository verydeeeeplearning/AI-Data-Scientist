"""OpenAIProvider tests using mock SDK."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.domain.entities.provider_models import ProviderSDKConfig
from ds_agent.domain.interfaces.llm_provider import LLMProvider


def _make_openai_text_response(text="Hello", prompt_tokens=100, completion_tokens=50):
    """Create a mock OpenAI API response."""
    message = MagicMock()
    message.content = text
    message.tool_calls = None

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.cache_read_input_tokens = 0
    usage.reasoning_tokens = 0

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    resp.model = "gpt-4.1"
    return resp


def _make_openai_tool_response():
    """Create a mock OpenAI response with tool calls."""
    func = MagicMock()
    func.name = "profile_data"
    func.arguments = '{"file": "data.csv"}'

    tc = MagicMock()
    tc.id = "call_1"
    tc.type = "function"
    tc.function = func

    message = MagicMock()
    message.content = None
    message.tool_calls = [tc]

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "tool_calls"

    usage = MagicMock()
    usage.prompt_tokens = 200
    usage.completion_tokens = 100
    usage.cache_read_input_tokens = 0
    usage.reasoning_tokens = 0

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    resp.model = "gpt-4.1"
    return resp


def _make_reasoning_response():
    """Create a mock o-series response with reasoning tokens."""
    message = MagicMock()
    message.content = "The answer is 42."
    message.tool_calls = None

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"

    details = MagicMock()
    details.reasoning_tokens = 500

    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 50
    usage.cache_read_input_tokens = 0
    usage.reasoning_tokens = 0
    usage.completion_tokens_details = details

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    resp.model = "o3"
    return resp


class TestOpenAIProvider:
    @pytest.fixture
    def mock_openai_module(self):
        mock_client = AsyncMock()
        mock_module = MagicMock()
        mock_module.AsyncOpenAI.return_value = mock_client
        return mock_module, mock_client

    def _create_provider(self, mock_module):
        with patch.dict("sys.modules", {"openai": mock_module}):
            from ds_agent.providers.openai_provider import OpenAIProvider

            provider = OpenAIProvider.__new__(OpenAIProvider)
            provider._model = "gpt-4.1"
            provider._config = ProviderSDKConfig()
            provider._client = mock_module.AsyncOpenAI()
            return provider

    def test_implements_protocol(self, mock_openai_module):
        mock_module, _ = mock_openai_module
        provider = self._create_provider(mock_module)
        assert isinstance(provider, LLMProvider)

    @pytest.mark.asyncio
    async def test_chat_text_response(self, mock_openai_module):
        mock_module, mock_client = mock_openai_module
        provider = self._create_provider(mock_module)
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_openai_text_response("Analysis complete")
        )

        messages = [ChatMessage(role=Role.USER, content="Analyze")]
        resp = await provider.chat(messages)

        assert resp.content == "Analysis complete"
        assert resp.tool_calls is None
        assert resp.usage.input_tokens == 100

    @pytest.mark.asyncio
    async def test_chat_tool_calls(self, mock_openai_module):
        mock_module, mock_client = mock_openai_module
        provider = self._create_provider(mock_module)
        mock_client.chat.completions.create = AsyncMock(return_value=_make_openai_tool_response())

        messages = [ChatMessage(role=Role.USER, content="Profile data")]
        resp = await provider.chat(messages)

        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "profile_data"

    @pytest.mark.asyncio
    async def test_reasoning_tokens(self, mock_openai_module):
        mock_module, mock_client = mock_openai_module
        provider = self._create_provider(mock_module)
        # Use o3 model for reasoning
        provider._model = "o3"
        mock_client.chat.completions.create = AsyncMock(return_value=_make_reasoning_response())

        messages = [ChatMessage(role=Role.USER, content="Complex")]
        resp = await provider.chat(messages)

        assert resp.content == "The answer is 42."
        assert resp.usage.reasoning_tokens == 500

    def test_model_normalization(self, mock_openai_module):
        mock_module, _ = mock_openai_module
        with patch.dict("sys.modules", {"openai": mock_module}):
            from ds_agent.providers.openai_provider import OpenAIProvider

            p = OpenAIProvider.__new__(OpenAIProvider)
            assert p._normalize_model_id("openai/gpt-4.1") == "gpt-4.1"
            assert p._normalize_model_id("gpt-4.1") == "gpt-4.1"

    def test_get_model_info(self, mock_openai_module):
        mock_module, _ = mock_openai_module
        provider = self._create_provider(mock_module)
        info = provider.get_model_info()

        assert info.provider == "openai"
        assert info.model_id == "gpt-4.1"
        assert info.max_context_tokens == 1_048_576

    # --- Phase 4: Gap-filling tests ---

    def test_get_model_info_unknown_defaults(self, mock_openai_module):
        """Unknown model → fallback context/output limits."""
        mock_module, _ = mock_openai_module
        provider = self._create_provider(mock_module)
        provider._model = "unknown-future-model"
        info = provider.get_model_info()

        assert info.model_id == "unknown-future-model"
        assert info.max_context_tokens > 0  # should have a default

    @pytest.mark.asyncio
    async def test_count_tokens_estimation(self, mock_openai_module):
        """count_tokens returns an integer estimation."""
        mock_module, _ = mock_openai_module
        provider = self._create_provider(mock_module)

        messages = [ChatMessage(role=Role.USER, content="Hello world")]
        count = await provider.count_tokens(messages)

        assert isinstance(count, int)
        assert count > 0

    @pytest.mark.asyncio
    async def test_count_tokens_fallback_on_error(self, mock_openai_module):
        """When tiktoken fails, fallback to len//4 estimation."""
        mock_module, _ = mock_openai_module
        provider = self._create_provider(mock_module)

        with patch.dict("sys.modules", {"tiktoken": None}):
            # Force the import to fail inside count_tokens
            messages = [ChatMessage(role=Role.USER, content="A" * 100)]
            count = await provider.count_tokens(messages)
            assert isinstance(count, int)
            assert count > 0

    @pytest.mark.asyncio
    async def test_chat_with_tools(self, mock_openai_module):
        """Tools should be passed to the API call."""
        mock_module, mock_client = mock_openai_module
        provider = self._create_provider(mock_module)
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_openai_text_response("OK")
        )

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        await provider.chat(messages, tools=tools)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tool_choice"] == "auto"

    @pytest.mark.asyncio
    async def test_chat_with_max_tokens(self, mock_openai_module):
        """max_tokens should be passed for non-reasoning models."""
        mock_module, mock_client = mock_openai_module
        provider = self._create_provider(mock_module)
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_openai_text_response("OK")
        )

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        await provider.chat(messages, max_tokens=1000)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["max_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_chat_reasoning_model_uses_max_completion_tokens(self, mock_openai_module):
        """Reasoning models should use max_completion_tokens instead of max_tokens."""
        mock_module, mock_client = mock_openai_module
        provider = self._create_provider(mock_module)
        provider._model = "o3"
        mock_client.chat.completions.create = AsyncMock(return_value=_make_reasoning_response())

        messages = [ChatMessage(role=Role.USER, content="Complex")]
        await provider.chat(messages, max_tokens=2000)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "max_completion_tokens" in call_kwargs
        assert "max_tokens" not in call_kwargs

    @pytest.mark.asyncio
    async def test_chat_reasoning_model_no_temperature(self, mock_openai_module):
        """Reasoning models should not receive temperature parameter."""
        mock_module, mock_client = mock_openai_module
        provider = self._create_provider(mock_module)
        provider._model = "o3"
        mock_client.chat.completions.create = AsyncMock(return_value=_make_reasoning_response())

        messages = [ChatMessage(role=Role.USER, content="Complex")]
        await provider.chat(messages, temperature=0.5)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "temperature" not in call_kwargs

    def test_is_reasoning_model_true(self, mock_openai_module):
        mock_module, _ = mock_openai_module
        provider = self._create_provider(mock_module)
        provider._model = "o3"
        assert provider._is_reasoning_model() is True

    def test_is_reasoning_model_false(self, mock_openai_module):
        mock_module, _ = mock_openai_module
        provider = self._create_provider(mock_module)
        provider._model = "gpt-4.1"
        assert provider._is_reasoning_model() is False

    def test_get_model_info_gpt54(self, mock_openai_module):
        mock_module, _ = mock_openai_module
        provider = self._create_provider(mock_module)
        provider._model = "gpt-5.4"
        info = provider.get_model_info()
        assert info.display_name == "GPT-5.4"
        assert info.max_context_tokens == 1_050_000


class TestOpenAIProviderInit:
    def test_init_with_config(self):
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            from ds_agent.providers.openai_provider import OpenAIProvider

            provider = OpenAIProvider("gpt-4.1", ProviderSDKConfig(api_key="sk-test"))
            assert provider._model == "gpt-4.1"
            mock_openai.AsyncOpenAI.assert_called_once()

    def test_init_normalizes_prefix(self):
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            from ds_agent.providers.openai_provider import OpenAIProvider

            provider = OpenAIProvider("openai/gpt-4.1", ProviderSDKConfig())
            assert provider._model == "gpt-4.1"

    def test_init_default_config(self):
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            from ds_agent.providers.openai_provider import OpenAIProvider

            provider = OpenAIProvider("gpt-4.1")
            assert provider._config is not None
