# Phase 03: Run and Task Inspection

**Priority**: P1  
**Status**: Completed  
**Implemented On**: 2026-04-13  
**Depends On**: Phase 02 recommended

---

## 1. Goal

Upgrade runtime summary cards into an inspection workflow so operators can
understand:

- what a run did
- why it failed
- how it relates to its task
- how it relates to its session

---

## 2. Implemented

### 2.1 Shared selection state for runtime inspection

Modified files:

- `electron/src/renderer/stores/runtimeStore.ts`

Implemented:

- `selectedRunId`
- `selectRun(...)`
- `clearSelectedRun()`

This gives the runtime UI one shared inspection state that can be driven from
either the runs list or the tasks list.

### 2.2 Run inspector drawer

New files:

- `electron/src/renderer/components/runtime/RunDetailDrawer.tsx`

Modified files:

- `electron/src/renderer/components/layout/MainPanel.tsx`

Implemented:

- a right-side run inspector drawer in the main layout
- drawer content for:
  - run id
  - session id
  - surface
  - lifecycle timestamps
  - duration
  - cost
  - linked task id
  - original message
  - result preview
  - error
  - task context
- `Open Session` action from inside the drawer
- `Abort Run` action for running runs

This keeps inspection close to the main operator workspace instead of burying
detail inside narrow runtime cards.

### 2.3 Runs panel inspection flow

Modified files:

- `electron/src/renderer/components/runtime/RunsPanel.tsx`

Implemented:

- `Inspect` action on each run card
- active-card highlight for the currently inspected run
- existing abort action preserved

This turns the runs list into a navigable summary instead of a static list.

### 2.4 Task-to-run navigation

Modified files:

- `electron/src/renderer/components/runtime/TasksPanel.tsx`

Implemented:

- `Inspect run` action on each task card
- selected-run highlight when a task points to the currently open inspector run

This is the first explicit bridge from task state to run state in the Electron
frontend.

---

## 3. Changed Files

New files:

- `electron/src/renderer/components/runtime/RunDetailDrawer.tsx`

Modified files:

- `electron/src/renderer/stores/runtimeStore.ts`
- `electron/src/renderer/components/runtime/RunsPanel.tsx`
- `electron/src/renderer/components/runtime/TasksPanel.tsx`
- `electron/src/renderer/components/layout/MainPanel.tsx`

---

## 4. Runtime Result

After this phase, the operator flow is:

1. Open runtime tab
2. Choose a run from `Runs`
   - or choose `Inspect run` from `Tasks`
3. Review the selected run in a right-side drawer
4. Jump to the linked session if needed
5. Abort the run directly from the drawer if it is still active

This makes the runtime surface much closer to a real operator console.

---

## 5. Verification

Executed:

```bash
cd electron && npm run typecheck
cd electron && npm run build
python -m pytest tests/e2e/test_ws_e2e.py tests/unit/infrastructure/test_api.py \
  -q -p no:cacheprovider \
  --basetemp="C:\Users\aquap\.codex\memories\pytest_electron_phase03_1"
```

Result:

- `electron typecheck` passed
- `electron build` passed
- `79 passed`

Notes:

- build still emits the existing Vite chunk-size warning
- this phase required no backend changes
- inspection detail is limited to the data already present in `run.list` and
  `task.list`

---

## 6. Remaining Gap

Still deferred after this phase:

- project surface
- auth-model compatibility UX
- alert and recovery timeline
- richer inspection beyond existing `run.list` payload detail

The main parity gap is now no longer run/task visibility. It shifts to project
workflows and runtime event visibility.
