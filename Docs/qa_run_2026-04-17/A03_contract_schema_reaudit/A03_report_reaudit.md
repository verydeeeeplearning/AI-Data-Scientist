# A03 — Contract & Schema Auditor (Re-audit, Round 2)

**Tier**: 1
**Round**: 2 (re-audit of baseline `A03` after S3 Fix Sprint)
**Baseline status**: fail
**Re-audit status**: **pass**
**Baseline FINAL**: `Docs/qa_run_2026-04-17/A03_contract_schema/FINAL.json`
**Fix Sprint source**: `Docs/qa_run_2026-04-17/S3_drift_cleanup/FINAL.json`
**Code SHA**: unavailable (`.git` metadata absent in workspace)
**Code Snapshot ID**: `855dbf1da5fc0ca74af04d759d3976daf9f773d8a69ca350dd7029c37f06d880`

## 1. Scope (unchanged from baseline)

- `src/ds_agent/tools/*.py` 전체 `@tool` 정의 AST 스캔 + import/registry/schema 감사
- `src/ds_agent/agent/factory.py` 기준 hook registry 30개 시그니처 감사
- `src/ds_agent/api/ws_handler.py` `_METHOD_MAP` 80개 RPC 메서드 감사
- `src/ds_agent/config`, `src/ds_agent/application/dtos`, `src/ds_agent/domain/*`, `src/ds_agent/api/routes` 내 Pydantic 모델 감사

## 2. Methodology (same script, new output folder)

Ran `.tmp/qa_A03_reaudit/a03_contract_audit_reaudit.py` — a verbatim copy of the baseline audit script with three additions:

1. Output path redirected to `Docs/qa_run_2026-04-17/A03_contract_schema_reaudit/`.
2. `LineageCaptureService` wired at composition root inside `_hook_rows()` so
   `LineageCaptureHook()` construction succeeds (baseline run implicitly relied
   on earlier wiring; this re-audit wires it explicitly for determinism —
   does not alter measurement).
3. Captures each registered tool's `safety_level` in the summary JSON.

Followed up with exactly the three pytest commands prescribed in
`Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md` §4.3 and the F1/F2 targeted
commands from the re-audit work order.

## 3. Delta Matrix (baseline → re-audit)

| Area | Baseline Count / Pass / Fail | Re-audit Count / Pass / Fail | Delta |
|------|-----------------------------:|------------------------------:|-------|
| Tool contracts | 86 / 75 / 11 | 86 / 86 / 0 | **F1 resolved** (+11 pass) |
| Hook signatures | 30 / 30 / 0 | 30 / 30 / 0 | no regression |
| WS RPC methods | 80 / 80 / 0 | 80 / 80 / 0 | no regression |
| Pydantic models | 156 / 156 / 0 | 156 / 156 / 0 | no regression |
| Pytest import suite | 12 / 11 / 1 | 12 / 12 / 0 | **F1 resolved** |
| Pytest contract suite | 273 / 271 / 2 | 273 / 273 / 0 | **F2 resolved** |
| Pytest agent session registry | 14 / 14 / 0 | 14 / 14 / 0 | no regression |

Combined static rows: `352 / failing = 0`.

## 4. Prior Blocking Findings

### F1 — Bare `@tool` usage in learning_tools.py / portfolio_tools.py (11 sites)

**Status**: resolved.

Evidence:

- `A03_contract_summary.json`:
  - `decorated_tool_functions`: 86
  - `registered_tool_entries`: **86** (was 75)
  - `module_import_failures`: **{}** (was 2 entries)
  - `failing_tool_contracts`: **[]** (was 11 entries)
- All 11 functions now appear as registered tools with explicit
  `@tool(name=..., description=..., parameters=..., safety_level=...)` form:

| Tool | Safety Level |
|------|--------------|
| `list_learning_inbox` | safe |
| `review_learning_item` | caution |
| `get_learning_item` | safe |
| `list_promotions` | safe |
| `list_deprecations` | safe |
| `rollback_promotion` | caution |
| `list_my_portfolio` | safe |
| `pause_task` | caution |
| `resume_task` | caution |
| `set_sla` | caution |
| `request_monitoring` | caution |

Safety matrix aligns with Fix Sprint work order §5.2.1 + S3 CHANGELOG steps 3–4
(3 safe + 5 caution per spec; `list_promotions`/`list_deprecations` documented
as `safe` by S3 explicitly).

- `pytest tests/unit/infrastructure/test_cli_main.py::TestImportTools::test_import_tools_no_crash`
  PASSED (was FAILED).
- `python -c "from ds_agent.tools import learning_tools, portfolio_tools; print('import OK')"`
  succeeds without `TypeError`.

### F2 — WebSocket chat E2E monkeypatch ignored `authority_mode`

**Status**: resolved.

Evidence:

- `tests/e2e/test_ws_e2e.py` lines 339–348 and 393–402 now define a named
  `_fake_create_agent(session_id, callbacks, model=None, *, authority_mode=None, **kwargs)`
  (previously `lambda session_id, callbacks, model=None: mock_agent`).
- `pytest tests/e2e/test_ws_e2e.py::TestChatE2E` → 2 passed.
- `pytest tests/unit/infrastructure/test_agent_session_registry.py` → 14 passed
  (green both before and after — authority_mode contract test in the unit
  suite was already passing and remains passing).

## 5. Regression Check (baseline-green surfaces must remain green)

| Surface | Baseline | Re-audit | Regression? |
|---------|---------:|---------:|:-----------:|
| 30 hooks, signature + duplicate-name check | 0 fail | 0 fail | no |
| 80 WS RPC methods, async + `(self, params)` check | 0 fail | 0 fail | no |
| 156 Pydantic models, `model_json_schema()` + `Draft202012Validator.check_schema` | 0 fail | 0 fail | no |
| 14 agent session registry tests | 14/14 | 14/14 | no |
| CLI bootstrap (`python -m ds_agent.cli.main`) | — | boots REPL banner successfully | clean |

No new regressions detected.

## 6. Scope-respect Check for S3

The re-audit work order requires confirming S3 did not touch the `tool()`
decorator signature or migration code.

- `src/ds_agent/tools/registry.py` — `tool()` decorator signature inspected at
  runtime: `(name: str, description: str, category: str = 'general',
  parameters: dict | None = None, timeout: int = 120, prompt: str = '',
  safety_level: str = 'safe') -> Callable`.
  SHA256: `f722f958bae632e110528ea1c68e1bf966f9be0546cab6f36955a4dd351fcf02`.
  This matches the baseline signature (`name`, `description` required keyword
  arguments; bare `@tool` still intentionally rejected).
- S3's `FINAL.json` explicitly affirms
  `tool_decorator_signature_unchanged: true`, `migration_code_unchanged: true`.
- S3 `files_changed` list does **not** include `src/ds_agent/tools/registry.py`
  nor any `src/ds_agent/infrastructure/persistence/*_store.py` module.

Verdict: scope respected.

## 7. QA Plan Count Drift (carry-over observation)

The plan document `Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md` references
`76 tools`. The authoritative count post-S3 is **86 decorated tool functions,
all 86 registered**. The 11 learning/portfolio tools were the missing ones at
baseline; with them registered the canonical count is `86`, not `76`. This is
a doc-drift Recommendation (not a failure) — surfaced for documentation sync
in the release notes.

## 8. Verdict

- F1 resolved: **yes** — 11/11 previously-failing tool contracts now pass, import suite green.
- F2 resolved: **yes** — 2/2 previously-failing WS E2E chat tests pass.
- Regression on hook / WS RPC / Pydantic / agent session registry surfaces: **none**.
- S3 stayed within scope (no registry/migration code changes): **yes**.

**Tier 1 A03 gate**: **pass** on this re-audit.

## 9. Evidence Index

- `Docs/qa_run_2026-04-17/A03_contract_schema_reaudit/START.json`
- `Docs/qa_run_2026-04-17/A03_contract_schema_reaudit/FINAL.json` (this run)
- `Docs/qa_run_2026-04-17/A03_contract_schema_reaudit/A03_contract_matrix.csv`
- `Docs/qa_run_2026-04-17/A03_contract_schema_reaudit/A03_contract_summary.json`
- `Docs/qa_run_2026-04-17/A03_contract_schema_reaudit/pytest_import_tools.log`
- `Docs/qa_run_2026-04-17/A03_contract_schema_reaudit/junit_import_tools.xml`
- `Docs/qa_run_2026-04-17/A03_contract_schema_reaudit/pytest_contract_suite.log`
- `Docs/qa_run_2026-04-17/A03_contract_schema_reaudit/junit_contract_suite.xml`
- `Docs/qa_run_2026-04-17/A03_contract_schema_reaudit/pytest_agent_session_registry.log`
- `Docs/qa_run_2026-04-17/A03_contract_schema_reaudit/junit_agent_session_registry.xml`

## 10. Recommendations (non-blocking)

1. Update `Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md` tool count `76 → 86`
   to reflect the canonical registered count now that F1 is fixed.
2. Consider adding a lightweight architectural unit test asserting every tool
   module in `src/ds_agent/tools/*.py` imports cleanly and registers at least
   one tool — this would have caught F1 on first CI.
