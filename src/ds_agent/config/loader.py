"""Hierarchical config loader: env vars > yaml file > defaults."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog
import yaml

from ds_agent.application.migration import MigrationRunner
from ds_agent.config.schema import DSAgentConfig
from ds_agent.infrastructure.migration import CONFIG_MIGRATIONS
from ds_agent.infrastructure.secrets.api_key_manager import ApiKeyManager, create_api_key_manager
from ds_agent.infrastructure.secrets.config_secret_manager import (
    ConfigSecretManager,
    create_config_secret_manager,
    strip_persisted_config_secrets,
)

logger = structlog.get_logger()


def load_config(
    config_path: Path | None = None,
    *,
    api_key_manager: ApiKeyManager | None = None,
    config_secret_manager: ConfigSecretManager | None = None,
) -> DSAgentConfig:
    """Load config: defaults, YAML file, then environment overrides."""
    data: dict = {}
    resolved_path = config_path or get_default_config_path()
    resolved_api_key_manager = api_key_manager or create_api_key_manager()
    resolved_config_secret_manager = config_secret_manager or create_config_secret_manager()

    if resolved_path.exists():
        with open(resolved_path, encoding="utf-8") as f:
            file_data = yaml.safe_load(f)
            if isinstance(file_data, dict):
                data = file_data
                migrated_plaintext = False
                if _migrate_legacy_provider_api_keys(
                    data,
                    api_key_manager=resolved_api_key_manager,
                ):
                    migrated_plaintext = True
                    logger.info(
                        "config_plaintext_api_keys_migrated",
                        path=str(resolved_path),
                        backend=resolved_api_key_manager.backend_name,
                        persistent=resolved_api_key_manager.persistent,
                    )
                if _migrate_legacy_config_secrets(
                    data,
                    config_secret_manager=resolved_config_secret_manager,
                ):
                    migrated_plaintext = True
                    logger.info(
                        "config_plaintext_secrets_migrated",
                        path=str(resolved_path),
                        backend=resolved_config_secret_manager.backend_name,
                        persistent=resolved_config_secret_manager.persistent,
                    )
                if migrated_plaintext:
                    _persist_raw_config_data(resolved_path, data)

                migration_runner = MigrationRunner(
                    migrations=CONFIG_MIGRATIONS,
                    backup_dir=resolved_path.parent / ".migration-backups",
                )
                migration_result = migration_runner.run_for_store("config", data)
                if migration_result.migrated_count > 0:
                    data = migration_result.final_data
                    _persist_raw_config_data(resolved_path, data)
                    logger.info(
                        "config_schema_migrated",
                        path=str(resolved_path),
                        migrated_count=migration_result.migrated_count,
                        backups=[str(path) for path in migration_result.backed_up_paths],
                    )
                elif not migration_result.success:
                    logger.warning(
                        "config_schema_migration_failed",
                        path=str(resolved_path),
                        errors=migration_result.errors,
                    )
                    data = migration_result.final_data

    config = DSAgentConfig(**data)
    resolved_config_secret_manager.hydrate_config(config)

    if env_model := os.environ.get("DS_AGENT_MODEL"):
        config.provider.default_model = env_model
    if env_budget := os.environ.get("DS_AGENT_MAX_BUDGET_USD"):
        config.provider.max_budget_usd = float(env_budget)
    if env_warning_threshold := os.environ.get("DS_AGENT_BUDGET_WARNING_THRESHOLD_PCT"):
        config.provider.budget_warning_threshold_pct = float(env_warning_threshold)
    if env_mode := os.environ.get("DS_AGENT_MODE"):
        config.agent.mode = env_mode  # type: ignore[assignment]
    if env_iterations := os.environ.get("DS_AGENT_MAX_ITERATIONS"):
        config.agent.max_iterations = int(env_iterations)
    if env_gemini_client_secret := os.environ.get("DS_AGENT_GEMINI_CLIENT_SECRET"):
        config.oauth.gemini_client_secret = env_gemini_client_secret
    if env_telegram_bot_token := os.environ.get("DS_AGENT_TELEGRAM_BOT_TOKEN"):
        config.channels.telegram.bot_token = env_telegram_bot_token
    if env_sentry_dsn := os.environ.get("DS_AGENT_SENTRY_DSN"):
        config.observability.sentry_dsn = env_sentry_dsn
    if env_sentry_environment := os.environ.get("DS_AGENT_SENTRY_ENVIRONMENT"):
        config.observability.sentry_environment = env_sentry_environment
    if env_error_reporting := os.environ.get("DS_AGENT_ERROR_REPORTING_ENABLED"):
        config.observability.error_reporting_enabled = _parse_env_bool(env_error_reporting)
    if env_telemetry := os.environ.get("DS_AGENT_TELEMETRY_ENABLED"):
        config.observability.telemetry_enabled = _parse_env_bool(env_telemetry)

    return config


def save_config(config: DSAgentConfig, config_path: Path) -> None:
    """Save config to YAML file."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(exclude_defaults=False, by_alias=True, mode="json")
    data = strip_persisted_config_secrets(data)
    _persist_raw_config_data(config_path, data)


def get_default_config_path() -> Path:
    """Get the default config file path."""
    if env_path := os.environ.get("DS_AGENT_CONFIG_PATH"):
        return Path(env_path).expanduser()
    return Path.home() / ".ds-agent" / "config.yaml"


def _persist_raw_config_data(config_path: Path, data: dict[str, Any]) -> None:
    """Persist raw config payload including migration metadata."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as config_file:
        yaml.safe_dump(
            data,
            config_file,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )


def _migrate_legacy_provider_api_keys(
    data: dict,
    *,
    api_key_manager: ApiKeyManager,
) -> bool:
    """Move legacy plaintext provider keys into secret storage."""
    provider_data = data.get("provider")
    if not isinstance(provider_data, dict):
        return False

    legacy_keys = provider_data.pop("api_keys", None)
    if not isinstance(legacy_keys, dict):
        return False

    for provider, key in legacy_keys.items():
        if isinstance(key, str) and key.strip():
            api_key_manager.set(str(provider), key)
    return True


def _migrate_legacy_config_secrets(
    data: dict,
    *,
    config_secret_manager: ConfigSecretManager,
) -> bool:
    """Move plaintext config secrets into secure storage."""
    migrated = config_secret_manager.migrate_from_data(data)
    return migrated


def _parse_env_bool(raw_value: str) -> bool:
    normalized = raw_value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}
