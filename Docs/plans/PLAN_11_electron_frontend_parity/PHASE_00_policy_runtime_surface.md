# Phase 00: Policy Runtime Surface

**Priority**: P0  
**Status**: Completed  
**Implemented On**: 2026-04-13  
**Depends On**: current backend only

---

## 1. Goal

Expose backend autonomous policy state in the Electron runtime tab so operators
can see more than aggregate runtime counters.

This phase was intentionally read-only. The purpose was to surface policy state
cleanly before adding editing flows.

---

## 2. Implemented

### 2.1 Dedicated policy state in renderer

New files:

- `electron/src/renderer/stores/policyStore.ts`
- `electron/src/renderer/hooks/usePolicy.ts`

Implemented:

- a dedicated Zustand store for policy state
- normalized `PolicySnapshot` payloads from `policy.get`
- periodic refresh of policy state while connected
- reset behavior on disconnect

The policy state is now independent from `runtimeStore`, which keeps the split
between runtime counters and policy payloads clear.

### 2.2 Runtime policy panel

New files:

- `electron/src/renderer/components/runtime/PolicyPanel.tsx`

Modified files:

- `electron/src/renderer/components/layout/Sidebar.tsx`

Implemented:

- a new read-only `PolicyPanel` inside the runtime tab
- profile-level summary text for:
  - `manual`
  - `balanced`
  - `aggressive`
- recurring-goal preview list
- standing-order preview list
- empty states when no policy items exist
- compact count cards for recurring goals and standing orders

This makes the runtime tab closer to an operator console instead of a pure
session/run/task monitor.

### 2.3 App wiring and refresh behavior

Modified files:

- `electron/src/renderer/App.tsx`

Implemented:

- `usePolicy(...)` is now started alongside:
  - `useWorkflow(...)`
  - `useRuntime(...)`
- policy refresh is triggered on the same high-signal lifecycle events:
  - `stream.done`
  - `approval.requested`
  - `approval.resolved`
  - `workspace.changed`

This keeps policy state aligned with the existing runtime refresh pattern.

---

## 3. Changed Files

New files:

- `electron/src/renderer/stores/policyStore.ts`
- `electron/src/renderer/hooks/usePolicy.ts`
- `electron/src/renderer/components/runtime/PolicyPanel.tsx`

Modified files:

- `electron/src/renderer/App.tsx`
- `electron/src/renderer/components/layout/Sidebar.tsx`

---

## 4. Runtime Result

After this phase, the runtime tab now shows:

- current automation profile
- short explanation of what that profile means
- recurring-goal previews
- standing-order previews
- last policy refresh time

This phase does **not** yet allow editing recurring goals or standing orders.
That remains Phase 01.

---

## 5. Verification

Executed:

```bash
cd electron && npm run typecheck
cd electron && npm run build
python -m pytest tests/e2e/test_ws_e2e.py tests/unit/infrastructure/test_api.py \
  -q -p no:cacheprovider \
  --basetemp="C:\Users\aquap\.codex\memories\pytest_electron_phase00_1"
```

Result:

- `electron typecheck` passed
- `electron build` passed
- `79 passed`

Notes:

- build emitted a Vite chunk-size warning for existing large bundles
- no backend source changes were needed for this phase

---

## 6. Remaining Gap

Still deferred after this phase:

- recurring-goal create/update UI
- standing-order editing UI
- session-to-chat binding
- run/task inspection drawers

Those are the correct next steps because the policy read surface now exists.
