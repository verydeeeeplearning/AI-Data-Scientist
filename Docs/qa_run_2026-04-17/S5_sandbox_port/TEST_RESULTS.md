# S5 — Test Results

All verification commands are run from repository root on Windows 11 with
Python 3.12.10. Raw logs accompany each command.

## 1. lint-imports (import-linter)

Command: `lint-imports`
Raw log: `lint_imports.log`

```
Analyzed 496 files, 1390 dependencies.
--------------------------------------

Domain must not depend on outer layers KEPT
Application must not depend on infrastructure KEPT

Contracts: 2 kept, 0 broken.
```

Delta vs S1 FINAL.json:
- Before S5: 1 broken — `ds_agent.application.services.execution_router -> ds_agent.tools.sandbox (l.9) -> ds_agent.infrastructure.sandbox.preamble (l.231, l.260)`.
- After S5: 0 broken. The direct `tools.sandbox` import at
  `execution_router.py:9` has been removed; the transitive chain no longer
  originates in the application layer.

## 2. scripts/check_import_contracts.py

Command: `python scripts/check_import_contracts.py ; echo exit=$?`
Raw log: `check_import_contracts.log`

```
import contracts: ok
exit=0
```

## 3. Architecture tests

Command: `python -m pytest tests/unit/architecture/ -v --tb=short`
Raw log: `pytest_architecture.log`

```
collected 7 items

tests/unit/architecture/test_application_infrastructure_boundary.py::test_application_layer_has_no_infrastructure_imports PASSED
tests/unit/architecture/test_application_infrastructure_boundary.py::test_previously_flagged_services_are_clean[lineage_capture_service.py] PASSED
tests/unit/architecture/test_application_infrastructure_boundary.py::test_previously_flagged_services_are_clean[reproducibility_exporter.py] PASSED
tests/unit/architecture/test_application_infrastructure_boundary.py::test_previously_flagged_services_are_clean[scheduler_service.py] PASSED
tests/unit/architecture/test_import_contracts.py::test_static_import_contracts_are_clean PASSED
tests/unit/architecture/test_semantic_layer_deps.py::test_semantic_domain_has_no_forbidden_imports PASSED
tests/unit/architecture/test_semantic_layer_deps.py::test_semantic_application_has_no_infrastructure_imports PASSED

============================== 7 passed in 0.76s ==============================
```

## 4. R1-focused tests (ExecutionRouter port inversion)

Command: `python -m pytest tests/unit/application/test_execution_router.py -v --tb=short`
Raw log: `pytest_s5_scope.log`

```
collected 4 items

tests/unit/application/test_execution_router.py::TestExecutionRouter::test_maps_tool_names_to_expected_paths PASSED
tests/unit/application/test_execution_router.py::TestExecutionRouter::test_creates_expected_sandbox_for_tool PASSED
tests/unit/application/test_execution_router.py::TestExecutionRouter::test_router_accepts_any_sandbox_factory_port_implementation PASSED
tests/unit/application/test_execution_router.py::TestExecutionRouter::test_router_raises_when_factory_missing_on_sandbox_call PASSED

============================== 4 passed ==============================
```

TDD trace:
- RED run (before `execution_router.py` edit): 3 of 4 failed as designed
  (`ModuleNotFoundError: ds_agent.infrastructure.sandbox.sandbox_factory`,
  `TypeError: ExecutionRouter() takes no arguments`, `DID NOT RAISE RuntimeError`).
  Full RED log is not persisted (same commands re-run after GREEN).
- GREEN run (after refactor): all 4 pass, as shown above.

## 5. R3-focused tests (Subagent orchestrator)

Command: `python -m pytest tests/unit/application/test_subagent.py -v --tb=short`

```
collected 4 items

tests/unit/application/test_subagent.py::TestSubagentOrchestration::test_subagent_spawn_and_execute PASSED
tests/unit/application/test_subagent.py::TestSubagentOrchestration::test_builder_validator_feedback_loop PASSED
tests/unit/application/test_subagent.py::TestSubagentOrchestration::test_subagent_budget_isolation PASSED
tests/unit/application/test_subagent.py::TestSubagentOrchestration::test_parallel_subagents_return_results_in_input_order PASSED

============================== 4 passed in 1.70s ==============================
```

Delta vs S1: all 4 were previously failing with
`RuntimeError: Lineage service is not configured. Call set_lineage_service() at the composition root before use.`
The new autouse fixture in `tests/unit/application/conftest.py` wires an
in-memory `LineageCaptureService` before every test in the folder. Tests
that do their own explicit wiring (e.g. `test_lineage_service.py`) are
unaffected because the previous value is restored on teardown and the
hooks under test receive a service via the constructor argument.

## 6. S5 combined scope sweep

Command: `python -m pytest tests/unit/architecture/ tests/unit/application/test_execution_router.py tests/unit/application/test_subagent.py tests/unit/application/test_lineage_service.py -v --tb=short`
Raw log: `pytest_s5_scope.log`

Result: `19 passed in 2.84s`. This confirms:
- R1 boundary is clean (4 architecture tests)
- R1 DI contract is honoured (4 execution-router tests)
- R3 subagent hooks work through the composition-root fixture (4 subagent tests)
- Existing lineage-service tests still pass with the autouse fixture in place (4 tests)
- Semantic layer deps unchanged (3 tests)

## 7. AST scan — application → tools/infrastructure

Raw log: `ast_scan.log`

```
violations: 0
```

Zero direct imports from `ds_agent.application.*` into `ds_agent.tools.*`
or `ds_agent.infrastructure.*`. Exactly matches S1's post-fix invariant,
now also satisfied for `execution_router.py`.

## 8. ruff (S5-scope files)

Command:
```
ruff check src/ds_agent/application/ports/sandbox_port.py \
           src/ds_agent/application/services/execution_router.py \
           src/ds_agent/infrastructure/sandbox/sandbox_factory.py \
           src/ds_agent/application/ports/__init__.py \
           tests/unit/application/test_execution_router.py \
           tests/unit/application/conftest.py
```
Raw log: `ruff.log`

```
All checks passed!
```

## 9. mypy (S5-scope files)

Command:
```
python -m mypy src/ds_agent/application/ports/sandbox_port.py \
               src/ds_agent/application/services/execution_router.py \
               src/ds_agent/infrastructure/sandbox/sandbox_factory.py
```
Raw log: `mypy.log`

```
Success: no issues found in 3 source files
```

Full-src regression: `python -m mypy src/ds_agent` reports 383 pre-existing
errors (identical error families to the S1 FINAL.json baseline — all in files
outside S5 scope: `api/ws_handler.py`, `api/app.py`, etc.). None of the
S5-touched files are in the error list (verified with
`grep -E "sandbox_port|execution_router|sandbox_factory" mypy_full.log` → empty).

## 10. Broader application scope sweep

Command: `python -m pytest tests/unit/application/ --tb=short`
Raw log: `pytest_application.log`

```
1 failed, 488 passed in 6.95s
```

The single failure — `test_semantic_ports.py::test_semantic_ports_are_runtime_checkable`
— was already failing in the S1 baseline (see S1 `pytest_scope_regression.log`
line 420) and lives in `ds_agent.memory.semantic`, wholly outside S5 scope.
No new regressions were introduced.

## 11. Scoped unit regression (filesystem flake acknowledged)

Command: `python -m pytest tests/unit/ --deselect tests/unit/application/test_semantic_ports.py::test_semantic_ports_are_runtime_checkable --tb=short`
Raw log: `pytest_unit_regression.log`

```
18 failed, 2102 passed, 1 deselected
```

The 18 failures are Windows-specific workspace/state-leak flakes in
`test_file_ops.py`, `test_placeholder_tools.py`, `test_telegram_runner.py`,
`test_decision_os_scheduler.py`, `test_integration_tools.py`. They are
unrelated to S5:

- `test_file_ops.py` (10) — pass individually
  (`pytest tests/unit/infrastructure/test_file_ops.py::TestReadFile::test_read_existing_file`
  → `1 passed`). Classic Windows `.tmp` directory reuse flake — the same
  class of failure S2/S3/S4 acknowledged and documented.
- `test_placeholder_tools.py`, `test_telegram_runner.py`,
  `test_decision_os_scheduler.py`, `test_integration_tools.py` — fail even
  in tiny isolated runs due to pre-existing SQLite/workspace state
  pollution in `data/` from prior runs (expected empty memory returns 5
  seeded records; expected active_sessions=2 returns 5; etc.). These have
  nothing to do with the sandbox-port refactor or the subagent fixture.

Per the FIX_SPRINT_WORK_ORDER.md §1.4 and S5 instructions, scope-isolated
verification (sections 3–10 above) is the authoritative signal for this
stream. Full `pytest tests/unit/ -x` is acknowledged as unreliable on
Windows for the project's current snapshot.
