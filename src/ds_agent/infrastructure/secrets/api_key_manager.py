"""API key management backed by a SecretStoragePort."""

from __future__ import annotations

from collections.abc import Iterable

from ds_agent.infrastructure.secrets.secret_storage import (
    SecretStoragePort,
    get_shared_secret_storage,
)

API_KEY_PROVIDERS: tuple[str, ...] = (
    "anthropic",
    "openai",
    "groq",
    "deepseek",
    "minimax",
    "qwen",
    "zhipu",
    "moonshot",
    "gemini",
)


def mask_secret(value: str) -> str:
    """Mask a secret for UI-safe display."""
    if len(value) > 8:
        return value[:4] + "..." + value[-4:]
    return "***"


class ApiKeyManager:
    """API key CRUD facade built on top of secret storage."""

    def __init__(
        self,
        storage: SecretStoragePort,
        *,
        prefix: str = "api_key",
    ) -> None:
        self._storage = storage
        self._prefix = prefix

    @property
    def backend_name(self) -> str:
        return self._storage.backend_name

    @property
    def persistent(self) -> bool:
        return self._storage.persistent

    def set(self, provider: str, key: str) -> None:
        provider_name = provider.strip().lower()
        value = key.strip()
        if not provider_name:
            raise ValueError("provider is required")
        if not value:
            raise ValueError("key is required")
        self._storage.store(self._storage_key(provider_name), value)

    def get(self, provider: str) -> str | None:
        provider_name = provider.strip().lower()
        if not provider_name:
            return None
        return self._storage.retrieve(self._storage_key(provider_name))

    def delete(self, provider: str) -> bool:
        provider_name = provider.strip().lower()
        if not provider_name:
            return False
        return self._storage.delete(self._storage_key(provider_name))

    def exists(self, provider: str) -> bool:
        provider_name = provider.strip().lower()
        if not provider_name:
            return False
        return self._storage.exists(self._storage_key(provider_name))

    def mask(self, provider: str) -> str | None:
        key = self.get(provider)
        if key is None:
            return None
        return mask_secret(key)

    def masked(self, providers: Iterable[str] = API_KEY_PROVIDERS) -> dict[str, str]:
        masked: dict[str, str] = {}
        for provider in providers:
            value = self.mask(provider)
            if value is not None:
                masked[provider] = value
        return masked

    def _storage_key(self, provider: str) -> str:
        return f"{self._prefix}:{provider}"


def create_api_key_manager(storage: SecretStoragePort | None = None) -> ApiKeyManager:
    """Create an API key manager using the shared secret storage by default."""
    return ApiKeyManager(storage or get_shared_secret_storage())
