"""Central SQLite migration inventory and runner.

Fix Sprint S4 (A04-F3): aggregates per-store SQLite migrations into a single,
machine-auditable plan. Each registered store exposes ``target_version`` plus
two callables — ``current_version_fn(db_path)`` probes the on-disk schema
version, and ``apply_fn(db_path)`` applies pending migrations up to the
store's target version (idempotently).

The module deliberately depends only on the persistence-layer adapters; it
does **not** import anything from the domain or application layers.
Composition is passive: instantiating each adapter's ``Sqlite*Store`` class
triggers the adapter's own ``_migrate()`` / ``_initialize()`` flow, which is
already idempotent. The central runner wraps those flows with a uniform API
and surfaces a single aggregate view (``migration_inventory``) that callers
(tests, ops tooling, audits) can use to verify the plan-level ``v1~v13``
claim from one place.

The aggregate maximum target version across registered stores is ``13``,
owned by ``learning_store`` (see
``Docs/qa_run_2026-04-17/S4_v13_migration/RECOMMENDATIONS.md`` for the
decision rationale).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path


def _schema_version_of(db_path: Path) -> int:
    """Read the terminal ``schema_migrations.version`` from a SQLite file.

    Returns ``0`` when the file does not exist yet, the table is missing, or
    the table is empty. Safe to call against a path that points at either a
    fresh empty DB or a partially-migrated one.
    """
    path = Path(db_path)
    if not path.exists():
        return 0
    with sqlite3.connect(path) as conn:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        if exists is None:
            return 0
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    if row is None or row[0] is None:
        return 0
    return int(row[0])


def _apply_learning_store(db_path: Path) -> None:
    """Instantiate ``SqliteLearningStore`` so its ``_migrate()`` runs."""
    # Import locally to keep this module free of top-level persistence coupling
    # and to sidestep circular-import risk at package import time.
    from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore

    SqliteLearningStore(db_path)


def _apply_task_contract_store(db_path: Path) -> None:
    """Instantiate ``SqliteTaskContractStore`` so its ``_initialize()`` runs."""
    from ds_agent.infrastructure.persistence.task_contract_store import (
        SqliteTaskContractStore,
    )

    SqliteTaskContractStore(db_path)


def _apply_work_object_store(db_path: Path) -> None:
    """Instantiate ``SqliteWorkObjectStore`` so its ``_initialize()`` runs.

    This also triggers the underlying ``SqliteTaskContractStore`` migrations
    because the two stores share the same physical database file.
    """
    from ds_agent.infrastructure.persistence.work_object_store import (
        SqliteWorkObjectStore,
    )

    SqliteWorkObjectStore(db_path)


def _apply_semantic_store(db_path: Path) -> None:
    """Instantiate ``SemanticSqliteDatabase`` so its ``_initialize()`` runs."""
    from ds_agent.memory.semantic.infrastructure.sqlite_base import (
        SemanticSqliteDatabase,
    )

    SemanticSqliteDatabase(db_path)


@dataclass(frozen=True)
class StoreMigration:
    """Immutable registry record for a single SQLite-backed store.

    Attributes:
        store_name:
            Stable identifier used as the inventory key. Must be unique across
            registered stores.
        target_version:
            The terminal ``schema_migrations.version`` this store advances to
            after ``apply`` is invoked against a fresh database.
        current_version:
            Function ``(db_path) -> int`` that returns the on-disk terminal
            version of the store, or ``0`` when the database has not yet been
            initialized.
        apply:
            Function ``(db_path) -> None`` that applies pending migrations
            for this store, idempotently. Must not raise when invoked against
            a fully migrated database.
    """

    store_name: str
    target_version: int
    current_version: Callable[[Path], int]
    apply: Callable[[Path], None]


# The aggregate maximum target version across STORE_MIGRATIONS must be 13.
# learning_store owns v13; its schema change is additive (see module docstring
# and the RECOMMENDATIONS.md decision record). Other stores keep their
# established per-store targets — this registry does not retrofit them.
STORE_MIGRATIONS: list[StoreMigration] = [
    StoreMigration(
        store_name="learning_store",
        target_version=13,
        current_version=_schema_version_of,
        apply=_apply_learning_store,
    ),
    StoreMigration(
        store_name="task_contract_store",
        target_version=10,
        current_version=_schema_version_of,
        apply=_apply_task_contract_store,
    ),
    StoreMigration(
        store_name="work_object_store",
        target_version=12,
        current_version=_schema_version_of,
        apply=_apply_work_object_store,
    ),
    StoreMigration(
        store_name="semantic_store",
        target_version=7,
        current_version=_schema_version_of,
        apply=_apply_semantic_store,
    ),
]


def migration_inventory() -> dict[str, int]:
    """Return a ``{store_name: target_version}`` snapshot of the registry.

    Pure — does not touch disk. Useful for audits, CLI diagnostics, and test
    assertions that verify the plan-level version claim holds independently
    of any particular database instance.
    """
    return {spec.store_name: spec.target_version for spec in STORE_MIGRATIONS}


def run_all_migrations(
    connections: Mapping[str, str | Path],
) -> dict[str, int]:
    """Apply pending migrations for every registered store.

    Args:
        connections:
            Mapping from ``store_name`` (as declared in ``STORE_MIGRATIONS``)
            to the SQLite database path the adapter should migrate. Stores
            omitted from the mapping are skipped — this makes partial runs
            (e.g. a single-store upgrade in a test) possible without forcing
            the caller to allocate databases they do not use.

    Returns:
        Mapping from ``store_name`` to the terminal ``schema_migrations``
        version observed on disk after migrations run.

    Idempotency:
        Invoking this function twice with the same arguments is safe — each
        registered adapter's ``_migrate()`` / ``_initialize()`` method is
        already idempotent.
    """
    result: dict[str, int] = {}
    for spec in STORE_MIGRATIONS:
        raw_path = connections.get(spec.store_name)
        if raw_path is None:
            continue
        db_path = Path(raw_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        spec.apply(db_path)
        result[spec.store_name] = spec.current_version(db_path)
    return result


__all__ = [
    "STORE_MIGRATIONS",
    "StoreMigration",
    "migration_inventory",
    "run_all_migrations",
]
