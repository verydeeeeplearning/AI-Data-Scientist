"""OAuth provider tests: Codex CLI auth + Gemini OAuth."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from ds_agent.domain.entities.messages import ChatMessage, LLMResponse, Role, Usage
from ds_agent.domain.interfaces.llm_provider import LLMProvider


class TestCodexAuthReader:
    """Test reading credentials from ~/.codex/auth.json."""

    def test_read_valid_codex_auth(self, tmp_path):
        from ds_agent.providers.codex_oauth import read_codex_credentials

        auth_file = tmp_path / ".codex" / "auth.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text(
            json.dumps(
                {
                    "auth_mode": "chatgpt",
                    "tokens": {
                        "access_token": "fake-access-token",
                        "refresh_token": "fake-refresh-token",
                        "account_id": "user-123",
                    },
                }
            )
        )

        creds = read_codex_credentials(codex_home=str(tmp_path / ".codex"))
        assert creds is not None
        assert creds["access_token"] == "fake-access-token"
        assert creds["refresh_token"] == "fake-refresh-token"

    def test_read_missing_file(self, tmp_path):
        from ds_agent.providers.codex_oauth import read_codex_credentials

        creds = read_codex_credentials(codex_home=str(tmp_path / ".codex"))
        assert creds is None

    def test_read_api_key_mode_ignored(self, tmp_path):
        from ds_agent.providers.codex_oauth import read_codex_credentials

        auth_file = tmp_path / ".codex" / "auth.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text(
            json.dumps(
                {
                    "auth_mode": "api-key",
                    "api_key": "sk-...",
                }
            )
        )

        creds = read_codex_credentials(codex_home=str(tmp_path / ".codex"))
        assert creds is None  # Only chatgpt mode


class TestCodexOAuthProvider:
    """Test CodexOAuthProvider with mocked HTTP calls."""

    def _make_provider(self, access_token="fake-token"):
        from ds_agent.providers.codex_oauth import CodexOAuthProvider

        provider = CodexOAuthProvider.__new__(CodexOAuthProvider)
        provider._access_token = access_token
        provider._model = "gpt-4.1"
        return provider

    def test_implements_protocol(self):
        provider = self._make_provider()
        assert isinstance(provider, LLMProvider)

    def test_get_model_info(self):
        provider = self._make_provider()
        info = provider.get_model_info()
        assert info.provider == "openai-codex"
        assert info.model_id == "gpt-4.1"


class TestGeminiOAuthProvider:
    """Test GeminiOAuthProvider — LiteLLM delegation adapter."""

    def _make_provider(self, api_key="fake-api-key"):
        from ds_agent.providers.gemini_oauth import GeminiOAuthProvider

        return GeminiOAuthProvider(model="gemini-2.5-pro", api_key=api_key)

    def test_implements_protocol(self):
        provider = self._make_provider()
        assert isinstance(provider, LLMProvider)

    def test_get_model_info(self):
        provider = self._make_provider()
        info = provider.get_model_info()
        assert info.provider == "google-gemini"
        assert info.model_id == "gemini-2.5-pro"
        assert info.supports_tools is True

    def test_delegate_is_litellm(self):
        from ds_agent.providers.litellm_provider import LiteLLMProvider

        provider = self._make_provider()
        assert isinstance(provider._delegate, LiteLLMProvider)

    def test_litellm_model_prefix(self):
        """Delegate must use ``gemini/<model>`` for LiteLLM routing."""
        provider = self._make_provider()
        assert provider._delegate._model == "gemini/gemini-2.5-pro"

    def test_env_var_fallback(self, monkeypatch):
        from ds_agent.providers.gemini_oauth import GeminiOAuthProvider

        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "env-gemini-key")
        provider = GeminiOAuthProvider(model="gemini-2.5-pro")
        assert provider._api_key == "env-gemini-key"

    def test_oauth_token_store_fallback(self, monkeypatch):
        from ds_agent.providers.gemini_oauth import GeminiOAuthProvider

        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        fake_profile = SimpleNamespace(oauth=SimpleNamespace(access="oauth-access-xyz"))
        token_store = SimpleNamespace(
            load_by_provider=lambda _p: fake_profile,
        )
        provider = GeminiOAuthProvider(model="gemini-2.5-pro", token_store=token_store)
        assert provider._api_key == "oauth-access-xyz"


class TestCodexAuthEdgeCases:
    """Phase 4: Codex credential edge cases."""

    def test_read_invalid_json(self, tmp_path):
        from ds_agent.providers.codex_oauth import read_codex_credentials

        auth_file = tmp_path / ".codex" / "auth.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text("{invalid json!!!")

        creds = read_codex_credentials(codex_home=str(tmp_path / ".codex"))
        assert creds is None

    def test_read_no_tokens_key(self, tmp_path):
        from ds_agent.providers.codex_oauth import read_codex_credentials

        auth_file = tmp_path / ".codex" / "auth.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text(json.dumps({"auth_mode": "chatgpt"}))

        creds = read_codex_credentials(codex_home=str(tmp_path / ".codex"))
        assert creds is None


class TestGeminiProviderEdgeCases:
    """Phase 4: Gemini provider edge cases."""

    def test_gemini_count_tokens_estimation(self):
        from ds_agent.providers.gemini_oauth import GeminiOAuthProvider

        provider = GeminiOAuthProvider(model="gemini-2.5-pro", api_key="x")
        messages = [ChatMessage(role=Role.USER, content="Hello world test")]
        import asyncio

        count = asyncio.run(provider.count_tokens(messages))
        assert isinstance(count, int)
        assert count > 0

    def test_gemini_get_model_info_metadata(self):
        from ds_agent.providers.gemini_oauth import GeminiOAuthProvider

        provider = GeminiOAuthProvider(model="gemini-2.5-pro", api_key="x")
        info = provider.get_model_info()
        assert info.provider == "google-gemini"
        assert info.max_context_tokens > 0


class TestProviderRouterOAuth:
    """Test ProviderRouter recognizes OAuth providers."""

    def test_parse_codex_model(self):
        from ds_agent.providers.router import parse_model_string

        provider, model = parse_model_string("codex/gpt-4.1")
        assert provider == "codex"
        assert model == "gpt-4.1"

    def test_parse_gemini_model(self):
        from ds_agent.providers.router import parse_model_string

        provider, model = parse_model_string("gemini/gemini-2.5-pro")
        assert provider == "gemini"
        assert model == "gemini-2.5-pro"


class TestCodexOAuthChat:
    """Test CodexOAuthProvider.chat with mocked curl SSE."""

    def _make_provider(self):
        from ds_agent.providers.codex_oauth import CodexOAuthProvider

        provider = CodexOAuthProvider.__new__(CodexOAuthProvider)
        provider._access_token = "fake-token"
        provider._account_id = "fake-account"
        provider._model = "gpt-4.1"
        provider._token_store = None
        return provider

    @pytest.mark.asyncio
    async def test_chat_success(self):
        provider = self._make_provider()

        sse_events = [
            {
                "type": "response.output_text.delta",
                "delta": "CodexResult",
            },
            {
                "type": "response.completed",
                "response": {
                    "model": "gpt-4.1",
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [
                                {"type": "output_text", "text": "CodexResult"},
                            ],
                        }
                    ],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            },
        ]

        with patch.object(
            provider, "_curl_sse", new=AsyncMock(return_value=sse_events)
        ) as mock_curl:
            messages = [ChatMessage(role=Role.USER, content="Hello")]
            result = await provider.chat(messages)

        assert result.content == "CodexResult"
        assert result.usage.input_tokens == 10
        assert result.usage.output_tokens == 5

        url, body = mock_curl.call_args[0]
        assert url == "https://chatgpt.com/backend-api/wham/responses"
        assert body["stream"] is True
        assert body["store"] is False
        assert body["input"] == [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Hello"}],
            }
        ]

    @pytest.mark.asyncio
    async def test_chat_with_tools(self):
        provider = self._make_provider()

        sse_events = [
            {
                "type": "response.completed",
                "response": {
                    "model": "gpt-4.1",
                    "output": [],
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            },
        ]

        with patch.object(
            provider, "_curl_sse", new=AsyncMock(return_value=sse_events)
        ) as mock_curl:
            tools = [{"type": "function", "function": {"name": "test", "parameters": {}}}]
            messages = [ChatMessage(role=Role.USER, content="Hello")]
            await provider.chat(messages, tools=tools)

        _url, body = mock_curl.call_args[0]
        assert "tools" in body
        assert body["tool_choice"] == "auto"

    @pytest.mark.asyncio
    async def test_count_tokens(self):
        provider = self._make_provider()
        messages = [ChatMessage(role=Role.USER, content="Hello world test")]
        count = await provider.count_tokens(messages)
        assert isinstance(count, int)
        assert count > 0

    def test_get_model_info_unknown(self):
        from ds_agent.providers.codex_oauth import CodexOAuthProvider

        provider = CodexOAuthProvider.__new__(CodexOAuthProvider)
        provider._model = "future-model"
        info = provider.get_model_info()
        assert info.provider == "openai-codex"
        assert info.max_context_tokens == 128_000  # default

    def test_init_with_access_token(self, tmp_path):
        """Provider initialized with explicit access_token should not read files."""
        from ds_agent.providers.codex_oauth import CodexOAuthProvider

        # Use tmp_path as codex_home so no real credentials leak into the test.
        provider = CodexOAuthProvider(
            model="gpt-4.1",
            access_token="test-token",
            codex_home=str(tmp_path / "nonexistent"),
        )
        assert provider._access_token == "test-token"
        # curl-based implementation: no OpenAI client to inspect.
        assert provider._account_id == ""

    def test_init_without_creds_raises(self, tmp_path):
        """Missing creds should raise RuntimeError."""
        from ds_agent.providers.codex_oauth import CodexOAuthProvider

        with pytest.raises(RuntimeError, match="Codex CLI credentials not found"):
            CodexOAuthProvider(model="gpt-4.1", codex_home=str(tmp_path / "nonexistent"))


class TestGeminiOAuthChat:
    """GeminiOAuthProvider.chat delegates to LiteLLM."""

    @pytest.mark.asyncio
    async def test_chat_delegates_to_litellm(self):
        from ds_agent.providers.gemini_oauth import GeminiOAuthProvider

        provider = GeminiOAuthProvider(model="gemini-2.5-pro", api_key="test-key")

        mock_response = LLMResponse(
            content="Gemini via LiteLLM",
            usage=Usage(input_tokens=10, output_tokens=5),
            model="gemini/gemini-2.5-pro",
        )
        provider._delegate.chat = AsyncMock(return_value=mock_response)

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        tools = [{"type": "function", "function": {"name": "x", "parameters": {}}}]
        result = await provider.chat(messages, tools=tools, temperature=0.2)

        provider._delegate.chat.assert_awaited_once()
        call_kwargs = provider._delegate.chat.await_args.kwargs
        assert call_kwargs["tools"] == tools
        assert call_kwargs["temperature"] == 0.2
        # Response is returned; model name stripped back to public form
        assert result.content == "Gemini via LiteLLM"
        assert result.model == "gemini-2.5-pro"

    @pytest.mark.asyncio
    async def test_chat_propagates_errors(self):
        from ds_agent.providers.gemini_oauth import GeminiOAuthProvider

        provider = GeminiOAuthProvider(model="gemini-2.5-pro", api_key="test-key")
        provider._delegate.chat = AsyncMock(side_effect=RuntimeError("quota"))

        with pytest.raises(RuntimeError, match="quota"):
            await provider.chat([ChatMessage(role=Role.USER, content="x")])

    def test_get_model_info_unknown_model(self):
        from ds_agent.providers.gemini_oauth import GeminiOAuthProvider

        provider = GeminiOAuthProvider(model="gemini-future-model", api_key="x")
        info = provider.get_model_info()
        assert info.provider == "google-gemini"
        assert info.max_context_tokens == 1_048_576  # default


class TestCodexOAuthInitEdgeCases:
    def test_init_reads_from_file(self, tmp_path):
        """Should read creds from codex_home if no access_token provided."""
        import json as _json

        from ds_agent.providers.codex_oauth import CodexOAuthProvider

        auth_file = tmp_path / "auth.json"
        auth_file.write_text(
            _json.dumps(
                {
                    "auth_mode": "chatgpt",
                    "tokens": {
                        "access_token": "file-token",
                        "refresh_token": "refresh",
                        "account_id": "file-account",
                    },
                }
            )
        )

        provider = CodexOAuthProvider(model="gpt-4.1", codex_home=str(tmp_path))
        assert provider._access_token == "file-token"
        # curl-based implementation reads account_id from the credential file
        # and keeps it for the ChatGPT-Account-Id header.
        assert provider._account_id == "file-account"
