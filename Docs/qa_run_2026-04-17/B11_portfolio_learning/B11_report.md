# B11 — Portfolio / Learning Governance Test Report

**Agent**: B11 Portfolio / Learning Governance Tester
**Date**: 2026-04-17
**Scope**: Spec 09 (Portfolio), Spec 10 (Learning Governance) — feature flag on/off
**Code SHA**: `git-unavailable` (non-git workspace; see HANDOFF §8.4)
**Evidence bundle**: `Docs/qa_run_2026-04-17/B11_portfolio_learning/`

---

## 1. Executive summary

| Path | Area | Result |
|:----:|------|:------:|
| 1 | Portfolio 4-quadrant transition matrix + illegal reject | **PASS** |
| 2 | `max_active_slots` hard constraint (2, 3rd refused) | **PASS** |
| 3 | PriorityCalculator formula + informational-only | **PASS** (with doc-drift note) |
| 4 | WaitCondition 4 kinds judgement | **PASS** (with maturity note) |
| 5 | Learning 8-state machine happy path + illegal reject | **PASS** |
| 6 | Promotion thresholds 1.00 / 1.00 / 1.02 | **PASS** |
| 7 | Auto-deprecation on 2nd consecutive failure | **PASS** |
| 8 | Rollback atomicity under mid-failure | **FAIL** |
| 9 | Feature flag off (portfolio + governance) | **PASS** (structural caveat) |

Summary: **8 / 9 PASS, 1 / 9 FAIL**.

The FAIL is on Path 8 (rollback atomicity) — a concrete, reproducible non-atomic write ordering in `RollbackPromotionUseCase`. All four hard-constraint checks of direct scope were otherwise met:

- `max_active_slots` — ENFORCED.
- Auto-deprecation on 2nd failure — ENFORCED.
- PriorityCalculator informational-only (LLM=orchestrator principle) — ENFORCED.
- Rollback atomicity — **NOT ENFORCED**.

Self-pass is NOT declared per HANDOFF §6.3. The next-tier judge should review the rollback atomicity finding (§4.8) as a potential Tier 2 blocker or a Fix-Sprint Round 3 candidate.

---

## 2. Test harness

### 2.1 Scoped pytest run

Command:
```
pytest \
  tests/unit/domain/test_portfolio_entry.py \
  tests/unit/domain/test_learning_item.py \
  tests/unit/application/test_portfolio_scheduler.py \
  tests/unit/application/test_learning_inbox.py \
  tests/unit/application/test_review_learning_item.py \
  tests/unit/application/test_promote_learning_item.py \
  tests/unit/application/test_deprecate_learning_item.py \
  tests/unit/application/test_rollback_promotion.py \
  tests/unit/application/test_revalidation_scheduler.py \
  tests/unit/application/test_promotion_gate_usecases.py \
  tests/unit/application/test_self_improve_promotion_gate.py \
  tests/unit/infrastructure/test_promotion_decision_store.py \
  tests/integration/infrastructure/test_sqlite_portfolio_store.py \
  tests/integration/infrastructure/test_sqlite_learning_store.py \
  -v --tb=short --junitxml=.tmp/qa_B11/junit.xml
```

**Result: 145 passed in 1.31s** — no fails, no flakes. Junit: `.tmp/qa_B11/junit.xml`.

### 2.2 Bespoke probes (this agent)

- `.tmp/qa_B11/probe_paths.py` — 9-path matrix probe.
- `.tmp/qa_B11/probe_rollback_sqlite.py` — real-SQLite rollback atomicity probe.

### 2.3 Respected constraints

- No source modification.
- No real external calls (all mocked or in-process).
- No full regression pytest (scope-isolated per HANDOFF §4.5).
- No `data/` access (temp workspaces via `DS_AGENT_WORKSPACE_DIR`).
- No LLM hint injection.

---

## 3. Coverage map (paths → files → pytest)

| Path | Production | Tests that cover it |
|------|------------|---------------------|
| 1 Quadrants | `domain/portfolio/portfolio_entry.py` | `tests/unit/domain/test_portfolio_entry.py` (all cases) |
| 2 max_slots | `application/portfolio/slot_manager.py` | `test_portfolio_scheduler.py::TestSlotManager::*` |
| 3 PriorityCalculator | `application/portfolio/priority_calculator.py` | `TestPriorityCalculator::test_p0_scores_higher_than_p3`, `test_sla_urgency_for_overdue` |
| 4 WaitCondition | `application/portfolio/wait_condition_evaluator.py` | `TestWaitConditionEvaluator::*` |
| 5 Learning SM | `domain/learning/learning_item.py` | `tests/unit/domain/test_learning_item.py::TestStateMachine::*` |
| 6 Thresholds | `application/learning/promote_learning_item.py` | `test_promote_learning_item.py::TestPromotionGate::*` |
| 7 Auto-deprecate | `application/learning/deprecate_learning_item.py` | `test_deprecate_learning_item.py::TestAutoDeprecation::*` + `test_revalidation_scheduler.py` |
| 8 Rollback | `application/learning/rollback_promotion.py` | `test_rollback_promotion.py` (happy-path only; no atomicity injection) + **this agent's sqlite probe** |
| 9 Flag gate | `tools/portfolio_tools.py`, `tools/learning_tools.py`, `agent/prompt_builder.py:294-301` | no pytest coverage for DISABLED branch — **this agent's live probe** fills the gap |

Note: path 8 and path 9 DISABLED branches had **no pre-existing pytest coverage**. This agent's probes are the only evidence.

---

## 4. Per-path findings

### 4.1 Path 1 — Quadrant transitions

- 17 / 17 matrix cases match expectation (11 allowed + 6 illegal).
- Live `PortfolioEntry.transition_to(...)` raises `ValueError` on illegal `playbook_candidate → monitoring`.
- **Spec drift note**: plan text lists terminal set `{completed, failed, cancelled}`; code uses `{completed, cancelled, archived}`. `archived` serves the purpose of `failed` (absorbing post-monitoring terminal). Not a hard-constraint violation; worth updating the spec text.

### 4.2 Path 2 — `max_active_slots`

- `DS_AGENT_MAX_ACTIVE_SLOTS=2`, 2 active entries pre-seeded.
- `SlotManager.acquire_or_refuse()` returns "All 2 active slots are occupied. …".
- `resume_task` tool emits `{"ok": false, "error": {"code": "SLOT_FULL", …}}`.
- Current-active-count information embedded in message (contains digit `2`).
- Hard-constraint verdict: **ENFORCED**.

See `B11_max_slots_rejection_sample.json` for the verbatim response.

### 4.3 Path 3 — PriorityCalculator

- Formula (implementation): `business_weight * 2.0 + sla_urgency * 3.0 + age_factor * 0.5`.
- Probe: P1 entry, SLA −1h, created 1d ago → `raw_score = 36.5`. Matches formula to 6 decimals.
- Public API is `{score, rank}` only. No transition, enforce, schedule, or store-mutating methods.
- `rank()` is pure over the passed list — does not call `store.save_*`.
- **LLM-orchestrator principle: PRESERVED** — scores are decoration, not control.
- **Spec drift**: plan §5.7.3 names coefficients `0.5 / 1.0 / 0.2`; code uses `2.0 / 3.0 / 0.5`. Ordering intent (P0 ≫ P3, overdue dominates) is preserved. Doc drift only.

### 4.4 Path 4 — WaitCondition kinds

- Timer (elapsed): `satisfied=true`, reason contains "expired".
- Timer (pending): `satisfied=false`, reason contains "remaining".
- Timer (missing spec): `satisfied=false`, reason contains "missing".
- Approval: `satisfied=false`, reason "approval check requires runtime context".
- Data freshness: `satisfied=false`, reason "data freshness check requires warehouse adapter".
- External: `satisfied=false`, reason "external resource check requires adapter".

The evaluator returns dataclass results; does not transition. Safe default is fail-pending (never false-positive "satisfied"). **Maturity note**: only Timer has a real check; Approval/Freshness/External require adapter wiring. Not a hard-constraint violation.

### 4.5 Path 5 — Learning 8-state machine

- Happy-path walk `proposed → under_review → approved → promoted → monitored → deprecated → archived` succeeds via `LearningItem.transition_to`.
- 7 illegal transitions (skip, reverse, out-of-terminal) all raise `ValueError`.
- Note: the code also defines a `rejected` state + `rejected → proposed` re-submission path. That's 8 operational states + 1 archived terminal (total 9 states). Does not contradict the spec's 8-state mention (which is an informal summary).

### 4.6 Path 6 — Promotion thresholds

- `THRESHOLDS = {PATTERN: 1.00, KB_ENTRY: 1.00, CUSTOM_SKILL: 1.02}` matches spec exactly.
- Just-below cases (`T − 0.01`) raise `ValueError: Eval score … below threshold`; item stays `approved`.
- At-threshold / above-threshold: promotion record created, item transitions to `promoted`.

### 4.7 Path 7 — Auto-deprecation

- `auto_deprecate_on_failure` called on a `promoted` item:
  - 1st call → returns `None` (failure recorded); item status stays `promoted`.
  - 2nd call → returns `DeprecationRecord`; item status = `deprecated`.
- `RevalidationScheduler.record_result(score < threshold)` flows through the same path.
- Hard-constraint verdict: **ENFORCED**.

### 4.8 Path 8 — Rollback atomicity — **FAIL**

**Finding**: `RollbackPromotionUseCase.execute(item_id)` makes two independent store writes:
1. `store.save_item(updated)` — commits item status transition to `deprecated`.
2. `store.save_deprecation_record(dep_record)` — separate commit.

No use-case-level transaction wraps them. `SqliteLearningStore.save_item` and `save_deprecation_record` each call `self._conn.commit()` independently.

**Probe** (`.tmp/qa_B11/probe_rollback_sqlite.py`, output saved as `B11_rollback_atomicity_sqlite_probe.json`):
- Real `SqliteLearningStore` backed by a temp `learning.db`.
- `save_deprecation_record` wrapped to raise `RuntimeError("injected…")`.
- After exception:
  - `item.status = "deprecated"` (persisted in sqlite).
  - `list_deprecation_records()` contains **zero** rows for the item.
  - `verdict = NON_ATOMIC_PARTIAL`.

**Impact**: audit-trail split. The item shows as deprecated but has no matching `DeprecationRecord`. Reconciliation from the record table alone cannot recover the rollback reason/time/actor.

**Mitigation options** (not implemented by this agent):
- Wrap both writes in a single-connection txn inside the use case.
- Add a compensating revert on `save_deprecation_record` exception (restore item to previous status).
- Refactor the store to provide a combined `save_item_and_deprecation(...)` method that commits once.

### 4.9 Path 9 — Feature flag off

- `DS_AGENT_PORTFOLIO_ENABLED=false`: all 5 portfolio tools (`list_my_portfolio`, `pause_task`, `resume_task`, `request_monitoring`, `set_sla`) return `{"ok": false, "error": {"code": "DISABLED", …}}`.
- `DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1=false`: all 4 read-side learning tools tested return `DISABLED`. The write-side tools (`review_learning_item`, `rollback_promotion`) have the same guard by inspection.
- **Prompt-builder gate**: `_build_learning_governance_context` returns `None` when the governance flag is off — the "# Learning Governance" block is fully omitted from the system prompt.
- **Structural caveat**: `@tool(...)` decorators run at module-import time, so the registered schema remains in `ToolRegistry`. Spec intent "not exposed in the prompt" is **behaviorally** met (zero state mutation possible) but not **structurally** for portfolio tools. Acceptable — hard-constraint not violated.

---

## 5. LLM = orchestrator principle audit (HANDOFF §4.2)

| Component | Enforces execution order? | Behaviour |
|-----------|:-------------------------:|-----------|
| `PriorityCalculator` | NO | Computes informational scores; no mutation. |
| `SlotManager` | **Hard constraint only** | Refuses `acquire` when full; does not schedule or order LLM's work. |
| `WaitConditionEvaluator` | NO | Returns `EvaluationResult`; LLM decides to call `resume_task`. |
| `PortfolioEvaluator` | NO | Read-only snapshot for prompt context. |
| `RevalidationScheduler.get_due_items` | NO | Lists due items; does not auto-run. |
| `DeprecateLearningItemUseCase.auto_deprecate_on_failure` | **Hard constraint only** | Fires exclusively on 2nd consecutive eval failure. |
| `PromoteLearningItemUseCase` | **Gate only** | Threshold-gated; does not schedule the LLM. |

No code path hard-codes an LLM execution sequence. The principle is preserved.

---

## 6. Spec-vs-implementation drift log (documentation, not failures)

| ID | Location | Drift | Severity |
|----|----------|-------|:--------:|
| D1 | Plan §5.7.1 | Spec text `{completed, failed, cancelled}` vs code `{completed, cancelled, archived}` | LOW (doc) |
| D2 | Plan §5.7.3 | Spec coefficients `0.5 / 1.0 / 0.2` vs code `2.0 / 3.0 / 0.5` | LOW (doc, behaviour equivalent) |
| D3 | Plan §5.7.4 | "Data Freshness / External / Approval — satisfied logic" vs impl returns `requires adapter` pending | MED (maturity gap) |
| D4 | Plan §5.7.9 | "tool not exposed in prompt" vs impl gate on body only (tool registry still lists name) | LOW (behaviour safe) |
| D5 | Spec 10 general | No off switch for Self-Improve — FLAG IS IMPLEMENTED; earlier draft notes were incorrect | FIXED |

---

## 7. Recommended follow-ups (outside this agent's fix authority)

1. **Rollback atomicity (BLOCKING candidate)**: fix `RollbackPromotionUseCase` to be atomic. Assign to Fix Sprint Round 3 or a new Self-Improve stream.
2. **Approval / DataFreshness / External evaluators**: wire real adapters or explicitly mark them as v2 maturity gap in the spec.
3. **Prompt-builder hide-on-flag-off (optional)**: add a `build_portfolio_section` early-return when `DS_AGENT_PORTFOLIO_ENABLED` is off, so the tool schema is also omitted from the prompt — aligns with the Governance pattern.
4. **Spec-text update**: reconcile D1, D2 with current code.
5. **Add pytest coverage for DISABLED branches**: neither `portfolio_tools.py` nor `learning_tools.py` has tests for the flag-off response. Recommended as Tier 2 follow-up.

---

## 8. Deliverables checklist

- [x] `START.json` — created.
- [x] Scoped pytest executed; junit saved to `.tmp/qa_B11/junit.xml`.
- [x] `B11_state_traces.md` — written.
- [x] `B11_state_transitions.jsonl` — written (categorized event log).
- [x] `B11_flag_on_off_diff.md` — written.
- [x] `B11_max_slots_rejection_sample.json` — written.
- [x] `B11_rollback_atomicity_sqlite_probe.json` — written.
- [x] `B11_path_results.json` — full probe dump.
- [x] `B11_report.md` — this file.
- [x] `FINAL.json` — written (see separate file).

---

## 9. Metrics

| Metric | Value |
|--------|:-----:|
| Paths verified | **8 / 9** |
| `max_active_slots` enforced | **true** |
| Auto-deprecation enforced | **true** |
| Rollback atomic | **false** |
| PriorityCalculator informational only | **true** |
| pytest scope result | 145 / 145 passed |
| Drift items logged | 4 (1 fixed) |
