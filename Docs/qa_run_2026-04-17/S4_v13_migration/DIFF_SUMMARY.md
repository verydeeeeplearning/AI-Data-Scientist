# S4 — Diff Summary

**Stream**: S4 (v13 SQLite central migration runner)
**Date**: 2026-04-17

## Files Changed

### New files (3)

| Path | Type | Purpose |
|------|------|---------|
| `src/ds_agent/infrastructure/migration/sqlite_migrations.py` | new | Central migration registry + `migration_inventory()` + `run_all_migrations()` |
| `tests/integration/infrastructure/test_central_migration_runner.py` | new | 6 integration tests validating the central runner (RED → GREEN → passing) |
| `Docs/qa_run_2026-04-17/S4_v13_migration/RECOMMENDATIONS.md` | new | Decision record for v13 owner + schema change |

### Modified files (2)

| Path | Type | Nature of change |
|------|------|-----------------|
| `src/ds_agent/infrastructure/migration/__init__.py` | modify | Re-export `STORE_MIGRATIONS`, `StoreMigration`, `migration_inventory`, `run_all_migrations` |
| `src/ds_agent/infrastructure/persistence/learning_store.py` | modify | Add v13 migration: `_SCHEMA_VERSION` constant updated to 13; new `_apply_v13()` method adds `description TEXT` column to `schema_migrations` and stamps v13 row; v1 row is backfilled with descriptive text. Pure addition — no existing behavior removed |

### Files NOT touched (explicit scope guardrails)

- `src/ds_agent/infrastructure/persistence/work_object_store.py` — owned by S3's assertion updates; its v11/v12 migrations are unchanged.
- `src/ds_agent/infrastructure/persistence/task_contract_store.py` — untouched; v10 remains terminal.
- `src/ds_agent/memory/semantic/infrastructure/sqlite_base.py` — untouched; v7 remains terminal.
- `tests/integration/infrastructure/test_sqlite_work_object_store.py` — S3 scope.
- `tests/integration/semantic/test_migration_v6.py` — S3 scope.
- `src/ds_agent/agent/factory.py` — intentionally not touched. Each store's constructor already triggers its idempotent `_migrate()`/`_initialize()` flow, so the central runner is additive (audit surface). This avoids collision with S1, which also operates in `factory.py`.
- Domain layer — no changes.
- Other streams' files (`application/ports/`, `infrastructure/observability/`, `tools/`) — no changes.

## Key Details

### `sqlite_migrations.py`

- `StoreMigration` — frozen dataclass with four fields: `store_name`, `target_version`, `current_version(db_path)->int`, `apply(db_path)->None`.
- `STORE_MIGRATIONS` — list of 4 entries: learning_store=13, task_contract_store=10, work_object_store=12, semantic_store=7. Aggregate max = 13.
- `migration_inventory()` — pure function, returns `{store_name: target_version}`.
- `run_all_migrations(connections)` — iterates the registry, invokes each store's `apply` callable against the caller-provided DB path, returns observed terminal versions. Idempotent (adapter methods already are).
- Module imports persistence adapters lazily inside each `_apply_*` helper to avoid circular imports at package init time.

### `learning_store.py` v13 migration

- v1 block remains byte-identical. v13 is strictly additive.
- `_apply_v13()`:
  - Adds `description TEXT` nullable column to `schema_migrations` (guarded by `PRAGMA table_info` check — idempotent).
  - Backfills v1 row with `"v1: initial learning governance schema"`.
  - Inserts/replaces v13 row with description
    `"v13: add audit description column to schema_migrations for central runner traceability"`.
- Version jump from v1 → v13 is intentional. The learning store's schema did not change between releases 1 and 13; v13 is purely the audit-column addition. Rationale in `RECOMMENDATIONS.md` §4.
