# S6 Changelog — Rollback Atomicity (FAIL-B11-8)

**Stream**: S6 (Fix Sprint Round 3)
**Date**: 2026-04-17
**Addresses**: FAIL-B11-8 (Rollback audit-trail split in
`RollbackPromotionUseCase`)

## What changed

1. **New application-layer port**
   `ds_agent.application.ports.learning_store_port.LearningStoreAtomicPort`
   declares a single method, `save_item_and_deprecation(*, item,
   deprecation)`, for use cases that need co-committed persistence of a
   `LearningItem` update and its matching `DeprecationRecord`.

2. **Use case switch**
   `RollbackPromotionUseCase.execute(...)` now performs its two
   persistence writes through the new atomic port method instead of two
   independent store calls (`save_item` then `save_deprecation_record`).

3. **SQLite implementation**
   `SqliteLearningStore.save_item_and_deprecation(...)` wraps both
   INSERT-OR-REPLACE statements in a single `BEGIN IMMEDIATE … COMMIT`
   block. On any exception the method executes `ROLLBACK` (via
   `contextlib.suppress(sqlite3.Error)` for defensive rollback) and
   re-raises — so the store is byte-for-byte identical to its pre-call
   state with respect to these two rows.

4. **Regression tests**
   `tests/unit/application/test_rollback_atomicity.py` (new) contains
   five tests covering the use-case surface (mocked store) and the
   SQLite adapter (against `tmp_path`), including the adversarial
   rollback scenario that reproduces the B11 probe.

## What did NOT change

- `ds_agent.domain.interfaces.learning.LearningStore` — untouched, per
  work-order constraint §3.6 (no domain-layer changes).
- `PromoteLearningItemUseCase`, `DeprecateLearningItemUseCase`,
  `ReviewLearningItemUseCase` — also have double-write patterns but are
  **out of scope** for S6. See `RECOMMENDATIONS.md` for follow-up.
- Legacy `save_item` / `save_deprecation_record` methods on the store —
  kept intact so other callers are not affected.
- `data/` production databases — no touch (tests use `tmp_path`,
  probe simulation uses `.tmp/qa_S6/`).

## Re-audit hint for B11

Re-run `B11_rollback_atomicity_sqlite_probe.json` equivalent scenario.
Expected post-fix output:

```json
{"atomic": true, "item_status_after": "promoted",
 "any_deprecation_record_persisted": false,
 "verdict": "ATOMIC_REVERT"}
```

A local simulation (`B11_probe_simulation.json`) confirms this. The
`atomicity_kind` field the B11 harness expects should therefore read
`"atomic"` when re-run against HEAD.

## Clean Architecture alignment

- Dependency rule preserved: application imports only domain
  entities and the new port. No infrastructure import from
  application. `lint-imports`: 2 contracts kept, 0 broken.
- The port is a pure Protocol — no flow, no orchestration, no
  implicit behaviour. The atomicity guarantee is a **data contract**,
  not a framework-imposed workflow, so the
  "LLM = orchestrator" principle from the project CLAUDE.md is
  preserved.
