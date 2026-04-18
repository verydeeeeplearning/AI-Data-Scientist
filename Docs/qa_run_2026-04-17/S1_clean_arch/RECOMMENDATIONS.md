# S1 Clean Architecture - RECOMMENDATIONS

These are findings surfaced during S1 verification that fall **outside S1's
declared scope** and should be routed to follow-up streams. No code change
was made for any of these.

## R1. Transitive infrastructure import via `ds_agent.tools.sandbox`

**Severity**: medium (breaks `lint-imports` even though direct AST scan is clean)

**Finding**:
```
ds_agent.application.services.execution_router -> ds_agent.tools.sandbox (l.9)
ds_agent.tools.sandbox -> ds_agent.infrastructure.sandbox.preamble (l.231, l.260)
```

`execution_router` (application) imports `ds_agent.tools.sandbox` (tools), and
`tools.sandbox` imports from `ds_agent.infrastructure.sandbox.preamble`. Even
though no file under `src/ds_agent/application/` directly names
`ds_agent.infrastructure`, the transitive chain violates the Clean
Architecture Dependency Rule at runtime.

**Why not fixed in S1**: The Resume work order explicitly forbids edits in
`tools/`, `infrastructure/observability/`, `infrastructure/migration/`. The
fix belongs to a tools-stream refactor: introduce a `SandboxPreamblePort` in
the application (or tools-interface) layer and inject the concrete preamble
from the composition root, identical pattern to what S1 did for lineage /
notebook / cron.

**Suggested scope for follow-up**:
- Create `src/ds_agent/application/ports/sandbox_preamble_port.py` (or the
  equivalent location if `tools` has its own port layer).
- Refactor `ds_agent.tools.sandbox` to accept the preamble by injection.
- Wire `SandboxPreamble(...)` (or the concrete module) at factory.py.
- Re-run `lint-imports`; expect `0 broken`.

## R2. Deferred wiring for `ReproducibilityExporter`

**Severity**: low (dead-code-ish — class exists but is never instantiated
outside tests today).

**Finding**:
```
grep -rn "ReproducibilityExporter" src/  →  (class definition only)
```

No production code path currently constructs `ReproducibilityExporter`. When
a CLI command, API route, or background job eventually needs reproducibility
export, the call site must construct:

```python
from ds_agent.application.services.reproducibility_exporter import ReproducibilityExporter
from ds_agent.infrastructure.artifact.notebook_engine import NotebookEngine

exporter = ReproducibilityExporter(experiment_log=..., notebook_engine=NotebookEngine())
```

This mirrors the existing test setup at
`tests/unit/application/test_reproducibility.py:31,53`.

**Why not fixed in S1**: There is no existing wiring site to upgrade; adding
a new one would constitute feature work, which Resume scope forbids.

## R3. Subagent test fixture gap (pre-existing design assumption)

**Severity**: medium (5 unit tests fail today)

**Finding**: `tests/unit/application/test_subagent.py::TestSubagentOrchestration::*`
(4 tests) fail with:

```
RuntimeError: Lineage service is not configured. Call set_lineage_service()
at the composition root before use.
```

The chain is:
```
SubagentOrchestrator._run_subagent
  → ProcessSubagent.execute
    → build_hook_registry(...)
      → LineageCaptureHook()
        → get_lineage_service()  # raises because set_lineage_service was never called
```

The S1 refactor made `get_lineage_service()` strict (raise instead of
silently constructing a default). Subagent tests rely on `build_hook_registry`
to be callable without the factory-level composition root ever having run.

**Why not fixed in S1**: `subagent_orchestrator.py`, `governance_hooks.py`,
`process_subagent.py`, and the test fixtures are outside S1's file list.
Adding a conftest-level `set_lineage_service(Mock())` fixture or decoupling
`build_hook_registry` from `get_lineage_service` belongs to a subagent or
test-infra stream.

**Suggested scope for follow-up**:
- Option A: Add a pytest fixture in `tests/conftest.py` or
  `tests/unit/application/conftest.py` that calls `set_lineage_service(...)`
  with a no-op fake before subagent tests run.
- Option B: Make `LineageCaptureHook` gracefully degrade (e.g. skip lineage
  when the service is unset) so tests without the composition root can still
  exercise orchestration.
- Option C: Make `build_hook_registry` accept an explicit lineage-service
  argument (preferred — aligns with Clean Architecture and avoids hidden
  process-global state).

## R4. Pre-existing mypy errors in S1-touched files

**Severity**: low

Three mypy errors remain in `lineage_capture_service.py` and
`reproducibility_exporter.py`, all pre-existing relative to S1:

1. `lineage_capture_service.py:38` — `dict` invariance on `content=content`.
   Could be fixed by typing the intermediate dict as `dict[str, object]`
   explicitly or via `Mapping[str, object]`.
2. `lineage_capture_service.py:179` — `os.sys.version` → use `import sys`
   and `sys.version`.
3. `reproducibility_exporter.py:37` — variable `content` reused for `str`
   and `dict[str, object]` → introduce two variables or annotate as
   `str | dict[str, object]`.

These are mechanical fixes appropriate for a lint-cleanup PR; none of them
affect the port-inversion work and none of them alter runtime behavior.
