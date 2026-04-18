"""Generic migration runner for versioned persisted stores."""

from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger()


@dataclass(frozen=True)
class MigrationSpec:
    """Single pure migration step for a logical store."""

    store: str
    from_version: int
    to_version: int
    description: str
    migrate: Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class MigrationResult:
    """Result of applying zero or more migrations to store data."""

    success: bool
    migrated_count: int
    final_data: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    backed_up_paths: list[Path] = field(default_factory=list)
    rolled_back: bool = False


class MigrationRunner:
    """Apply ordered migrations with pre-migration backups."""

    def __init__(
        self,
        migrations: list[MigrationSpec],
        backup_dir: Path | None = None,
    ) -> None:
        self._migrations = migrations
        self._backup_dir = (
            backup_dir
            if backup_dir is not None
            else Path("~/.ds-agent/.migration-backups").expanduser()
        )

    def run_for_store(self, store: str, data: dict[str, Any]) -> MigrationResult:
        """Run all available migrations for a given store payload."""
        initial = deepcopy(data)
        if not initial:
            return MigrationResult(
                success=True,
                migrated_count=0,
                final_data=initial,
            )

        current_version = self._get_schema_version(initial)
        chain = self._resolve_chain(store=store, current_version=current_version)
        if not chain:
            return MigrationResult(
                success=True,
                migrated_count=0,
                final_data=initial,
            )

        backup_path = self._create_backup(
            store=store,
            data=initial,
            version=current_version,
        )
        current = deepcopy(initial)
        migrated_count = 0
        try:
            for spec in chain:
                current = deepcopy(spec.migrate(deepcopy(current)))
                current["_schema_version"] = spec.to_version
                migrated_count += 1
                logger.info(
                    "store_migration_applied",
                    store=store,
                    from_version=spec.from_version,
                    to_version=spec.to_version,
                    description=spec.description,
                )
        except Exception as exc:
            logger.warning(
                "store_migration_failed",
                store=store,
                version=current_version,
                error=str(exc),
            )
            return MigrationResult(
                success=False,
                migrated_count=migrated_count,
                final_data=initial,
                errors=[str(exc)],
                backed_up_paths=[backup_path],
                rolled_back=True,
            )

        return MigrationResult(
            success=True,
            migrated_count=migrated_count,
            final_data=current,
            backed_up_paths=[backup_path],
        )

    def _resolve_chain(self, *, store: str, current_version: int) -> list[MigrationSpec]:
        by_from_version = {
            spec.from_version: spec
            for spec in sorted(
                (migration for migration in self._migrations if migration.store == store),
                key=lambda migration: (migration.from_version, migration.to_version),
            )
        }
        chain: list[MigrationSpec] = []
        version = current_version
        while version in by_from_version:
            spec = by_from_version[version]
            chain.append(spec)
            version = spec.to_version
        return chain

    @staticmethod
    def _get_schema_version(data: dict[str, Any]) -> int:
        version = data.get("_schema_version", 1)
        try:
            return int(version)
        except (TypeError, ValueError):
            return 1

    def _create_backup(
        self,
        *,
        store: str,
        data: dict[str, Any],
        version: int,
    ) -> Path:
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        suffix = ".yaml" if store == "config" else ".json"
        backup_path = self._backup_dir / f"{store}_v{version}_{timestamp}{suffix}"
        if suffix == ".yaml":
            backup_path.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
        else:
            backup_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return backup_path
