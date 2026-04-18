"""Tests for ConfigManager — extracted from AppState (4.1.4)."""

from __future__ import annotations

import pytest

from ds_agent.api.config_manager import (
    PERSISTENT_CONFIG_PATHS,
    SESSION_DEFAULT_PATHS,
    SESSION_OVERRIDE_PATHS,
    ConfigManager,
)
from ds_agent.config.schema import DSAgentConfig


@pytest.fixture
def config() -> DSAgentConfig:
    return DSAgentConfig()


@pytest.fixture
def mgr(config: DSAgentConfig) -> ConfigManager:
    return ConfigManager(config)


class TestConfigManagerBasic:
    """Core get/set functionality."""

    def test_get_dump_returns_dict(self, mgr: ConfigManager) -> None:
        dump = mgr.get_dump()
        assert isinstance(dump, dict)
        assert "provider" in dump
        assert "agent" in dump

    def test_set_allowed_path(self, mgr: ConfigManager) -> None:
        mgr.set("agent.mode", "supervised")
        assert mgr.config.agent.mode == "supervised"

    def test_set_disallowed_path_raises(self, mgr: ConfigManager) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            mgr.set("nonexistent.path", "value")

    def test_set_empty_path_raises(self, mgr: ConfigManager) -> None:
        with pytest.raises(ValueError, match="path is required"):
            mgr.set("", "value")

    def test_set_budget(self, mgr: ConfigManager) -> None:
        mgr.set("provider.max_budget_usd", 25.0)
        assert mgr.config.provider.max_budget_usd == 25.0

    def test_set_model(self, mgr: ConfigManager) -> None:
        mgr.set("provider.default_model", "openai/gpt-4o")
        assert mgr.config.provider.default_model == "openai/gpt-4o"
        assert mgr.config.provider.quality_preset.value == "custom"

    def test_set_use_case_fields(self, mgr: ConfigManager) -> None:
        mgr.set("agent.use_case_hint", "reporting")
        mgr.set("agent.use_case_context", "Favor decision-ready summaries.")
        assert mgr.config.agent.use_case_hint == "reporting"
        assert mgr.config.agent.use_case_context == "Favor decision-ready summaries."

    def test_set_observability_fields(self, mgr: ConfigManager) -> None:
        mgr.set("observability.error_reporting_enabled", True)
        mgr.set("observability.telemetry_enabled", True)
        assert mgr.config.observability.error_reporting_enabled is True
        assert mgr.config.observability.telemetry_enabled is True

    def test_set_authority_overlay_fields(self, mgr: ConfigManager) -> None:
        mgr.set("gateway.authority_overlay", "incident")
        mgr.set("gateway.authority_overlay_started_at", "2026-04-16T09:00:00+00:00")
        assert mgr.config.gateway.authority_overlay == "incident"
        assert mgr.config.gateway.authority_overlay_started_at == "2026-04-16T09:00:00+00:00"

    def test_default_config_stays_on_balanced_preset(self, mgr: ConfigManager) -> None:
        assert mgr.config.provider.quality_preset.value == "balanced"
        assert mgr.config.provider.fallback_models == ["openai/gpt-4.1-mini"]

    def test_set_quality_preset_updates_models(self, mgr: ConfigManager) -> None:
        mgr.set("provider.quality_preset", "fast")

        assert mgr.config.provider.quality_preset.value == "fast"
        assert mgr.config.provider.default_model == "anthropic/claude-haiku-4-5"
        assert mgr.config.provider.fallback_models == ["openai/gpt-4.1-mini"]

    def test_init_hydrates_missing_fallback_for_known_preset_model(self) -> None:
        mgr = ConfigManager(
            DSAgentConfig(
                provider={
                    "default_model": "anthropic/claude-sonnet-4-6",
                    "fallback_models": [],
                }
            )
        )

        assert mgr.config.provider.quality_preset.value == "balanced"
        assert mgr.config.provider.fallback_models == ["openai/gpt-4.1-mini"]


class TestConfigManagerApiKeys:
    """API key operations."""

    def test_set_api_key(self, mgr: ConfigManager) -> None:
        mgr.set_api_key("anthropic", "sk-ant-test-key-12345678")
        assert mgr.api_key_manager.get("anthropic") == "sk-ant-test-key-12345678"

    def test_get_api_keys_masked_long_key(self, mgr: ConfigManager) -> None:
        mgr.set_api_key("anthropic", "sk-ant-test-key-12345678")
        masked = mgr.get_api_keys_masked()
        assert masked["anthropic"] == "sk-a...5678"

    def test_get_api_keys_masked_short_key(self, mgr: ConfigManager) -> None:
        mgr.set_api_key("groq", "short")
        masked = mgr.get_api_keys_masked()
        assert masked["groq"] == "***"

    def test_get_dump_redacts_sensitive_config_fields(self, mgr: ConfigManager) -> None:
        mgr.config.oauth.gemini_client_secret = "super-secret"
        mgr.config.channels.telegram.bot_token = "12345:bot-token"

        dump = mgr.get_dump()

        assert dump["oauth"]["gemini_client_secret"] == "***REDACTED***"
        assert dump["channels"]["telegram"]["bot_token"] == "***REDACTED***"


class TestConfigManagerPersistence:
    """Persistence scope — 3.11 fix."""

    def test_persistent_paths_are_subset_of_allowed(self) -> None:
        from ds_agent.api.routes.config import ALLOWED_CONFIG_PATHS

        assert PERSISTENT_CONFIG_PATHS.issubset(ALLOWED_CONFIG_PATHS)

    def test_session_default_paths_are_subset_of_allowed(self) -> None:
        from ds_agent.api.routes.config import ALLOWED_CONFIG_PATHS

        assert SESSION_DEFAULT_PATHS.issubset(ALLOWED_CONFIG_PATHS)

    def test_session_override_paths_are_subset_of_allowed(self) -> None:
        from ds_agent.api.routes.config import ALLOWED_CONFIG_PATHS

        assert SESSION_OVERRIDE_PATHS.issubset(ALLOWED_CONFIG_PATHS)

    def test_all_scopes_cover_all_allowed(self) -> None:
        """Every allowed path must belong to exactly one scope."""
        from ds_agent.api.routes.config import ALLOWED_CONFIG_PATHS

        all_scoped = PERSISTENT_CONFIG_PATHS | SESSION_DEFAULT_PATHS | SESSION_OVERRIDE_PATHS
        assert all_scoped == ALLOWED_CONFIG_PATHS

    def test_persist_called_for_persistent_path(
        self, mgr: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []
        monkeypatch.setattr(mgr, "_persist", lambda: calls.append("persisted"))
        mgr.set("provider.max_budget_usd", 5.0)
        assert calls == ["persisted"]

    def test_persist_called_for_observability_path(
        self, mgr: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []
        monkeypatch.setattr(mgr, "_persist", lambda: calls.append("persisted"))
        mgr.set("observability.error_reporting_enabled", True)
        assert calls == ["persisted"]

    def test_persist_not_called_for_session_path(
        self, mgr: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []
        monkeypatch.setattr(mgr, "_persist", lambda: calls.append("persisted"))
        mgr.set("agent.mode", "supervised")
        assert calls == []

    def test_persist_not_called_for_override_path(
        self, mgr: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []
        monkeypatch.setattr(mgr, "_persist", lambda: calls.append("persisted"))
        mgr.set("agent.context_window", 64000)
        assert calls == []

    def test_injected_config_does_not_write_default_user_config(
        self, mgr: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[object, object]] = []
        monkeypatch.setattr(
            "ds_agent.api.config_manager.save_config",
            lambda config, path: calls.append((config, path)),
        )

        mgr.set("provider.max_budget_usd", 5.0)

        assert calls == []
