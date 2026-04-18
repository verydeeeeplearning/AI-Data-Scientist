# S6 Test Results

## Scope-isolated pytest

Command:
```
pytest \
  tests/unit/application/test_rollback_atomicity.py \
  tests/unit/application/test_rollback_promotion.py \
  tests/unit/application/test_promote_learning_item.py \
  tests/unit/application/test_deprecate_learning_item.py \
  tests/integration/infrastructure/test_sqlite_learning_store.py \
  -v --tb=short \
  --junitxml=Docs/qa_run_2026-04-17/S6_rollback_atomicity/junit.xml
```

Result: **33 passed, 0 failed** (see `junit.xml`).

Breakdown:
- `test_rollback_atomicity.py` — **5/5 PASSED** (all new)
  - `TestRollbackAtomicity::test_use_case_uses_atomic_write`
  - `TestRollbackAtomicity::test_atomic_failure_raises_and_does_not_split_writes`
  - `TestSqliteStoreAtomicity::test_port_is_runtime_checkable_on_sqlite_store`
  - `TestSqliteStoreAtomicity::test_atomic_success_persists_both_rows`
  - `TestSqliteStoreAtomicity::test_atomic_failure_rolls_back_both_rows`
- `test_rollback_promotion.py` — 4/4 PASSED (1 assertion updated to new contract)
- `test_promote_learning_item.py` — 6/6 PASSED
- `test_deprecate_learning_item.py` — 5/5 PASSED
- `test_sqlite_learning_store.py` — 13/13 PASSED

## RED → GREEN evidence

**RED** (before fix):
`junit_red.xml` captured two failing tests on the pristine codebase:
```
tests/unit/application/test_rollback_atomicity.py::TestRollbackAtomicity::test_use_case_uses_atomic_write FAILED
  AssertionError: assert 0 == 1
  where 0 = <MagicMock name='mock.save_item_and_deprecation' ...>.call_count
tests/unit/application/test_rollback_atomicity.py::TestRollbackAtomicity::test_atomic_failure_raises_and_does_not_split_writes FAILED
  Failed: DID NOT RAISE <class 'RuntimeError'>
```
Interpretation: the use case did not even attempt `save_item_and_deprecation`
(method didn't exist), and a failure injected into that method obviously
couldn't propagate because the call never happened. This directly
reproduces FAIL-B11-8.

**GREEN** (after fix): all five atomicity tests pass, including the
end-to-end SQLite rollback test (`test_atomic_failure_rolls_back_both_rows`)
which proves that injecting a failure into the deprecation INSERT leaves
**both** rows absent from the DB — the invariant the B11 probe would
otherwise flag as `atomic=false`.

## B11 probe re-simulation (post-fix)

See `B11_probe_simulation.json` for the output of a local re-run of the
same scenario the original B11 probe used:

```json
{
  "exception_raised": true,
  "item_status_after": "promoted",
  "any_deprecation_record_persisted": false,
  "atomic": true,
  "verdict": "ATOMIC_REVERT (item kept promoted, no deprecation record)"
}
```

Compare to the original failing probe
(`Docs/qa_run_2026-04-17/B11_portfolio_learning/B11_rollback_atomicity_sqlite_probe.json`):

```json
{
  "exception_raised": true,
  "item_status_after": "deprecated",
  "any_deprecation_record_persisted": false,
  "atomic": false,
  "verdict": "NON_ATOMIC_PARTIAL (item deprecated without DeprecationRecord)"
}
```

The status flipped from `"deprecated"` (half-committed) to `"promoted"`
(fully rolled back) and `atomic` flipped from `false` to `true`.
The B11 reaudit agent should confirm this independently.

## Static checks

- `ruff check` on the four modified/new scope files: **All checks passed!**
- `python scripts/check_import_contracts.py`: `import contracts: ok`
- `lint-imports`: `Contracts: 2 kept, 0 broken` (both
  `domain_independence` and `application_independence_from_infrastructure`
  remain green).
- `mypy src/ds_agent/application/learning/ src/ds_agent/infrastructure/persistence/`:
  3 pre-existing errors in files outside S6 scope (`lineage_store.py`,
  `submit_learning_proposal.py`, `work_object_store.py`). S6 changes add
  **zero** new mypy errors. Per work-order instructions these three are
  ignored.

## Data safety

No production database was touched. All storage tests run against
`tmp_path` fixtures. The B11 probe simulation used `.tmp/qa_S6/` per
the "no real data" constraint in the work order.
