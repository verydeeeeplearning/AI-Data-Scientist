"""Provider router with smart model string parsing and fallback chain."""

from __future__ import annotations

import os
import time
from collections.abc import Awaitable, Callable

import structlog

from ds_agent.domain.entities.messages import ChatMessage, LLMResponse
from ds_agent.domain.entities.provider_models import ModelInfo, ProviderSDKConfig
from ds_agent.domain.interfaces.llm_provider import LLMProvider

logger = structlog.get_logger()

ANTHROPIC_PREFIXES = ("claude-",)
OPENAI_PREFIXES = ("gpt-", "o1", "o3", "o4")
KNOWN_PROVIDER_PREFIXES = ("anthropic/", "openai/")


def parse_model_string(model: str) -> tuple[str, str]:
    """Parse model string into (provider_type, model_id)."""
    if model.startswith("ollama/"):
        return "ollama", model[len("ollama/") :]
    if model.startswith("vllm/"):
        return "vllm", model[len("vllm/") :]
    if model.startswith("sglang/"):
        return "sglang", model[len("sglang/") :]

    if model.startswith("codex/"):
        return "codex", model[len("codex/") :]
    if model.startswith("gemini/"):
        return "gemini", model[len("gemini/") :]

    if model.startswith("anthropic/"):
        return "anthropic", model[len("anthropic/") :]
    if model.startswith("openai/"):
        return "openai", model[len("openai/") :]

    if model.startswith("gemini-"):
        return "gemini", model
    for prefix in ANTHROPIC_PREFIXES:
        if model.startswith(prefix):
            return "anthropic", model
    for prefix in OPENAI_PREFIXES:
        if model.startswith(prefix):
            return "openai", model

    return "litellm", model


class ProviderRouter:
    """Smart provider routing with fallback chain."""

    def __init__(
        self,
        model: str,
        api_keys: dict[str, str] | None = None,
        fallback_models: list[str] | None = None,
        token_store: object | None = None,
        api_key_resolver: Callable[[str], str | None] | None = None,
        event_callback: Callable[[str, dict], None] | None = None,
    ) -> None:
        self._model = model
        self._api_keys = api_keys or {}
        self._token_store = token_store
        self._event_callback = event_callback
        self._api_key_resolver = api_key_resolver or (
            lambda provider_type: self._resolve_api_key(provider_type, self._api_keys)
        )

        model_chain = [model, *(fallback_models or [])]
        self._provider_entries = [
            (
                model_name,
                self._create_provider(
                    model_name,
                    token_store=token_store,
                    api_key_resolver=self._api_key_resolver,
                ),
            )
            for model_name in model_chain
        ]
        self._primary = self._provider_entries[0][1]
        self._fallbacks = [provider for _model_name, provider in self._provider_entries[1:]]

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        """Route chat to primary, falling back on provider failure."""
        errors: list[tuple[str, Exception]] = []

        for idx, (model_name, provider) in enumerate(self._iter_provider_entries()):
            try:
                response = await provider.chat(
                    messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    on_delta=on_delta,
                    **kwargs,
                )
                if idx > 0 and errors:
                    self._emit_fallback_event(
                        from_model=errors[-1][0],
                        to_model=model_name,
                        failed_models=[failed_model for failed_model, _exc in errors],
                        cause=errors[-1][1],
                    )
                return response
            except Exception as exc:
                logger.warning("provider_failed", model=model_name, error=str(exc))
                errors.append((model_name, exc))

        raise Exception(f"All providers failed: {[str(error) for _model, error in errors]}")

    async def count_tokens(self, messages: list[ChatMessage]) -> int:
        """Delegate to primary provider."""
        return await self._primary.count_tokens(messages)

    def get_model_info(self) -> ModelInfo:
        """Delegate to primary provider."""
        return self._primary.get_model_info()

    def _iter_provider_entries(self) -> list[tuple[str, LLMProvider]]:
        provider_entries = getattr(self, "_provider_entries", None)
        if provider_entries is not None:
            return list(provider_entries)
        return [
            ("primary", self._primary),
            *[
                (f"fallback_{index}", provider)
                for index, provider in enumerate(self._fallbacks, start=1)
            ],
        ]

    def _emit_fallback_event(
        self,
        *,
        from_model: str,
        to_model: str,
        failed_models: list[str],
        cause: Exception,
    ) -> None:
        emit_event = getattr(self, "_event_callback", None)
        if not callable(emit_event):
            return

        reason = self._classify_failure(cause)
        occurred_at = int(time.time() * 1000)
        fallback_payload = {
            "from": from_model,
            "to": to_model,
            "reason": reason,
            "failedModels": failed_models,
            "message": (
                f"Switched from {from_model} to {to_model} "
                f"after a {reason.replace('_', ' ')} failure."
            ),
            "occurredAt": occurred_at,
        }

        emit_event("provider.fallback", fallback_payload)
        emit_event(
            "runtime.alert",
            {
                "eventId": f"provider-fallback-{occurred_at}-{to_model}",
                "category": "health",
                "kind": "provider.fallback",
                "severity": "info",
                "message": fallback_payload["message"],
                "source": "provider_router",
                "metadata": fallback_payload,
                "createdAt": occurred_at / 1000,
            },
        )

    @staticmethod
    def _classify_failure(exc: Exception) -> str:
        message = str(exc).lower()
        if "rate limit" in message or "rate_limited" in message or "429" in message:
            return "rate_limit"
        if "timeout" in message:
            return "timeout"
        if (
            "unauthorized" in message
            or "forbidden" in message
            or "authentication" in message
            or "api key" in message
            or "auth" in message
        ):
            return "auth"
        return "provider_error"

    @staticmethod
    def _resolve_api_key(provider_type: str, api_keys: dict[str, str]) -> str | None:
        """Resolve API key from a config dict or environment variable."""
        key = api_keys.get(provider_type)
        if key:
            return key
        return os.environ.get(f"{provider_type.upper()}_API_KEY")

    @staticmethod
    def _create_provider(
        model: str,
        api_keys: dict[str, str] | None = None,
        token_store: object | None = None,
        api_key_resolver: Callable[[str], str | None] | None = None,
    ) -> LLMProvider:
        """Create a provider instance based on the model string."""
        provider_type, model_id = parse_model_string(model)
        resolved_api_keys = api_keys or {}
        resolve_key = api_key_resolver or (
            lambda name: ProviderRouter._resolve_api_key(name, resolved_api_keys)
        )

        if provider_type == "ollama":
            from ds_agent.providers.ollama import OllamaProvider

            return OllamaProvider(model=model_id)

        if provider_type in ("vllm", "sglang"):
            from ds_agent.providers.local_discovery import (
                SGLANG_DEFAULT_URL,
                VLLM_DEFAULT_URL,
            )
            from ds_agent.providers.ollama import OllamaProvider

            base_url = VLLM_DEFAULT_URL if provider_type == "vllm" else SGLANG_DEFAULT_URL
            return OllamaProvider(model=model_id, base_url=base_url)

        if provider_type == "codex":
            from ds_agent.providers.codex_oauth import CodexOAuthProvider

            return CodexOAuthProvider(model=model_id, token_store=token_store)

        if provider_type == "gemini":
            from ds_agent.providers.gemini_oauth import GeminiOAuthProvider

            return GeminiOAuthProvider(
                model=model_id,
                api_key=resolve_key("gemini"),
                token_store=token_store,
            )

        config = ProviderSDKConfig(api_key=resolve_key(provider_type))

        if provider_type == "anthropic":
            from ds_agent.providers.anthropic import AnthropicProvider

            return AnthropicProvider(model_id, config)

        if provider_type == "openai":
            from ds_agent.providers.openai_provider import OpenAIProvider

            return OpenAIProvider(model_id, config)

        from ds_agent.providers.litellm_provider import LiteLLMProvider

        return LiteLLMProvider(model, config)
