"""Shared provider/auth factory for Electron, Telegram, CLI, and gateway paths."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from ds_agent.domain.interfaces.llm_provider import LLMProvider
from ds_agent.infrastructure.auth.token_store import AuthProfileStore
from ds_agent.infrastructure.secrets.api_key_manager import ApiKeyManager, create_api_key_manager
from ds_agent.infrastructure.secrets.secret_storage import (
    SecretStoragePort,
    get_shared_secret_storage,
)
from ds_agent.providers.ollama import OllamaClient
from ds_agent.providers.router import ProviderRouter

if TYPE_CHECKING:
    from ds_agent.config.schema import DSAgentConfig

_API_KEY_STATUS_PROVIDERS: tuple[str, ...] = (
    "anthropic",
    "openai",
    "groq",
    "deepseek",
    "minimax",
    "qwen",
    "zhipu",
    "moonshot",
)

_PROVIDER_LABELS: dict[str, str] = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "groq": "Groq",
    "deepseek": "DeepSeek",
    "minimax": "MiniMax",
    "qwen": "Qwen",
    "zhipu": "Zhipu",
    "moonshot": "Moonshot",
    "codex": "ChatGPT (Codex)",
    "gemini": "Google Gemini",
    "ollama": "Ollama",
}


def _provider_label(provider: str) -> str:
    return _PROVIDER_LABELS.get(provider, provider.capitalize())


def _health_from_auth_status(provider: str, auth_status: str) -> dict[str, object]:
    if auth_status == "active":
        status = "ok"
        has_credentials = True
        message = "Credentials are configured and ready."
    elif auth_status == "local":
        status = "ok"
        has_credentials = True
        message = "Local runtime is selected."
    elif auth_status == "need_key":
        status = "unavailable"
        has_credentials = False
        message = "API key required."
    elif auth_status == "not_configured":
        status = "unavailable"
        has_credentials = False
        message = "OAuth login required."
    else:
        status = "degraded"
        has_credentials = False
        message = "Provider status could not be determined."

    return {
        "id": provider,
        "label": _provider_label(provider),
        "status": status,
        "hasCredentials": has_credentials,
        "authStatus": auth_status,
        "latencyMs": None,
        "message": message,
        "checkedAt": time.time(),
    }


async def _ollama_health_snapshot(auth_status: str) -> dict[str, object]:
    client = OllamaClient()
    started = time.perf_counter()
    running = await client.is_running()
    latency_ms = round((time.perf_counter() - started) * 1000)

    if not running:
        return {
            "id": "ollama",
            "label": _provider_label("ollama"),
            "status": "unavailable",
            "hasCredentials": True,
            "authStatus": auth_status,
            "latencyMs": None,
            "message": "Ollama is not reachable on this computer.",
            "checkedAt": time.time(),
            "modelCount": 0,
        }

    models = await client.list_models()
    if not models:
        return {
            "id": "ollama",
            "label": _provider_label("ollama"),
            "status": "degraded",
            "hasCredentials": True,
            "authStatus": auth_status,
            "latencyMs": latency_ms,
            "message": "Ollama is reachable, but no local models were found.",
            "checkedAt": time.time(),
            "modelCount": 0,
        }

    return {
        "id": "ollama",
        "label": _provider_label("ollama"),
        "status": "ok",
        "hasCredentials": True,
        "authStatus": auth_status,
        "latencyMs": latency_ms,
        "message": f"Ollama is reachable with {len(models)} local model(s).",
        "checkedAt": time.time(),
        "modelCount": len(models),
    }


def resolve_api_key(provider: str, api_key_manager: ApiKeyManager | None = None) -> str | None:
    """Resolve API key from secret storage first, then environment."""
    key = api_key_manager.get(provider) if api_key_manager is not None else None
    if key:
        return key
    return os.environ.get(f"{provider.upper()}_API_KEY")


def create_auth_profile_store(
    config: DSAgentConfig,
    *,
    secrets: SecretStoragePort | None = None,
) -> AuthProfileStore:
    """Create the shared auth profile store from config."""
    oauth_cfg = getattr(config, "oauth", None)
    store_path = getattr(oauth_cfg, "token_store_path", None) if oauth_cfg else None
    return AuthProfileStore(store_path, secrets=secrets or get_shared_secret_storage())


def create_provider_router(
    model: str,
    config: DSAgentConfig,
    token_store: AuthProfileStore | None = None,
    api_key_manager: ApiKeyManager | None = None,
    emit_event: Callable[[str, dict], None] | None = None,
) -> LLMProvider:
    """Create the runtime's shared provider router for a model."""
    manager = api_key_manager or create_api_key_manager()
    kwargs: dict[str, object] = {
        "fallback_models": config.provider.fallback_models,
        "token_store": token_store,
        "api_key_resolver": manager.get,
    }
    if emit_event is not None:
        kwargs["event_callback"] = emit_event
    return ProviderRouter(
        model,
        **kwargs,
    )


def get_provider_auth_statuses(
    config: DSAgentConfig,
    token_store: AuthProfileStore | None = None,
    api_key_manager: ApiKeyManager | None = None,
) -> dict[str, str]:
    """Build provider auth statuses from the same shared auth substrate."""
    manager = api_key_manager or create_api_key_manager()
    statuses: dict[str, str] = {}

    codex_auth = Path.home() / ".codex" / "auth.json"
    codex_has_store = token_store.has_provider("codex") if token_store is not None else False
    statuses["codex"] = "active" if (codex_auth.exists() or codex_has_store) else "not_configured"

    for provider in _API_KEY_STATUS_PROVIDERS:
        statuses[provider] = "active" if resolve_api_key(provider, manager) else "need_key"

    gemini_has_store = token_store.has_provider("gemini") if token_store is not None else False
    statuses["gemini"] = (
        "active" if (resolve_api_key("gemini", manager) or gemini_has_store) else "need_key"
    )

    statuses["ollama"] = "local"
    return statuses


async def get_provider_health_snapshot(
    config: DSAgentConfig,
    token_store: AuthProfileStore | None = None,
    api_key_manager: ApiKeyManager | None = None,
) -> list[dict[str, object]]:
    """Return operator-facing provider health data for product surfaces."""
    auth_statuses = get_provider_auth_statuses(
        config,
        token_store=token_store,
        api_key_manager=api_key_manager,
    )

    snapshots: dict[str, dict[str, object]] = {
        provider: _health_from_auth_status(provider, status)
        for provider, status in auth_statuses.items()
    }
    snapshots["ollama"] = await _ollama_health_snapshot(auth_statuses.get("ollama", "local"))
    return [snapshots[key] for key in sorted(snapshots)]
