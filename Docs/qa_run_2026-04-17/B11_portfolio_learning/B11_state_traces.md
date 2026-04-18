# B11 — State Transition Traces (Portfolio + Learning Governance)

**Agent**: B11 Portfolio / Learning Governance Tester
**Date**: 2026-04-17
**Specs**: Spec 09 (Portfolio), Spec 10 (Learning Governance)
**Evidence**: `B11_state_transitions.jsonl`, `B11_path_results.json`, `B11_rollback_atomicity_sqlite_probe.json`

---

## 1. Portfolio 4-quadrant transition matrix

Implementation source of truth: `src/ds_agent/domain/portfolio/portfolio_entry.py` — `_ALLOWED_TRANSITIONS`.

### 1.1 Operational quadrants

| From \ To | active | waiting | monitoring | playbook_candidate | completed | cancelled | archived |
|:---------:|:------:|:-------:|:----------:|:------------------:|:---------:|:---------:|:--------:|
| active | — | OK | OK | ✗ | OK | OK | ✗ |
| waiting | OK | — | ✗ | ✗ | ✗ | OK | ✗ |
| monitoring | OK | ✗ | — | OK | OK | ✗ | OK |
| playbook_candidate | ✗ | ✗ | ✗ | — | ✗ | ✗ | OK |

### 1.2 Terminal quadrants (all outbound = ✗)

| From | Any outbound target |
|:----:|:-------------------:|
| completed | ✗ |
| cancelled | ✗ |
| archived | ✗ |

### 1.3 Illegal-transition probes verified

| # | Source | Target | Expected | Actual | Verdict |
|:-:|--------|--------|:--------:|:------:|:-------:|
| T1 | playbook_candidate | monitoring | reject | reject | PASS |
| T2 | playbook_candidate | active | reject | reject | PASS |
| T3 | completed | active | reject | reject | PASS |
| T4 | cancelled | active | reject | reject | PASS |
| T5 | archived | active | reject | reject | PASS |
| T6 | waiting | monitoring | reject | reject | PASS |

Live `PortfolioEntry.transition_to(...)` raises `ValueError: transition from playbook_candidate to monitoring is not allowed` on illegal attempt.

### 1.4 Spec vs. impl drift note

The test plan §5.7.1 text says "3 terminal (completed/failed/cancelled)". Implementation defines terminal set as **completed / cancelled / archived** — no `failed` state. `archived` is reachable from `monitoring` and `playbook_candidate`. This is a spec-text vs. code-truth drift but does NOT break a hard constraint; all transitions are validator-enforced.

---

## 2. `max_active_slots` hard constraint

Implementation: `src/ds_agent/application/portfolio/slot_manager.py`.

### 2.1 Probe

- env `DS_AGENT_MAX_ACTIVE_SLOTS=2`
- 2 ACTIVE portfolio entries pre-seeded → `active_count=2`
- `SlotManager.acquire_or_refuse()` called on behalf of a third resume

### 2.2 Observed response

```
max_slots: 2
active_count: 2
available_slots: 0
refusal_msg: "All 2 active slots are occupied. Pause or complete an active task before resuming another."
informs_llm_current_active_count: true (number "2" is embedded in the message)
```

### 2.3 Tool-level JSON response sample

When `resume_task` is invoked over the capacity limit, `portfolio_tools.resume_task` returns:

```json
{
  "ok": false,
  "error": {
    "code": "SLOT_FULL",
    "message": "All 2 active slots are occupied. Pause or complete an active task before resuming another."
  }
}
```

Hard-constraint verdict: **ENFORCED** — the code path cannot be bypassed by the LLM.

---

## 3. PriorityCalculator — formula + informational-only

Implementation: `src/ds_agent/application/portfolio/priority_calculator.py`.

### 3.1 Public API surface

`PriorityCalculator` exposes exactly two methods: `score()` and `rank()`. No `execute`, `schedule`, `run`, `transition`, or `enforce` methods. No store mutation calls anywhere in the class.

### 3.2 Formula (implementation)

```
raw_score = business_weight * 2.0 + sla_urgency * 3.0 + age_factor * 0.5
```

where:
- `business_weight ∈ {P0: 4.0, P1: 3.0, P2: 2.0, P3: 1.0}`
- `sla_urgency ∈ {overdue: 10.0, <1h: 5.0, <4h: 3.0, <1d: 1.0, else: 0.0}`
- `age_factor = clamp(age_seconds / 86400, 0, 5.0)`

### 3.3 Probe case

Entry: P1, SLA deadline 1h past, created 1d ago.

- business_weight = 3.0
- sla_urgency = 10.0 (overdue)
- age_factor = 1.0
- `raw_score = 3.0*2.0 + 10.0*3.0 + 1.0*0.5 = 36.5`

Observed: `raw_score=36.5`, matches.

### 3.4 Spec-vs-impl coefficient drift

Test plan §5.7.3 says `business_weight=0.5, sla_urgency=1.0, age_factor=0.2`. The live code uses `2.0, 3.0, 0.5`. The **ordering intent** (P0 > P3; overdue dominates) is preserved; the numeric coefficients differ. This is a **spec/doc drift** — it does not change behaviour or introduce LLM override.

### 3.5 LLM-orchestrator principle check

- `PriorityCalculator` never calls `store.save_entry`, `store.record_transition`, or any mutator.
- Scores are serialised into the system-prompt context for the LLM to consider (see `portfolio_evaluator.PortfolioSnapshot`).
- The LLM is free to pick any active entry regardless of score.

Verdict: **informational_only = true**. Hermes-style orchestration principle preserved (per HANDOFF §4.2).

---

## 4. WaitCondition evaluation (4 kinds)

Implementation: `src/ds_agent/application/portfolio/wait_condition_evaluator.py`.

| Kind | Probe spec | Expected | Observed `satisfied` | Reason snippet |
|------|-----------|---------:|:--------------------:|----------------|
| timer (elapsed) | `resume_at = now−2h` | satisfied | **true** | "timer expired at …" |
| timer (pending) | `resume_at = now+1h` | pending | false | "timer pending, … remaining" |
| approval | `approval_id=apr_1` | pending (requires runtime) | false | "approval check requires runtime context" |
| data_freshness | `table=orders` | pending (requires adapter) | false | "data freshness check requires warehouse adapter" |
| external_resource | `endpoint=…` | pending (requires adapter) | false | "external resource check requires adapter" |

### 4.1 Principle check

The evaluator returns an `EvaluationResult` dataclass — it does NOT transition any `PortfolioEntry`. The LLM reads the result through context and independently decides to call `resume_task`. Information-provider role preserved.

### 4.2 Spec-vs-impl note

Test plan lists "Data Freshness / External / Approval / Timer — each's `satisfied` judgment logic". The implementation wires **only Timer** to a functional check in `WaitConditionEvaluator`. Approval / Data Freshness / External evaluators return "requires … adapter/context" and `satisfied=false` until a runtime-side adapter is provided. This is NOT a bypassable hard constraint; it is a conservative default (fail-pending, never false-positive "satisfied"). Documented as a maturity gap, not a failure.

---

## 5. Learning 8-state machine

Implementation: `src/ds_agent/domain/learning/learning_item.py` — `_ALLOWED_TRANSITIONS`.

### 5.1 Happy-path walk verified

```
proposed → under_review → approved → promoted → monitored → deprecated → archived
```

Confirmed end-to-end via `LearningItem.transition_to(...)` chained calls.

### 5.2 Invalid transitions (reverse / skip / terminal)

| From | To | Expected | Actual | PASS? |
|------|----|:--------:|:------:|:-----:|
| proposed | approved (skip) | reject | reject | PASS |
| proposed | promoted (skip) | reject | reject | PASS |
| approved | monitored (skip) | reject | reject | PASS |
| promoted | proposed (reverse) | reject | reject | PASS |
| deprecated | promoted (reverse) | reject | reject | PASS |
| archived | proposed (terminal) | reject | reject | PASS |
| archived | approved (terminal) | reject | reject | PASS |

Live `LearningItem.transition_to(LearningItemStatus.PROPOSED, ...)` from `promoted` raises
`ValueError: transition from promoted to proposed is not allowed`.

### 5.3 Note on rejected state

The implementation also defines `REJECTED` with a re-submission path `rejected → proposed`. This is outside the 7-state happy path named in the spec but is a legitimate additional state (not a hard-constraint violation).

---

## 6. Promotion thresholds

Implementation: `src/ds_agent/application/learning/promote_learning_item.py::THRESHOLDS`.

```python
THRESHOLDS = {
    PATTERN: 1.00,
    KB_ENTRY: 1.00,
    CUSTOM_SKILL: 1.02,
}
```

Values match test-plan spec exactly.

### 6.1 Boundary behaviour (verified)

For each item type, evaluated at `baseline_score=1.0` with eval_score = `threshold ± 0.01`:

| Item type | eval = T−0.01 | eval = T | eval = T+0.01 |
|-----------|:-------------:|:--------:|:-------------:|
| pattern (T=1.00) | rejected | promoted | promoted |
| kb_entry (T=1.00) | rejected | promoted | promoted |
| custom_skill (T=1.02) | rejected | promoted | promoted |

"Just-below" cases raise `ValueError: Eval score … below threshold …` and leave the item in `approved` (no promotion record).

---

## 7. Auto-deprecation hard constraint

Implementation: `src/ds_agent/application/learning/deprecate_learning_item.py::auto_deprecate_on_failure`.

### 7.1 Probe

Promoted item → call `auto_deprecate_on_failure` twice:

| Attempt | Return | Item status after |
|:-------:|--------|:-----------------:|
| 1st | None (failure recorded) | promoted |
| 2nd | DeprecationRecord | **deprecated** |

Hard-constraint verdict: **ENFORCED** — auto-deprecation fires on the 2nd consecutive failure; item transitions irreversibly to `deprecated`; subsequent rehabilitation requires a new proposal cycle (since `deprecated → promoted` is forbidden; only `deprecated → archived`).

### 7.2 Revalidation integration

`RevalidationScheduler.record_result(score, threshold=0.9)` delegates to `auto_deprecate_on_failure` on `score < threshold`. 2nd failure returns `action_taken="deprecated"`; this is covered by existing `test_revalidation_scheduler.py`.

---

## 8. Rollback atomicity — **FAIL**

Implementation: `src/ds_agent/application/learning/rollback_promotion.py::RollbackPromotionUseCase.execute`.

### 8.1 Execution ordering

```
1. store.get_item(item_id)
2. store.get_promotion_record(item_id)
3. item.transition_to(DEPRECATED, now)  (domain-only)
4. construct DeprecationRecord          (domain-only)
5. store.save_item(updated)             (sqlite commit #1)
6. store.save_deprecation_record(...)   (sqlite commit #2)
```

There is **no use-case-level transaction boundary** wrapping steps 5 and 6. The underlying `SqliteLearningStore.save_item` and `save_deprecation_record` each commit independently.

### 8.2 Injected mid-failure probe (real SQLite)

See `B11_rollback_atomicity_sqlite_probe.json`:

```
exception_raised: true
item_status_after: "deprecated"
any_deprecation_record_persisted: false
verdict: NON_ATOMIC_PARTIAL (item deprecated without DeprecationRecord)
```

### 8.3 Impact

Audit trail inconsistency: item shows `deprecated` but the `deprecation_records` table has no corresponding row. A crash or exception between `save_item` and `save_deprecation_record` puts the learning-governance substrate into a state that cannot be reconstructed from the record table alone.

### 8.4 Verdict

**FAIL** — "Rollback 원자성" hard constraint not met. Mitigation options (for the owning stream, not this agent):

- Wrap the two store writes in a single-connection transaction inside `RollbackPromotionUseCase`.
- Or add compensating action: on `save_deprecation_record` failure, reverse the item save back to `promoted`.
- Or refactor the store to provide a combined `save_item_with_deprecation_record(...)` method that commits once.

---

## 9. Feature flag off — tool guard behaviour

Implementation: `src/ds_agent/tools/portfolio_tools.py::_get_portfolio_store`.

### 9.1 Gate logic

```python
if os.environ.get("DS_AGENT_PORTFOLIO_ENABLED", "").lower() not in {"1", "true", "yes"}:
    return None
```

When the guard returns `None`, every portfolio tool returns
`{"ok": false, "error": {"code": "DISABLED", "message": "Portfolio manager is not enabled…"}}`.

### 9.2 Probe results

All 5 portfolio tools (`list_my_portfolio`, `pause_task`, `resume_task`, `request_monitoring`, `set_sla`) return DISABLED when `DS_AGENT_PORTFOLIO_ENABLED=false`.

### 9.3 Caveat

The `@tool(...)` decorator registers tool names at **module import time**, *before* the flag is read. So the tool entries are still present in the ToolRegistry; only the **runtime body** refuses. Practical consequence: the LLM sees the tool schema in the system prompt (since prompts pull from registry) but every invocation will be rejected at body-entry with a clear DISABLED message.

If the spec intent is "tool schema is also hidden from the prompt when flag is off", an additional prompt-builder gate would be needed. The current implementation protects *behavior* (no state mutation) but not *schema visibility*.

See `B11_flag_on_off_diff.md` for the side-by-side comparison.

---

## 10. JSONL trace

All probe events are recorded in `B11_state_transitions.jsonl` (one JSON object per line). Categories:

- `portfolio_quadrant_transition`
- `portfolio_illegal_transition_attempt`
- `slot_acquire_attempt`
- `priority_calculator_rank`
- `wait_condition_evaluation`
- `learning_transition`
- `promotion_threshold_check`
- `auto_deprecation`
- `rollback_atomicity_probe`
- `feature_flag_off`
- `feature_flag_on`
