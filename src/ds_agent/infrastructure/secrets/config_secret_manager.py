"""Secure storage helpers for config-backed secret fields."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ds_agent.config.schema import DSAgentConfig

from .secret_storage import SecretStoragePort, get_shared_secret_storage

CONFIG_SECRET_PATHS: tuple[str, ...] = (
    "oauth.gemini_client_secret",
    "channels.telegram.bot_token",
)

_CONFIG_SECRET_KEYS: dict[str, str] = {
    path: f"config_secret:{path}" for path in CONFIG_SECRET_PATHS
}


class ConfigSecretManager:
    """Manage config-scoped secrets outside the persisted YAML file."""

    def __init__(self, storage: SecretStoragePort) -> None:
        self._storage = storage

    @property
    def backend_name(self) -> str:
        return self._storage.backend_name

    @property
    def persistent(self) -> bool:
        return self._storage.persistent

    def set(self, path: str, value: str) -> None:
        secret_key = self._secret_key(path)
        self._storage.store(secret_key, value)

    def get(self, path: str) -> str | None:
        secret_key = self._secret_key(path)
        return self._storage.retrieve(secret_key)

    def delete(self, path: str) -> bool:
        secret_key = self._secret_key(path)
        return self._storage.delete(secret_key)

    def migrate_from_data(self, data: dict[str, Any]) -> bool:
        """Move plaintext config secrets out of a raw config dict."""
        migrated = False
        for path in CONFIG_SECRET_PATHS:
            value = _pop_nested_value(data, path)
            if isinstance(value, str) and value.strip():
                self.set(path, value)
                migrated = True
        return migrated

    def hydrate_config(self, config: DSAgentConfig) -> None:
        """Inject secure values into the in-memory config model."""
        for path in CONFIG_SECRET_PATHS:
            value = self.get(path)
            if value is not None:
                _set_nested_attr(config, path, value)

    @staticmethod
    def _secret_key(path: str) -> str:
        try:
            return _CONFIG_SECRET_KEYS[path]
        except KeyError as exc:
            raise ValueError(f"Unsupported config secret path: {path}") from exc


def create_config_secret_manager(storage: SecretStoragePort | None = None) -> ConfigSecretManager:
    """Create a config secret manager backed by the shared storage by default."""
    return ConfigSecretManager(storage or get_shared_secret_storage())


def strip_persisted_config_secrets(data: dict[str, Any]) -> dict[str, Any]:
    """Remove secret-bearing config fields from a serialized config payload."""
    sanitized = deepcopy(data)
    for path in CONFIG_SECRET_PATHS:
        _pop_nested_value(sanitized, path)
    return sanitized


def _pop_nested_value(data: dict[str, Any], path: str) -> Any | None:
    parts = path.split(".")
    current: Any = data
    parents: list[tuple[dict[str, Any], str]] = []

    for part in parts[:-1]:
        if not isinstance(current, dict):
            return None
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            return None
        parents.append((current, part))
        current = next_value

    if not isinstance(current, dict):
        return None

    value = current.pop(parts[-1], None)
    if value is None:
        return None

    while parents:
        parent, key = parents.pop()
        child = parent.get(key)
        if isinstance(child, dict) and not child:
            parent.pop(key, None)
            continue
        break
    return value


def _set_nested_attr(config: DSAgentConfig, path: str, value: str) -> None:
    target: Any = config
    parts = path.split(".")
    for part in parts[:-1]:
        target = getattr(target, part)
    setattr(target, parts[-1], value)
