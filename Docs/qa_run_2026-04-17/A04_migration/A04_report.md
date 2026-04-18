# A04 — Migration & Config Auditor

**Tier**: 1  
**Duration**: 263 sec  
**Status**: fail  
**Code SHA**: unavailable (`.git` metadata not present in current workspace snapshot)  
**Dependencies**: none

## 1. Scope

- Config migration runner (`MigrationRunner`, `CONFIG_MIGRATIONS`) and config schema v4 loading path
- SQLite-backed schema initialization / migration paths currently implemented in persistence stores
- Invalid YAML / schema validation behavior for config loading
- `uv.lock` / `pyproject.toml` optional dependency consistency
- Feature flag default-off behavior for `DS_AGENT_PORTFOLIO_ENABLED` and `DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1`

## 2. Methodology

- Ran targeted pytest coverage for migration/config paths:
  - `tests/unit/application/test_migration_runner.py`
  - `tests/unit/infrastructure/test_config.py`
  - `tests/integration/infrastructure/test_sqlite_learning_store.py`
  - `tests/integration/infrastructure/test_sqlite_task_contract_store.py`
  - `tests/integration/infrastructure/test_sqlite_work_object_store.py`
  - `tests/integration/semantic/test_migration_v6.py`
- Captured JUnit XML and raw pytest stdout.
- Created invalid config fixtures under `A04_config_fixtures/` and loaded them through `ds_agent.config.loader.load_config(...)` to verify `ValidationError` sharpness.
- Created fresh SQLite databases under `.tmp/qa_A04/` and inspected `schema_migrations` plus table/column inventories after store initialization.
- Checked lockfile consistency with `uv lock --check` and `uv sync --all-extras --locked --dry-run`.

## 3. Results Matrix

| Check | Result | Evidence |
|---|---|---|
| Config migration runner unit suite | pass | `A04_migration_log.txt`, `junit.xml` |
| Config loader / schema v4 unit suite | pass | `A04_migration_log.txt`, `junit.xml` |
| Invalid config cases return sharp `ValidationError` | pass | `A04_config_validation.json` |
| Feature flags default to off when env vars unset | pass | `A04_config_validation.json` |
| `uv.lock` up to date with project metadata | pass | `A04_dependency_check.txt` |
| Optional dependencies resolve in locked dry-run | pass | `A04_dependency_check.txt` |
| SQLite migration test slice | fail | `A04_migration_log.txt`, `junit.xml` |
| Plan claim: SQLite `v1→v13` path exists and is auditable from central migration package | fail | `A04_sqlite_inventory.json`, `A04_sqlite_inventory.txt` |

## 4. Failures and Anomalies

1. `tests/integration/infrastructure/test_sqlite_work_object_store.py::test_sqlite_work_object_store_round_trip_and_migration` failed.
   Repro: run the pytest command captured in `A04_migration_log.txt`.
   Observed: expected `schema_migrations` max version `11`, actual `12`.
   Likely cause: implementation advanced to `_MIGRATION_V11_1_VERSION_SQL -> version 12` in `src/ds_agent/infrastructure/persistence/work_object_store.py`, but the integration assertion still expects the older terminal version.

2. `tests/integration/semantic/test_migration_v6.py::test_semantic_migration_v6_applies_and_is_idempotent` failed.
   Repro: same pytest command.
   Observed: expected `schema_migrations` max version `6`, actual `7`.
   Likely cause: implementation now applies `_MIGRATION_V7_SQL` in `src/ds_agent/memory/semantic/infrastructure/sqlite_base.py`, but the test still asserts the pre-v7 terminal version.

3. The plan requirement "SQLite v1~v13 migration" is not supported by the currently discoverable central migration package.
   Observed:
   - `src/ds_agent/infrastructure/migration/` contains only `config_migrations.py` and `__init__.py`.
   - No explicit central SQLite v13 migration runner was found.
   - Fresh-store inventory shows terminal versions: learning `1`, task contract `10`, work object `12`, semantic `7`.
   - Highest observed schema version is `12`, so the plan-level `v13` claim is not satisfied in code as audited.

## 5. Evidence Index

- `Docs/qa_run_2026-04-17/A04_migration/START.json`
- `Docs/qa_run_2026-04-17/A04_migration/A04_migration_log.txt`
- `Docs/qa_run_2026-04-17/A04_migration/junit.xml`
- `Docs/qa_run_2026-04-17/A04_migration/A04_dependency_check.txt`
- `Docs/qa_run_2026-04-17/A04_migration/A04_config_validation.json`
- `Docs/qa_run_2026-04-17/A04_migration/A04_sqlite_inventory.json`
- `Docs/qa_run_2026-04-17/A04_migration/A04_sqlite_inventory.txt`
- `Docs/qa_run_2026-04-17/A04_migration/A04_config_fixtures/`

## 6. Recommendations

- Treat A04 as `fail` and hold the Tier 1 gate until migration expectations are clarified.
- Decide whether the source of truth is the implementation or the plan:
  - If implementation is correct, update the stale integration tests and the pre-release plan/documentation to the actual distributed schema-version model.
  - If the plan is correct, implement the missing SQLite `v13` migration path and add/repair coverage so the terminal schema version is observable in code and tests.
- Add a single machine-readable migration inventory test so future version bumps cannot drift independently across plan, code, and tests.
