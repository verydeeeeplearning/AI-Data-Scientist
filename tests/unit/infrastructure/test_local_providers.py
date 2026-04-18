"""Local LLM provider tests: Ollama, vLLM/SGLang discovery."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ds_agent.domain.interfaces.llm_provider import LLMProvider


class TestOllamaClient:
    """Test Ollama API client (server detection, model listing, pull)."""

    @pytest.mark.asyncio
    async def test_check_server_running(self):
        from ds_agent.providers.ollama import OllamaClient

        client = OllamaClient(base_url="http://127.0.0.1:11434")

        with patch("ds_agent.providers.ollama.aiohttp") as mock_aiohttp:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.text = AsyncMock(return_value="Ollama is running")
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock(return_value=None)

            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=mock_resp)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_aiohttp.ClientSession = MagicMock(return_value=mock_session)

            result = await client.is_running()
            assert result is True

    @pytest.mark.asyncio
    async def test_check_server_not_running(self):
        from ds_agent.providers.ollama import OllamaClient

        client = OllamaClient(base_url="http://127.0.0.1:11434")

        with patch("ds_agent.providers.ollama.aiohttp") as mock_aiohttp:
            mock_aiohttp.ClientSession = MagicMock(side_effect=Exception("Connection refused"))
            result = await client.is_running()
            assert result is False

    @pytest.mark.asyncio
    async def test_list_models(self):
        from ds_agent.providers.ollama import OllamaClient

        client = OllamaClient()
        mock_response = {
            "models": [
                {"name": "qwen2.5:32b", "size": 20_000_000_000},
                {"name": "llama3.3:70b", "size": 40_000_000_000},
            ]
        }

        with patch.object(client, "_get_json", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            models = await client.list_models()

            assert len(models) == 2
            assert models[0]["name"] == "qwen2.5:32b"
            assert models[1]["name"] == "llama3.3:70b"

    @pytest.mark.asyncio
    async def test_get_model_info(self):
        from ds_agent.providers.ollama import OllamaClient

        client = OllamaClient()
        mock_response = {
            "modelinfo": {"general.context_length": 32768},
            "parameters": "num_ctx 32768",
        }

        with patch.object(client, "_post_json", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            info = await client.get_model_context_length("qwen2.5:32b")
            assert info == 32768

    @pytest.mark.asyncio
    async def test_list_models_server_down(self):
        from ds_agent.providers.ollama import OllamaClient

        client = OllamaClient()
        with patch.object(
            client,
            "_get_json",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused"),
        ):
            models = await client.list_models()
            assert models == []


class TestOllamaProvider:
    def test_implements_protocol(self):
        from ds_agent.providers.ollama import OllamaProvider

        provider = OllamaProvider.__new__(OllamaProvider)
        provider._model = "qwen2.5:32b"
        provider._base_url = "http://127.0.0.1:11434"
        assert isinstance(provider, LLMProvider)

    def test_get_model_info(self):
        from ds_agent.providers.ollama import OllamaProvider

        provider = OllamaProvider.__new__(OllamaProvider)
        provider._model = "qwen2.5:32b"
        provider._base_url = "http://127.0.0.1:11434"
        provider._context_length = 32768

        info = provider.get_model_info()
        assert info.provider == "ollama"
        assert info.model_id == "qwen2.5:32b"
        assert info.max_context_tokens == 32768

    def test_init_with_openai_sdk(self):
        """Test constructor calls openai.AsyncOpenAI."""
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            from ds_agent.providers.ollama import OllamaProvider

            provider = OllamaProvider(model="qwen2.5:32b")
            assert provider._model == "qwen2.5:32b"
            assert provider._context_length == 4096
            mock_openai.AsyncOpenAI.assert_called_once()

    def test_init_custom_base_url(self):
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            from ds_agent.providers.ollama import OllamaProvider

            provider = OllamaProvider(model="llama3:8b", base_url="http://192.168.1.100:11434")
            assert provider._base_url == "http://192.168.1.100:11434"


class TestLocalDiscovery:
    """Test OpenAI-compatible local server discovery (vLLM, SGLang)."""

    @pytest.mark.asyncio
    async def test_discover_vllm_models(self):
        from ds_agent.providers.local_discovery import discover_openai_compatible_models

        mock_response = {
            "data": [
                {"id": "meta-llama/Llama-3-8B-Instruct"},
                {"id": "Qwen/Qwen2.5-32B"},
            ]
        }

        with patch(
            "ds_agent.providers.local_discovery._fetch_json",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            models = await discover_openai_compatible_models("http://127.0.0.1:8000/v1")
            assert len(models) == 2
            assert models[0] == "meta-llama/Llama-3-8B-Instruct"

    @pytest.mark.asyncio
    async def test_discover_server_down(self):
        from ds_agent.providers.local_discovery import discover_openai_compatible_models

        with patch(
            "ds_agent.providers.local_discovery._fetch_json",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused"),
        ):
            models = await discover_openai_compatible_models("http://127.0.0.1:8000/v1")
            assert models == []


class TestProviderRouterLocal:
    def test_parse_ollama_model(self):
        from ds_agent.providers.router import parse_model_string

        provider, model = parse_model_string("ollama/qwen2.5:32b")
        assert provider == "ollama"
        assert model == "qwen2.5:32b"

    def test_parse_vllm_model(self):
        from ds_agent.providers.router import parse_model_string

        provider, model = parse_model_string("vllm/meta-llama/Llama-3-8B")
        assert provider == "vllm"
        assert model == "meta-llama/Llama-3-8B"

    def test_parse_sglang_model(self):
        from ds_agent.providers.router import parse_model_string

        provider, model = parse_model_string("sglang/Qwen/Qwen3-8B")
        assert provider == "sglang"
        assert model == "Qwen/Qwen3-8B"


class TestDiscoverAllLocalServers:
    """Test discover_all_local_servers aggregation."""

    @pytest.mark.asyncio
    async def test_discover_all_no_servers(self):
        from ds_agent.providers.local_discovery import discover_all_local_servers

        with (
            patch(
                "ds_agent.providers.local_discovery.discover_openai_compatible_models",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("ds_agent.providers.ollama.OllamaClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.is_running = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            results = await discover_all_local_servers()
            assert results == {}

    @pytest.mark.asyncio
    async def test_discover_all_ollama_running(self):
        from ds_agent.providers.local_discovery import discover_all_local_servers

        with (
            patch(
                "ds_agent.providers.local_discovery.discover_openai_compatible_models",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("ds_agent.providers.ollama.OllamaClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.is_running = AsyncMock(return_value=True)
            mock_client.list_models = AsyncMock(
                return_value=[{"name": "qwen2.5:32b"}, {"name": "llama3:8b"}]
            )
            mock_client_cls.return_value = mock_client

            results = await discover_all_local_servers()
            assert "ollama" in results
            assert len(results["ollama"]) == 2

    @pytest.mark.asyncio
    async def test_discover_all_vllm_running(self):
        from ds_agent.providers.local_discovery import discover_all_local_servers

        async def mock_discover(base_url, **kwargs):
            if "8000" in base_url:
                return ["meta-llama/Llama-3-8B"]
            return []

        with (
            patch(
                "ds_agent.providers.local_discovery.discover_openai_compatible_models",
                side_effect=mock_discover,
            ),
            patch("ds_agent.providers.ollama.OllamaClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.is_running = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            results = await discover_all_local_servers()
            assert "vllm" in results
            assert results["vllm"] == ["meta-llama/Llama-3-8B"]

    @pytest.mark.asyncio
    async def test_discover_openai_compatible_empty_data(self):
        """Empty data list should return empty."""
        from ds_agent.providers.local_discovery import discover_openai_compatible_models

        with patch(
            "ds_agent.providers.local_discovery._fetch_json",
            new_callable=AsyncMock,
            return_value={"data": []},
        ):
            models = await discover_openai_compatible_models("http://127.0.0.1:8000/v1")
            assert models == []

    @pytest.mark.asyncio
    async def test_discover_openai_compatible_missing_id(self):
        """Model entries without 'id' should be skipped."""
        from ds_agent.providers.local_discovery import discover_openai_compatible_models

        with patch(
            "ds_agent.providers.local_discovery._fetch_json",
            new_callable=AsyncMock,
            return_value={"data": [{"name": "no-id-field"}, {"id": "valid-model"}]},
        ):
            models = await discover_openai_compatible_models("http://127.0.0.1:8000/v1")
            assert models == ["valid-model"]


class TestOllamaProviderChat:
    """Test OllamaProvider.chat with mocked openai client."""

    def _make_provider(self):
        from ds_agent.providers.ollama import OllamaProvider

        provider = OllamaProvider.__new__(OllamaProvider)
        provider._model = "qwen2.5:32b"
        provider._base_url = "http://127.0.0.1:11434"
        provider._context_length = 32768

        mock_client = AsyncMock()
        provider._client = mock_client
        return provider, mock_client

    @pytest.mark.asyncio
    async def test_chat_success(self):
        provider, mock_client = self._make_provider()

        # Build mock response
        message = MagicMock()
        message.content = "Ollama response"
        message.tool_calls = None
        choice = MagicMock()
        choice.message = message
        choice.finish_reason = "stop"
        usage = MagicMock()
        usage.prompt_tokens = 10
        usage.completion_tokens = 5
        usage.cache_read_input_tokens = 0
        usage.reasoning_tokens = 0
        resp = MagicMock()
        resp.choices = [choice]
        resp.usage = usage
        resp.model = "qwen2.5:32b"

        mock_client.chat.completions.create = AsyncMock(return_value=resp)

        from ds_agent.domain.entities.messages import ChatMessage, Role

        messages = [ChatMessage(role=Role.USER, content="Hello")]
        result = await provider.chat(messages)
        assert result.content == "Ollama response"

    @pytest.mark.asyncio
    async def test_chat_with_tools(self):
        provider, mock_client = self._make_provider()

        message = MagicMock()
        message.content = "OK"
        message.tool_calls = None
        choice = MagicMock()
        choice.message = message
        choice.finish_reason = "stop"
        usage = MagicMock()
        usage.prompt_tokens = 10
        usage.completion_tokens = 5
        usage.cache_read_input_tokens = 0
        usage.reasoning_tokens = 0
        resp = MagicMock()
        resp.choices = [choice]
        resp.usage = usage
        resp.model = "qwen2.5:32b"
        mock_client.chat.completions.create = AsyncMock(return_value=resp)

        from ds_agent.domain.entities.messages import ChatMessage, Role

        tools = [{"type": "function", "function": {"name": "test", "parameters": {}}}]
        messages = [ChatMessage(role=Role.USER, content="Hello")]
        await provider.chat(messages, tools=tools)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "tools" in call_kwargs

    @pytest.mark.asyncio
    async def test_count_tokens_estimation(self):
        provider, _ = self._make_provider()
        from ds_agent.domain.entities.messages import ChatMessage, Role

        messages = [ChatMessage(role=Role.USER, content="Hello world test")]
        count = await provider.count_tokens(messages)
        assert isinstance(count, int)
        assert count > 0


class TestOllamaClientPullModel:
    """Test OllamaClient.pull_model."""

    @pytest.mark.asyncio
    async def test_pull_model_success(self):
        from ds_agent.providers.ollama import OllamaClient

        client = OllamaClient()

        # Create a proper async iterator for resp.content
        lines = [b'{"status": "pulling"}\n', b'{"status": "done"}\n']

        class AsyncLineIterator:
            def __init__(self, data):
                self._data = iter(data)

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(self._data)
                except StopIteration:
                    raise StopAsyncIteration from None

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.content = AsyncLineIterator(lines)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("ds_agent.providers.ollama.aiohttp") as mock_aiohttp:
            mock_aiohttp.ClientSession = MagicMock(return_value=mock_session)
            mock_aiohttp.ClientTimeout = MagicMock()
            result = await client.pull_model("qwen2.5:32b")
            assert result is True

    @pytest.mark.asyncio
    async def test_pull_model_failure(self):
        from ds_agent.providers.ollama import OllamaClient

        client = OllamaClient()

        with patch("ds_agent.providers.ollama.aiohttp") as mock_aiohttp:
            mock_aiohttp.ClientSession = MagicMock(side_effect=Exception("Connection refused"))
            result = await client.pull_model("nonexistent-model")
            assert result is False


class TestOllamaClientContextLength:
    """Test context length detection edge cases."""

    @pytest.mark.asyncio
    async def test_context_length_fallback_on_error(self):
        from ds_agent.providers.ollama import OllamaClient

        client = OllamaClient()
        with patch.object(
            client,
            "_post_json",
            new_callable=AsyncMock,
            side_effect=Exception("Server error"),
        ):
            length = await client.get_model_context_length("model")
            assert length == 4096  # default

    @pytest.mark.asyncio
    async def test_context_length_from_parameters_string(self):
        from ds_agent.providers.ollama import OllamaClient

        client = OllamaClient()
        mock_response = {
            "modelinfo": {},  # no general.context_length
            "parameters": "stop [INST]\nnum_ctx 65536\nother param",
        }
        with patch.object(client, "_post_json", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            length = await client.get_model_context_length("model")
            assert length == 65536

    @pytest.mark.asyncio
    async def test_context_length_default_no_info(self):
        from ds_agent.providers.ollama import OllamaClient

        client = OllamaClient()
        mock_response = {
            "modelinfo": {},
            "parameters": "stop [INST]",
        }
        with patch.object(client, "_post_json", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            length = await client.get_model_context_length("model")
            assert length == 4096


class TestFetchJson:
    """Test _fetch_json with aiohttp."""

    @pytest.mark.asyncio
    async def test_fetch_json_with_aiohttp(self):
        from ds_agent.providers.local_discovery import _fetch_json

        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value={"data": [{"id": "model1"}]})
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_aiohttp = MagicMock()
        mock_aiohttp.ClientSession = MagicMock(return_value=mock_session)
        mock_aiohttp.ClientTimeout = MagicMock()

        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await _fetch_json("http://127.0.0.1:8000/v1/models")
            assert "data" in result
