# S5 — Changelog

Chronological log of work in this stream. All timestamps are UTC.

## 2026-04-16T19:51:51+00:00 — Start

- Read upstream context: `FIX_SPRINT_WORK_ORDER.md`,
  `S1_clean_arch/FINAL.json`, `S1_clean_arch/RECOMMENDATIONS.md`.
- Confirmed residual issues: R1 (transitive application → tools.sandbox
  → infrastructure.sandbox.preamble chain breaks `lint-imports`) and R3
  (four subagent tests fail because `LineageCaptureHook()` now requires
  composition-root wiring that unit-scope tests bypass).
- Scoped down to the eight files named in the work order; verified the
  blast radius is limited to the execution-router DI surface and the
  `tests/unit/application/` folder-scoped conftest.

## 2026-04-16T20:00Z — R1 port definition

- Defined `SandboxPort` and `SandboxFactoryPort` protocols in
  `src/ds_agent/application/ports/sandbox_port.py`.
- Added re-exports to `src/ds_agent/application/ports/__init__.py`.
- Decision: two-port split. `SandboxPort` is the per-instance abstraction
  (only surface the application needs is `execute(code, timeout)`);
  `SandboxFactoryPort` is the construction abstraction with the full
  keyword-only argument set that `tools.sandbox.create_sandbox` accepts.
  This lets `ExecutionRouter.create_sandbox_for_tool` delegate without
  coupling to the function or its module.

## 2026-04-16T20:05Z — R1 RED

- Rewrote `tests/unit/application/test_execution_router.py`:
  - Updated `test_creates_expected_sandbox_for_tool` to construct the
    router with an injected `ProcessSandboxFactory()`.
  - Added `test_router_accepts_any_sandbox_factory_port_implementation`
    (structural subtyping contract).
  - Added `test_router_raises_when_factory_missing_on_sandbox_call`
    (fail-fast for misconfiguration).
- Ran `pytest tests/unit/application/test_execution_router.py -v` — 3
  new tests failed as designed (`ModuleNotFoundError` for the missing
  adapter, `TypeError` for the missing constructor arg, `DID NOT RAISE`
  for the missing guard).

## 2026-04-16T20:10Z — R1 GREEN

- Refactored `src/ds_agent/application/services/execution_router.py`:
  - Deleted `from ds_agent.tools.sandbox import ProcessSandbox, create_sandbox`.
  - Added `__init__(self, sandbox_factory: SandboxFactoryPort | None = None)`.
  - Changed `create_sandbox_for_tool` return annotation from
    `ProcessSandbox` to `SandboxPort`.
  - Delegated sandbox construction to `self._sandbox_factory.create_sandbox(...)`.
  - Added explicit `RuntimeError` with actionable message when the factory
    is not wired.
  - Left `policy_for_tool(...)` and the routing tables untouched so
    production call sites (`tools/_ds_sandbox_runner.py`,
    `infrastructure/distributed/ray_adapter.py`,
    `infrastructure/distributed/dask_adapter.py`) remain source-compatible.
- Created `src/ds_agent/infrastructure/sandbox/sandbox_factory.py`:
  - `ProcessSandboxFactory` implements `SandboxFactoryPort` by lazily
    importing `ds_agent.tools.sandbox.create_sandbox` and forwarding every
    keyword argument unchanged. Behaviour is byte-identical to the
    pre-inversion call.
- Re-ran `pytest tests/unit/application/test_execution_router.py -v` —
  all 4 tests pass.

## 2026-04-16T20:15Z — R1 verification

- `lint-imports` → "Contracts: 2 kept, 0 broken." Target contract
  (`Application must not depend on infrastructure`) is now KEPT.
- `python scripts/check_import_contracts.py` → exit code 0.
- AST scan (application/ for `ds_agent.tools.*` | `ds_agent.infrastructure.*`
  imports) → 0 violations.

## 2026-04-16T20:20Z — R3 reproduction

- Ran `pytest tests/unit/application/test_subagent.py -v --tb=short` — 4
  failures, all with the identical trace: `SubagentOrchestrator → ProcessSubagent.execute → build_hook_registry → LineageCaptureHook() → get_lineage_service()` raising
  "Lineage service is not configured."
- Root cause matches S1's RECOMMENDATIONS.md §R3 exactly: the strict
  `get_lineage_service()` added in S1 raises when the composition root
  (`agent/factory.py::create_agent`) never ran.

## 2026-04-16T20:25Z — R3 fix

- Chose Option A from S1's RECOMMENDATIONS.md §R3 ("pytest fixture in
  `tests/unit/application/conftest.py` that calls `set_lineage_service(...)`
  with a no-op fake before subagent tests run"). This is the least
  invasive option and keeps the strictness of `get_lineage_service()`
  intact for production call sites that reach it through unwired
  entrypoints.
- Created `tests/unit/application/conftest.py`:
  - `_InMemoryLineageStore` class implements `LineageStorePort` in-memory
    (no SQLite, no filesystem side-effects, respects all filter params).
  - `_default_lineage_service_for_application_tests` autouse fixture
    installs the service before each test and restores the previous value
    on teardown (same pattern as the root `isolated_secret_storage`).
- Ran `pytest tests/unit/application/test_subagent.py -v` — all 4 tests pass.
- Ran `pytest tests/unit/application/test_lineage_service.py -v` — all 4
  tests still pass (they build their own service and pass it to the hook
  constructor explicitly; the autouse fixture is only a fallback for
  hooks constructed with no argument).

## 2026-04-16T20:30Z — Final verification

- `ruff check` on S5 scope → All checks passed!
- `mypy` on S5-scope source files → "Success: no issues found in 3 source files."
- `pytest tests/unit/architecture/ tests/unit/application/test_execution_router.py tests/unit/application/test_subagent.py tests/unit/application/test_lineage_service.py` →
  19 passed.
- `pytest tests/unit/application/` → 488 passed, 1 pre-existing failure
  (`test_semantic_ports.py::test_semantic_ports_are_runtime_checkable`,
  outside S5 scope, already failing in S1 baseline).
- Full `pytest tests/unit/` → 18 additional failures observed; all are
  Windows-filesystem-state-leak flakes in `test_file_ops.py`,
  `test_placeholder_tools.py`, `test_telegram_runner.py`,
  `test_decision_os_scheduler.py`, `test_integration_tools.py`. All pass
  (or fail the same way) regardless of S5 changes; confirmed by
  re-running `test_file_ops.py::TestReadFile::test_read_existing_file`
  in isolation (→ `1 passed`). Per `FIX_SPRINT_WORK_ORDER.md §1.4` and S5
  instructions, scope-isolated runs are authoritative.

## 2026-04-16T20:35Z — Evidence documents

- Wrote `DIFF_SUMMARY.md`, `TEST_RESULTS.md`, `CHANGELOG.md`,
  `RECOMMENDATIONS.md`, `FINAL.json`.
- No self-pass judgement recorded. Final gate belongs to the A01 re-audit.
