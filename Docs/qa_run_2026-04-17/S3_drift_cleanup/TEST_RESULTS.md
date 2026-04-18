# S3 — Drift Cleanup: Test Results

## 1. Smoke — Tool Imports (A03-F1 acceptance)

Command:
```
python -c "from ds_agent.tools import learning_tools, portfolio_tools; print('OK')"
```

Result: `OK`. All 11 tools registered:

```
tool_registered  name=list_learning_inbox
tool_registered  name=review_learning_item
tool_registered  name=get_learning_item
tool_registered  name=list_promotions
tool_registered  name=list_deprecations
tool_registered  name=rollback_promotion
tool_registered  name=list_my_portfolio
tool_registered  name=pause_task
tool_registered  name=resume_task
tool_registered  name=set_sla
tool_registered  name=request_monitoring
```

## 2. Target Tests — 4 Issues

```
pytest tests/e2e/test_ws_e2e.py::TestChatE2E \
       tests/integration/infrastructure/test_sqlite_work_object_store.py \
       tests/integration/semantic/test_migration_v6.py -v
```

Result: `4 passed in 1.75s`

- `test_chat_send_returns_session_and_done` — PASS (A03-F2)
- `test_chat_history_after_send` — PASS (A03-F2)
- `test_sqlite_work_object_store_round_trip_and_migration` — PASS (A04-F1)
- `test_semantic_migration_v6_applies_and_is_idempotent` — PASS (A04-F2)

## 3. Baseline A03 / A04 Audit Scope (isolated re-runs)

```
pytest tests/integration/test_all_tools_registered.py -v
```
Result: `6 passed in 0.97s`. The `test_total_tool_count` check adapts to the registry
census, so the 11 newly explicit tools do not break the aggregate count assertion.

## 4. Lint

```
ruff check src/ds_agent/tools/learning_tools.py \
           src/ds_agent/tools/portfolio_tools.py \
           tests/e2e/test_ws_e2e.py \
           tests/integration/infrastructure/test_sqlite_work_object_store.py \
           tests/integration/semantic/test_migration_v6.py
```
Result: `All checks passed!` for all 5 files modified by this stream.

Pre-existing ruff errors elsewhere in `src/` and `tests/` (51 total) are out of scope
for S3 and untouched.

## 5. Type Check

```
mypy src/ds_agent/tools/learning_tools.py src/ds_agent/tools/portfolio_tools.py
```
Result: 2 pre-existing errors reported on `_get_learning_store()` and
`_get_portfolio_store()` helpers (missing return type annotations). These predate the
S3 change — the functions themselves and the file-level state were not modified by this
stream. No new mypy errors introduced.

## 6. Full Regression — Environmental Note

A full `pytest --tb=short` sweep was run. Raw tally: `41 failed, 2341 passed, 5 skipped`.

Every failure was triaged by re-running the offending test in isolation; each then
PASSED. Root cause: stale Windows file handles under `.tmp/pytest/` (OS-level
`WinError 32`, `WinError 183`, `WinError 145`) combined with the `ToolRegistry`
module-level singleton causing cross-test interference when the full session
accumulates. None of these failures reproduce when the target slice is run alone, and
none of them touch the files modified by S3.

Examples of isolated re-run confirming no S3-caused regression:

- `pytest tests/integration/test_all_tools_registered.py` → `6 passed`
- `pytest tests/unit/architecture/test_application_infrastructure_boundary.py` →
  `4 passed`
- `pytest tests/unit/infrastructure/test_file_ops.py::TestReadFile::test_read_existing_file`
  → `1 passed`
- `pytest tests/unit/tools/test_integration_tools.py::test_work_object_tool_lifecycle`
  → `1 passed`

Full regression re-validation under a clean Windows tmp environment is deferred to the
A03/A04 re-audit stage per the work-order protocol (S3 agent does not self-judge).
