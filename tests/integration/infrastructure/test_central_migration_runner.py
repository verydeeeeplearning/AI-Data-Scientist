"""Integration tests for the central SQLite migration runner.

Covers Fix Sprint S4 requirements (A04-F3):
- migration_inventory() reports per-store target versions
- run_all_migrations() is idempotent
- aggregate maximum version across registered stores is 13
- backward load: partial state (e.g. learning_store stuck at v1) recovers to v13
- per-store current version probe works on a fresh empty database
"""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import pytest

from ds_agent.infrastructure.migration.sqlite_migrations import (
    STORE_MIGRATIONS,
    StoreMigration,
    migration_inventory,
    run_all_migrations,
)


@pytest.fixture
def store_paths(tmp_path: Path) -> dict[str, Path]:
    """Return a mapping {store_name -> fresh empty sqlite path}."""
    suffix = uuid.uuid4().hex[:8]
    return {
        spec.store_name: tmp_path / f"{spec.store_name}_{suffix}.db" for spec in STORE_MIGRATIONS
    }


def _max_version(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return 0 if row is None or row[0] is None else int(row[0])


def test_migration_inventory_reports_target_versions_for_each_store() -> None:
    inventory = migration_inventory()

    assert isinstance(inventory, dict)
    # Every registered store must appear in the inventory
    assert set(inventory.keys()) == {spec.store_name for spec in STORE_MIGRATIONS}
    # Inventory reports each registered store's target version
    for spec in STORE_MIGRATIONS:
        assert inventory[spec.store_name] == spec.target_version


def test_aggregate_max_target_version_is_thirteen() -> None:
    """A04-F3: observed_max_schema_version must be 13.

    At least one store in the central registry must own v13.
    """
    inventory = migration_inventory()
    assert max(inventory.values()) == 13
    # At least one store declares v13 as its target
    assert any(spec.target_version == 13 for spec in STORE_MIGRATIONS)


def test_run_all_migrations_reaches_target_for_each_store(
    store_paths: dict[str, Path],
) -> None:
    """Empty DBs migrate up to each store's declared target version."""
    result = run_all_migrations(store_paths)

    # run_all_migrations returns {store_name: final_version}
    for spec in STORE_MIGRATIONS:
        assert result[spec.store_name] == spec.target_version
        assert _max_version(store_paths[spec.store_name]) == spec.target_version

    # Aggregate max across results is 13
    assert max(result.values()) == 13


def test_run_all_migrations_is_idempotent(store_paths: dict[str, Path]) -> None:
    """Second invocation must produce identical state (no schema churn)."""
    first = run_all_migrations(store_paths)
    # Capture a snapshot of schema_migrations rows per store
    snapshots_before: dict[str, list[tuple[int, str]]] = {}
    for name, path in store_paths.items():
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT version, applied_at FROM schema_migrations ORDER BY version"
            ).fetchall()
        snapshots_before[name] = [(int(r[0]), str(r[1])) for r in rows]

    second = run_all_migrations(store_paths)

    assert first == second

    for name, path in store_paths.items():
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT version, applied_at FROM schema_migrations ORDER BY version"
            ).fetchall()
        rows_typed = [(int(r[0]), str(r[1])) for r in rows]
        assert rows_typed == snapshots_before[name], (
            f"schema_migrations for store {name} changed across idempotent runs"
        )


def test_backward_load_from_partial_state_advances_to_target(
    tmp_path: Path,
) -> None:
    """Simulate a pre-v13 DB for the v13 owner and verify run_all advances it.

    We pick the store that owns the v13 target, manually stamp its
    schema_migrations table at an earlier version (v1 for the isolated
    learning-like owner; otherwise the lowest intermediate target minus 1),
    then run the runner and assert it reaches target_version == 13.
    """
    # Identify the store that owns v13
    v13_owner = next(spec for spec in STORE_MIGRATIONS if spec.target_version == 13)

    store_paths = {
        spec.store_name: tmp_path / f"{spec.store_name}_partial.db" for spec in STORE_MIGRATIONS
    }

    # Seed the v13 owner's DB at an earlier version (v1 — bootstrap only
    # the schema_migrations table, not the owner's real schema; the runner
    # must detect the gap and apply the remaining migrations, including v13).
    v13_path = store_paths[v13_owner.store_name]
    with sqlite3.connect(v13_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO schema_migrations(version, applied_at) "
            "VALUES (1, datetime('now'))"
        )
        conn.commit()

    result = run_all_migrations(store_paths)

    assert result[v13_owner.store_name] == 13
    assert _max_version(v13_path) == 13


def test_store_migration_dataclass_is_frozen_and_has_required_fields() -> None:
    """Contract test: StoreMigration is an immutable registry record."""
    from dataclasses import FrozenInstanceError

    for spec in STORE_MIGRATIONS:
        assert isinstance(spec, StoreMigration)
        # Frozen: attempting to mutate must raise FrozenInstanceError
        with pytest.raises(FrozenInstanceError):
            spec.target_version = spec.target_version  # type: ignore[misc]
