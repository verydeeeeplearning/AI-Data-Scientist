# S4 — v13 Migration Scope Decision

**Stream**: S4 (SQLite central migration runner + v13 introduction)
**Date**: 2026-04-17
**Author**: Fix Sprint S4 agent
**Status**: Decision recorded

## 1. Problem

A04 audit (§4.3) found:

- `src/ds_agent/infrastructure/migration/` contained only `config_migrations.py`
  and `__init__.py` — no central SQLite migration runner.
- Per-store terminal schema versions: `learning_store=1`, `task_contract_store=10`,
  `work_object_store=12`, `semantic_store=7`. Aggregate max = **12**.
- Pre-release plan claimed "v1~v13 SQLite migrations" — not verifiable in code.

User decision (per `FIX_SPRINT_WORK_ORDER.md` §1): **v13 is the source of truth**.
S4 must add v13 in code, not update the plan.

## 2. Decision

**v13 owner**: `learning_store` (`src/ds_agent/infrastructure/persistence/learning_store.py`).

**v13 schema change**: Additive — adds a nullable `description TEXT` column to the
`schema_migrations` table, backfills the v1 row, and stamps a v13 row whose
`description` documents the migration intent. No changes to any domain table.

## 3. Rationale for Choosing `learning_store`

We evaluated four candidate owners against three constraints:

| Constraint | Detail |
|-----------|--------|
| **C1** | Must not break S3-owned test files (`test_sqlite_work_object_store.py`, `test_migration_v6.py`) |
| **C2** | Must not touch other existing per-store migrations (work_order §6 scope) |
| **C3** | Must result in observed_max_schema_version == 13 |

| Candidate | terminal | existing test assertion | Verdict |
|-----------|----------|-------------------------|---------|
| `work_object_store` | 12 | `test_sqlite_work_object_store.py` asserts `version == 12` (S3-owned) | REJECTED — would silently break S3 once both streams merge |
| `task_contract_store` | 10 | `test_sqlite_task_contract_store.py` asserts `version == 10` | REJECTED — not S3-owned but would need matching assertion update, and its DB file is shared with `work_object_store`, contaminating that DB's terminal version too |
| `semantic_store` | 7 | `test_migration_v6.py` asserts `version == 7` (S3-owned) | REJECTED — same S3 collision risk |
| `learning_store` | 1 | No `schema_migrations` version assertion in `test_sqlite_learning_store.py` | **SELECTED** — isolated DB file, no test assertion to collide with, safe to jump to v13 |

`learning_store` has the largest version gap (1→13), but the jump is conceptually
a single additive migration (not 12 hidden migrations). The implementation
applies v1 (unchanged) and v13 in sequence; intermediate versions v2..v12 are
intentionally unused in this store. This matches the reality that learning
governance did not evolve schema-wise between release 1 and 13.

## 4. Rationale for Choosing "add `description` column"

We evaluated three candidate schema changes:

| Candidate | Verdict |
|-----------|---------|
| Rebuild/re-index portfolio-related tables | REJECTED — real schema change with runtime risk, premature for a version sync |
| Add `applied_at_utc` alongside existing `applied_at` | REJECTED — existing `applied_at` is already TEXT ISO-8601 UTC; duplicate |
| **Add `description TEXT` to `schema_migrations`** | **SELECTED** — defensive, audit-only, backward-compatible |

The `description` column:

- Is nullable (backward-compatible reads don't break).
- Is surfaced through the central inventory in `sqlite_migrations.py` so future
  runs can record per-migration intent alongside the version number.
- Documents the intent of v13 itself in its own row (`v13: add audit description
  column to schema_migrations for central runner traceability`).
- Creates a defensible audit trail for the central runner concept introduced in
  S4 without forcing unrelated domain-schema churn.

This is the change listed in `FIX_SPRINT_WORK_ORDER.md` §9 Contingency as
"가장 방어 가능한 변경" when scope is unclear.

## 5. What was NOT changed (scope guardrails)

- `src/ds_agent/infrastructure/persistence/work_object_store.py` — untouched
  (owned v11/v12 migrations remain byte-identical).
- `src/ds_agent/infrastructure/persistence/task_contract_store.py` — untouched.
- `src/ds_agent/memory/semantic/infrastructure/sqlite_base.py` — untouched.
- `tests/integration/infrastructure/test_sqlite_work_object_store.py` — S3 scope,
  not modified here.
- `tests/integration/semantic/test_migration_v6.py` — S3 scope, not modified here.
- `src/ds_agent/agent/factory.py` — no modification required. Existing
  composition root already instantiates each store, which triggers that store's
  idempotent `_migrate()` / `_initialize()` flow. The central runner is
  additive: it exposes `migration_inventory()` and `run_all_migrations()` as an
  *auditable* façade for ops tooling and tests, but runtime wiring of the agent
  is unchanged. This also avoided conflict with S1, which may modify
  `factory.py` in parallel.
- No domain-layer changes.

## 6. Follow-up recommendations (NOT implemented here)

These are observations outside S4 scope; they are not changes.

1. **Unify per-store migration tables under a single `schema_migrations`
   convention**. Each store has its own `schema_migrations` table on a
   possibly-separate DB file. A future round could introduce a uniform
   `store_name` column to enable cross-store joins for audit dashboards.
2. **Expose a CLI subcommand** (`ds-agent migrate status`) that prints
   `migration_inventory()` + per-store `current_version(db_path)` deltas,
   so operators can see schema drift at a glance without opening sqlite.
3. **Retrofit old stores** to record `description` too. Currently only the
   learning store's v13 carries descriptions; work_object, task_contract, and
   semantic stores still use the v1-style `(version, applied_at)` shape. A
   later round can add `description` to those tables if the audit pattern
   proves valuable. This is intentionally left out of S4 because the
   work_order forbids touching other stores' migrations.
4. **Consider dense version numbering**. The learning store's jump from v1 to
   v13 is legal (SQLite doesn't care) but cosmetically odd. A future round
   could either (a) backfill intermediate "no-op" rows v2..v12 for continuity,
   or (b) adopt a sparse-version-with-changelog convention across all stores.
   S4 deliberately does neither to keep the change minimal and reversible.

## 7. Rollback Plan

If v13 is later found undesirable:

1. Drop the central runner module:
   `rm src/ds_agent/infrastructure/migration/sqlite_migrations.py`
2. Revert `src/ds_agent/infrastructure/migration/__init__.py` to its pre-S4
   exports.
3. Revert the `_apply_v13` block and `_SCHEMA_VERSION = 13` constant in
   `src/ds_agent/infrastructure/persistence/learning_store.py` to
   `_SCHEMA_VERSION = 1` and remove the `_apply_v13` method.
4. Delete `tests/integration/infrastructure/test_central_migration_runner.py`.

The v13 `description` column addition is non-destructive (ALTER TABLE ADD
COLUMN with nullable TEXT). Existing learning-store DBs that have v13 applied
remain readable after rollback because the column is simply ignored.

---

**Summary**: v13 is owned by `learning_store`, applied as an additive audit
column on `schema_migrations`. The central runner in
`src/ds_agent/infrastructure/migration/sqlite_migrations.py` aggregates
per-store migrations (no runtime wiring change) so A04 can verify
`observed_max_schema_version == 13` from a single inventory.
