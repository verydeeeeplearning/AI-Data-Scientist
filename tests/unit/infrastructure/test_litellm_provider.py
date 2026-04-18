"""LiteLLMProvider tests — model info, chat routing, graceful errors."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.providers.litellm_provider import LITELLM_MODELS, LiteLLMProvider


class TestLiteLLMModels:
    def test_deepseek_in_catalog(self):
        assert "deepseek/deepseek-chat" in LITELLM_MODELS
        assert "deepseek/deepseek-reasoner" in LITELLM_MODELS

    def test_minimax_in_catalog(self):
        assert "minimax/MiniMax-M2.5" in LITELLM_MODELS

    def test_qwen_in_catalog(self):
        assert "qwen/qwen3.6-plus-preview" in LITELLM_MODELS
        assert "qwen/qwen3.5-plus" in LITELLM_MODELS

    def test_groq_in_catalog(self):
        assert "groq/llama-3.3-70b-versatile" in LITELLM_MODELS
        assert "groq/llama-4-scout-17b-16e-instruct" in LITELLM_MODELS

    def test_chinese_providers_in_catalog(self):
        assert "zhipu/glm-5" in LITELLM_MODELS
        assert "moonshot/kimi-k2.5" in LITELLM_MODELS


class TestLiteLLMProvider:
    def _create_provider(self, model: str = "deepseek/deepseek-chat"):
        mock_litellm = MagicMock()
        mock_litellm.acompletion = AsyncMock()
        mock_litellm.token_counter = MagicMock(return_value=100)

        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            provider = LiteLLMProvider.__new__(LiteLLMProvider)
            provider._model = model
            provider._config = MagicMock()
            provider._config.api_key = None
            provider._api_key = None
            provider._litellm = mock_litellm
        return provider, mock_litellm

    def test_get_model_info_deepseek(self):
        provider, _ = self._create_provider("deepseek/deepseek-chat")
        info = provider.get_model_info()
        assert info.model_id == "deepseek/deepseek-chat"
        assert info.provider == "deepseek"
        assert info.display_name == "DeepSeek V3.2"
        assert info.max_context_tokens == 128_000

    def test_get_model_info_minimax(self):
        provider, _ = self._create_provider("minimax/MiniMax-M2.5")
        info = provider.get_model_info()
        assert info.provider == "minimax"
        assert info.display_name == "MiniMax M2.5"
        assert info.max_context_tokens == 200_000

    def test_get_model_info_unknown_model_defaults(self):
        provider, _ = self._create_provider("unknown/some-model")
        info = provider.get_model_info()
        assert info.provider == "litellm"
        assert info.max_context_tokens == 128_000

    @pytest.mark.asyncio
    async def test_chat_calls_litellm_acompletion(self):
        provider, mock_litellm = self._create_provider()

        # Mock response
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello from DeepSeek"
        mock_choice.message.tool_calls = None
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_usage.cache_read_input_tokens = 0
        mock_usage.reasoning_tokens = 0

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "deepseek-chat"

        mock_litellm.acompletion = AsyncMock(return_value=mock_response)

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        resp = await provider.chat(messages)

        assert resp.content == "Hello from DeepSeek"
        mock_litellm.acompletion.assert_called_once()
        call_kwargs = mock_litellm.acompletion.call_args[1]
        assert call_kwargs["model"] == "deepseek/deepseek-chat"

    @pytest.mark.asyncio
    async def test_count_tokens_fallback(self):
        provider, mock_litellm = self._create_provider()
        mock_litellm.token_counter.side_effect = Exception("not supported")

        messages = [ChatMessage(role=Role.USER, content="Hello world")]
        count = await provider.count_tokens(messages)
        assert count > 0

    @pytest.mark.asyncio
    async def test_count_tokens_success(self):
        provider, mock_litellm = self._create_provider()
        mock_litellm.token_counter.return_value = 42

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        count = await provider.count_tokens(messages)
        assert count == 42

    @pytest.mark.asyncio
    async def test_chat_error_raises(self):
        """On LiteLLM error, exception should propagate (3.7 fix: no swallowing)."""
        provider, mock_litellm = self._create_provider()
        mock_litellm.acompletion = AsyncMock(side_effect=Exception("API rate limited"))

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        with pytest.raises(Exception, match="API rate limited"):
            await provider.chat(messages)

    @pytest.mark.asyncio
    async def test_chat_with_tools(self):
        """Tools should be passed through to LiteLLM."""
        provider, mock_litellm = self._create_provider()

        # Create mock response
        mock_choice = MagicMock()
        mock_choice.message.content = "OK"
        mock_choice.message.tool_calls = None
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_usage.cache_read_input_tokens = 0
        mock_usage.reasoning_tokens = 0

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "deepseek-chat"
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)

        tools = [{"type": "function", "function": {"name": "test", "parameters": {}}}]
        messages = [ChatMessage(role=Role.USER, content="Hello")]
        await provider.chat(messages, tools=tools)

        call_kwargs = mock_litellm.acompletion.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tool_choice"] == "auto"

    @pytest.mark.asyncio
    async def test_chat_with_max_tokens(self):
        provider, mock_litellm = self._create_provider()

        mock_choice = MagicMock()
        mock_choice.message.content = "OK"
        mock_choice.message.tool_calls = None
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_usage.cache_read_input_tokens = 0
        mock_usage.reasoning_tokens = 0

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "deepseek-chat"
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        await provider.chat(messages, max_tokens=500)

        call_kwargs = mock_litellm.acompletion.call_args[1]
        assert call_kwargs["max_tokens"] == 500

    @pytest.mark.asyncio
    async def test_chat_with_api_key(self):
        """If api_key is set, it should be passed to acompletion."""
        provider, mock_litellm = self._create_provider()
        provider._api_key = "sk-test-key"

        mock_choice = MagicMock()
        mock_choice.message.content = "OK"
        mock_choice.message.tool_calls = None
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_usage.cache_read_input_tokens = 0
        mock_usage.reasoning_tokens = 0

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "deepseek-chat"
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        await provider.chat(messages)

        call_kwargs = mock_litellm.acompletion.call_args[1]
        assert call_kwargs["api_key"] == "sk-test-key"

    def test_get_model_info_groq(self):
        provider, _ = self._create_provider("groq/llama-3.3-70b-versatile")
        info = provider.get_model_info()
        assert info.provider == "groq"
        assert info.display_name == "Llama 3.3 70B (Groq)"


class TestLiteLLMProviderInit:
    """Test constructor and API key resolution."""

    def test_init_with_api_key_in_config(self):
        mock_litellm = MagicMock()
        from ds_agent.domain.entities.provider_models import ProviderSDKConfig

        cfg = ProviderSDKConfig(api_key="sk-test")
        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            provider = LiteLLMProvider("deepseek/deepseek-chat", cfg)
            assert provider._api_key == "sk-test"

    def test_init_resolves_key_from_env(self, monkeypatch):
        mock_litellm = MagicMock()
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-from-env")
        from ds_agent.domain.entities.provider_models import ProviderSDKConfig

        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            provider = LiteLLMProvider("deepseek/deepseek-chat", ProviderSDKConfig())
            assert provider._api_key == "sk-from-env"

    def test_init_no_key(self, monkeypatch):
        mock_litellm = MagicMock()
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        from ds_agent.domain.entities.provider_models import ProviderSDKConfig

        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            provider = LiteLLMProvider("deepseek/deepseek-chat", ProviderSDKConfig())
            assert provider._api_key is None

    def test_init_import_error(self):
        """Missing litellm should raise ImportError."""
        from ds_agent.domain.entities.provider_models import ProviderSDKConfig

        with (
            patch.dict("sys.modules", {"litellm": None}),
            pytest.raises(ImportError, match="litellm"),
        ):
            import importlib

            import ds_agent.providers.litellm_provider as mod

            importlib.reload(mod)
            mod.LiteLLMProvider("deepseek/deepseek-chat", ProviderSDKConfig())
