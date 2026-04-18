from __future__ import annotations

from pathlib import Path

from ds_agent.application.migration import MigrationRunner, MigrationSpec
from ds_agent.config.schema import CURRENT_CONFIG_SCHEMA_VERSION
from ds_agent.infrastructure.migration import CONFIG_MIGRATIONS


def test_no_migration_needed_when_current() -> None:
    runner = MigrationRunner(migrations=CONFIG_MIGRATIONS)

    result = runner.run_for_store(
        "config", {"_schema_version": CURRENT_CONFIG_SCHEMA_VERSION, "provider": {}}
    )

    assert result.success is True
    assert result.migrated_count == 0
    assert result.final_data["_schema_version"] == CURRENT_CONFIG_SCHEMA_VERSION


def test_migration_applied_in_order() -> None:
    migrations = [
        MigrationSpec(
            store="config",
            from_version=1,
            to_version=2,
            description="step 1",
            migrate=lambda data: {**data, "step1": True},
        ),
        MigrationSpec(
            store="config",
            from_version=2,
            to_version=3,
            description="step 2",
            migrate=lambda data: {**data, "step2": True},
        ),
    ]
    runner = MigrationRunner(migrations=migrations)

    result = runner.run_for_store("config", {"_schema_version": 1})

    assert result.success is True
    assert result.migrated_count == 2
    assert result.final_data["_schema_version"] == 3
    assert result.final_data["step1"] is True
    assert result.final_data["step2"] is True


def test_migration_is_idempotent() -> None:
    runner = MigrationRunner(migrations=CONFIG_MIGRATIONS)
    data = {
        "_schema_version": 1,
        "provider": {"api_keys": {"anthropic": "key"}},
    }

    result1 = runner.run_for_store("config", data)
    result2 = runner.run_for_store("config", result1.final_data)

    assert result1.success is True
    assert result1.migrated_count == 3
    assert result1.final_data["_schema_version"] == CURRENT_CONFIG_SCHEMA_VERSION
    assert result1.final_data["observability"]["telemetry_enabled"] is False
    assert result2.success is True
    assert result2.migrated_count == 0


def test_backup_created_before_migration(tmp_path: Path) -> None:
    runner = MigrationRunner(migrations=CONFIG_MIGRATIONS, backup_dir=tmp_path)

    result = runner.run_for_store("config", {"_schema_version": 1, "provider": {}})

    assert result.success is True
    backups = list(tmp_path.glob("config_v1_*.yaml"))
    assert len(backups) == 1


def test_rollback_on_migration_failure(tmp_path: Path) -> None:
    def failing_migrate(data: dict[str, object]) -> dict[str, object]:
        raise ValueError("simulated failure")

    runner = MigrationRunner(
        migrations=[
            MigrationSpec(
                store="config",
                from_version=1,
                to_version=2,
                description="fail",
                migrate=failing_migrate,
            )
        ],
        backup_dir=tmp_path,
    )

    result = runner.run_for_store("config", {"_schema_version": 1, "provider": {}})

    assert result.success is False
    assert result.migrated_count == 0
    assert result.final_data == {"_schema_version": 1, "provider": {}}
    assert result.rolled_back is True
    assert len(result.backed_up_paths) == 1


def test_v3_config_migrates_observability_defaults() -> None:
    runner = MigrationRunner(migrations=CONFIG_MIGRATIONS)

    result = runner.run_for_store("config", {"_schema_version": 3, "provider": {}})

    assert result.success is True
    assert result.migrated_count == 1
    assert result.final_data["_schema_version"] == CURRENT_CONFIG_SCHEMA_VERSION
    assert result.final_data["observability"] == {
        "sentry_dsn": None,
        "sentry_environment": "production",
        "telemetry_enabled": False,
        "error_reporting_enabled": False,
    }
