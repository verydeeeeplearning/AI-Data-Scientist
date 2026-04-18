"""Ollama native provider — local LLM serving.

Auto-detects running Ollama server, lists available models,
pulls models on demand, and queries context window sizes.
"""

from __future__ import annotations

import structlog

from ds_agent.domain.entities.messages import ChatMessage, LLMResponse
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.providers.base import messages_to_openai_format, openai_response_to_llm_response

logger = structlog.get_logger()

try:
    import aiohttp
except ImportError:
    aiohttp = None  # type: ignore[assignment]

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


class OllamaClient:
    """Low-level Ollama API client."""

    def __init__(self, base_url: str = DEFAULT_OLLAMA_URL) -> None:
        self._base_url = base_url.rstrip("/")

    async def is_running(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(self._base_url, timeout=aiohttp.ClientTimeout(total=3)) as resp,
            ):
                return resp.status == 200
        except Exception:
            return False

    async def list_models(self) -> list[dict]:
        """List locally available models via /api/tags."""
        try:
            data = await self._get_json("/api/tags")
            return list(data.get("models", []))
        except Exception as e:
            logger.debug("ollama_list_error", error=str(e))
            return []

    async def get_model_context_length(self, model: str) -> int:
        """Query model's context window via /api/show."""
        try:
            data = await self._post_json("/api/show", {"name": model})
            # Try modelinfo.general.context_length first
            model_info = data.get("modelinfo", {})
            ctx = model_info.get("general.context_length")
            if ctx:
                return int(ctx)
            # Fallback: parse parameters string
            params = data.get("parameters", "")
            for line in params.split("\n"):
                if "num_ctx" in line:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        return int(parts[-1])
            return 4096  # default
        except Exception as e:
            logger.debug("ollama_show_error", model=model, error=str(e))
            return 4096

    async def pull_model(
        self,
        model: str,
        on_progress: object | None = None,
    ) -> bool:
        """Pull a model via /api/pull. Returns True on success."""
        import json

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    f"{self._base_url}/api/pull",
                    json={"name": model},
                    timeout=aiohttp.ClientTimeout(total=3600),
                ) as resp,
            ):
                async for line in resp.content:
                    line_str = line.decode("utf-8").strip()
                    if not line_str:
                        continue
                    try:
                        status = json.loads(line_str)
                        if on_progress and callable(on_progress):
                            on_progress(status.get("status", ""))
                    except json.JSONDecodeError:
                        pass
                return resp.status == 200
        except Exception as e:
            logger.error("ollama_pull_error", model=model, error=str(e))
            return False

    async def _get_json(self, path: str) -> dict:
        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{self._base_url}{path}",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp,
        ):
            return dict(await resp.json())

    async def _post_json(self, path: str, data: dict) -> dict:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self._base_url}{path}",
                json=data,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp,
        ):
            return dict(await resp.json())


class OllamaProvider:
    """Ollama LLM provider using OpenAI-compatible API.

    Uses Ollama's /v1/chat/completions endpoint (OpenAI compatible).
    """

    def __init__(
        self,
        model: str = "qwen2.5:32b",
        base_url: str = DEFAULT_OLLAMA_URL,
    ) -> None:
        self._model = model
        self._base_url = base_url
        self._context_length = 4096  # updated on first call

        try:
            import openai

            self._client = openai.AsyncOpenAI(
                api_key="ollama",  # Ollama doesn't need real key
                base_url=f"{base_url}/v1",
            )
        except ImportError as e:
            raise ImportError("openai SDK required: pip install openai") from e

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        on_delta: object = None,  # streaming not supported; accepted for protocol compat
        **kwargs: object,
    ) -> LLMResponse:
        openai_messages = messages_to_openai_format(messages)

        call_kwargs: dict = {
            "model": self._model,
            "messages": openai_messages,
            "temperature": temperature,
        }
        if tools:
            call_kwargs["tools"] = tools
            call_kwargs["tool_choice"] = "auto"
        if max_tokens:
            call_kwargs["max_tokens"] = max_tokens

        raw = await self._client.chat.completions.create(**call_kwargs)
        return openai_response_to_llm_response(raw)

    async def count_tokens(self, messages: list[ChatMessage]) -> int:
        return sum(len(m.content or "") for m in messages) // 4

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            model_id=self._model,
            provider="ollama",
            display_name=self._model,
            max_context_tokens=self._context_length,
            max_output_tokens=self._context_length // 2,
            supports_tools=True,
        )
