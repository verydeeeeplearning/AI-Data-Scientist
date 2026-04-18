# Phase 08: Policy Automation and Deferred Scope

**Priority**: P3  
**Milestone**: Post-MVP  
**Status**: Completed  
**Implemented On**: 2026-04-12

---

## 1. Goal

Add a policy layer above the single-agent autonomous runtime so the system can:

- decide when proactive work is allowed
- suppress runaway automation under pressure
- schedule recurring autonomous goals
- react to monitoring alerts with profile-aware behavior

This phase does not add multi-agent orchestration. It hardens the existing
single-agent runtime so its autonomous behavior is explicit, throttleable, and
operator-visible.

---

## 2. Implemented

### 2.1 Policy-driven autonomous dispatch

Modified files:

- `src/ds_agent/runtime/policy_engine.py`
- `src/ds_agent/runtime/coordinator.py`

Implemented:

- `manual | balanced | aggressive` automation profiles are now evaluated by a
  real `PolicyEngine`
- coordinator dispatch is now policy-first instead of hard-coded event matching
- successful dispatch is recorded only after a run is actually started
  - this fixes false-positive throttling from early bookkeeping
- recurring-goal dispatch uses goal-aware dedupe keys
- monitoring alerts and runtime pressure are now first-class policy inputs

Result:

- `manual`
  - suppresses proactive autonomous work
- `balanced`
  - allows direct runtime wake-ups such as file changes and recovery
- `aggressive`
  - additionally allows monitoring-driven remediation and periodic review

### 2.2 Recurring goals and standing orders surfaced through runtime state

Modified files:

- `src/ds_agent/api/ws_handler.py`

Implemented:

- `AppState` now owns the shared `JsonPolicyStore`
- runtime status now includes:
  - `automationProfile`
  - `recurringGoalCount`
  - `standingOrderCount`
  - `resourcePressure`
- new WebSocket RPC methods:
  - `policy.get`
  - `policy.upsertRecurringGoal`
  - `policy.setStandingOrders`
- workspace changes now rebuild the policy store with the rest of runtime state
- changing `gateway.automation_profile` while the daemon is running now restarts
  the background runtime so the new profile is applied cleanly

This makes policy state part of the same shared runtime substrate already used
by Electron, Telegram, and CLI paths.

### 2.3 Monitoring sensors integrated into the daemon

Modified files:

- `src/ds_agent/gateway/daemon.py`

Integrated existing Phase 08 modules:

- `ModelMonitorSensor`
- `PipelineHealthSensor`
- `SystemResourceSensor`
- `PolicyEngine`

Implemented:

- autonomous daemon now starts and stops all monitoring sensors together with
  file-watch and schedule sensors
- runtime pressure state is exposed back to operator surfaces
- aggressive profile enables higher-frequency schedule-driven review
- pipeline failures, degraded model metrics, and runtime pressure now flow into
  the same coordinator path as other autonomous wake-up events

This closes the gap between "background loop exists" and "background loop makes
policy-bounded decisions from operating signals."

### 2.4 Electron operator console visibility

Modified files:

- `electron/src/renderer/stores/runtimeStore.ts`
- `electron/src/renderer/components/runtime/GatewayStatusPanel.tsx`

Implemented:

- runtime console now shows:
  - automation profile
  - recurring goal count
  - standing order count
  - resource pressure state
- operator can now change the automation profile directly from Electron

This keeps the Electron app aligned with the non-developer control-surface goal:
operators can see the autonomous policy state without reading backend files.

---

## 3. Runtime Behavior

After this phase, autonomous runtime behavior is:

1. Sensors publish events into the shared hub
2. Coordinator asks the policy engine whether that event may dispatch work
3. Policy engine considers:
   - automation profile
   - resource pressure
   - throttling window
   - recurring-goal due state
   - monitoring alert type
4. If allowed, coordinator starts one tracked run through the existing runtime
5. After a successful start:
   - throttling history is updated
   - recurring-goal trigger state is persisted

This is the first phase where autonomous behavior is governed by explicit
runtime policy instead of only event wiring.

---

## 4. Changed Files

New files:

- `tests/unit/infrastructure/test_policy_runtime.py`

Modified files:

- `src/ds_agent/runtime/policy_engine.py`
- `src/ds_agent/runtime/coordinator.py`
- `src/ds_agent/gateway/daemon.py`
- `src/ds_agent/api/ws_handler.py`
- `electron/src/renderer/stores/runtimeStore.ts`
- `electron/src/renderer/components/runtime/GatewayStatusPanel.tsx`
- `tests/unit/infrastructure/test_autonomous_runtime.py`
- `tests/unit/infrastructure/test_api.py`

Existing runtime modules integrated in this phase:

- `src/ds_agent/runtime/policy_store.py`
- `src/ds_agent/runtime/sensors/model_monitor.py`
- `src/ds_agent/runtime/sensors/pipeline_health.py`
- `src/ds_agent/runtime/sensors/system_resource.py`

---

## 5. Verification

Executed:

```bash
python -m pytest tests/unit/infrastructure/test_policy_runtime.py \
  tests/unit/infrastructure/test_autonomous_runtime.py \
  tests/unit/infrastructure/test_api.py \
  -q -p no:cacheprovider \
  --basetemp="C:\Users\aquap\.codex\memories\pytest_phase08_run1"
```

Result:

- `79 passed`

Additional verification:

- `python -m ruff check ...` passed for the changed Python files
- `python -m ruff format --check ...` passed for the changed Python files
- `cd electron && npx tsc --noEmit` passed
- `mypy` was not executed because the current environment does not have the
  module installed

---

## 6. Notes

Important decisions in this phase:

- recurring goals were implemented as policy inputs, not as a second planner
- throttling is recorded only after a run is truly dispatched
- resource pressure suppresses proactive automation instead of trying to recover
  by scheduling even more work
- aggressive mode is intentionally the only profile that reacts to monitoring
  alerts without a fresh user prompt

This keeps the autonomy upgrade incremental and compatible with the current
single-agent architecture.

---

## 7. Remaining Gap

Still deferred after this phase:

- recurring-goal CRUD beyond upsert-style updates
- Electron editors for standing orders and recurring-goal definitions
- per-surface policy overrides
- richer health heuristics for model degradation and pipeline instability
- multi-agent routing and child-session orchestration

Those stay out of scope for this phase because they would move the system from
policy-bounded autonomy into orchestration design.
