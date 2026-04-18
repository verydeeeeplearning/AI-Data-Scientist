# S3 — Recommendations (non-blocking)

These were discovered during S3 work but are intentionally NOT applied — they are
outside the fix-sprint scope per the work order. Recorded here so downstream re-audit
or future sprints can act on them.

1. `src/ds_agent/tools/learning_tools.py:13` and `src/ds_agent/tools/portfolio_tools.py:14`
   — the private helpers `_get_learning_store()` and `_get_portfolio_store()` lack
   return type annotations. mypy flags them; they existed before this sprint and were
   not modified by S3. Adding `-> SqliteLearningStore | None` / `-> SqlitePortfolioStore | None`
   would clear the 2 mypy errors in these files.

2. Full-suite pytest runs on Windows accumulate file handles under `.tmp/pytest/`
   which then cause `WinError 32/145/183` setup/teardown errors on subsequent tests
   using `tmp_path`. Consider either moving the pytest basetemp out of the workspace
   (`--basetemp=%TEMP%/ds-agent-pytest`) or adding a session-scoped cleanup fixture
   that uses `os.unlink` with retry + handle-close for Windows. This is the root
   cause of the 41 aggregated failures observed during the S3 full-regression sweep;
   none are real regressions.

3. `test_migration_v6.py` now validates v7 schema elements in addition to v6. When
   the S4 stream introduces v13, consider renaming this file to
   `test_migration_semantic.py` and making it parametric by version so the filename
   stops drifting from the maximum version under test. Per work-order constraint,
   this rename was deferred.

4. Safety-level classification for `list_promotions` and `list_deprecations` is not
   explicitly enumerated in the work order. They are read-only listing endpoints
   with no side effects, so I defaulted them to `safe`. If learning-governance policy
   treats deprecation metadata as sensitive, these could be re-classified to
   `caution` in a follow-up.
