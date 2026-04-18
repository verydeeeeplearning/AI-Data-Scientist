"""Secret storage adapters and managers."""

from .api_key_manager import API_KEY_PROVIDERS, ApiKeyManager, create_api_key_manager, mask_secret
from .config_secret_manager import (
    CONFIG_SECRET_PATHS,
    ConfigSecretManager,
    create_config_secret_manager,
    strip_persisted_config_secrets,
)
from .connector_secret_manager import ConnectorSecretManager, create_connector_secret_manager
from .secret_storage import (
    InMemorySecretStorage,
    KeyringSecretStorage,
    SecretStorageError,
    SecretStoragePort,
    build_default_secret_storage,
    describe_secret_storage,
    get_shared_secret_storage,
    set_shared_secret_storage,
)

__all__ = [
    "API_KEY_PROVIDERS",
    "CONFIG_SECRET_PATHS",
    "ApiKeyManager",
    "ConfigSecretManager",
    "ConnectorSecretManager",
    "InMemorySecretStorage",
    "KeyringSecretStorage",
    "SecretStorageError",
    "SecretStoragePort",
    "build_default_secret_storage",
    "create_api_key_manager",
    "create_config_secret_manager",
    "create_connector_secret_manager",
    "describe_secret_storage",
    "get_shared_secret_storage",
    "mask_secret",
    "set_shared_secret_storage",
    "strip_persisted_config_secrets",
]
