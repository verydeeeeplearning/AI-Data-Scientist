# A04 Migration & Config — Re-audit Report (Round 2)

**Agent**: A04-reaudit
**Date**: 2026-04-17
**Baseline FINAL**: `Docs/qa_run_2026-04-17/A04_migration/FINAL.json` (status = **fail**)
**Fix Sprint Inputs**: S3 (drift cleanup), S4 (v13 migration)
**Verdict**: **PASS**

---

## 1. Baseline Issues & Resolution Status

| ID | Description | Baseline Value | Re-audit Value | Resolved |
|----|-------------|----------------|----------------|----------|
| F1 | `test_sqlite_work_object_store` expected v11 | fail (expected 11) | assertion updated → expects 12; test passes | Yes |
| F2 | `test_migration_v6` expected v6 | fail (expected 6) | assertion updated → expects 7; test passes | Yes |
| F3 | plan claim v13 not satisfied; no central v13 runner | `observed_max=12`, runner missing | `observed_max=13`, central runner exists, 6 new tests pass | Yes |

All 3 prior failures are resolved.

---

## 2. Plan §4.4 Re-execution Evidence

### 2.1 Central runner inventory

```json
{
  "migration_inventory": {
    "learning_store": 13,
    "task_contract_store": 10,
    "work_object_store": 12,
    "semantic_store": 7
  },
  "aggregate_max_target": 13,
  "observed_max_schema_version": 13,
  "v13_owner_store": "learning_store"
}
```

See `sqlite_inventory_reaudit.json` for the full dump.

### 2.2 Idempotency

Second invocation of `run_all_migrations` on already-migrated DBs produced identical schema_migrations rows (version + applied_at). **No drift on second run.**

### 2.3 Backward load

Seeded `learning_store` DB with only `schema_migrations` table at v1; ran `run_all_migrations` → learning_store reached v13 and all other stores reached their target versions. **Backward-load path works.**

### 2.4 Pydantic config rejection

Re-ran 3 invalid fixtures via `ds_agent.config.loader.load_config`:
- `invalid_agent_mode.yaml` → `ValidationError` (literal_error on agent.mode)
- `invalid_max_iterations.yaml` → `ValidationError` (int_parsing)
- `invalid_connector.yaml` → `ValidationError` (Connector settings require 'database')

All 3 rejected.

### 2.5 Dependency lock

```
uv lock --check     → exit 0 ("Resolved 178 packages in 2ms")
uv sync --extra all --locked --dry-run → exit 0
```

### 2.6 Feature-flag defaults (off with empty env)

Verified both `DS_AGENT_PORTFOLIO_ENABLED` and `DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1` are **off** when env var is unset — call-site check in `portfolio_tools.py`, `learning_tools.py`, `prompt_builder.py` requires value in `{"1","true","yes"}`.

---

## 3. Test Execution

| Suite | Command | Result |
|-------|---------|--------|
| Central runner (new) | `pytest tests/integration/infrastructure/test_central_migration_runner.py` | 6 passed (after 1 spurious flake on first run; 3 consecutive reruns all green) |
| Drift-fix targets | `pytest test_sqlite_work_object_store.py test_migration_v6.py test_sqlite_learning_store.py test_sqlite_task_contract_store.py` | 18 passed |
| Full migration scope | `pytest tests/integration/infrastructure/ tests/integration/semantic/ tests/unit/application/test_migration_runner.py tests/unit/infrastructure/test_config.py` | **107 passed, 5 skipped, 0 failed** |

Flake note: the 6-case central runner file flaked once with `no such table: schema_migrations` on one sub-test (`test_run_all_migrations_reaches_target_for_each_store`) in the first run; it then passed cleanly in 3 consecutive full-file reruns and every isolated single-case run. Direct in-process reproduction (outside pytest) succeeded every time and produced the correct terminal versions `{learning_store:13, task_contract_store:10, work_object_store:12, semantic_store:7}`. Classified as a Windows .tmp file-handle flake consistent with the work-order guidance.

---

## 4. Scope Guardrail Verification

### S3 (drift cleanup)
Per S3 FINAL.json: only assertion values in 2 test files touched (plus 3 tool files out of A04 scope). Verified:
- `tests/integration/infrastructure/test_sqlite_work_object_store.py` line 139 now asserts `version == 12`.
- `tests/integration/semantic/test_migration_v6.py` line 43 now asserts `version == 7`.

### S4 (v13 migration) — critical scope check
Plan constraint: S4 must NOT modify store migration code in `work_object_store.py`, `task_contract_store.py`, or semantic `sqlite_base.py`.

Verified:
- `src/ds_agent/infrastructure/persistence/work_object_store.py`: mtime 2026-04-16 21:04 (pre-dates S4); no `v13` markers; terminal version in code still 12.
- `src/ds_agent/infrastructure/persistence/task_contract_store.py`: mtime 2026-04-16 13:02 (pre-dates S4); terminal version still 10.
- `src/ds_agent/memory/semantic/infrastructure/sqlite_base.py`: mtime 2026-04-16 16:24 (pre-dates S4); no `v13` markers; terminal version still 7.

S4 additions (confirmed):
- **New** `src/ds_agent/infrastructure/migration/sqlite_migrations.py` — central runner (`STORE_MIGRATIONS`, `StoreMigration`, `migration_inventory`, `run_all_migrations`).
- **Modified** `src/ds_agent/infrastructure/migration/__init__.py` — re-exports central runner API.
- **Modified** `src/ds_agent/infrastructure/persistence/learning_store.py` — added v13 migration `_apply_v13` (adds nullable `description TEXT` column to `schema_migrations` + backfill + v13 row).
- **New** `tests/integration/infrastructure/test_central_migration_runner.py` — 6 test cases.

**Scope respected**: true.

---

## 5. Regression Check vs Baseline Passing Items

| Prior pass | Baseline | Re-audit | Regressed |
|-----------|----------|----------|-----------|
| `uv_lock_check_exit_code` | 0 | 0 | no |
| `uv_sync_all_extras_locked_dry_run_exit_code` | 0 | 0 | no |
| `invalid_config_cases_with_validation_error` | 3/3 | 3/3 | no |
| `feature_flags_default_off` | both true | both true | no |
| Existing migration tests (learning_store, task_contract_store CRUD, semantic repos) | pass | pass | no |

---

## 6. Final Verdict

All pass criteria met:
- `observed_max_schema_version == 13`
- `central_sqlite_v13_runner_found == true`
- `plan_claim_v13_satisfied == true`
- Work object v11→v12 drift resolved
- Semantic v6→v7 drift resolved
- uv_lock / config validation / feature-flag regression: none
- S3/S4 respected their scope constraints

**Status**: PASS.
