# S3 — Drift Cleanup Changelog

## 2026-04-17 — Sprint session

1. Recorded START.json with inputs + scope.
2. Read `tools/registry.py` and confirmed `tool()` decorator keyword signature
   (`name`, `description` required; `parameters`, `timeout`, `prompt`, `safety_level`,
   `category` optional).
3. A03-F1 (learning_tools.py): rewrote 6 bare `@tool` decorators to explicit keyword
   form, preserving docstring bodies, parameter defaults, and types. Applied
   safety_level per work-order matrix (`list_learning_inbox`, `get_learning_item`,
   `list_promotions`, `list_deprecations` as `safe`; `review_learning_item`,
   `rollback_promotion` as `caution`).
4. A03-F1 (portfolio_tools.py): same treatment on 5 bare `@tool` decorators.
   `list_my_portfolio` as `safe`; `pause_task`, `resume_task`, `set_sla`,
   `request_monitoring` as `caution`.
5. Verified imports succeed and 11 tools register by running
   `python -c "from ds_agent.tools import learning_tools, portfolio_tools"`.
6. A03-F2: replaced the two `lambda ... model=None: mock_agent` monkeypatch targets
   in `tests/e2e/test_ws_e2e.py` with a named `_fake_create_agent` function that
   accepts `authority_mode` (keyword-only) plus `**kwargs` for forward compatibility.
7. A04-F1: inspected `_MIGRATION_V11_1_SQL` / `_MIGRATION_V11_1_VERSION_SQL` in
   `work_object_store.py`; updated the integration test to assert `version == 12` and
   to positively verify that `integration_event_log.request_payload_json` column is
   present.
8. A04-F2: inspected `_MIGRATION_V7_SQL` in `sqlite_base.py`; updated
   `test_migration_v6.py` to assert `version == 7` and to positively verify
   `semantic_snapshot_manifest` and `semantic_snapshot_row` tables. File name
   intentionally kept (rename out of scope).
9. Ran target tests: 4/4 PASS.
10. Ran ruff on the 5 touched files: clean.
11. Ran mypy on the 2 modified tool files: no new errors (2 pre-existing annotation
    warnings on untouched helpers).
12. Ran full regression sweep; triaged each failure via isolated re-run and confirmed
    every reported failure is a pre-existing Windows tmp-handle / test isolation
    issue unrelated to this stream's scope.
13. Authored DIFF_SUMMARY.md, TEST_RESULTS.md, and this CHANGELOG.
14. Recorded FINAL.json.
