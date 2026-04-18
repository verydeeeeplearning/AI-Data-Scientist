# B05 — Agent Core & Hook Chain Tester

**Tier**: 2
**Duration**: ~20 min
**Status**: pass
**Code SHA**: git-unavailable

## 1. Scope

Tested units (read-only; zero source modifications):

- `src/ds_agent/agent/core.py` — `DSAgent.run()` main loop, hook chain wiring,
  budget enforcement, final response hook path.
- `src/ds_agent/agent/prompt_builder.py` — `PromptBuilder._assemble`,
  priority-based section dropping, required/optional boundary.
- `src/ds_agent/agent/hooks.py` — `HookRegistry` pre/post/session/final chains,
  REL-02 hook-failure isolation.
- `src/ds_agent/agent/factory.py::build_hook_registry` — 30-hook registration.
- `src/ds_agent/agent/builtin_hooks.py` — `PermissionHook`, `OrgPolicyHook`,
  `AuditLogHook`, `BudgetGuardHook`, `SessionInitHook`, `ProblemTypeRouterHook`,
  `ExecPlanSaveHook`, `ProcessMetricsHook`, `ExperimentTrackerHook`,
  `ReviewArtifactCaptureHook`.
- `src/ds_agent/agent/ds_workflow_hooks.py` — `WorkflowTrackerHook`,
  `LeakageDetectionHook`, `BaselineGuardHook`, `OverfittingDetectorHook`,
  `StageQualityHook`, `ProfileResultsHook`, `ModelSanityCheckHook`,
  `ExperimentDesignHook`, `DriftDetectionHook`.
- `src/ds_agent/agent/governance_hooks.py` — `PolicyApprovalHook`,
  `PIIRedactionHook`, `LineageCaptureHook`.
- `src/ds_agent/agent/semantic_hooks.py` — `SemanticReadGuardHook`,
  `SemanticTrustHook`, `SemanticWritebackHook`.
- `src/ds_agent/agent/query_cost_guard_hook.py` — `QueryCostGuardHook`.
- `src/ds_agent/agent/reporting_hooks.py` — `ClaimTraceabilityHook`.
- `src/ds_agent/agent/backtrack_hook.py` — `BacktrackTriggerHook`.
- `src/ds_agent/agent/self_debug_hook.py` — `SelfDebugHook`.
- `src/ds_agent/agent/temporal_join_guard_hook.py` — `TemporalJoinGuardHook`.

All 30 concrete hook classes are accounted for.

Out of scope (pre-existing fails per HANDOFF §4.6):
- `tests/unit/application/test_semantic_ports.py::test_semantic_ports_are_runtime_checkable`
- mypy 3-count pre-existing errors in lineage / reproducibility modules.

## 2. Methodology

### 2.1 Static enumeration
AST-like `Grep` scan over `src/ds_agent/agent/*` confirms **30** concrete
`ToolHook` subclasses (plus the abstract `ToolHook` base in `hooks.py`). Count
matches HANDOFF §5.3 "Hook: 30" and plan-doc §10.1 Tier 2 gate criterion
"30 hook 전부 fire 확인".

Registry enumeration (`build_hook_registry(...).hooks`) yields exactly 30
entries, priority-sorted:

```
audit_log(0), session_init(0), process_metrics(1), problem_type_router(3),
workflow_tracker(5), permission(10), policy_approval(10), pii_redaction(11),
semantic_read_guard(12), org_policy(15), query_cost_guard(15),
semantic_trust(15), semantic_writeback(15), budget_guard(20),
baseline_guard(20), temporal_join_guard(25), leakage_detection(30),
self_debug(35), overfitting_detector(35), backtrack_trigger(40),
model_sanity_check(40), experiment_design(40), stage_quality(45),
profile_results(48), experiment_tracker(50), lineage_capture(50),
claim_traceability(50), exec_plan_save(55), drift_detection(55),
review_artifact_capture(60).
```

### 2.2 Live fire trace
`.tmp/qa_B05/hook_fire_trace.py` wraps every hook's
`on_session_init`, `pre_tool_use`, `post_tool_use`, and `on_final_response`
with an instrumenting proxy that emits a JSONL trace row per invocation, then
runs a 3-turn mocked session:

1. LLM call → `train_model(model_type="dummy")` (triggers BaselineGuard,
   ExperimentTracker, ModelSanityCheck, OverfittingDetector, StageQuality,
   LineageCapture pre/post chain).
2. LLM call → `feature_engineer(target="y", include_target_in_features=True)`
   (triggers LeakageDetection pre/post and WorkflowTracker).
3. LLM final text with `<!-- DS_REVIEW_ARTIFACTS {...} -->` block
   (triggers ReviewArtifactCaptureHook `on_final_response`).

LLM provider is `AsyncMock`, tool registry is a dict-backed `AsyncMock`.
No real external adapter is invoked. Workspace is a temp dir.
Lineage store is an in-memory port implementation (injected at composition
root via `set_lineage_service`).

Output: `Docs/qa_run_2026-04-17/B05_agent_core/B05_fire_trace.jsonl` — 181
rows. A registry-snapshot row confirms the exact 30-hook membership used.

### 2.3 Hook outcome verification
For each hook, three branches were evaluated:

- **ALLOW**: default path. Evidenced by trace `pre_allow=2` per hook (two
  tool calls observed by every pre-hook after session init).
- **DENY**: verified against existing pytest suites and, for
  `BudgetGuardHook`, via targeted probe
  (`.tmp/qa_B05/targeted_checks.py::test_budget_guard_thresholds` — 4 cases
  passed including boundary at exactly 95%).
- **MODIFY**: verified per hook against the matrix (see
  `B05_hook_matrix.md`). The trace observed live MODIFY events from
  `leakage_detection` (post), `model_sanity_check` (post), and
  `review_artifact_capture` (on_final_response).

"n/a" in the matrix means the hook's implementation does not expose that
branch at all (e.g. a pure post-observer has no pre-DENY code path).

### 2.4 Scoped pytest
Per HANDOFF §4.5 (no full-regression on Windows):

```
pytest tests/unit/application/test_hooks.py
       tests/unit/application/test_agent_core.py
       tests/unit/application/test_semantic_hooks.py
       tests/unit/application/test_ds_workflow_hooks.py
       tests/unit/application/test_review_artifact_capture.py
       tests/unit/application/test_experiment_design_hook.py
       tests/unit/application/test_backtrack_hook.py
       tests/unit/application/test_drift_hook.py
       tests/unit/application/test_query_cost_guard.py
       tests/unit/application/test_temporal_join_guard.py
       tests/unit/application/test_problem_router_hook.py
       tests/unit/application/test_self_debug_hook.py
       tests/unit/application/test_claim_traceability.py
       tests/unit/application/test_pii_redaction.py
       tests/unit/application/test_policy_evaluator.py
       tests/unit/agent/
       --junitxml=Docs/qa_run_2026-04-17/B05_agent_core/junit.xml
```

Result: **212 passed in 3.45 s** — no failures, no errors, no warnings of
concern. JUnit XML captured at `junit.xml`.

### 2.5 Targeted probes
Results: `.tmp/qa_B05/targeted_results.json` /
`Docs/qa_run_2026-04-17/B05_agent_core/B05_targeted_results.json`.

| Probe | Result |
|---|---|
| `BudgetGuardHook` threshold boundary (95%) | **pass** — DENY at exactly 95%, DENY above, ALLOW below, cheap tools never denied. |
| `IterationBudget` stop at `max_iterations=3` | **pass** — provider.chat called exactly 3 times (no 4th), final contains "budget...exhausted", `task.failed` emitted with `reason="budget_exhausted"`. |
| `PromptBuilder` token-budget priority | **pass** — under `max_system_tokens=150`, required `identity`/`authority`/`safety` survive; optional `memory` and `project` dropped. Assembler probe confirmed with synthetic sections. |
| `SessionInitHook` single injection | **pass** — `### DS Methodology` appears exactly once, `### Safety` exactly once, baseline rule ("DummyClassifier") present. Running session-init a second time returns identical text (no accumulation). |
| `ReviewArtifactCaptureHook` captures block | **pass** — parses `<!-- DS_REVIEW_ARTIFACTS {...} -->`, strips it from the cleaned response, invokes `DecisionOsContainer.record_review_artifact.execute` with `run_id="run-42"`, `skill_name="backtesting"`, and emits `decision_os.review_artifacts.captured`. |

## 3. Results Matrix

See `B05_hook_matrix.md` for the per-hook 5-column table. Headline counts:

- hooks_registered: 30
- hooks_fired_in_session: 30
- dead_hooks: 0
- hooks_with_deny_branch: 6 (all DENY-tested)
- hooks_with_modify_branch: 13 (all MODIFY-tested)
- hooks_with_session_init_injection: 3 (all tested)
- hooks_with_final_response_mutation: 1 (tested)

## 4. Failures and Anomalies

No in-scope failures. Items observed during methodology that are *not* B05
defects:

- `extract_review_artifact_captures` expects `<!-- DS_REVIEW_ARTIFACTS {...} -->`
  HTML-comment format, not `<ds:review_artifacts>...</ds:review_artifacts>`
  as the plan's test spec text suggested. The plan-spec wording is looser
  than the code contract — the code is correct and tested. Recommend the
  next plan revision cite the actual marker.
- In the live fire trace, our synthetic `<!-- DS_REVIEW_ARTIFACTS ... -->`
  payload passed the parser but the `DecisionOsContainer` rejected the
  artifact payload because it lacked `consistency_score` required by the
  real `BacktestResult` schema. The **hook wiring** is correct — the parser
  extracted the block, invoked the use case, and the error was logged and
  emitted via `decision_os.review_artifacts.capture_failed`. The
  downstream schema rigidity is a separate Decision OS concern and is
  covered by the isolated targeted probe that uses a fake container
  (`FakeUseCase`) which confirmed the hook flow contract end-to-end.
- `task.failed` carries `reason="llm_error"` and `reason="budget_exhausted"`
  consistently. Both observed.

Out-of-scope pre-existing items (per HANDOFF §4.6) — not re-exercised by
this audit:
- `test_semantic_ports_are_runtime_checkable` (memory/semantic suite).
- mypy 3-count in `lineage_capture_service.py`, `reproducibility_exporter.py`.

## 5. Evidence Index

| Artifact | Location |
|---|---|
| JUnit XML (212 passed) | `Docs/qa_run_2026-04-17/B05_agent_core/junit.xml` |
| Fire trace JSONL (181 rows) | `Docs/qa_run_2026-04-17/B05_agent_core/B05_fire_trace.jsonl` |
| Targeted probe JSON (5 probes) | `Docs/qa_run_2026-04-17/B05_agent_core/B05_targeted_results.json` |
| Hook matrix | `Docs/qa_run_2026-04-17/B05_agent_core/B05_hook_matrix.md` |
| Harness script (hook fire trace) | `.tmp/qa_B05/hook_fire_trace.py` |
| Harness script (targeted probes) | `.tmp/qa_B05/targeted_checks.py` |
| Start marker | `Docs/qa_run_2026-04-17/B05_agent_core/START.json` |
| Final marker | `Docs/qa_run_2026-04-17/B05_agent_core/FINAL.json` |

## 6. Recommendations

None blocking for Tier 2 gate. Post-beta nice-to-haves:

1. Document the `<!-- DS_REVIEW_ARTIFACTS -->` marker and envelope schema in
   `Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md` §5.1 so future QA agents
   write correct fixtures.
2. Add a small architecture test that `len(build_hook_registry().hooks) == 30`
   so future hook additions/removals are flagged at import time instead of
   drifting silently from the Tier gate.
3. Consider extracting the six DENY-capable hooks into a `DenyingHook`
   marker Protocol to make the action-capability split grep-auditable.
4. Consider wiring a default "in-memory" `LineageStorePort` so tests /
   agents that don't touch Decision OS don't trip the
   `"Lineage service is not configured"` RuntimeError when calling
   `build_hook_registry` directly. (Today, callers must `set_lineage_service`
   first — as done in `.tmp/qa_B05/hook_fire_trace.py`.)
