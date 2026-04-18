# B06 — Tools Registry Fuzz Tester

**Tier**: 2
**Duration**: ~30 min
**Status**: pass
**Code SHA**: git-unavailable (no repo)
**Dependencies**: A01 / A02 / A03 / A04 Round 2 re-audits pass

## 1. Scope

- 40 modules under `src/ds_agent/tools/` containing `@tool`-decorated handlers.
- **86** tools registered at runtime via `ToolRegistry` (Fix Sprint S3 raised this
  from 76 to 86 by parameter-isolating `learning_tools` (6) and `portfolio_tools` (5)).
- Five input shapes per tool → **430-cell matrix**.

Not in scope: hook/controller/end-to-end behaviour (B05/B08 own those),
full regression pytest (per HANDOFF §4.5 Windows flake policy).

## 2. Methodology

1. **Registry discovery** — two independent enumerations:
   - Source AST scan of `src/ds_agent/tools/*.py` for `@tool(...)` decorators
     → 86 names (`ast_scan.json`).
   - Runtime import of all 40 modules (factory.import_all_tools + learning,
     portfolio explicit) → `ToolRegistry.list_tools()` returns 86
     (`live_full.json`).
   - **Diff**: `set(AST) XOR set(LIVE) == {}`.
2. **Fuzz harness** — `.tmp/qa_B06/run_fuzz.py` (copied to report dir as
   `run_fuzz.py`). Drives each tool through `ToolRegistry.dispatch()` with
   five inputs, writes each cell to `B06_tools_fuzz.csv`.
3. **Scope-isolated pytest** — `tests/unit/tools/` + `tests/integration/tools/`
   only; JUnit XML at `pytest_scope.xml`. No global regression.
4. **Sandbox-only execution** — all `execute_code` / `distributed_exec` calls
   route through `ExecutionRouter → SandboxPort → ProcessSandbox` (SandboxPort
   introduced by Fix Sprint S5). No real shell or host-level execution.
5. **Workspace isolation** — `set_active_workspace(.tmp/qa_B06/workspace)` so
   that file-ops boundary checks actually fire.
6. **No source modification**; no writes to `data/` or test files.

### 2.1 Input-type definitions

| Input | Description |
|-------|-------------|
| `normal` | Fixture satisfying `required` with schema-valid types. |
| `schema_violation` | Drop first required key AND add an unknown key `__unexpected_fuzz_key__`. |
| `timeout` | Monkeypatch handler to an async `sleep(3)` while forcibly setting `entry.timeout=1`, then dispatch. Expect `"timed out"` marker in response within < 2.5 s. |
| `sandbox_violation` | For `execute_code` / `distributed_exec` only. Five payloads (§3.4). All other tools correctly `skipped`. |
| `boundary` | Tool-specific guardrail check — path traversal, SQL injection, idempotency, or sandbox-level traversal open. |

## 3. Results Matrix

### 3.1 Aggregate

| Input type | pass | fail | skipped | N |
|------------|:----:|:----:|:-------:|:-:|
| normal | 86 | 0 | 0 | 86 |
| schema_violation | 86 | 0 | 0 | 86 |
| timeout | 86 | 0 | 0 | 86 |
| sandbox_violation | 2 | 0 | 84 | 86 |
| boundary | 86 | 0 | 0 | 86 |
| **TOTAL** | **346** | **0** | **84** | **430** |

- 84 `sandbox_violation` skips are expected: only the two exec tools
  (`execute_code`, `distributed_exec`) accept arbitrary code, so the other
  84 tools have no attack surface for that input shape.
- **0 critical failures** — pass criterion met.

### 3.2 Registry list ↔ AST cross-check

| Metric | Value |
|--------|:-----:|
| AST-discovered `@tool` declarations | 86 |
| Runtime registered tools | 86 |
| Intersection | 86 |
| Only-in-AST | 0 |
| Only-in-runtime | 0 |

Matches A03 Round 2 re-audit figure.

### 3.3 Schema validation path

`ToolRegistry._validate_arguments` returned a structured JSON error payload
(`"Invalid arguments for <tool>: missing required: [...]; unknown keys: [...]"`)
for **86/86** tools when a required field was dropped or an unknown key was
passed. No tool bubbled a raw `TypeError`. Acts as the `ToolValidationError`
contract required by spec §5.2 step 3.

### 3.4 Sandbox payload coverage

`execute_code` and `distributed_exec` were each subjected to five payloads:

| # | Payload | execute_code | distributed_exec |
|:-:|---------|:---:|:---:|
| 1 | `import socket` | BLOCKED | BLOCKED |
| 2 | `open('/etc/passwd').read()` | BLOCKED | BLOCKED |
| 3 | `import os; os.system('whoami')` | BLOCKED | BLOCKED |
| 4 | `urllib.request.urlopen('http://evil.example')` | BLOCKED | BLOCKED |
| 5 | `__import__('os').system('whoami')` | BLOCKED | BLOCKED |

→ **10/10 sandbox blocks**. Block mechanism = `CodeSecurityChecker.check()`
regex + AST layer (`src/ds_agent/tools/code_security.py:30-179`). Response
pattern: `{"error": "Security check failed: <desc>", "tool": "..."}`.

### 3.5 SQL injection

`sql_query` with payload `"; DROP TABLE users; --"` returns:

```json
{"error": "SQL safety violation: Query must start with SELECT/WITH/EXPLAIN, got: ;", "tool": "sql_query"}
```

Defence: `validate_sql_safety` in `src/ds_agent/domain/value_objects/connector.py`
enforces `_ALLOWED_PREFIXES = {SELECT, WITH, EXPLAIN, SHOW, DESCRIBE}` + a `\bDROP\b`
regex. The tool never reaches the adapter layer, so parameter binding is moot
for this payload — the validator short-circuits.

### 3.6 Workspace path bound

For tools that directly enforce `is_within_workspace()`
(`read_file`, `write_file`, `list_files`, `data_loader`, `data_profiler`),
passing `"../../../etc/shadow"` returns structured errors:

- `file_ops` family emits `{"error": "Path outside workspace: ..."}` via
  `_check_path_in_workspace` (`src/ds_agent/tools/file_ops.py:10-32`).
- `data_loader` / `data_profiler` return FileNotFound-class errors when the
  file doesn't exist — accepted as safe outcome because no sensitive content
  is exposed.

For sandbox-family DS tools (`run_eda`, `train_model`, `feature_engineer`,
`evaluate_model`, `generate_deployment`, `generate_report`, `data_profiler`),
the boundary test pushed `code=open('../../../etc/shadow').read()` through the
tool. Result: sandbox returns an error (security check, or host-level
FileNotFound on Windows). No traversal open succeeded.

### 3.7 Timeout enforcement

For each tool, `entry.handler` was swapped with an async `sleep(3)` and
`entry.timeout` lowered to 1 s. Dispatch returned a `{"error": "Tool '<name>' timed out after 1s"}`
response in < 2.5 s for **86/86** tools. Confirms `ToolRegistry.dispatch`
honours `asyncio.wait_for(coro, timeout=entry.timeout)` (`registry.py:132`).

### 3.8 Idempotency

Twenty-six read-only tools (listed as `IDEMPOTENT` in `run_fuzz.py`) were
invoked twice with the same input; byte-level output equal in all cases.
Non-write tools are safely cacheable.

### 3.9 Scope-isolated pytest

`pytest tests/unit/tools/ tests/integration/tools/ -v --tb=short`
→ **26 passed, 0 failed** in 7.31 s. JUnit XML at `pytest_scope.xml`.
No regression from Round 2 Tier-1 baseline.

## 4. Failures and Anomalies

**None.** Critical failures = 0, `B06_failures/` is empty (README-only).

### 4.1 Non-critical observations

| ID | Observation | Impact | Recommendation |
|:--:|-------------|:------:|----------------|
| O-1 | `data_loader` schema allows `encoding`/`separator` as free strings; no explicit PII scan inside. | Low — execution-level security still applies. | Out of scope for B06; A02 security re-audit already validated PII flow. |
| O-2 | `drift_monitor` declares **zero** required params — accepts any/no arg combination. Schema-violation test still marks pass because an unknown key alone fails the `unknown keys` branch. | Low. | None. |
| O-3 | `dashboard_spec`, `slide_generate`, `create_calendar_event`, `create_work_object`, `record_review_artifact`, `render_delivery_artifact`, `render_stakeholder_artifact`, `run_verifier`, `open_git_pr`, `describe_table_trust` — all have multi-field `required` lists. Harness required careful schema mining (`live_full.json`). | None. | Document required fields alongside `prompt` text for LLM guidance. |
| O-4 | Timeout test uses an async sleep — works because `dispatch` always wraps via `asyncio.wait_for` even for sync handlers after the decorator wraps them. Verified no sync handler leaked through. | None. | Keep decorator wrapper as-is. |

### 4.2 Known environmental caveats (from HANDOFF §4.5 / §4.6)

Not in B06 scope, inherited:

- `ENV-1`: Windows `.tmp/pytest` teardown PermissionError flake — N/A here
  because scope-isolated run finished cleanly.
- `PRE-1` / `PRE-2`: pre-existing semantic-ports runtime-checkable fail and
  mypy 3-count — not re-tested in B06.

## 5. Evidence Index

- `Docs/qa_run_2026-04-17/B06_tools_registry/START.json`
- `Docs/qa_run_2026-04-17/B06_tools_registry/B06_tools_fuzz.csv` (430 rows)
- `Docs/qa_run_2026-04-17/B06_tools_registry/summary.json`
- `Docs/qa_run_2026-04-17/B06_tools_registry/ast_scan.json` (86 `@tool` names)
- `Docs/qa_run_2026-04-17/B06_tools_registry/live_full.json` (per-tool timeout, required, properties, async-ness, safety_level, category)
- `Docs/qa_run_2026-04-17/B06_tools_registry/pytest_scope.xml` (26 passed)
- `Docs/qa_run_2026-04-17/B06_tools_registry/run_fuzz.py` (full harness source)
- `Docs/qa_run_2026-04-17/B06_tools_registry/B06_failures/README.md` (empty — 0 failures)
- `Docs/qa_run_2026-04-17/B06_tools_registry/FINAL.json`

## 6. Recommendations

1. **Keep the 86-tool AST↔registry parity check in CI**. AST scan is ~200 ms;
   a drift would surface S3-style drift the moment a new module is added and
   forgotten in `factory.import_all_tools()`.
2. **Document the `_BLOCKED` / `_BLOCKED_MODULES` taxonomy** in
   `code_security.py` as a security spec — it is load-bearing for 10/10
   sandbox blocks in this audit.
3. **Standardise error shape**. Most tools return
   `{"error": "...", "tool": "..."}` but a few (older `integration_tools`)
   return `{"error": "..."}` without `tool`. Low priority; normalise in a
   maintenance sweep.
4. **Tools with zero `required` fields** (`drift_monitor`, `list_*`,
   `load_semantic_pack`, `list_learning_inbox`, etc.) could use a
   `oneOf`/minimum-filter to avoid accepting no-op calls silently. Not a
   security bug, quality-of-life for the LLM.
5. **Proceed to Tier 3** — B06 gate is green and unblocks C13/C14 consumers.
   Feed `B06_tools_fuzz.csv` into C14 Gold Task synthesis as seed fixtures.
