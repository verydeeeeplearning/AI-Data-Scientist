"""Google Gemini provider — thin OAuth/API-key aware adapter over LiteLLM.

LiteLLM already implements Gemini function calling and multi-turn tool_result
handling. This provider resolves credentials (explicit API key → env var →
OAuth token from ``AuthProfileStore``) and delegates chat() to
``LiteLLMProvider``. Only model metadata / token counting live here.

Credential precedence:
  1. ``api_key`` constructor arg (AI Studio key)
  2. ``GEMINI_API_KEY`` env var
  3. ``access_token`` constructor arg
  4. OAuth access token from the ``token_store`` (provider="gemini")
"""

from __future__ import annotations

import os

import structlog

from ds_agent.domain.entities.messages import ChatMessage, LLMResponse
from ds_agent.domain.entities.provider_models import ModelInfo, ProviderSDKConfig

logger = structlog.get_logger()

GEMINI_MODELS: dict[str, dict] = {
    # Gemini 3 — preview family
    "gemini-3-pro-preview": {
        "display_name": "Gemini 3 Pro (Preview)",
        "max_context": 1_048_576,
        "max_output": 65_536,
    },
    "gemini-3-flash-preview": {
        "display_name": "Gemini 3 Flash (Preview)",
        "max_context": 1_048_576,
        "max_output": 65_536,
    },
    "gemini-3.1-pro-preview": {
        "display_name": "Gemini 3.1 Pro (Preview)",
        "max_context": 1_048_576,
        "max_output": 65_536,
    },
    "gemini-3.1-flash-lite-preview": {
        "display_name": "Gemini 3.1 Flash-Lite (Preview)",
        "max_context": 1_048_576,
        "max_output": 65_536,
    },
    # Stable GA
    "gemini-2.5-pro": {
        "display_name": "Gemini 2.5 Pro",
        "max_context": 1_048_576,
        "max_output": 65_536,
    },
    "gemini-2.5-flash": {
        "display_name": "Gemini 2.5 Flash",
        "max_context": 1_048_576,
        "max_output": 65_536,
    },
    "gemini-2.5-flash-lite": {
        "display_name": "Gemini 2.5 Flash-Lite",
        "max_context": 1_048_576,
        "max_output": 65_536,
    },
}


def _resolve_gemini_key(
    api_key: str | None,
    access_token: str | None,
    token_store: object | None,
) -> str | None:
    """Return the API key/token to hand to LiteLLM (or None if unavailable)."""
    if api_key:
        return api_key
    env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if env_key:
        return env_key
    if access_token:
        return access_token
    if token_store is not None:
        try:
            profile = token_store.load_by_provider("gemini")  # type: ignore[union-attr,attr-defined]
        except Exception:
            profile = None
        if profile and getattr(profile, "oauth", None):
            return getattr(profile.oauth, "access", None)
    return None


class GeminiOAuthProvider:
    """Gemini provider with auto-detected transport.

    Two delivery paths are supported; the router picks one automatically:

    1. **CLI subprocess** (true OAuth via user's subscription) — chosen when
       ``~/.gemini/oauth_creds.json`` exists AND no explicit API key was
       supplied. Delegates to ``GeminiCliProvider``. This is the path that
       mirrors OpenClaw's 3-way classification and consumes the user's
       Gemini subscription quota.
    2. **LiteLLM HTTP** (API-key against generativelanguage.googleapis.com) —
       chosen when an API key is available (arg / env / token_store). This
       is the pay-per-call path, unrelated to any consumer subscription.

    Constructor shape preserved so existing callsites (ProviderRouter etc.)
    do not need to change.
    """

    def __init__(
        self,
        model: str = "gemini-2.5-pro",
        access_token: str | None = None,
        api_key: str | None = None,
        token_store: object | None = None,
        *,
        force_transport: str | None = None,
    ) -> None:
        self._model = model
        resolved_key = _resolve_gemini_key(api_key, access_token, token_store)
        transport = force_transport or self._pick_transport(resolved_key)

        if transport == "cli":
            from ds_agent.providers.gemini_cli import GeminiCliProvider

            self._transport = "cli"
            self._delegate = GeminiCliProvider(model=model)
            self._api_key = None
            return

        from ds_agent.providers.litellm_provider import LiteLLMProvider

        self._transport = "litellm"
        self._api_key = resolved_key
        litellm_model = model if model.startswith("gemini/") else f"gemini/{model}"
        self._delegate = LiteLLMProvider(
            litellm_model,
            ProviderSDKConfig(api_key=resolved_key or ""),
        )

    @staticmethod
    def _pick_transport(resolved_key: str | None) -> str:
        """Prefer CLI when OAuth creds exist and no explicit API key was set."""
        from ds_agent.providers.gemini_cli import (
            gemini_cli_available,
            gemini_oauth_creds_present,
        )

        if resolved_key:
            return "litellm"
        if gemini_cli_available() and gemini_oauth_creds_present():
            return "cli"
        return "litellm"

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        on_delta: object = None,
        **kwargs: object,
    ) -> LLMResponse:
        response = await self._delegate.chat(
            messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            on_delta=on_delta,
            **kwargs,
        )
        # Preserve caller expectation: model id reported without the
        # ``gemini/`` LiteLLM prefix.
        response.model = self._model
        return response

    async def count_tokens(self, messages: list[ChatMessage]) -> int:
        return await self._delegate.count_tokens(messages)

    def get_model_info(self) -> ModelInfo:
        meta = GEMINI_MODELS.get(self._model, {})
        return ModelInfo(
            model_id=self._model,
            provider="google-gemini",
            display_name=meta.get("display_name", self._model),
            max_context_tokens=meta.get("max_context", 1_048_576),
            max_output_tokens=meta.get("max_output", 65_536),
            supports_tools=True,
            supports_vision=True,
        )
