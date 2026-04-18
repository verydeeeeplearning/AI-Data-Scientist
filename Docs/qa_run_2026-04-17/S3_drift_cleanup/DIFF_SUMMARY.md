# S3 — Drift Cleanup: Diff Summary

## Files Modified (5)

### 1. `src/ds_agent/tools/learning_tools.py` — modify
Converted 6 bare `@tool` decorators at lines 42, 108, 169, 200, 225, 251 to explicit
`@tool(name=..., description=..., parameters=..., safety_level=...)` form.

- `list_learning_inbox` → safety_level=`safe`
- `review_learning_item` → safety_level=`caution`
- `get_learning_item` → safety_level=`safe`
- `list_promotions` → safety_level=`safe`
- `list_deprecations` → safety_level=`safe`
- `rollback_promotion` → safety_level=`caution`

Docstring bodies were preserved verbatim; only the first sentence was reused as `description`.
Parameter schemas were lifted from each function signature (types + defaults) without
adding new runtime behavior.

### 2. `src/ds_agent/tools/portfolio_tools.py` — modify
Converted 5 bare `@tool` decorators at lines 38, 69, 139, 196, 240.

- `list_my_portfolio` → safety_level=`safe`
- `pause_task` → safety_level=`caution`
- `resume_task` → safety_level=`caution`
- `set_sla` → safety_level=`caution`
- `request_monitoring` → safety_level=`caution`

### 3. `tests/e2e/test_ws_e2e.py` — modify
Two `monkeypatch.setattr(..., "_create_agent", lambda ...)` call sites (line 339 and 388
region) replaced with a named `_fake_create_agent(session_id, callbacks, model=None, *,
authority_mode=None, **kwargs)` function so the double accepts the new keyword-only
kwarg `authority_mode` (and any future kwargs) without `TypeError`.

### 4. `tests/integration/infrastructure/test_sqlite_work_object_store.py` — modify
- `assert version == 11` → `assert version == 12`
- Added a read of `PRAGMA table_info(integration_event_log)` and a positive assertion
  `"request_payload_json" in integration_event_columns` covering the v12 migration
  (`_MIGRATION_V11_1_SQL` adds this column for DLQ replay).

### 5. `tests/integration/semantic/test_migration_v6.py` — modify
- `assert version == 6` → `assert version == 7`
- Added assertions `"semantic_snapshot_manifest" in tables` and
  `"semantic_snapshot_row" in tables` covering the v7 migration (`_MIGRATION_V7_SQL`
  introduces the semantic snapshot manifest/row tables).

File name intentionally kept as `test_migration_v6.py` (rename out of scope per work
order).

## Files NOT Modified
- `src/ds_agent/tools/registry.py` — `tool()` decorator signature untouched.
- `src/ds_agent/infrastructure/persistence/work_object_store.py` — migration code
  unchanged; only assertions updated on the test side.
- `src/ds_agent/memory/semantic/infrastructure/sqlite_base.py` — migration code
  unchanged; only assertions updated on the test side.
- No v13 migration added (S4 scope).
- No changes under `application/`, `infrastructure/observability/`, or `.importlinter`.
