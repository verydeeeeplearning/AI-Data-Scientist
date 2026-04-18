# B09 Autonomy Control Plane — Test Report

**Agent**: B09 (Tier 2 — Feature Behavior)
**Date**: 2026-04-17
**Scope**: Spec 04 — Authority / Audience / Mission / ActionMatrix / ActionClassifier / approval / PolicyStudio.
**Self-judgement**: suspended. `FINAL.json.status` = `"pending_reviewer_judgement"`.

---

## 1. Scope

Per plan §5.5 the following 8 paths are probed:

| # | Path | Probe target |
|---|------|--------------|
| 1 | Authority 6 modes × risk tier matrix | `src/ds_agent/runtime/action_matrix.py` + runtime `AutonomyPolicy.evaluate` |
| 2 | Audience 5 personas | `src/ds_agent/domain/value_objects/audience_persona.py` + `agent/prompt_sections.py` + `application/services/audience_renderer.py` |
| 3 | Mission Pack YAML → prompt injection | `src/ds_agent/skills/mission_pack_loader.py` + bundled `weekly-kpi-triage.yaml` |
| 4 | ActionClassifier 5 strategies | `src/ds_agent/runtime/action_classifier.py` |
| 5 | Incident override 24h auto-expiry | `src/ds_agent/runtime/authority_overlay.py` |
| 6 | Freeze hard constraint | `AutonomyPolicy.evaluate` runtime overlay + matrix interaction |
| 7 | Certification persistence across restart | `src/ds_agent/infrastructure/persistence/certification_store.py` |
| 8 | PolicyStudio preview/apply (4 presets) | `ActionMatrix.with_overrides` contract surface |

Out of scope: electron UI, real external connectors, full pytest regression (§4.5 soft-fail).

---

## 2. Methodology

1. **Scope-isolated pytest**: 20 autonomy-relevant test modules (unit + integration) — 130 tests.
   Command: `pytest tests/unit/runtime/test_{action_matrix,authority_overlay,action_classifier,autonomy_policy_basic,legacy_mode_migration}.py tests/integration/test_autonomy_policy_matrix.py tests/unit/domain/{test_authority_mode,test_audience_persona,test_mission_pack,test_certification_spec}.py tests/unit/skills/test_mission_pack_loader.py tests/unit/application/{test_audience_renderer,test_submit_certification}.py tests/unit/presentation/{test_prompt_sections_authority_and_audience,test_prompt_mission_section,test_certification_presenters}.py tests/unit/infrastructure/{test_certification_cli,test_certification_api_routes}.py tests/integration/infrastructure/test_sqlite_certification_store.py tests/integration/test_mission_boundary_enforcement.py -v --tb=short`.
   → **130 passed, 0 failed**. JUnit: `B09_pytest_junit.xml`.
2. **Authority×ActionMatrix cross-tab**: `.tmp/qa_B09/build_authority_matrix.py` iterates every registered `ActionClass` × every `AuthorityMode`, classifies each action into SAFE/CAUTION/CRITICAL risk bucket, and compares against spec-derived expected-outcome set.
   → `B09_authority_matrix.csv` (84 cells).
3. **Runtime scenario probes**: `.tmp/qa_B09/test_b09_scenarios.py` exercises `AutonomyPolicy.evaluate()`, `resolve_authority_overlay()`, `ActionClassifier.classify()`, `ActionMatrix.with_overrides()` for every spec-required behavior.
4. **Audience diff dump**: `agent.prompt_sections.build_audience_section` rendered for each of the 5 personas with an identical authority+mission preamble. Output: `B09_audience_diffs/*.md`.
5. **Certification restart**: SQLite store written in process A (disposed), reopened in process B from the same file. Observed `is_certified=True` pre and post.

No source code was modified. No real external adapter was invoked.

---

## 3. Results Matrix

### 3.1 Authority × Action cell matrix (static `ActionMatrix.default()`)

| authority_mode | matrix cells | strict-spec pass | strict-spec fail |
|---|---:|---:|---:|
| shadow     | 14 | 14 | 0 |
| supervised | 14 | 14 | 0 |
| delegate   | 14 | 14 | 0 |
| autopilot  | 14 | 14 | 0 |
| incident   | 14 | 14 | 0 |
| freeze     | 14 | 11 | 3 |
| **total**  | **84** | **81** | **3** |

The 3 FREEZE fails at the static-matrix level:

| action | risk | matrix verdict | expected |
|---|---|---|---|
| `read_sensitive_table` | CAUTION (PII/restricted read) | `approve` | `skip` |
| `feature_engineering`  | CAUTION (local write)         | `auto`    | `skip` |
| `artifact_draft`       | CAUTION (local write)         | `auto`    | `skip` |

However, the runtime layer compensates: `AutonomyPolicy.evaluate()` lines 145-153 apply a hard-constraint overlay:

```python
if (
    context.authority is AuthorityMode.FREEZE
    and resolved_action_class.write_side_effect is not WriteEffect.NONE
):
    return AutonomyDecision(blocked=True, reason="freeze_mode_blocks_writes")
```

So `feature_engineering` and `artifact_draft` **are blocked at runtime** despite the static matrix saying `auto`. Runtime probe confirmed:

| action | static verdict | runtime result |
|---|---|---|
| `feature_engineering` | auto   | **BLOCKED** (reason=`freeze_mode_blocks_writes`) |
| `artifact_draft`       | auto   | **BLOCKED** (reason=`freeze_mode_blocks_writes`) |
| `read_sensitive_table` | approve | requires_approval=True (reason=`action_matrix_approve`) — matrix still asks for human gate |
| `read_sql_gold`        | auto   | AUTO (no block) — read-only, no side effect |
| `read_sql_bronze`      | auto   | AUTO (no block) — read-only |
| All 9 write classes    | skip/approve → runtime blocked | **9/9 writes blocked under FREEZE** |

### 3.2 Spec-vs-code discrepancy: "Freeze 모드에서 SAFE 도구조차 DENY"

Plan §5.5 probe #6 says *"Freeze 모드에서 SAFE 도구조차 DENY"*. Actual implementation:

- **All writes**: DENY (blocked). ✅ matches hard-constraint intent.
- **Read-only, public/internal sensitivity** (`read_sql_gold`, `read_sql_bronze`): AUTO (allowed). ⚠️ does not match "SAFE 도구조차 DENY".
- **Restricted/PII reads** (`read_sensitive_table`, `read_pii_table`): approve / skip.

This is a **semantic gap**, not a safety hole — FREEZE does block every potentially externally-observable mutation. Reads are retained for diagnostic work while frozen. Whether this matches product intent is a design-judgement question for the reviewer. Recorded without source edit per §4.1 (auditor ≠ fixer).

### 3.3 Audience 5-persona differentiation

All 5 personas produce distinct prompt sections. Cross-diff summary (all 5 rendered into `B09_audience_diffs/<persona>.md` with identical authority=delegate + mission=weekly-kpi-triage preamble):

| persona | lead-line directive |
|---|---|
| `junior_mentor` | "Teach the reasoning, not just the answer." |
| `peer_ds`       | "Be concise, technical, and reproducible." |
| `senior_staff`  | "Lead with the decision, risk, and caveat." |
| `executive`     | "Lead with business impact and the required decision." — Required to use SAFE / REVIEW / DANGER risk labels. |
| `auditor`       | "Every important claim needs a concrete source reference or policy reference." |

Each section diverges in tone + expected artifact shape; no two personas collapse to identical output.

Additionally `AudienceRenderer` (application-service layer) maps personas to different narrative-generation prompts (`_PERSONA_PROMPTS`) and different format expectations — covered by `tests/unit/application/test_audience_renderer.py` (3 tests passed).

### 3.4 Mission Pack YAML injection

`MissionPackLoader` loads bundled `weekly-kpi-triage.yaml` (v1). Rendered prompt section (`build_mission_section`) contains, verbatim:

```
## Mission Pack
MISSION: weekly-kpi-triage (v1)
- summary: Weekly KPI anomaly triage for growth, sales, and marketing operators.
- defaults: authority=delegate, audience=senior_staff
- skills_required: hypothesis-ranking, uncertainty-quantification
- boundary.allowed_data_domains: growth, sales, marketing
- boundary.required_semantic_metrics: monthly_churn_rate, revenue_per_user, dau
- boundary.allowed_action_classes: read_sql_gold, read_sql_bronze, artifact_draft, jira_create
- required_checks: schema_drift, temporal_leakage, baseline_compare, subgroup_stability, causal_assumption_check
- required_artifacts: exec_brief, ds_appendix, jira_ticket
- auto_escalate_when: confidence_low, deploy_needed, sensitive_data_detected, anomaly_severity_critical
- success_criteria: issue_classified, root_cause_identified, owner_assigned, next_action_proposed
```

**Goal / constraint semantic mapping** (plan §5.5 #3):
- "goal" ≈ **summary** + **success_criteria** (both present).
- "constraint" ≈ **boundary.\*** + **auto_escalate_when** + **required_checks/artifacts** (all present).

One minor deviation from plan wording: the domain field is named `summary`, not `goal`. The concept is preserved; only the field name differs. Recorded as information — no remediation by B09.

### 3.5 ActionClassifier — 5 strategies

22 probes across all 5 ordered strategies. 22/22 classified correctly:

| strategy                | probes | correct |
|---|---:|---:|
| SqlActionClassificationStrategy              | 4 | 4 |
| DeploymentActionClassificationStrategy       | 2 | 2 |
| GovernanceActionClassificationStrategy       | 8 | 8 |
| PythonExecutionActionClassificationStrategy  | 4 | 4 |
| ToolMapClassificationStrategy (tool-map)     | 3 | 3 |
| fallback (unknown tool)                      | 1 | 1 |

Plus 46 parametrized cases in `tests/unit/runtime/test_action_classifier.py` (all pass). Argument-driven discriminators observed correct:
- SQL `data_sensitivity=pii` → `read_pii_table`, `DELETE FROM` → `delete_table`, `source_tier=bronze` → `read_sql_bronze`, default → `read_sql_gold`.
- `generate_deployment(environment=prod)` → `prod_deploy`, else `staging_deploy`.
- `policy_check(record_approval=True)` → `jira_create` (mutation), else read.
- `standing_order(action=list|view_history)` → read, `create|update|delete|run_now` → `jira_create`.
- `execute_code` token heuristics: model.fit → training, StandardScaler → feature_engineering, plt.savefig → artifact_draft, shutil.rmtree → delete_table.

### 3.6 Incident 24-hour auto-expiry (boundary)

`resolve_authority_overlay(mode="incident", started_at=T0, now=T0+delta)` probed at 4 boundary points:

| delta | overlay.mode | overlay.expired | effective_mode |
|---|---|---|---|
| 0h        | `incident` | False | `incident` |
| 23h 59m   | `incident` | False | `incident` |
| 24h 00m exact | None   | True  | falls back to legacy `delegate` |
| 24h 01m   | None       | True  | falls back to legacy `delegate` |

Boundary is **inclusive on expiry** (`current_time >= expires_at`). 23h59m is still active. 24h is already expired. Plan §5.5 #5 passes.

### 3.7 Freeze hard-constraint end-to-end

Via `AutonomyPolicy.evaluate` with `authority=FREEZE` iterated over all 13 action classes:

- **Writes (9 classes)**: 9/9 blocked. `WriteEffect != NONE` guard fires (`feature_engineering`, `artifact_draft`) or matrix returns `skip` (the other 7).
- **Sensitive reads**: `read_pii_table`=`skip`, `read_sensitive_table`=`approve` (gated, not auto-executed).
- **Gold / bronze reads**: AUTO (allowed — diagnostic read-only).

**freeze_deny_all_writes = True**. **freeze_deny_all_tools = False** (strict reading of plan).

### 3.8 Certification persistence across restart

1. Process A: `SqliteCertificationStore(db_path).save_certification(record)` with `level=autopilot`. `is_certified=True`.
2. Process A disposed (`del store_a`).
3. Process B: fresh `SqliteCertificationStore(db_path)` on the same file. `is_certified('weekly-kpi-triage', autopilot, version=1) = True`. Approvers tuple preserved: `('alice@example.com', 'bob@example.com')`. Level preserved: `autopilot`.

Plan §5.5 #7 passes.

### 3.9 PolicyStudio 4 presets

PolicyStudio is the spec-level name for `ActionMatrix.with_overrides()` — the runtime surface returns a new immutable `ActionMatrix` with overridden cells; the default matrix is untouched (frozen `@dataclass`). Contract supports preview/apply (caller decides which matrix is stored active). Four preset shapes simulated per plan wording:

| preset                | overrides applied                                  | cells correct |
|---|---|---:|
| delegated_peer        | `jira_create`/delegate=auto, `slack_post`/delegate=auto | 2/2 |
| executive_review      | `prod_deploy`/{delegate,autopilot}=dual, `email_send`/delegate=dual | 3/3 |
| audit_guard           | `read_pii_table`/{delegate,autopilot}=skip, `delete_table`/autopilot=skip | 3/3 |
| mentor_walkthrough    | `feature_engineering`/delegate=ask, `model_training`/delegate=ask | 2/2 |

**4/4 preset applications produce the expected overridden cells.** Original matrix unchanged after override (immutability preserved).

> ⚠ **Not verified by B09**: whether PolicyStudio UI ships built-in YAML for these four preset names. No file under `src/ds_agent/**/policy_studio*` or similar was found. B09 tested only the runtime contract surface that would back such presets. Recommend C15 or a PolicyStudio-specific agent confirm the UI wiring.

---

## 4. Failures & discrepancies (record-only)

| ID | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| B09-F1 | low | static matrix | 3 FREEZE×CAUTION cells (`read_sensitive_table=approve`, `feature_engineering=auto`, `artifact_draft=auto`) read as non-skip at the matrix layer. Runtime overlay compensates for the two writes. | Either align static matrix to `skip` for FREEZE or document in code comment that FREEZE write-blocking is runtime-overlay-only (defense-in-depth would update both). |
| B09-F2 | info  | spec wording | Plan §5.5 #6 says "Freeze 모드에서 SAFE 도구조차 DENY"; implementation allows read-only SAFE reads under FREEZE (diagnostic path). | Reviewer to decide: tighten code to match plan, or update plan to reflect "all writes DENY, reads allowed" intent. |
| B09-F3 | info  | spec wording | Plan §5.5 #3 says Mission injects "goal/constraint" sections; domain field is named `summary`, not `goal`. Semantics preserved via `summary`+`success_criteria`+`boundary.*`. | Reviewer decides — cosmetic; wording alignment in spec would be clearer. |
| B09-F4 | info  | discoverability | No explicit `policy_studio` module or shipped preset YAMLs located. Runtime override contract works; UI binding unverified. | C15 packaging agent or dedicated PolicyStudio agent to confirm electron wiring and preset presence. |

None of these are blocking. None requires source change within B09 scope. All are defense-in-depth or doc-alignment items.

---

## 5. Evidence

| file | description |
|---|---|
| `Docs/qa_run_2026-04-17/B09_autonomy/START.json` | agent start marker |
| `Docs/qa_run_2026-04-17/B09_autonomy/B09_pytest_junit.xml` | 130 scoped tests, all pass |
| `Docs/qa_run_2026-04-17/B09_autonomy/B09_authority_matrix.csv` | 84-cell authority × action matrix with expected/actual/match columns |
| `Docs/qa_run_2026-04-17/B09_autonomy/B09_audience_diffs/junior_mentor.md` | Junior mentor prompt slice |
| `Docs/qa_run_2026-04-17/B09_autonomy/B09_audience_diffs/peer_ds.md` | Peer DS prompt slice |
| `Docs/qa_run_2026-04-17/B09_autonomy/B09_audience_diffs/senior_staff.md` | Senior staff prompt slice |
| `Docs/qa_run_2026-04-17/B09_autonomy/B09_audience_diffs/executive.md` | Executive prompt slice |
| `Docs/qa_run_2026-04-17/B09_autonomy/B09_audience_diffs/auditor.md` | Auditor prompt slice |
| `Docs/qa_run_2026-04-17/B09_autonomy/FINAL.json` | machine-readable summary |
| `.tmp/qa_B09/build_authority_matrix.py` | matrix generator probe |
| `.tmp/qa_B09/test_b09_scenarios.py` | runtime scenario probe |

---

## 6. Recommendations

1. **Align FREEZE semantics**: either add a `skip` entry to the static `ActionMatrix` for every non-NONE-write CAUTION action in FREEZE row (defense-in-depth), **or** update plan wording. Defense-in-depth is preferable for auditability (the matrix becomes the single source of truth, not matrix + overlay).
2. **Mission schema naming**: consider renaming `summary` → `goal` at the YAML level (with backward-compat alias) to match plan vocabulary, or add explicit `goal` field distinct from summary.
3. **PolicyStudio preset inventory**: ship 4 preset YAMLs under `src/ds_agent/skills/policy_studio_presets/` (or equivalent) so B09-F4 can be verified by contract rather than simulated.
4. **Runtime `blocks_external_writes` caveat**: the `AuthorityMode.blocks_external_writes` property currently covers only SHADOW + FREEZE; if plan intent includes blocking AUTOPILOT external writes without certification, that is already enforced by `requires_certification` + `_is_autopilot_certified`. No change needed — mention to Tier 3 reviewer.

---

## 7. LLM=Orchestrator principle check (HANDOFF §4.2)

Reviewed during probe design: every failing path documented above was recorded as information, not encoded as a force-apply "hint" that reshapes LLM decisions. The hard constraints identified:

- `FREEZE` write-block (runtime overlay) — enforced.
- `Incident` 24h auto-expiry — enforced (time-math hard rule).
- `max_active_slots` — out of B09 scope (B11).
- `requires_certification` for AUTOPILOT — enforced (hard gate before LLM can auto-execute).

Every other axis (Authority verdict family, Audience persona, Mission boundary) produces **information in system prompt** — no coerced step-by-step. Principle holds.
