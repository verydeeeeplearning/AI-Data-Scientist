# Phase 01: Policy Edit Surface

**Priority**: P0  
**Status**: Completed  
**Implemented On**: 2026-04-13  
**Depends On**: Phase 00

---

## 1. Goal

Turn the runtime policy section from a read-only monitor into an operator
control surface.

After this phase, recurring goals and standing orders can be maintained from
Electron without opening backend policy files.

---

## 2. Implemented

### 2.1 Reusable policy refresh path

Modified files:

- `electron/src/renderer/hooks/usePolicy.ts`

Implemented:

- exported `fetchPolicySnapshot(...)` so mutation UIs can refresh policy state
  immediately after save
- exported shared payload normalization for policy RPC results

This removes duplicated `policy.get` parsing and keeps mutation flows aligned
with the background refresh hook.

### 2.2 Recurring goal editor

New files:

- `electron/src/renderer/components/runtime/RecurringGoalEditor.tsx`
- `electron/src/renderer/components/runtime/RecurringGoalsPanel.tsx`

Implemented:

- recurring goal create flow
- recurring goal update flow
- enable / disable flow using existing upsert semantics
- session id input
- recurring prompt input
- interval input with unit selector:
  - minutes
  - hours
  - days
- validation for:
  - non-empty session id
  - non-empty prompt
  - interval > 0
- save feedback states:
  - saving
  - saved
  - error

This keeps the existing backend contract intact while giving operators a usable
front-end editing flow.

### 2.3 Standing orders editor

New files:

- `electron/src/renderer/components/runtime/StandingOrdersPanel.tsx`

Implemented:

- multiline standing-order editor
- one-line-per-order UX
- normalization on save:
  - trims empty lines
  - deduplicates repeated lines
- save / reset controls
- save feedback states:
  - saving
  - saved
  - error

This gives Electron a real control surface for the policy instructions that the
autonomous runtime reads.

### 2.4 Policy panel composition

Modified files:

- `electron/src/renderer/components/runtime/PolicyPanel.tsx`

Implemented:

- replaced static read-only recurring-goal and standing-order previews with:
  - `RecurringGoalsPanel`
  - `StandingOrdersPanel`
- kept top-level policy summary cards and profile explanation
- changed profile precedence so current runtime status can override stale policy
  snapshot profile text during refresh lag

Result:

- runtime tab now supports policy inspection and policy editing in one place

---

## 3. Changed Files

New files:

- `electron/src/renderer/components/runtime/RecurringGoalEditor.tsx`
- `electron/src/renderer/components/runtime/RecurringGoalsPanel.tsx`
- `electron/src/renderer/components/runtime/StandingOrdersPanel.tsx`

Modified files:

- `electron/src/renderer/hooks/usePolicy.ts`
- `electron/src/renderer/components/runtime/PolicyPanel.tsx`

---

## 4. Runtime Result

After this phase, operators can:

- create a recurring goal
- edit an existing recurring goal
- disable or re-enable a recurring goal
- edit standing orders inline
- save policy changes and see refreshed policy state immediately

Delete is still intentionally absent because the backend currently models safe
archive behavior through `enabled = false`.

---

## 5. Verification

Executed:

```bash
cd electron && npm run typecheck
cd electron && npm run build
python -m pytest tests/e2e/test_ws_e2e.py tests/unit/infrastructure/test_api.py \
  -q -p no:cacheprovider \
  --basetemp="C:\Users\aquap\.codex\memories\pytest_electron_phase01_1"
```

Result:

- `electron typecheck` passed
- `electron build` passed
- `79 passed`

Notes:

- build still emits the existing Vite chunk-size warning
- no backend source changes were required

---

## 6. Remaining Gap

Still deferred after this phase:

- opening a runtime session directly in the chat surface
- run / task inspection drawers
- project surface
- alert and recovery timeline

Those are the correct next steps because policy control is now editable from the
Electron runtime tab.
