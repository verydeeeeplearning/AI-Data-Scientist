# S6 Diff Summary — Rollback Atomicity Fix

## Files changed

| File | Kind | Lines added (net) | Rationale |
|------|------|-------------------|-----------|
| `src/ds_agent/application/ports/learning_store_port.py` | **NEW** | +70 | Declares `LearningStoreAtomicPort` Protocol at application layer. Keeps the atomicity concern out of the shared domain `LearningStore` Protocol while preserving the `application_independence_from_infrastructure` import-linter contract. |
| `src/ds_agent/application/learning/rollback_promotion.py` | modified | +15 / -5 | Use case now delegates the two-row persist to `store.save_item_and_deprecation(...)` (single atomic call) instead of calling `save_item` + `save_deprecation_record` as two separate commits. Extended docstring describes the atomicity contract. |
| `src/ds_agent/infrastructure/persistence/learning_store.py` | modified | +80 / -0 | `SqliteLearningStore.save_item_and_deprecation(...)` — wraps both INSERTs in a single `BEGIN IMMEDIATE … COMMIT` block. On any exception, rolls back via `contextlib.suppress(sqlite3.Error)` so the original exception is re-raised while both rows are left in their pre-call state. `import contextlib` added. |
| `tests/unit/application/test_rollback_atomicity.py` | **NEW** | +205 | New scope-isolated test file (one file, two suites): `TestRollbackAtomicity` verifies use-case-level atomicity with a mocked store; `TestSqliteStoreAtomicity` verifies storage-level atomicity on a real `SqliteLearningStore` against `tmp_path` (no production DB). |
| `tests/unit/application/test_rollback_promotion.py` | test-only adjustment | +7 / -2 | `test_rollback_transitions_to_deprecated` previously asserted the now-deprecated two-call pattern (`save_item` + `save_deprecation_record`). Updated to assert the new single-call pattern (`save_item_and_deprecation`). Behavioural asserts on `updated.status` and `dep_record.notes` are unchanged. Other three tests in the file are untouched. |

## Why no domain changes

`src/ds_agent/domain/interfaces/learning.py` (the existing `LearningStore`
Protocol) is intentionally **not modified**:

* Work-order constraint §3.6 forbids domain-layer changes.
* The atomicity contract is an *application*-level invariant (it exists
  because a specific use case needs the two rows co-committed), so the
  port belongs in `application/ports/`.
* The concrete `SqliteLearningStore` honours both Protocols — the
  domain one via structural typing (existing) and the new application
  one via the new method (verified by `isinstance(store,
  LearningStoreAtomicPort)` in the new SQLite test).

## Why no other use cases changed

REFACTOR-scan (see `RECOMMENDATIONS.md`) found three additional
double-write sites (`PromoteLearningItemUseCase`,
`DeprecateLearningItemUseCase`, `ReviewLearningItemUseCase`). Per
work-order scope they are **out of scope for S6** — recorded as
recommendations for a follow-up stream.
