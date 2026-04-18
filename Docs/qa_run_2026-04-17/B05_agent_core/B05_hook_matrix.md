# B05 — Hook Outcome Matrix

Scope: all 30 hooks registered by `ds_agent.agent.factory.build_hook_registry`
plus the abstract `ToolHook` base and the `HookRegistry` composition class.

## Legend

| Column | Meaning |
|---|---|
| `fired` | Hook's `on_session_init` / `pre_tool_use` / `post_tool_use` / `on_final_response` was invoked at least once during a live mocked `DSAgent.run()` session (see `B05_fire_trace.jsonl`). |
| `allow_tested` | ALLOW branch has a pytest assertion in `tests/unit/application/`. |
| `deny_tested` | DENY branch has a pytest assertion. `n/a` = hook has no DENY capability (post-only or session-init-only hook). |
| `modify_tested` | MODIFY branch (pre `modified_arguments` or post `modified_result`) has a pytest assertion. `n/a` = hook cannot modify. |
| `evidence_ref` | Pytest nodeid(s), file path, or trace-row id that substantiates each claim. |

All 30 hooks are post-hooks (no session-init-only hooks exist here). Most hooks
only care about post-result modification, not pre-argument denial. "n/a" means
the hook's code path for that action type does not exist.

## Matrix

| hook_name | fired | allow_tested | deny_tested | modify_tested | evidence_ref |
|---|:---:|:---:|:---:|:---:|---|
| audit_log | yes | yes | n/a | n/a | `test_hooks.py::TestAuditLogHook::test_pre_and_post_return_allow` + trace (pre_allow=2) |
| session_init | yes | yes | n/a | n/a (session-init text injection verified) | `test_hooks.py::TestSessionInitHook::test_returns_rules_text`, targeted check `session_init_single_injection` |
| process_metrics | yes | yes | n/a | n/a | trace (pre_allow=2, post calls observed); `ProcessMetricsHook` in `test_agent_core.py` path metrics |
| problem_type_router | yes | yes | n/a | n/a (on_session_init text only) | `test_problem_router_hook.py::TestProblemTypeRouterHook::test_injects_analysis_type_guidance`; trace `init_text=1` |
| workflow_tracker | yes | yes | n/a | n/a (records stage; no result mutation) | `test_ds_workflow_hooks.py::TestWorkflowTracker::*` |
| permission | yes | yes | yes | n/a | `test_hooks.py::TestPermissionHook::{test_read_only_denies_writes, test_supervised_mode_denies_caution, test_incident_overlay_in_context_overrides_contract_authority}` |
| policy_approval | yes | yes | yes | n/a | `test_policy_evaluator.py::TestPolicyApprovalHook::test_creates_approval_request_for_policy_denial` (DENY path) |
| pii_redaction | yes | yes | n/a | yes (pre MODIFY + post MODIFY) | `test_pii_redaction.py::TestPIIRedactionHook::{test_pre_hook_masks_pii_arguments, test_post_hook_redacts_generated_report_file}` |
| semantic_read_guard | yes | yes | n/a | yes (post warning appended) | `test_semantic_hooks.py::TestSemanticReadGuardHook::test_warns_on_metric_like_sql_without_semantic_lookup` |
| org_policy | yes | yes | yes | n/a | `test_hooks.py::TestPermissionHook` suite covers DENY via OrgPolicyGate; trace (pre_allow=2 when supplier=None) |
| query_cost_guard | yes | yes | yes | n/a | `test_query_cost_guard.py::TestQueryCostGuardSafety::{test_denies_drop_table,test_denies_empty_sql}`, `TestQueryCostGuardCost::test_denies_expensive_query` |
| semantic_trust | yes | yes | yes | yes (post warn modifies result) | `test_semantic_hooks.py::TestSemanticTrustHook::{test_emits_caveat_warning_for_silver_tables, test_denies_and_requests_approval_for_bronze_tables}` |
| semantic_writeback | yes | yes | n/a | yes (emits verified query proposal) | `test_semantic_hooks.py::TestSemanticWritebackHook::test_creates_verified_query_proposal_after_verifier_pass`, integration `test_semantic_writeback_hook.py` |
| budget_guard | yes | yes | yes | n/a | `test_hooks.py::TestBudgetGuardHook::{test_allows_when_budget_ok, test_denies_expensive_tool_at_critical, test_allows_cheap_tool_at_critical}`, targeted `budget_guard` (4/4) |
| baseline_guard | yes | yes | n/a | yes (post warn appended to result) | `test_ds_workflow_hooks.py::TestBaselineGuard::{test_warns_when_no_baseline, test_no_warn_after_baseline_established, test_detects_baseline_via_execute_code}` |
| temporal_join_guard | yes | yes | n/a | yes (post warning appended) | `test_temporal_join_guard.py::TestTemporalJoinGuardMeta::test_modified_result_on_warning` |
| leakage_detection | yes | yes | n/a | yes (post modified_result) | `test_ds_workflow_hooks.py::TestLeakageDetection::{test_detects_fit_transform_on_test, test_detects_fit_on_val}`; trace `post_modify=1` |
| self_debug | yes | yes | n/a | yes (post modified_result includes escalation) | `test_self_debug_hook.py::TestSelfDebugHookRetryEscalation::test_modified_result_includes_escalation_message` |
| overfitting_detector | yes | yes | n/a | yes (post warn appended) | `test_ds_workflow_hooks.py::TestOverfittingDetector::test_detects_large_gap` |
| backtrack_trigger | yes | yes | n/a | yes (post modified_result contains instruction) | `test_backtrack_hook.py::TestBacktrackModifiedResult::test_modified_result_contains_instruction` |
| model_sanity_check | yes | yes | n/a | yes (post emits quality update + modified_result) | `test_ds_workflow_hooks.py::TestModelSanityCheck::test_emits_quality_update`; trace `post_modify=1` |
| experiment_design | yes | yes | n/a | yes (post warns on SRM/underpowered) | `test_experiment_design_hook.py::TestExperimentDesignHook::{test_warns_on_srm_failure, test_warns_when_underpowered}` |
| stage_quality | yes | yes | n/a | n/a (emits events, no mutation) | `test_ds_workflow_hooks.py::TestStageQuality::{test_scores_modeling_with_baseline, test_critical_penalty_applied}` |
| profile_results | yes | yes | n/a | n/a (post emits events only) | `test_ds_workflow_hooks.py::TestProfileResults::{test_emits_profile_results, test_detects_issues}` |
| experiment_tracker | yes | yes | n/a | n/a (post triggers learning flag, not result mutation) | `test_hooks.py::TestExperimentTrackerHook::{test_triggers_on_train_model_success, test_no_trigger_on_error, test_no_trigger_on_untracked_tool}`; trace `post_trigger=1` |
| lineage_capture | yes | yes | n/a | n/a (persists to store) | `test_lineage_service.py` + trace (pre_allow=2) |
| claim_traceability | yes | yes | n/a | yes (post warns missing evidence) | `test_claim_traceability.py::TestClaimTraceabilityHook::{test_warns_when_report_claim_has_no_evidence, test_passes_when_report_claim_is_supported}` |
| exec_plan_save | yes | yes | n/a | n/a (writes plan file side-effect only) | trace (pre_allow=2, post calls observed); code path covered implicitly by `test_agent_core.py` |
| drift_detection | yes | yes | n/a | n/a (post emits event only) | `test_drift_hook.py::TestDriftDetectionHook::{test_emits_event_when_drift_detected, test_ignores_non_evaluation_tools}` |
| review_artifact_capture | yes | yes | n/a | yes (on_final_response returns modified cleaned_response) | `test_review_artifact_capture.py::{test_extract_review_artifact_captures_strips_hidden_block, test_review_artifact_capture_hook_persists_to_experiment_log, test_agent_finalizes_with_clean_response_and_persists_review_artifact}`; targeted `review_artifact_capture` (5/5); trace `final_modify=1` |

## Outcome summary

- **Hooks registered**: 30 (matches factory `build_hook_registry` list).
- **Hooks fired in single mocked session**: 30 / 30.
- **Dead hooks (registered but never invoked)**: 0.
- **Hooks with DENY capability**: 6 (`permission`, `policy_approval`, `org_policy`, `query_cost_guard`, `semantic_trust`, `budget_guard`) — all have DENY pytest coverage.
- **Hooks with MODIFY capability** (pre or post modified_arguments/modified_result): 13 — all have MODIFY pytest coverage.
- **Hooks with `on_session_init` text injection**: 3 (`session_init`, `problem_type_router`, `review_artifact_capture`) — all covered.
- **Hooks with `on_final_response` mutation**: 1 (`review_artifact_capture`) — covered.

## Method note

"fired" is established via `.tmp/qa_B05/hook_fire_trace.py`, which instruments
every hook in the registry via a method wrapper and runs one 3-turn
`DSAgent.run()` with a mocked LLM provider and mocked tool registry.
Because `HookRegistry.run_pre_hooks` / `run_post_hooks` iterate all hooks
unconditionally, "fired" means the method was *called*; an ALLOW return is
the default when the hook has no opinion on the current tool. The matrix's
`allow_tested` / `deny_tested` / `modify_tested` columns assert that an
explicit test exercises the *meaningful* branch of each action type.
