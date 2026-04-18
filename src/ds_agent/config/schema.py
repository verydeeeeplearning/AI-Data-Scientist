"""Configuration schema — Pydantic models.

Settings Lifecycle 3-Tier Scope (3.11):

1. **Persistent** — saved to disk on every ``config.set`` change, survives app restart.
   Paths: ``provider.default_model``, ``provider.max_budget_usd``, ``agent.workspace_dir``

2. **Session Default** — applied to new sessions, NOT persisted to disk.
   Paths: ``agent.mode``, ``agent.max_iterations``

3. **Session Override** — in-memory only, affects running session.
   Paths: ``agent.context_window``, ``agent.auto_compress``, ``gateway.host``, ``gateway.port``

Canonical scope definitions live in ``ds_agent.api.config_manager``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ds_agent.domain.value_objects.connector import (
    ConnectorConfig,
    ConnectorOptionScalar,
    ConnectorType,
    CredentialMethod,
)
from ds_agent.domain.value_objects.quality_preset import (
    QualityPreset,
    get_quality_preset_config,
)

CURRENT_CONFIG_SCHEMA_VERSION = 4


class ProviderConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    quality_preset: QualityPreset = QualityPreset.BALANCED
    default_model: str = "anthropic/claude-sonnet-4-6"
    fallback_models: list[str] = Field(
        default_factory=lambda: list(get_quality_preset_config(QualityPreset.BALANCED).fallback)
    )
    max_budget_usd: float = 10.0
    budget_warning_threshold_pct: float = Field(default=80.0, ge=1.0, le=99.0)


class AgentConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    max_iterations: int = 100
    context_window: int = 128_000
    auto_compress: bool = True
    workspace_dir: str = "~/.ds-agent/workspace"
    mode: Literal["auto", "supervised", "step-by-step"] = "auto"
    domain_pack: str | None = None
    use_case_hint: str | None = None
    use_case_context: str | None = None
    # P1-13: agent response language. Passed into the system prompt so the
    # LLM answers in the user's preferred language. Defaults to Korean for the
    # initial launch market — override via onboarding / settings UI.
    language: Literal["ko", "en", "ja"] = "ko"


class ApprovalRuleConfig(BaseModel):
    """Configurable policy rule for policy-based approvals."""

    model_config = ConfigDict(validate_assignment=True)

    action: str = "*"
    data_sensitivity: Literal["public", "internal", "pii", "restricted"] | None = None
    environment: str | None = None
    confidence_threshold: float | None = None
    decision: Literal["auto", "approval", "double_check", "deny"] = "auto"


class ApprovalConfig(BaseModel):
    """Approval policy configuration."""

    model_config = ConfigDict(validate_assignment=True)

    default_mode: Literal["legacy", "policy"] = "policy"
    standing_threshold: int = 3
    rules: list[ApprovalRuleConfig] = Field(default_factory=list)


class GatewayConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 18790
    autonomous_runtime_enabled: bool = False
    autonomous_cooldown_seconds: float = 15.0
    autonomous_max_concurrent_runs: int = 1
    autonomous_budget_per_run_usd: float = 5.0
    automation_profile: Literal["manual", "balanced", "aggressive"] = "balanced"
    authority_overlay: Literal["incident", "freeze"] | None = None
    authority_overlay_started_at: str | None = None


class TelegramConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = False
    bot_token: str = ""
    allow_from: list[str] = Field(default_factory=list)


class ChannelsConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    telegram: TelegramConfig = TelegramConfig()


class OAuthConfig(BaseModel):
    """OAuth provider configuration for PKCE flows."""

    model_config = ConfigDict(validate_assignment=True)

    gemini_client_id: str = ""
    gemini_client_secret: str = ""
    token_store_path: str = "~/.ds-agent/auth_profiles.json"


class ObservabilityConfig(BaseModel):
    """Crash reporting and telemetry controls."""

    model_config = ConfigDict(validate_assignment=True)

    sentry_dsn: str | None = None
    sentry_environment: str = "production"
    telemetry_enabled: bool = False
    error_reporting_enabled: bool = False


class WarehouseConnectorSettings(BaseModel):
    """Serializable connector settings for runtime adapter creation."""

    model_config = ConfigDict(validate_assignment=True, populate_by_name=True)

    type: ConnectorType
    label: str = ""
    options: dict[str, ConnectorOptionScalar] = Field(default_factory=dict)
    host: str = Field(default="", exclude=True)
    database: str = Field(default="", exclude=True)
    schema_name: str = Field(default="public", alias="schema", exclude=True)
    credential_method: CredentialMethod = CredentialMethod.ENV
    credential_ref: str = ""
    read_only: bool = True
    timeout_seconds: int = 30
    max_rows: int = 10_000

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_shape(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        normalized = deepcopy(data)
        raw_options = normalized.get("options")
        options = dict(raw_options) if isinstance(raw_options, dict) else {}
        core_keys = {
            "type",
            "label",
            "options",
            "host",
            "database",
            "schema",
            "schema_name",
            "credential_method",
            "credential_ref",
            "read_only",
            "timeout_seconds",
            "max_rows",
        }

        if normalized.get("host") not in (None, ""):
            options.setdefault("host", normalized["host"])
        if normalized.get("database") not in (None, ""):
            connector_type = normalized.get("type")
            database_key = (
                "project_id"
                if connector_type in {ConnectorType.BIGQUERY, ConnectorType.BIGQUERY.value}
                else "database"
            )
            options.setdefault(database_key, normalized["database"])
        schema_value = normalized.get("schema", normalized.get("schema_name"))
        if schema_value not in (None, ""):
            options.setdefault("schema", schema_value)

        for key in list(normalized):
            if key in core_keys:
                continue
            options.setdefault(key, normalized[key])

        normalized["options"] = options
        return normalized

    @model_validator(mode="after")
    def _sync_legacy_fields(self) -> WarehouseConnectorSettings:
        object.__setattr__(self, "host", _string_option(self.options, "host", aliases=("account",)))
        database_key = "project_id" if self.type == ConnectorType.BIGQUERY else "database"
        object.__setattr__(self, "database", _string_option(self.options, database_key))
        default_schema = (
            "public" if self.type in {ConnectorType.POSTGRES, ConnectorType.SNOWFLAKE} else ""
        )
        object.__setattr__(
            self,
            "schema_name",
            _string_option(
                self.options,
                "schema",
                aliases=("dataset",),
                default=default_schema,
            ),
        )
        if not self.label:
            object.__setattr__(self, "label", self.database or self.host or self.type.value)
        required_field = "project_id" if self.type == ConnectorType.BIGQUERY else "database"
        if not self.database:
            raise ValueError(f"Connector settings require '{required_field}'")
        return self

    def to_domain(self, name: str = "default") -> ConnectorConfig:
        """Convert to the immutable domain connector config."""
        return ConnectorConfig(
            name=name,
            type=self.type,
            label=self.label or name,
            options=dict(self.options),
            host=self.host,
            database=self.database,
            schema=self.schema_name,
            credential_method=self.credential_method,
            credential_ref=self.credential_ref,
            read_only=self.read_only,
            timeout_seconds=self.timeout_seconds,
            max_rows=self.max_rows,
        )


class SandboxConfig(BaseModel):
    """P0-01 sandbox runtime policy.

    Controls the defence-in-depth layer that enforces file/network/subprocess
    boundaries on agent-generated code. See
    ``docs/productization/P0_01_code_execution_sandbox.md`` for design notes.
    """

    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = True
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    max_memory_mb: int = Field(default=2048, ge=64, le=65_536)
    block_subprocess: bool = True
    approved_hosts: list[str] = Field(
        default_factory=lambda: ["pypi.org", "files.pythonhosted.org"]
    )
    data_dirs: list[str] = Field(
        default_factory=list,
        description=(
            "Additional read-only directories beyond the workspace. Typical values: "
            "dataset upload dirs, shared reference data mounts."
        ),
    )


class DSAgentConfig(BaseModel):
    """Root configuration model."""

    model_config = ConfigDict(validate_assignment=True, populate_by_name=True)

    schema_version: int = Field(
        default=CURRENT_CONFIG_SCHEMA_VERSION,
        alias="_schema_version",
    )
    provider: ProviderConfig = ProviderConfig()
    agent: AgentConfig = AgentConfig()
    approval: ApprovalConfig = ApprovalConfig()
    gateway: GatewayConfig = GatewayConfig()
    channels: ChannelsConfig = ChannelsConfig()
    oauth: OAuthConfig = OAuthConfig()
    observability: ObservabilityConfig = ObservabilityConfig()
    sandbox: SandboxConfig = SandboxConfig()
    connectors: dict[str, WarehouseConnectorSettings] = Field(default_factory=dict)


def _string_option(
    options: dict[str, ConnectorOptionScalar],
    key: str,
    *,
    aliases: tuple[str, ...] = (),
    default: str = "",
) -> str:
    if key in options and options[key] not in (None, ""):
        return str(options[key])
    for alias in aliases:
        if alias in options and options[alias] not in (None, ""):
            return str(options[alias])
    return default
