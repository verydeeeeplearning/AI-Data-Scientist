# S4 — Changelog

**Stream**: S4 (v13 SQLite central migration runner)
**Date**: 2026-04-17

## Chronological record

1. Read `FIX_SPRINT_WORK_ORDER.md` §1 and §6 for scope and constraints.
2. Read A04 audit report and `A04_sqlite_inventory.json` to confirm baseline:
   learning=1, task_contract=10, work_object=12, semantic=7; aggregate max = 12;
   `plan_claim_v13_satisfied=false`.
3. Read each store's migration implementation:
   - `infrastructure/persistence/work_object_store.py` (v11 + v12 markers)
   - `infrastructure/persistence/task_contract_store.py` (v5, v6, v10)
   - `infrastructure/persistence/learning_store.py` (v1 only)
   - `memory/semantic/infrastructure/sqlite_base.py` (v6, v7)
4. Reviewed S3's scope (`S3_drift_cleanup/START.json`) — S3 updates assertions in
   `test_sqlite_work_object_store.py` (11→12) and `test_migration_v6.py` (6→7).
   These test files are S3-owned and must not be touched by S4.
5. Selected v13 owner: `learning_store`. Rationale:
   isolated DB, no conflicting test assertions, lowest collision risk with S3.
   Documented in `RECOMMENDATIONS.md`.
6. Selected v13 schema change: add `description TEXT` column to
   `schema_migrations` table (additive, defensive audit column).
7. Wrote `START.json` capturing decision and plan.
8. RED: authored `tests/integration/infrastructure/test_central_migration_runner.py`
   with 6 test cases:
   - inventory structure / coverage
   - aggregate max == 13
   - per-store fresh-DB migration reaches target
   - idempotency (two invocations produce identical schema_migrations rows)
   - backward load (v13 owner stamped at v1 → runner advances to v13)
   - `StoreMigration` dataclass frozen / structural contract
   Confirmed RED via `pytest … -v` (collection ModuleNotFoundError as expected).
9. GREEN: added v13 migration to `learning_store.py`:
   - Bumped `_SCHEMA_VERSION` constant to 13.
   - Added `_apply_v13()` method with idempotent ALTER TABLE guard via
     `PRAGMA table_info`, v1 description backfill, and v13 row stamp.
   - Modified `_migrate()` to call `_apply_v13` when `current < 13`.
10. GREEN: created `src/ds_agent/infrastructure/migration/sqlite_migrations.py`:
    - Frozen `StoreMigration` dataclass.
    - `STORE_MIGRATIONS` list (learning=13, task_contract=10, work_object=12,
      semantic=7).
    - `migration_inventory()` pure function.
    - `run_all_migrations(connections)` function — iterates registry, skips
      missing entries, returns observed terminal versions.
    - Lazy imports for adapter classes to avoid circular imports.
11. GREEN: extended `src/ds_agent/infrastructure/migration/__init__.py` to
    re-export the new symbols alongside the existing `CONFIG_MIGRATIONS` exports.
12. Ran the new test file: 6 PASSED.
13. Ran existing migration-adjacent tests (learning/work_object/task_contract/
    semantic): 18 PASSED — no regressions.
14. Ran ruff check and format on S4 scope: CLEAN.
15. Ran mypy on S4 scope: CLEAN (`Success: no issues found in 4 source files`).
16. Ran full `tests/integration/` + migration-runner + config suite: 254 PASSED,
    5 skipped, 0 failures.
17. Ran full `pytest -q` regression: 22 failures + 11 errors, all pre-existing
    and unrelated to S4 (verified by running failing files in isolation — they
    PASS alone; only Windows tmp_path permission races and pre-existing
    non-migration bugs manifest in full-suite mode).
18. Wrote `RECOMMENDATIONS.md` with decision rationale, rollback plan, and
    follow-up suggestions (not implemented).
19. Wrote `DIFF_SUMMARY.md` documenting exact files added/modified/untouched.
20. Wrote `TEST_RESULTS.md` documenting all verification outcomes.
21. Wrote this `CHANGELOG.md`.
22. Wrote `FINAL.json` capturing stream completion state.

## Deviations from plan

- **Did not modify `factory.py`**: the work order noted it as a possible
  integration point but flagged concurrency with S1. Analysis showed no
  integration change was necessary — each store's constructor already triggers
  its idempotent `_migrate()` / `_initialize()` method at runtime, so the
  central runner serves as an *audit façade* (for tests, ops tooling, and
  future CLI diagnostics) rather than a runtime wiring change. This is the
  minimum-viable integration and avoids any collision with S1.
- **Version numbering for learning_store jumps from v1 to v13**: intentional.
  The learning store had no schema changes between releases 1 and 13; the v13
  row documents the audit-column addition introduced by this fix sprint.
  Alternative (dense backfill of v2..v12 no-op rows) was considered and
  rejected as cosmetic churn — see `RECOMMENDATIONS.md` §6.
