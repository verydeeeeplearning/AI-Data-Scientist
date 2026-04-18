"""LiteLLM provider — universal gateway for non-native providers.

Handles Chinese models (DeepSeek, MiniMax, Qwen, GLM, Kimi),
Groq, Together AI, OpenRouter, and any other LiteLLM-supported provider.
"""

from __future__ import annotations

import os

import structlog

from ds_agent.domain.entities.messages import ChatMessage, LLMResponse
from ds_agent.domain.entities.provider_models import ModelInfo, ProviderSDKConfig
from ds_agent.providers.base import messages_to_openai_format, openai_response_to_llm_response

logger = structlog.get_logger()

# Known models routed through LiteLLM — metadata for model info & UI catalog
LITELLM_MODELS: dict[str, dict] = {
    # DeepSeek
    "deepseek/deepseek-chat": {
        "display_name": "DeepSeek V3.2",
        "provider": "deepseek",
        "max_context": 128_000,
        "max_output": 8_192,
        "auth_type": "api_key",
    },
    "deepseek/deepseek-reasoner": {
        "display_name": "DeepSeek R1",
        "provider": "deepseek",
        "max_context": 128_000,
        "max_output": 8_192,
        "reasoning": True,
        "auth_type": "api_key",
    },
    # MiniMax
    "minimax/MiniMax-M2.5": {
        "display_name": "MiniMax M2.5",
        "provider": "minimax",
        "max_context": 200_000,
        "max_output": 8_192,
        "auth_type": "api_key",
    },
    # Qwen (Alibaba)
    "qwen/qwen3.6-plus-preview": {
        "display_name": "Qwen 3.6 Plus (Preview)",
        "provider": "qwen",
        "max_context": 1_000_000,
        "max_output": 32_768,
        "auth_type": "free_api_key",
    },
    "qwen/qwen3.5-plus": {
        "display_name": "Qwen 3.5 Plus",
        "provider": "qwen",
        "max_context": 1_000_000,
        "max_output": 32_768,
        "auth_type": "api_key",
    },
    # Zhipu / GLM
    "zhipu/glm-5": {
        "display_name": "GLM-5",
        "provider": "zhipu",
        "max_context": 200_000,
        "max_output": 8_192,
        "auth_type": "api_key",
    },
    # Moonshot / Kimi
    "moonshot/kimi-k2.5": {
        "display_name": "Kimi K2.5",
        "provider": "moonshot",
        "max_context": 256_000,
        "max_output": 8_192,
        "auth_type": "api_key",
    },
    # Groq (fast inference)
    "groq/llama-4-scout-17b-16e-instruct": {
        "display_name": "Llama 4 Scout (Groq)",
        "provider": "groq",
        "max_context": 131_072,
        "max_output": 8_192,
        "auth_type": "free_api_key",
    },
    "groq/qwen3-32b": {
        "display_name": "Qwen 3 32B (Groq)",
        "provider": "groq",
        "max_context": 131_072,
        "max_output": 8_192,
        "auth_type": "free_api_key",
    },
    "groq/llama-3.3-70b-versatile": {
        "display_name": "Llama 3.3 70B (Groq)",
        "provider": "groq",
        "max_context": 131_072,
        "max_output": 32_768,
        "auth_type": "free_api_key",
    },
}

# Map provider name in model string to environment variable prefix
_ENV_KEY_MAP: dict[str, str] = {
    "deepseek": "DEEPSEEK_API_KEY",
    "minimax": "MINIMAX_API_KEY",
    "qwen": "QWEN_API_KEY",
    "zhipu": "ZHIPU_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
    "groq": "GROQ_API_KEY",
}


class LiteLLMProvider:
    """Universal provider via LiteLLM — routes to any OpenAI-compatible API."""

    def __init__(self, model: str, config: ProviderSDKConfig | None = None) -> None:
        self._model = model
        self._config = config or ProviderSDKConfig()

        # Resolve API key: explicit config > environment variable
        self._api_key = self._config.api_key
        if not self._api_key:
            provider_prefix = model.split("/")[0] if "/" in model else ""
            env_var = _ENV_KEY_MAP.get(provider_prefix, f"{provider_prefix.upper()}_API_KEY")
            self._api_key = os.environ.get(env_var)

        try:
            import litellm

            self._litellm = litellm
        except ImportError as e:
            raise ImportError(
                "litellm SDK is required for this provider. "
                "Install: pip install 'ds-agent[litellm]'"
            ) from e

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        on_delta: object = None,  # streaming not supported; accepted for protocol compat
        **kwargs: object,
    ) -> LLMResponse:
        """Route chat through LiteLLM."""
        openai_messages = messages_to_openai_format(messages)

        call_kwargs: dict = {
            "model": self._model,
            "messages": openai_messages,
            "temperature": temperature,
        }
        if self._api_key:
            call_kwargs["api_key"] = self._api_key
        if tools:
            call_kwargs["tools"] = tools
            call_kwargs["tool_choice"] = "auto"
        if max_tokens:
            call_kwargs["max_tokens"] = max_tokens

        try:
            raw_response = await self._litellm.acompletion(**call_kwargs)
            return openai_response_to_llm_response(raw_response)
        except Exception:
            # 3.7 fix: re-raise so the router fallback chain can try the next provider
            logger.error("litellm_error", model=self._model, exc_info=True)
            raise

    async def count_tokens(self, messages: list[ChatMessage]) -> int:
        """Token counting via LiteLLM or fallback."""
        try:
            text = "\n".join(m.content or "" for m in messages)
            return int(self._litellm.token_counter(model=self._model, text=text))
        except Exception:
            return sum(len(m.content or "") for m in messages) // 4

    def get_model_info(self) -> ModelInfo:
        """Return model metadata from LITELLM_MODELS catalog."""
        meta = LITELLM_MODELS.get(self._model, {})
        return ModelInfo(
            model_id=self._model,
            provider=meta.get("provider", "litellm"),
            display_name=meta.get("display_name", self._model),
            max_context_tokens=meta.get("max_context", 128_000),
            max_output_tokens=meta.get("max_output", 4_096),
            supports_tools=True,
            supports_vision=meta.get("vision", False),
        )
