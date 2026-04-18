"""ProviderRouter tests: model string parsing, auto provider selection, fallback."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ds_agent.domain.entities.messages import ChatMessage, LLMResponse, Role, Usage
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.providers.router import ProviderRouter, parse_model_string


class TestParseModelString:
    def test_anthropic_prefix(self):
        provider, model = parse_model_string("anthropic/claude-sonnet-4")
        assert provider == "anthropic"
        assert model == "claude-sonnet-4"

    def test_openai_prefix(self):
        provider, model = parse_model_string("openai/gpt-4.1")
        assert provider == "openai"
        assert model == "gpt-4.1"

    def test_litellm_prefix(self):
        provider, model = parse_model_string("groq/llama-3.3-70b")
        assert provider == "litellm"
        assert model == "groq/llama-3.3-70b"

    def test_ollama_prefix(self):
        provider, model = parse_model_string("ollama/qwen2.5:32b")
        assert provider == "ollama"
        assert model == "qwen2.5:32b"

    def test_bare_claude_model(self):
        provider, model = parse_model_string("claude-sonnet-4")
        assert provider == "anthropic"
        assert model == "claude-sonnet-4"

    def test_bare_gpt_model(self):
        provider, model = parse_model_string("gpt-4.1")
        assert provider == "openai"
        assert model == "gpt-4.1"

    def test_bare_o_series(self):
        provider, model = parse_model_string("o3-mini")
        assert provider == "openai"
        assert model == "o3-mini"

    def test_unknown_model_defaults_to_litellm(self):
        provider, model = parse_model_string("some-random-model")
        assert provider == "litellm"
        assert model == "some-random-model"

    def test_openrouter_prefix(self):
        provider, model = parse_model_string("openrouter/anthropic/claude-sonnet-4")
        assert provider == "litellm"
        assert model == "openrouter/anthropic/claude-sonnet-4"

    def test_deepseek_prefix(self):
        provider, model = parse_model_string("deepseek/deepseek-chat")
        assert provider == "litellm"
        assert model == "deepseek/deepseek-chat"

    def test_minimax_prefix(self):
        provider, model = parse_model_string("minimax/MiniMax-M2.5")
        assert provider == "litellm"
        assert model == "minimax/MiniMax-M2.5"

    def test_qwen_prefix(self):
        provider, model = parse_model_string("qwen/qwen3.6-plus-preview")
        assert provider == "litellm"
        assert model == "qwen/qwen3.6-plus-preview"

    def test_bare_gpt54_model(self):
        provider, model = parse_model_string("gpt-5.4")
        assert provider == "openai"
        assert model == "gpt-5.4"

    def test_bare_gpt54_mini(self):
        provider, model = parse_model_string("gpt-5.4-mini")
        assert provider == "openai"
        assert model == "gpt-5.4-mini"

    def test_bare_claude_opus_46(self):
        provider, model = parse_model_string("claude-opus-4-6")
        assert provider == "anthropic"
        assert model == "claude-opus-4-6"


class TestProviderRouter:
    def _mock_provider(self, response: LLMResponse | None = None):
        provider = AsyncMock()
        provider.chat = AsyncMock(
            return_value=response
            or LLMResponse(
                content="OK",
                usage=Usage(input_tokens=10, output_tokens=5),
                model="test",
            )
        )
        provider.count_tokens = AsyncMock(return_value=100)
        provider.get_model_info = MagicMock(
            return_value=ModelInfo(
                model_id="test",
                provider="test",
                display_name="Test",
                max_context_tokens=128000,
                max_output_tokens=4096,
            )
        )
        return provider

    @pytest.mark.asyncio
    async def test_routes_to_primary(self):
        primary = self._mock_provider()
        router = ProviderRouter.__new__(ProviderRouter)
        router._primary = primary
        router._fallbacks = []

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        resp = await router.chat(messages)

        assert resp.content == "OK"
        primary.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self):
        primary = self._mock_provider()
        primary.chat = AsyncMock(side_effect=Exception("API error"))

        fallback = self._mock_provider(
            LLMResponse(content="Fallback OK", usage=Usage(input_tokens=10, output_tokens=5))
        )

        router = ProviderRouter.__new__(ProviderRouter)
        router._primary = primary
        router._fallbacks = [fallback]

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        resp = await router.chat(messages)

        assert resp.content == "Fallback OK"
        fallback.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_emits_events_on_successful_fallback(self):
        primary = self._mock_provider()
        primary.chat = AsyncMock(side_effect=Exception("429 rate limit"))

        fallback = self._mock_provider(
            LLMResponse(content="Fallback OK", usage=Usage(input_tokens=10, output_tokens=5))
        )
        event_callback = MagicMock()

        router = ProviderRouter.__new__(ProviderRouter)
        router._primary = primary
        router._fallbacks = [fallback]
        router._provider_entries = [
            ("anthropic/claude-opus-4-6", primary),
            ("openai/gpt-4.1", fallback),
        ]
        router._event_callback = event_callback

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        resp = await router.chat(messages)

        assert resp.content == "Fallback OK"
        assert event_callback.call_count == 2

        fallback_event_name, fallback_payload = event_callback.call_args_list[0].args
        assert fallback_event_name == "provider.fallback"
        assert fallback_payload["from"] == "anthropic/claude-opus-4-6"
        assert fallback_payload["to"] == "openai/gpt-4.1"
        assert fallback_payload["reason"] == "rate_limit"

        alert_event_name, alert_payload = event_callback.call_args_list[1].args
        assert alert_event_name == "runtime.alert"
        assert alert_payload["kind"] == "provider.fallback"
        assert alert_payload["metadata"]["reason"] == "rate_limit"

    @pytest.mark.asyncio
    async def test_all_providers_fail_raises(self):
        primary = self._mock_provider()
        primary.chat = AsyncMock(side_effect=Exception("Primary fail"))

        fallback = self._mock_provider()
        fallback.chat = AsyncMock(side_effect=Exception("Fallback fail"))

        router = ProviderRouter.__new__(ProviderRouter)
        router._primary = primary
        router._fallbacks = [fallback]

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        with pytest.raises(Exception, match="All providers failed"):
            await router.chat(messages)

    def test_count_tokens_delegates_to_primary(self):
        primary = self._mock_provider()
        router = ProviderRouter.__new__(ProviderRouter)
        router._primary = primary
        router._fallbacks = []

        info = router.get_model_info()
        assert info.model_id == "test"


class TestParseModelStringEdgeCases:
    """Phase 4: Additional parse_model_string edge cases."""

    def test_parse_gemini_bare(self):
        provider, model = parse_model_string("gemini-2.5-pro")
        assert provider == "gemini"
        assert model == "gemini-2.5-pro"

    def test_parse_deepseek_prefix(self):
        provider, model = parse_model_string("deepseek/deepseek-chat")
        assert provider == "litellm"
        assert "deepseek" in model

    def test_parse_groq_prefix(self):
        provider, model = parse_model_string("groq/llama-4-scout-17b-16e-instruct")
        assert provider == "litellm"
        assert "llama" in model

    def test_parse_vllm_prefix(self):
        provider, model = parse_model_string("vllm/meta-llama/Llama-3-8B")
        assert provider == "vllm"
        assert model == "meta-llama/Llama-3-8B"

    def test_parse_sglang_prefix(self):
        provider, model = parse_model_string("sglang/Qwen/Qwen3-8B")
        assert provider == "sglang"
        assert model == "Qwen/Qwen3-8B"

    def test_parse_codex_prefix(self):
        provider, model = parse_model_string("codex/gpt-4.1")
        assert provider == "codex"
        assert model == "gpt-4.1"

    def test_parse_gemini_prefix(self):
        provider, model = parse_model_string("gemini/gemini-2.5-pro")
        assert provider == "gemini"
        assert model == "gemini-2.5-pro"

    def test_parse_o1_model(self):
        provider, model = parse_model_string("o1")
        assert provider == "openai"
        assert model == "o1"

    def test_parse_o4_mini(self):
        provider, model = parse_model_string("o4-mini")
        assert provider == "openai"
        assert model == "o4-mini"


class TestProviderRouterCreateProvider:
    """Test _create_provider for different model strings."""

    def test_create_ollama_provider(self):
        mock_provider = MagicMock()
        mock_ollama_module = MagicMock()
        mock_ollama_module.OllamaProvider.return_value = mock_provider
        with patch.dict("sys.modules", {"ds_agent.providers.ollama": mock_ollama_module}):
            # Clear any cached import
            import importlib

            import ds_agent.providers.router as router_mod

            importlib.reload(router_mod)
            router_mod.ProviderRouter._create_provider("ollama/qwen2.5:32b", {})
            mock_ollama_module.OllamaProvider.assert_called_once_with(model="qwen2.5:32b")

    def test_create_vllm_provider(self):
        mock_provider = MagicMock()
        mock_ollama_module = MagicMock()
        mock_ollama_module.OllamaProvider.return_value = mock_provider
        mock_discovery_module = MagicMock()
        mock_discovery_module.VLLM_DEFAULT_URL = "http://127.0.0.1:8000/v1"
        mock_discovery_module.SGLANG_DEFAULT_URL = "http://127.0.0.1:30000/v1"
        with patch.dict(
            "sys.modules",
            {
                "ds_agent.providers.ollama": mock_ollama_module,
                "ds_agent.providers.local_discovery": mock_discovery_module,
            },
        ):
            import importlib

            import ds_agent.providers.router as router_mod

            importlib.reload(router_mod)
            router_mod.ProviderRouter._create_provider("vllm/meta-llama/Llama-3-8B", {})
            call_kwargs = mock_ollama_module.OllamaProvider.call_args
            assert "8000" in str(call_kwargs)

    def test_create_sglang_provider(self):
        mock_provider = MagicMock()
        mock_ollama_module = MagicMock()
        mock_ollama_module.OllamaProvider.return_value = mock_provider
        mock_discovery_module = MagicMock()
        mock_discovery_module.VLLM_DEFAULT_URL = "http://127.0.0.1:8000/v1"
        mock_discovery_module.SGLANG_DEFAULT_URL = "http://127.0.0.1:30000/v1"
        with patch.dict(
            "sys.modules",
            {
                "ds_agent.providers.ollama": mock_ollama_module,
                "ds_agent.providers.local_discovery": mock_discovery_module,
            },
        ):
            import importlib

            import ds_agent.providers.router as router_mod

            importlib.reload(router_mod)
            router_mod.ProviderRouter._create_provider("sglang/Qwen/Qwen3-8B", {})
            call_kwargs = mock_ollama_module.OllamaProvider.call_args
            assert "30000" in str(call_kwargs)

    def test_create_codex_provider(self):
        with patch("ds_agent.providers.codex_oauth.CodexOAuthProvider", create=True) as mock_cls:
            mock_cls.return_value = MagicMock()
            ProviderRouter._create_provider("codex/gpt-4.1", {})
            mock_cls.assert_called_once_with(model="gpt-4.1", token_store=None)

    def test_create_gemini_provider(self):
        with patch("ds_agent.providers.gemini_oauth.GeminiOAuthProvider", create=True) as mock_cls:
            mock_cls.return_value = MagicMock()
            ProviderRouter._create_provider("gemini/gemini-2.5-pro", {})
            mock_cls.assert_called_once()

    def test_create_anthropic_provider(self):
        with patch("ds_agent.providers.anthropic.AnthropicProvider", create=True) as mock_cls:
            mock_cls.return_value = MagicMock()
            ProviderRouter._create_provider("anthropic/claude-sonnet-4", {"anthropic": "sk-test"})
            mock_cls.assert_called_once()

    def test_create_openai_provider(self):
        with patch("ds_agent.providers.openai_provider.OpenAIProvider", create=True) as mock_cls:
            mock_cls.return_value = MagicMock()
            ProviderRouter._create_provider("openai/gpt-4.1", {"openai": "sk-test"})
            mock_cls.assert_called_once()

    def test_create_litellm_provider(self):
        with patch("ds_agent.providers.litellm_provider.LiteLLMProvider", create=True) as mock_cls:
            mock_cls.return_value = MagicMock()
            ProviderRouter._create_provider("groq/llama-3.3-70b", {})
            mock_cls.assert_called_once()


class TestProviderRouterResolveApiKey:
    def test_resolve_from_dict(self):
        key = ProviderRouter._resolve_api_key("anthropic", {"anthropic": "sk-from-dict"})
        assert key == "sk-from-dict"

    def test_resolve_from_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
        key = ProviderRouter._resolve_api_key("anthropic", {})
        assert key == "sk-from-env"

    def test_resolve_none_when_missing(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        key = ProviderRouter._resolve_api_key("anthropic", {})
        assert key is None

    def test_dict_takes_priority_over_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        key = ProviderRouter._resolve_api_key("openai", {"openai": "sk-dict"})
        assert key == "sk-dict"


class TestProviderRouterCountTokens:
    @pytest.mark.asyncio
    async def test_count_tokens_delegates(self):
        primary = AsyncMock()
        primary.count_tokens = AsyncMock(return_value=42)

        router = ProviderRouter.__new__(ProviderRouter)
        router._primary = primary
        router._fallbacks = []

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        count = await router.count_tokens(messages)
        assert count == 42
        primary.count_tokens.assert_called_once()
