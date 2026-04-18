"""Config store schema migrations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import structlog

from ds_agent.application.migration import MigrationSpec
from ds_agent.config.schema import CURRENT_CONFIG_SCHEMA_VERSION

logger = structlog.get_logger()


def migrate_config_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Remove legacy plaintext provider API key fields and stamp schema v2."""
    migrated = deepcopy(data)
    provider = migrated.get("provider")
    removed_keys = False
    if isinstance(provider, dict) and "api_keys" in provider:
        provider = deepcopy(provider)
        provider.pop("api_keys", None)
        migrated["provider"] = provider
        removed_keys = True
    migrated["_schema_version"] = 2
    logger.info(
        "config_migration_v1_to_v2",
        removed_legacy_api_keys=removed_keys,
    )
    return migrated


def migrate_config_v2_to_v3(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize connector settings into core fields plus type-specific options."""
    migrated = deepcopy(data)
    connectors = migrated.get("connectors")
    if not isinstance(connectors, dict):
        migrated["_schema_version"] = 3
        return migrated

    normalized_connectors: dict[str, Any] = {}
    core_keys = {
        "type",
        "label",
        "options",
        "credential_method",
        "credential_ref",
        "read_only",
        "timeout_seconds",
        "max_rows",
    }

    for name, raw_settings in connectors.items():
        if not isinstance(raw_settings, dict):
            normalized_connectors[name] = raw_settings
            continue

        connector_type = raw_settings.get("type")
        settings = deepcopy(raw_settings)
        options = dict(settings.get("options") or {})

        for key in list(settings):
            if key in core_keys:
                continue
            if key == "schema_name":
                if settings[key] not in (None, ""):
                    options.setdefault("schema", settings[key])
                continue
            if key == "database":
                database_key = "project_id" if connector_type == "bigquery" else "database"
                if settings[key] not in (None, ""):
                    options.setdefault(database_key, settings[key])
                continue
            if settings[key] not in (None, ""):
                options.setdefault(key, settings[key])

        normalized_connectors[name] = {
            "type": connector_type,
            "label": str(settings.get("label") or name),
            "credential_method": settings.get("credential_method", "env"),
            "credential_ref": settings.get("credential_ref", ""),
            "read_only": bool(settings.get("read_only", True)),
            "timeout_seconds": int(settings.get("timeout_seconds", 30)),
            "max_rows": int(settings.get("max_rows", 10_000)),
            "options": options,
        }

    migrated["connectors"] = normalized_connectors
    migrated["_schema_version"] = 3
    logger.info(
        "config_migration_v2_to_v3",
        normalized_connectors=len(normalized_connectors),
    )
    return migrated


def migrate_config_v3_to_v4(data: dict[str, Any]) -> dict[str, Any]:
    """Add observability defaults for crash reporting and telemetry controls."""

    migrated = deepcopy(data)
    observability = migrated.get("observability")
    normalized = dict(observability) if isinstance(observability, dict) else {}
    normalized.setdefault("sentry_dsn", None)
    normalized.setdefault("sentry_environment", "production")
    normalized.setdefault("telemetry_enabled", False)
    normalized.setdefault("error_reporting_enabled", False)
    migrated["observability"] = normalized
    migrated["_schema_version"] = CURRENT_CONFIG_SCHEMA_VERSION
    logger.info("config_migration_v3_to_v4", added_observability_defaults=True)
    return migrated


CONFIG_MIGRATIONS: list[MigrationSpec] = [
    MigrationSpec(
        store="config",
        from_version=1,
        to_version=2,
        description="Remove legacy provider.api_keys and add schema version.",
        migrate=migrate_config_v1_to_v2,
    ),
    MigrationSpec(
        store="config",
        from_version=2,
        to_version=3,
        description="Normalize connector settings into core fields plus options.",
        migrate=migrate_config_v2_to_v3,
    ),
    MigrationSpec(
        store="config",
        from_version=3,
        to_version=CURRENT_CONFIG_SCHEMA_VERSION,
        description="Add observability defaults for crash reporting and telemetry.",
        migrate=migrate_config_v3_to_v4,
    ),
]
