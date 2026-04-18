"""OpenAI native API provider.

Supports GPT-4 series and o-series reasoning models.
"""

from __future__ import annotations

import structlog

from ds_agent.domain.entities.messages import ChatMessage, LLMResponse
from ds_agent.domain.entities.provider_models import ModelInfo, ProviderSDKConfig
from ds_agent.providers.base import messages_to_openai_format, openai_response_to_llm_response

logger = structlog.get_logger()

OPENAI_MODELS: dict[str, dict] = {
    # Current (April 2026)
    "gpt-5.4": {
        "display_name": "GPT-5.4",
        "max_context": 1_050_000,
        "max_output": 128_000,
        "vision": True,
    },
    "gpt-5.4-mini": {
        "display_name": "GPT-5.4 Mini",
        "max_context": 400_000,
        "max_output": 128_000,
        "vision": True,
    },
    "gpt-5.4-nano": {
        "display_name": "GPT-5.4 Nano",
        "max_context": 400_000,
        "max_output": 128_000,
    },
    # Still available
    "gpt-4.1": {
        "display_name": "GPT-4.1",
        "max_context": 1_048_576,
        "max_output": 32_768,
    },
    "gpt-4.1-mini": {
        "display_name": "GPT-4.1 Mini",
        "max_context": 1_048_576,
        "max_output": 32_768,
    },
    "gpt-4.1-nano": {
        "display_name": "GPT-4.1 Nano",
        "max_context": 1_048_576,
        "max_output": 32_768,
    },
    # Legacy (o-series retired Feb 2026)
    "o1": {
        "display_name": "o1 (Legacy)",
        "max_context": 200_000,
        "max_output": 100_000,
        "reasoning": True,
        "legacy": True,
    },
    "o3": {
        "display_name": "o3 (Legacy)",
        "max_context": 200_000,
        "max_output": 100_000,
        "reasoning": True,
        "legacy": True,
    },
    "o3-mini": {
        "display_name": "o3 Mini (Legacy)",
        "max_context": 200_000,
        "max_output": 100_000,
        "reasoning": True,
        "legacy": True,
    },
    "o4-mini": {
        "display_name": "o4 Mini (Legacy)",
        "max_context": 200_000,
        "max_output": 100_000,
        "reasoning": True,
        "legacy": True,
    },
    "gpt-4o": {
        "display_name": "GPT-4o (Legacy)",
        "max_context": 128_000,
        "max_output": 16_384,
        "vision": True,
        "legacy": True,
    },
}


class OpenAIProvider:
    """OpenAI native API provider."""

    def __init__(self, model: str, config: ProviderSDKConfig | None = None) -> None:
        self._model = self._normalize_model_id(model)
        self._config = config or ProviderSDKConfig()

        try:
            import openai

            self._client = openai.AsyncOpenAI(
                api_key=self._config.api_key or None,
                base_url=self._config.base_url,
                timeout=self._config.timeout,
                max_retries=self._config.max_retries,
            )
        except ImportError as e:
            raise ImportError("openai SDK is required. Install: pip install openai") from e

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        on_delta: object = None,  # streaming not supported; accepted for protocol compat
        **kwargs: object,
    ) -> LLMResponse:
        """OpenAI Chat Completions API call."""
        openai_messages = messages_to_openai_format(messages)
        is_reasoning = self._is_reasoning_model()

        call_kwargs: dict = {
            "model": self._model,
            "messages": openai_messages,
        }

        if tools:
            call_kwargs["tools"] = tools
            call_kwargs["tool_choice"] = "auto"

        if is_reasoning:
            if kwargs.get("reasoning_effort"):
                call_kwargs["reasoning_effort"] = kwargs["reasoning_effort"]
            if max_tokens:
                call_kwargs["max_completion_tokens"] = max_tokens
        else:
            call_kwargs["temperature"] = temperature
            if max_tokens:
                call_kwargs["max_tokens"] = max_tokens

        if kwargs.get("response_format") is not None:
            call_kwargs["response_format"] = kwargs["response_format"]

        raw_response = await self._client.chat.completions.create(**call_kwargs)
        response = openai_response_to_llm_response(raw_response)

        # Extract reasoning tokens for o-series
        if hasattr(raw_response.usage, "completion_tokens_details"):
            details = raw_response.usage.completion_tokens_details
            if details and hasattr(details, "reasoning_tokens"):
                response.usage.reasoning_tokens = details.reasoning_tokens or 0

        return response

    async def count_tokens(self, messages: list[ChatMessage]) -> int:
        """Token counting via tiktoken."""
        try:
            import tiktoken

            encoding = tiktoken.encoding_for_model(self._model)
            total = 0
            for msg in messages:
                total += 4  # message overhead
                total += len(encoding.encode(msg.content or ""))
                if msg.role:
                    total += len(encoding.encode(msg.role.value))
            total += 2  # reply priming
            return total
        except Exception:
            return sum(len(m.content or "") for m in messages) // 4

    def get_model_info(self) -> ModelInfo:
        meta = self._get_model_meta()
        return ModelInfo(
            model_id=self._model,
            provider="openai",
            display_name=meta.get("display_name", self._model),
            max_context_tokens=meta.get("max_context", 128_000),
            max_output_tokens=meta.get("max_output", 4_096),
            supports_tools=True,
            supports_vision=meta.get("vision", False),
        )

    def _normalize_model_id(self, model: str) -> str:
        if model.startswith("openai/"):
            return model[len("openai/") :]
        return model

    def _get_model_meta(self) -> dict:
        if self._model in OPENAI_MODELS:
            return OPENAI_MODELS[self._model]
        for key, meta in OPENAI_MODELS.items():
            if self._model.startswith(key):
                return meta
        return {}

    def _is_reasoning_model(self) -> bool:
        return bool(self._get_model_meta().get("reasoning", False))
