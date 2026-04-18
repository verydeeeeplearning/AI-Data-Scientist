# S5 — DIFF Summary

Two residual issues from S1 (R1: transitive infrastructure import via
`tools.sandbox`, R3: subagent tests broken by composition-root-strict
LineageCaptureHook) are addressed by port inversion and a scoped pytest
fixture, respectively. Behavioural semantics of every adapter are preserved.

## New files

| File | Purpose |
|------|---------|
| `src/ds_agent/application/ports/sandbox_port.py` | Defines `SandboxPort` + `SandboxFactoryPort` Protocols. Application-layer abstraction for one running sandbox and for the factory that creates one from an `ExecutionPolicy`. |
| `src/ds_agent/infrastructure/sandbox/sandbox_factory.py` | `ProcessSandboxFactory` adapter implementing `SandboxFactoryPort`. Thin delegation to the existing `ds_agent.tools.sandbox.create_sandbox` function; imported lazily so the application layer stays decoupled. |
| `tests/unit/application/conftest.py` | Autouse fixture `_default_lineage_service_for_application_tests` that installs a process-global `LineageCaptureService` backed by an in-memory `LineageStorePort` implementation so subagent-orchestrator tests (which indirectly construct `LineageCaptureHook()` via `build_hook_registry`) no longer raise `RuntimeError: Lineage service is not configured`. Previous value is restored on teardown to preserve isolation for tests that do their own explicit wiring. |

## Modified files

| File | Change |
|------|--------|
| `src/ds_agent/application/ports/__init__.py` | Re-export `SandboxFactoryPort` and `SandboxPort`. |
| `src/ds_agent/application/services/execution_router.py` | Removed `from ds_agent.tools.sandbox import ProcessSandbox, create_sandbox` (this was the transitive chain root). Added `__init__(sandbox_factory: SandboxFactoryPort | None = None)`. `create_sandbox_for_tool(...)` now delegates to the injected factory and raises `RuntimeError` with an explicit message if none was provided. `policy_for_tool(...)` is unchanged — callers like `tools/_ds_sandbox_runner.py` and `infrastructure/distributed/*.py` that only use policy resolution remain source-compatible. Return type is now the application-layer abstraction (`SandboxPort`), not the concrete `ProcessSandbox`. |
| `tests/unit/application/test_execution_router.py` | Updated `test_creates_expected_sandbox_for_tool` to inject `ProcessSandboxFactory()` (composition-root-style wiring). Added `test_router_accepts_any_sandbox_factory_port_implementation` (verifies DI contract with a bespoke stub factory). Added `test_router_raises_when_factory_missing_on_sandbox_call` (verifies the explicit error path). |

## Files intentionally left unchanged (S5 scope guard)

- `src/ds_agent/tools/sandbox.py` — No modifications. The lazy imports of
  `ds_agent.infrastructure.sandbox.preamble` at lines 231 and 260 are an
  internal implementation detail of the tools layer (both are outer layers;
  tools → infrastructure is permitted). Leaving this alone preserves
  compatibility for all existing callers (`tools/_ds_sandbox_runner.py`,
  `infrastructure/distributed/ray_adapter.py`, `infrastructure/distributed/dask_adapter.py`,
  `create_secure_sandbox`).
- `src/ds_agent/agent/factory.py` — No wiring change required. `ExecutionRouter`
  is instantiated ad hoc at each call site; the only call sites that need a
  sandbox factory are tests (they inject `ProcessSandboxFactory()`
  directly). Production call sites only use `policy_for_tool(...)`, which
  does not depend on the factory.
- `src/ds_agent/agent/governance_hooks.py` — No change to `LineageCaptureHook`.
  The failing subagent tests are fixed at the test-fixture level, as
  recommended in S1's RECOMMENDATIONS.md (Option A).
- `src/ds_agent/infrastructure/process_subagent.py` — No change.
- `tests/unit/application/test_subagent.py` — No change to the test bodies
  themselves; the fix is entirely confined to the new conftest fixture.

## Behavioural impact

- `ExecutionRouter()` (no args) — unchanged behaviour for `policy_for_tool(...)`.
  Calling `create_sandbox_for_tool(...)` without injecting a factory now raises
  a descriptive `RuntimeError` instead of silently calling the factory
  function. This is an intentional fail-fast for misconfigured call sites; no
  production call site does this today.
- `ProcessSandboxFactory().create_sandbox(...)` — byte-for-byte identical
  forwarding to `tools.sandbox.create_sandbox(...)`. No functional change to
  the sandbox selection logic, policy enforcement, or return types.
- Subagent tests — pass with lineage records stored in an in-memory map
  instead of raising.
