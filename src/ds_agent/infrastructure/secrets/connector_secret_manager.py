"""Connector credential management backed by a SecretStoragePort."""

from __future__ import annotations

import json

from .secret_storage import SecretStoragePort, get_shared_secret_storage


class ConnectorSecretManager:
    """Persist structured connector credentials outside the config YAML."""

    def __init__(self, storage: SecretStoragePort) -> None:
        self._storage = storage

    @property
    def backend_name(self) -> str:
        return self._storage.backend_name

    @property
    def persistent(self) -> bool:
        return self._storage.persistent

    def store(self, connector_name: str, payload: dict[str, object]) -> str:
        credential_ref = self._credential_ref(connector_name)
        self._storage.store(credential_ref, json.dumps(payload, ensure_ascii=False))
        return credential_ref

    def load(self, credential_ref: str) -> dict[str, object] | None:
        raw = self._storage.retrieve(credential_ref)
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def delete(self, credential_ref: str) -> bool:
        return self._storage.delete(credential_ref)

    def has_secret(self, credential_ref: str) -> bool:
        if not credential_ref:
            return False
        return self._storage.exists(credential_ref)

    @staticmethod
    def _credential_ref(connector_name: str) -> str:
        normalized = connector_name.strip()
        if not normalized:
            raise ValueError("connector_name is required")
        return f"connector/{normalized}/credentials"


def create_connector_secret_manager(
    storage: SecretStoragePort | None = None,
) -> ConnectorSecretManager:
    """Create a connector secret manager using the shared storage by default."""
    return ConnectorSecretManager(storage or get_shared_secret_storage())
