"""Configuration manager single-responsibility wrapper for DSAgentConfig."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
from pydantic import ValidationError

from ds_agent.api.routes.config import ALLOWED_CONFIG_PATHS
from ds_agent.config.loader import get_default_config_path, load_config, save_config
from ds_agent.config.schema import DSAgentConfig, WarehouseConnectorSettings
from ds_agent.domain.value_objects.quality_preset import (
    QualityPreset,
    coerce_quality_preset,
    detect_quality_preset,
    get_quality_preset_config,
)
from ds_agent.infrastructure.secrets.api_key_manager import (
    API_KEY_PROVIDERS,
    ApiKeyManager,
    create_api_key_manager,
)

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Settings lifecycle 3-tier scope (3.11)
# ---------------------------------------------------------------------------

PERSISTENT_CONFIG_PATHS: frozenset[str] = frozenset(
    {
        "provider.quality_preset",
        "provider.default_model",
        "provider.max_budget_usd",
        "provider.budget_warning_threshold_pct",
        "agent.workspace_dir",
        "agent.use_case_hint",
        "agent.use_case_context",
        "agent.language",  # P1-13: user-preferred response language
        "gateway.autonomous_runtime_enabled",
        "gateway.autonomous_cooldown_seconds",
        "gateway.autonomous_max_concurrent_runs",
        "gateway.autonomous_budget_per_run_usd",
        "gateway.automation_profile",
        "gateway.authority_overlay",
        "gateway.authority_overlay_started_at",
        "observability.telemetry_enabled",
        "observability.error_reporting_enabled",
    }
)

SESSION_DEFAULT_PATHS: frozenset[str] = frozenset(
    {
        "agent.mode",
        "agent.max_iterations",
    }
)

SESSION_OVERRIDE_PATHS: frozenset[str] = frozenset(
    {
        "agent.context_window",
        "agent.auto_compress",
        "gateway.host",
        "gateway.port",
    }
)


class ConfigManager:
    """Manages DSAgentConfig lifecycle: load, get, set, persist."""

    def __init__(
        self,
        config: DSAgentConfig | None = None,
        config_path: str | Path | None = None,
        api_key_manager: ApiKeyManager | None = None,
    ) -> None:
        self._api_key_manager = api_key_manager or create_api_key_manager()
        if config is not None:
            self._config = config
            self._config_path = Path(config_path) if config_path is not None else None
        else:
            resolved_path = (
                Path(config_path) if config_path is not None else get_default_config_path()
            )
            self._config = load_config(resolved_path, api_key_manager=self._api_key_manager)
            self._config_path = resolved_path
        self._sync_quality_preset_from_models()

    @property
    def config(self) -> DSAgentConfig:
        return self._config

    @property
    def api_key_manager(self) -> ApiKeyManager:
        return self._api_key_manager

    @property
    def config_path(self) -> Path | None:
        return self._config_path

    def get_dump(self) -> dict[str, Any]:
        """Return a UI-safe config dict for JSON serialization."""
        return self._sanitize_dump(self._config.model_dump(mode="json"))

    def set(self, path: str, value: Any) -> None:
        """Update a config field by dotted path."""
        if not path:
            raise ValueError("path is required")

        if path not in ALLOWED_CONFIG_PATHS:
            raise ValueError(f"Config path not allowed: {path}")

        if path == "provider.quality_preset":
            self.set_quality_preset(value)
            return

        parts = path.split(".")
        obj: Any = self._config
        for part in parts[:-1]:
            obj = getattr(obj, part)

        try:
            setattr(obj, parts[-1], value)
        except ValidationError as exc:
            raise ValueError(f"Invalid value for {path}: {exc}") from exc

        if path == "provider.default_model":
            self._sync_quality_preset_from_models()

        if path in PERSISTENT_CONFIG_PATHS:
            self._persist()

    def set_quality_preset(self, preset: QualityPreset | str) -> None:
        """Apply a simple AI quality preset to model + fallback config."""

        try:
            resolved = coerce_quality_preset(preset)
        except ValueError as exc:
            raise ValueError(f"Invalid value for provider.quality_preset: {preset}") from exc

        self._config.provider.quality_preset = resolved
        if resolved != QualityPreset.CUSTOM:
            config = get_quality_preset_config(resolved)
            self._config.provider.default_model = config.primary
            self._config.provider.fallback_models = list(config.fallback)

        self._persist()

    def set_api_key(self, provider: str, key: str) -> None:
        """Store an API key in secure storage."""
        self._api_key_manager.set(provider, key)

    def upsert_connector(
        self,
        name: str,
        settings: WarehouseConnectorSettings,
    ) -> WarehouseConnectorSettings:
        """Create or replace one persisted connector definition."""
        normalized = name.strip()
        if not normalized:
            raise ValueError("Connector name is required")
        self._config.connectors[normalized] = settings
        self._persist()
        return self._config.connectors[normalized]

    def delete_connector(self, name: str) -> WarehouseConnectorSettings | None:
        """Delete one connector by name and persist the change."""
        normalized = name.strip()
        if not normalized:
            raise ValueError("Connector name is required")
        removed = self._config.connectors.pop(normalized, None)
        if removed is not None:
            self._persist()
        return removed

    def get_api_keys_masked(self) -> dict[str, str]:
        """Return configured API keys with masking for display."""
        return self._api_key_manager.masked(API_KEY_PROVIDERS)

    def _persist(self) -> None:
        """Write current config to disk."""
        if self._config_path is None:
            logger.debug("config_persist_skipped", reason="no_config_path")
            return
        save_config(self._config, self._config_path)
        logger.debug("config_persisted", path=str(self._config_path))

    def _sync_quality_preset_from_models(self) -> None:
        """Keep the stored preset aligned with the effective model selection."""

        detected = detect_quality_preset(
            self._config.provider.default_model,
            self._config.provider.fallback_models,
        )
        self._config.provider.quality_preset = detected
        if detected != QualityPreset.CUSTOM and not self._config.provider.fallback_models:
            config = get_quality_preset_config(detected)
            self._config.provider.fallback_models = list(config.fallback)

    @staticmethod
    def _sanitize_dump(data: dict[str, Any]) -> dict[str, Any]:
        """Redact sensitive config fields before returning them to clients."""
        redacted = dict(data)

        oauth = redacted.get("oauth")
        if isinstance(oauth, dict) and oauth.get("gemini_client_secret"):
            oauth_copy = dict(oauth)
            oauth_copy["gemini_client_secret"] = "***REDACTED***"
            redacted["oauth"] = oauth_copy

        channels = redacted.get("channels")
        if isinstance(channels, dict):
            telegram = channels.get("telegram")
            if isinstance(telegram, dict) and telegram.get("bot_token"):
                telegram_copy = dict(telegram)
                telegram_copy["bot_token"] = "***REDACTED***"
                channels_copy = dict(channels)
                channels_copy["telegram"] = telegram_copy
                redacted["channels"] = channels_copy

        return redacted
