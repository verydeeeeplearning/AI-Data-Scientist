# S5 — Recommendations (out-of-scope findings)

Findings surfaced during S5 verification that fall outside S5's declared
scope. No code change was made for any of these.

## RC-1. `tools/sandbox.py` still does lazy imports of `infrastructure.sandbox.preamble`

**Severity**: informational — does not break any contract after S5 because
both modules are outer layers (tools → infrastructure is permitted).

**Finding**: `src/ds_agent/tools/sandbox.py` still has:
- Line 231: `from ds_agent.infrastructure.sandbox.preamble import parse_violations`
- Line 260: `from ds_agent.infrastructure.sandbox.preamble import build_preamble`

These lazy imports were the reason the transitive chain reached
`infrastructure` from `application` before S5. With the router now
depending only on `SandboxPort`, the chain no longer starts in
application — so `lint-imports` is green. The import itself is not a
Clean Architecture violation (tools is outer; infrastructure is
another outer layer; outer→outer is fine).

If a future Clean Architecture iteration decides the tools package must
also isolate itself from infrastructure (e.g. to allow a pure-runtime
standalone distribution), then one more port inversion would be needed:
introduce a `SandboxPreamblePort` consumed by `tools/sandbox.py` and
implemented by an adapter in `infrastructure/sandbox/`. This was
explicitly out of scope for S5 per the instruction
"tools/sandbox.py의 lazy import 체인은 건드리지 말 것".

## RC-2. Router could be registered at composition root

**Severity**: informational.

**Finding**: `ExecutionRouter` is instantiated ad hoc at three call sites
(`tools/_ds_sandbox_runner.py:46`, `infrastructure/distributed/ray_adapter.py:38`,
`infrastructure/distributed/dask_adapter.py:49`), each of which creates
a fresh `ExecutionRouter()` purely to call `policy_for_tool(...)`.

If a future iteration wants all production sandbox creation to flow
through a single composition-root-wired router, `agent/factory.py` could
register one `ExecutionRouter(sandbox_factory=ProcessSandboxFactory())`
and publish it via a process-global accessor (same pattern as
`set_scheduler_service`, `set_lineage_service`). This is not necessary
today because the three call sites only use the policy-resolution method,
which does not depend on the factory.

## RC-3. Subagent tests could be made composition-root-agnostic at the service level

**Severity**: low.

**Finding**: The S5 fix for R3 uses an autouse conftest fixture because
the test specifications explicitly forbid touching
`governance_hooks.py`, `process_subagent.py`, or the tests themselves.
A more aggressive refactor — listed as Option C in S1's
RECOMMENDATIONS.md — would make `build_hook_registry` accept explicit
services as arguments, removing hidden process-global state entirely.
This is a desirable cleanup for a future sprint but is deliberately
deferred to keep S5 minimal.

## RC-4. Windows filesystem-state pollution in `data/`

**Severity**: medium for developer experience, low for CI correctness.

**Finding**: Full-unit-test sweeps on Windows show flakes in
`test_file_ops.py`, `test_placeholder_tools.py`, `test_telegram_runner.py`,
`test_decision_os_scheduler.py`, `test_integration_tools.py`. Several of
these fail even in isolation, because SQLite databases and JSON files
in `data/` are reused across runs (seeded records from prior sessions
are still present when a test expects an empty store).

Future hardening:
- Add an autouse fixture that points workspace-scoped stores into
  `tmp_path` for every test.
- Or add a `pytest` hook that wipes `data/memory/`, `data/governance/`,
  and `data/working/` at session start (with a `--keep-data` opt-out for
  debugging).

Out of S5's scope; logged here so the A01 / A04 re-audits are not
surprised by these flakes in their own full-suite sweeps.

## RC-5. `isinstance` checks in tests against the Protocol

**Severity**: informational.

`@runtime_checkable` protocols in Python perform structural isinstance
checks that can be surprisingly permissive (they only check attribute
presence, not signatures). The `test_router_accepts_any_sandbox_factory_port_implementation`
test uses a spy factory that structurally matches `SandboxFactoryPort`.
For stricter verification, mypy's type-check path is the primary
guarantee; `isinstance` is only used as a runtime smoke test.
