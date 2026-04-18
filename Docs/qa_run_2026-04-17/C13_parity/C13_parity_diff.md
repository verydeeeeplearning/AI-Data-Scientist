# C13 — Parity Diff Matrix

**Run date**: 2026-04-17
**Source of truth for raw numbers**: `channel_signatures.json`, `parity_diff_raw.json`
**Harness**: `parity_harness.py`
**Strategy**: factory-level simulated construction (fallback to code-level proof for Telegram bot / Electron packaged app — **fallback_used = true**, see §6).

## 1. Scenario × Channel matrix

| Scenario / Channel | CLI | Telegram | Electron (WS) |
|--------------------|:---:|:--------:|:-------------:|
| P-01 basic analysis → report | OK | OK | OK |
| P-02 autonomy mode transition | OK | OK | OK |
| P-03 learning governance | OK | OK | OK |

9/9 channel builds completed. 0 failures.

## 2. Equivalence fields (all identical across all 9 runs)

| Field | Value (all channels, all scenarios) |
|-------|-------------------------------------|
| `hook_count` | 30 |
| `hooks` (sorted class names) | Identical SHA of list — see §3 |
| `skill_names` | `scoping, data-profiling, eda, feature-engineering, modeling, evaluation, reporting` |
| `tool_count` | 75 |
| `tools_hash` | `a0c16d97f9de642e8562c734b562b44b7c85ea3c11323ab7c07131b33b598dea` |
| `budget.max_iterations` | 100 |
| `budget.max_cost_usd` | 10.0 |
| `mode` | `auto` |
| `authority_mode` | `null` (None — test seeds with overlay-not-set) |
| `transcript_store_wired` | false (harness did not supply one — same across channels) |
| `checkpoint_store_wired` | false |
| `goal_store_wired` | true |
| `working_memory_store_wired` | true |
| `approval_store_wired` | true |
| `skill_hub_wired` | true |
| `post_learner_wired` | true |
| `tool_registry_class` | `ds_agent.tools.registry.ToolRegistry` |

## 3. Hook chain (30 hooks — identical across 9 runs)

```
AuditLogHook
BacktrackTriggerHook
BaselineGuardHook
BudgetGuardHook
ClaimTraceabilityHook
DriftDetectionHook
ExecPlanSaveHook
ExperimentDesignHook
ExperimentTrackerHook
LeakageDetectionHook
LineageCaptureHook
ModelSanityCheckHook
OrgPolicyHook
OverfittingDetectorHook
PermissionHook
PIIRedactionHook
PolicyApprovalHook
ProblemTypeRouterHook
ProcessMetricsHook
ProfileResultsHook
QueryCostGuardHook
ReviewArtifactCaptureHook
SelfDebugHook
SemanticReadGuardHook
SemanticTrustHook
SemanticWritebackHook
SessionInitHook
StageQualityHook
TemporalJoinGuardHook
WorkflowTrackerHook
```

Matches plan / B05 agent-core gate (30 hooks).

## 4. Allowed deltas (expected per plan)

These differ by channel and are **not** required to match:

| Field | Observed difference |
|-------|---------------------|
| `channel` | `"CLI"` / `"Telegram"` / `"Electron"` |
| `session_id` | harness uses `<scenario>__<channel>` shape |
| `callbacks` class (in production) | `TUICallbacks` / `TelegramCallbacks` / WS-bound callbacks |
| `surface` (runtime-set via `set_runtime_context`) | `"cli"` / `"telegram"` / `"ws"` |
| timestamps in session logs | per-run wall clock |

## 5. Scenario-specific observations

### P-01 (basic analysis → report)

- All three channels wire identical `TaskContractContainer` (goal → metric_spec → verifier → DeliveryPack) via `build_task_contract_container(workspace_dir, store=None, llm_provider=provider)` in factory.py:387.
- DeliveryPack content hash is a runtime output and would be computed identically given the same LLM provider trace — harness does not execute LLM (per constraint "no real provider call"). Parity of the *production mechanism* is proven via the identical container and hook chain.

### P-02 (autonomy mode transition)

- All three channels accept the same `authority_mode` parameter in `create_agent`; the factory coerces via `AuthorityMode.coerce(...)` in factory.py:448.
- `PolicyApprovalHook`, `PermissionHook`, and `OrgPolicyHook` are registered identically — so Supervised → Delegate approval path is identically wired.
- The approval_store is passed identically through (harness seeded the same JsonApprovalStore location).

### P-03 (learning governance)

- The process-global `PostLearningAdapter` constructed at `factory.py:433` is identical across channels.
- `LearningInbox` promote/deprecate is driven by the `learning_store` (v13) mounted at workspace level — same DB path across channels; identical tool schema reachable because `tools_hash` matches.

## 6. Fallback declaration (required by plan §4)

**`fallback_used = true`** — the parity test was conducted at the
**Python factory-call level** rather than end-to-end through a real
Telegram bot (would require network + live bot token) or a packaged
Electron app (would require `npm run build` + chromium, and packaging
is C15's scope).

The fallback is authorised by the plan (§6.1 step 4 "실용 대안"): when
process-level execution of all three channels is impossible due to
environment constraints, prove parity via the `create_agent()` call-path
and inject a stubbed provider + stubbed callbacks. The evidence is:

1. Static source evidence — `call_graph_evidence.md` (all three entry
   points import & call `create_agent`).
2. Dynamic harness evidence — `parity_harness.py` + `channel_signatures.json`
   (9 runs, bit-identical signatures across equivalence fields).

The fallback does **not** run the LLM — the stub provider raises on
`chat()`. That is by design: the parity contract is about *wiring*
(hooks, tools, skills, stores, budget, prompt builder), not about
non-deterministic LLM output.

## 7. Residual gaps (outside C13 scope, informational)

| Gap | Where to address |
|-----|------------------|
| Real Telegram bot run with fake update harness | C16 Chaos/regression or post-beta integration run |
| Packaged Electron build + Playwright headless parity run | C15 Packaging agent (owns build pipeline) |
| LLM-dependent fields (`verdict.confidence`, `delivery_pack.content_hash`) byte-match | needs reproducible LLM stub fixture — propose adding a record-replay fixture as Tier 4 task |
| `tool_count` = 75 vs plan-documented 86 | Explained in `call_graph_evidence.md` §6 — lazy-imported tools from CLI/WS entry modules. Not a parity failure because all 3 channels see the same set. |
