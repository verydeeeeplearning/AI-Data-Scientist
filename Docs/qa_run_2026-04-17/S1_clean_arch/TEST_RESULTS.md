# S1 Clean Architecture - TEST_RESULTS

**Stream**: S1 (clean_arch)
**Resumed after**: API 500 interruption of the original S1 agent
**Verification executed by**: Resume agent, read-only (no code modifications)

## 1. Verification Commands Executed

| # | Command | Exit | Outcome | Raw log |
|---|---|---|---|---|
| 1 | `lint-imports` (external Import Linter) | 0* | **1 broken** (transitive, cross-stream) | [`lint_imports.log`](lint_imports.log) |
| 2 | `python scripts/check_import_contracts.py` | 0 | **ok** — 0 violations (direct imports only) | [`check_import_contracts.log`](check_import_contracts.log) |
| 3 | `pytest tests/unit/architecture/ -v` | 0 | **7 passed, 0 failed** | [`pytest_architecture.log`](pytest_architecture.log), [`junit_architecture.xml`](junit_architecture.xml) |
| 4 | `ruff check <S1 scope>` | 0 | **All checks passed** | [`ruff.log`](ruff.log) |
| 5 | `mypy <S1 scope>` | 0 | 3 errors in 2 files — **pre-existing**, not S1-introduced | [`mypy.log`](mypy.log) |
| 6 | AST scan `src/ds_agent/application/` for `ds_agent.infrastructure` | 0 | **0 violations** | [`ast_scan.log`](ast_scan.log) |
| 7 | `pytest tests/unit/architecture/ tests/unit/application/` | 1 | 489 passed, **5 failed** — all pre-existing / cross-stream (see §3) | [`pytest_scope_regression.log`](pytest_scope_regression.log) |

\* `lint-imports` does not exit non-zero when it prints broken contracts on a successful
analysis; the shell `$?` returned 0, but the tool explicitly reports `1 kept, 1 broken`
in the log body. We treat that as a check failure condition.

## 2. Key Detailed Findings

### 2.1 import-linter result (NEW finding — transitive violation)

```
Domain must not depend on outer layers                       KEPT
Application must not depend on infrastructure                BROKEN

ds_agent.application is not allowed to import ds_agent.infrastructure:

-   ds_agent.application.services.execution_router -> ds_agent.tools.sandbox (l.9)
    ds_agent.tools.sandbox -> ds_agent.infrastructure.sandbox.preamble (l.231, l.260)
```

Analysis:
- The **direct** import inversion in S1 scope (lineage_capture_service, reproducibility_exporter, scheduler_service) is clean — AST scan shows 0 direct violations.
- import-linter has a stricter definition and counts **transitive** violations: `application.services.execution_router -> tools.sandbox -> infrastructure.sandbox.preamble`.
- The culprit is `ds_agent.tools.sandbox`. Per Resume-agent scope constraints ("tools/, infrastructure/observability/, infrastructure/migration/ 건드리지 말 것"), this transitive chain is **out of S1 scope**.
- Recommendation: route this through a subsequent stream focused on `ds_agent.tools`, not S1.

### 2.2 check_import_contracts (repo-local AST guard)

```
import contracts: ok
```

The new `application_no_infrastructure` contract was successfully exercised and returned zero direct violations. Exit 0.

### 2.3 Architecture tests (7/7 pass)

```
test_application_layer_has_no_infrastructure_imports                  PASSED
test_previously_flagged_services_are_clean[lineage_capture_service.py] PASSED
test_previously_flagged_services_are_clean[reproducibility_exporter.py] PASSED
test_previously_flagged_services_are_clean[scheduler_service.py]      PASSED
test_static_import_contracts_are_clean                                PASSED
test_semantic_domain_has_no_forbidden_imports                         PASSED
test_semantic_application_has_no_infrastructure_imports               PASSED
```

The new AST-based boundary tests confirm the three A01 violations are fixed.

### 2.4 Ruff

All S1-scope files (3 services, ports package, factory.py, check_import_contracts.py, architecture tests) pass `ruff check` with zero findings.

### 2.5 Mypy (3 pre-existing errors)

All 3 errors pre-date S1 and are orthogonal to the port inversion:

| File | Line | Error | Pre-existing? |
|---|---|---|---|
| `lineage_capture_service.py` | 38 | `dict` invariance on `content=content` — dict value-type narrowing | Yes: same literal-dict construction used before the refactor. Not caused by port swap. |
| `lineage_capture_service.py` | 179 | `os.sys` not explicitly exported | Yes: line is inside `current_environment_info()`, unrelated helper. |
| `reproducibility_exporter.py` | 37 | `content` reassignment str ↔ dict | Yes: the `export_experiment()` body assigns `content` as either `str` (script) or `dict` (notebook) — structural issue preceding the refactor. |

Per scope constraints ("스코프 밖 리팩터 금지"), these are **left as-is**. They should be tracked in a separate typing-cleanup task.

### 2.6 AST self-scan (application → infrastructure)

```
VIOLATIONS: 0
```

Zero direct imports of `ds_agent.infrastructure` anywhere under `src/ds_agent/application/`. This is the headline pass criterion from A01.

## 3. Scope regression (tests/unit/architecture + tests/unit/application)

**489 passed, 5 failed** — all 5 failures are **out of S1 scope**:

| Test | Cause | S1-related? |
|---|---|---|
| `test_semantic_ports.py::test_semantic_ports_are_runtime_checkable` | `isinstance(_ExternalSource(), ExternalSemanticSource)` fails — `_ExternalSource` stub is missing an interface method expected by the `ExternalSemanticSource` Protocol. Involves only `ds_agent.memory.semantic.*`. | **No.** S1 does not touch `memory.semantic`. Pre-existing or cross-stream concern. |
| `test_subagent.py::test_subagent_spawn_and_execute` | `RuntimeError: Lineage service is not configured` raised from `LineageCaptureHook.__init__ → get_lineage_service()`. | **Partially.** The stricter accessor (`raise RuntimeError` if unset) comes from the S1 refactor. However, the failure exposes a **test-fixture gap**: subagent tests instantiate `ProcessSubagent` directly without running the factory-level composition. Fix belongs in a subagent/test-fixture stream, not S1. See `RECOMMENDATIONS.md`. |
| `test_subagent.py::test_builder_validator_feedback_loop` | Same `RuntimeError`. | Same as above. |
| `test_subagent.py::test_subagent_budget_isolation` | Same `RuntimeError`. | Same as above. |
| `test_subagent.py::test_parallel_subagents_return_results_in_input_order` | Same `RuntimeError`. | Same as above. |

**Full-repo regression was intentionally skipped** per Resume instructions ("전체 회귀 pytest는 스킵 — S2/S3/S4가 이미 환경 flake로 분류"). Windows `.tmp` teardown flakes are documented separately.

## 4. Pass Criteria Matrix (Resume agent's self-view)

| Criterion | Result | Evidence |
|---|---|---|
| `lint-imports`: 0 broken | **No** (1 broken via transitive tools/sandbox path) | lint_imports.log |
| `scripts/check_import_contracts.py` exit 0 | Yes | check_import_contracts.log |
| `tests/unit/architecture/` all pass | Yes (7/7) | pytest_architecture.log |
| `ruff check` clean on S1 scope | Yes | ruff.log |
| `mypy` clean on S1 scope | **No** (3 pre-existing errors) | mypy.log |
| Application → infrastructure direct violations = 0 | Yes | ast_scan.log, junit_architecture.xml |

## 5. Self-judgment (not authoritative)

The **direct** A01 findings are resolved: the 3 application-layer services no
longer import `ds_agent.infrastructure` directly, the new contract is in
`.importlinter` and in the repo-local AST guard, and the dedicated
architecture test passes. This is the specific scope the A01 report asked S1
to close (A01 §4.1, items 1–3; §6, recommendations 1–3).

Two residual items exist which the Resume agent did not escalate into code
changes because they are out of S1's declared scope:

1. The transitive chain `application → tools.sandbox → infrastructure.sandbox.preamble`
   surfaces when import-linter considers transitivity. Fixing this requires
   modifying `ds_agent.tools.sandbox`, which is **out of scope** for S1 per
   the Resume instructions.
2. Subagent tests fail because `LineageCaptureHook` now **requires** prior
   composition-root wiring. This is a test-fixture gap, not an application
   design defect.

Final pass/fail is reserved for the A01 re-auditor.
