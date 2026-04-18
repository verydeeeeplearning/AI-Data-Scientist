"""Config system tests."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from ds_agent.config.loader import get_default_config_path, load_config, save_config
from ds_agent.config.schema import CURRENT_CONFIG_SCHEMA_VERSION, DSAgentConfig
from ds_agent.domain.value_objects.connector import ConnectorType
from ds_agent.infrastructure.secrets.api_key_manager import create_api_key_manager
from ds_agent.infrastructure.secrets.config_secret_manager import create_config_secret_manager
from ds_agent.infrastructure.secrets.secret_storage import InMemorySecretStorage


class TestDSAgentConfig:
    def test_default_config(self):
        config = DSAgentConfig()
        assert config.provider.quality_preset.value == "balanced"
        assert config.provider.default_model == "anthropic/claude-sonnet-4-6"
        assert config.provider.fallback_models == ["openai/gpt-4.1-mini"]
        assert config.provider.budget_warning_threshold_pct == 80.0
        assert config.agent.max_iterations == 100
        assert config.agent.mode == "auto"
        assert config.agent.use_case_hint is None
        assert config.agent.use_case_context is None
        assert config.observability.sentry_dsn is None
        assert config.observability.sentry_environment == "production"
        assert config.observability.error_reporting_enabled is False
        assert config.observability.telemetry_enabled is False
        assert config.gateway.authority_overlay is None
        assert config.gateway.authority_overlay_started_at is None

    def test_custom_config(self):
        config = DSAgentConfig(
            provider={
                "default_model": "openai/gpt-4.1",
                "max_budget_usd": 5.0,
                "budget_warning_threshold_pct": 90.0,
            }
        )
        assert config.provider.default_model == "openai/gpt-4.1"
        assert config.provider.max_budget_usd == 5.0
        assert config.provider.budget_warning_threshold_pct == 90.0

    def test_mode_values(self):
        for mode in ("auto", "supervised", "step-by-step"):
            config = DSAgentConfig(agent={"mode": mode})
            assert config.agent.mode == mode

    def test_connector_settings_are_parsed(self):
        config = DSAgentConfig(
            connectors={
                "warehouse": {
                    "type": "postgres",
                    "host": "localhost",
                    "database": "analytics",
                    "credential_ref": "PG_DSN",
                }
            }
        )
        connector = config.connectors["warehouse"]
        assert connector.type == ConnectorType.POSTGRES
        assert connector.database == "analytics"
        assert connector.options["host"] == "localhost"
        assert connector.options["database"] == "analytics"
        assert connector.to_domain().credential_ref == "PG_DSN"


class TestConfigLoader:
    def test_default_config_path_uses_env_override(self, tmp_path, monkeypatch):
        config_path = tmp_path / "custom-config.yaml"
        monkeypatch.setenv("DS_AGENT_CONFIG_PATH", str(config_path))

        assert get_default_config_path() == Path(config_path)

    def test_load_from_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "provider:\n  default_model: openai/gpt-4.1\n  max_budget_usd: 20.0\n",
            encoding="utf-8",
        )
        config = load_config(config_path=config_file)
        assert config.provider.default_model == "openai/gpt-4.1"
        assert config.provider.max_budget_usd == 20.0

    def test_load_defaults_when_no_file(self, tmp_path):
        config = load_config(config_path=tmp_path / "nonexistent.yaml")
        assert config.provider.default_model == "anthropic/claude-sonnet-4-6"
        assert config.schema_version == CURRENT_CONFIG_SCHEMA_VERSION

    def test_env_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DS_AGENT_MODEL", "groq/llama-3.3-70b")
        config = load_config(config_path=tmp_path / "nonexistent.yaml")
        assert config.provider.default_model == "groq/llama-3.3-70b"

    def test_env_override_observability(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DS_AGENT_SENTRY_DSN", "https://public@example.ingest.sentry.io/1")
        monkeypatch.setenv("DS_AGENT_SENTRY_ENVIRONMENT", "staging")
        monkeypatch.setenv("DS_AGENT_ERROR_REPORTING_ENABLED", "true")
        monkeypatch.setenv("DS_AGENT_TELEMETRY_ENABLED", "1")

        config = load_config(config_path=tmp_path / "nonexistent.yaml")

        assert config.observability.sentry_dsn == "https://public@example.ingest.sentry.io/1"
        assert config.observability.sentry_environment == "staging"
        assert config.observability.error_reporting_enabled is True
        assert config.observability.telemetry_enabled is True

    def test_env_override_config_secrets(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DS_AGENT_GEMINI_CLIENT_SECRET", "desktop-secret")
        monkeypatch.setenv("DS_AGENT_TELEGRAM_BOT_TOKEN", "12345:desktop-bot-token")

        config = load_config(config_path=tmp_path / "nonexistent.yaml")

        assert config.oauth.gemini_client_secret == "desktop-secret"
        assert config.channels.telegram.bot_token == "12345:desktop-bot-token"

    def test_save_and_reload(self, tmp_path):
        config = DSAgentConfig(provider={"default_model": "test-model", "max_budget_usd": 42.0})
        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)

        loaded = load_config(config_path=config_path)
        assert loaded.provider.default_model == "test-model"
        assert loaded.provider.max_budget_usd == 42.0
        assert loaded.schema_version == CURRENT_CONFIG_SCHEMA_VERSION
        saved = config_path.read_text(encoding="utf-8")
        assert f"_schema_version: {CURRENT_CONFIG_SCHEMA_VERSION}" in saved

    def test_save_and_reload_connectors(self, tmp_path):
        config = DSAgentConfig(
            connectors={
                "warehouse": {
                    "type": "postgres",
                    "host": "localhost",
                    "database": "analytics",
                    "credential_ref": "PG_DSN",
                }
            }
        )
        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)
        saved = config_path.read_text(encoding="utf-8")

        loaded = load_config(config_path=config_path)
        assert "!!python/object" not in saved
        assert "options:" in saved
        assert loaded.connectors["warehouse"].schema_name == "public"
        assert "warehouse" in loaded.connectors
        assert loaded.connectors["warehouse"].type == ConnectorType.POSTGRES

    def test_load_migrates_plaintext_api_keys_out_of_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "provider:\n  default_model: openai/gpt-4.1\n  api_keys:\n    openai: sk-test-secret\n",
            encoding="utf-8",
        )
        api_key_manager = create_api_key_manager(InMemorySecretStorage())

        config = load_config(config_path=config_file, api_key_manager=api_key_manager)

        assert config.provider.default_model == "openai/gpt-4.1"
        assert api_key_manager.get("openai") == "sk-test-secret"
        assert config.schema_version == CURRENT_CONFIG_SCHEMA_VERSION
        saved = config_file.read_text(encoding="utf-8")
        assert "api_keys" not in saved
        assert "sk-test-secret" not in saved
        assert f"_schema_version: {CURRENT_CONFIG_SCHEMA_VERSION}" in saved
        backups = list((tmp_path / ".migration-backups").glob("config_v1_*.yaml"))
        assert len(backups) == 1

    def test_save_config_omits_plaintext_config_secrets(self, tmp_path):
        config = DSAgentConfig(
            oauth={"gemini_client_id": "client-id", "gemini_client_secret": "super-secret"},
            channels={"telegram": {"enabled": True, "bot_token": "12345:bot-token"}},
        )
        config_path = tmp_path / "config.yaml"

        save_config(config, config_path)

        saved = config_path.read_text(encoding="utf-8")
        assert "gemini_client_secret" not in saved
        assert "bot_token" not in saved
        assert "super-secret" not in saved
        assert "12345:bot-token" not in saved

    def test_load_migrates_plaintext_config_secrets_out_of_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            (
                "provider:\n"
                "  default_model: gemini/gemini-2.5-pro\n"
                "oauth:\n"
                "  gemini_client_id: client-id\n"
                "  gemini_client_secret: super-secret\n"
                "channels:\n"
                "  telegram:\n"
                "    enabled: true\n"
                "    bot_token: 12345:bot-token\n"
            ),
            encoding="utf-8",
        )
        secret_manager = create_config_secret_manager(InMemorySecretStorage())

        config = load_config(
            config_path=config_file,
            config_secret_manager=secret_manager,
        )

        assert config.oauth.gemini_client_secret == "super-secret"
        assert config.channels.telegram.bot_token == "12345:bot-token"
        assert secret_manager.get("oauth.gemini_client_secret") == "super-secret"
        assert secret_manager.get("channels.telegram.bot_token") == "12345:bot-token"
        saved = config_file.read_text(encoding="utf-8")
        assert "gemini_client_secret" not in saved
        assert "bot_token" not in saved
        assert "super-secret" not in saved
        assert "12345:bot-token" not in saved
        assert f"_schema_version: {CURRENT_CONFIG_SCHEMA_VERSION}" in saved

    def test_load_current_schema_is_idempotent(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            (
                f"_schema_version: {CURRENT_CONFIG_SCHEMA_VERSION}\n"
                "provider:\n"
                "  default_model: openai/gpt-4.1\n"
                "  max_budget_usd: 20.0\n"
            ),
            encoding="utf-8",
        )

        config_first = load_config(config_path=config_file)
        config_second = load_config(config_path=config_file)

        assert config_first.schema_version == CURRENT_CONFIG_SCHEMA_VERSION
        assert config_second.schema_version == CURRENT_CONFIG_SCHEMA_VERSION
        backups = list((tmp_path / ".migration-backups").glob("config_v*_*.yaml"))
        assert backups == []

    def test_load_migrates_legacy_connector_shape_to_options(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            (
                "_schema_version: 2\n"
                "connectors:\n"
                "  warehouse:\n"
                "    type: postgres\n"
                "    host: localhost\n"
                "    database: analytics\n"
                "    schema: public\n"
                "    credential_method: env\n"
                "    credential_ref: PG_DSN\n"
            ),
            encoding="utf-8",
        )

        config = load_config(config_path=config_file)

        connector = config.connectors["warehouse"]
        assert config.schema_version == CURRENT_CONFIG_SCHEMA_VERSION
        assert connector.options == {
            "host": "localhost",
            "database": "analytics",
            "schema": "public",
        }
        saved = config_file.read_text(encoding="utf-8")
        assert "options:" in saved
        assert "host: localhost" in saved
        assert "database: analytics" in saved
        assert "credential_ref: PG_DSN" in saved
        assert "observability:" in saved

    def test_load_migrates_v3_observability_defaults(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            ("_schema_version: 3\nprovider:\n  default_model: openai/gpt-4.1\n"),
            encoding="utf-8",
        )

        config = load_config(config_path=config_file)

        assert config.schema_version == CURRENT_CONFIG_SCHEMA_VERSION
        assert config.observability.sentry_dsn is None
        assert config.observability.sentry_environment == "production"
        assert config.observability.error_reporting_enabled is False
        assert config.observability.telemetry_enabled is False
        saved = config_file.read_text(encoding="utf-8")
        assert "observability:" in saved
        assert "error_reporting_enabled: false" in saved
        assert "telemetry_enabled: false" in saved


class TestValidateAssignment:
    """SEC-01: validate_assignment prevents invalid values via setattr."""

    def test_agent_mode_rejects_invalid_literal(self):
        config = DSAgentConfig()
        with pytest.raises(ValidationError):
            config.agent.mode = "definitely-invalid"

    def test_agent_mode_accepts_valid_literal(self):
        config = DSAgentConfig()
        config.agent.mode = "supervised"
        assert config.agent.mode == "supervised"

    def test_agent_max_iterations_rejects_string(self):
        config = DSAgentConfig()
        with pytest.raises(ValidationError):
            config.agent.max_iterations = "not-a-number"

    def test_provider_max_budget_rejects_string(self):
        config = DSAgentConfig()
        with pytest.raises(ValidationError):
            config.provider.max_budget_usd = "free"

    def test_gateway_port_rejects_string(self):
        config = DSAgentConfig()
        with pytest.raises(ValidationError):
            config.gateway.port = "not-a-port"

    def test_provider_default_model_accepts_string(self):
        config = DSAgentConfig()
        config.provider.default_model = "openai/gpt-4.1"
        assert config.provider.default_model == "openai/gpt-4.1"


_has_fastapi = True
try:
    import fastapi as _  # noqa: F401
except ImportError:
    _has_fastapi = False


@pytest.mark.skipif(not _has_fastapi, reason="fastapi not installed")
class TestConfigHttpWhitelist:
    """SEC-01: HTTP /api/config must enforce path whitelist."""

    def test_whitelist_contains_expected_paths(self):
        from ds_agent.api.routes.config import ALLOWED_CONFIG_PATHS as _ALLOWED_CONFIG_PATHS

        assert "provider.quality_preset" in _ALLOWED_CONFIG_PATHS
        assert "provider.default_model" in _ALLOWED_CONFIG_PATHS
        assert "provider.budget_warning_threshold_pct" in _ALLOWED_CONFIG_PATHS
        assert "agent.mode" in _ALLOWED_CONFIG_PATHS
        assert "agent.use_case_hint" in _ALLOWED_CONFIG_PATHS
        assert "agent.use_case_context" in _ALLOWED_CONFIG_PATHS
        assert "gateway.authority_overlay" in _ALLOWED_CONFIG_PATHS
        assert "gateway.authority_overlay_started_at" in _ALLOWED_CONFIG_PATHS
        assert "observability.error_reporting_enabled" in _ALLOWED_CONFIG_PATHS
        assert "observability.telemetry_enabled" in _ALLOWED_CONFIG_PATHS

    def test_whitelist_blocks_sensitive_paths(self):
        from ds_agent.api.routes.config import ALLOWED_CONFIG_PATHS as _ALLOWED_CONFIG_PATHS

        assert "provider.api_keys" not in _ALLOWED_CONFIG_PATHS
        assert "channels.telegram.bot_token" not in _ALLOWED_CONFIG_PATHS
        assert "observability.sentry_dsn" not in _ALLOWED_CONFIG_PATHS
