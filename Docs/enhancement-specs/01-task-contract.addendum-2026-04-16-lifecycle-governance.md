# 01 Task Contract Addendum (2026-04-16 lifecycle + governance)

## 1. Scope

This addendum records the next `01-task-contract` polish increment after the
assumption-verification operator flow had already landed earlier on
2026-04-16.

The goal of this increment was to close the remaining high-signal operator
coverage gaps called out in the previous `01` addendum:

- packaged-backend Mission Brief lifecycle coverage
- explicit rejection / rollback / delegation scenario coverage

## 2. Landed

### 2.1 Packaged-backend Mission Brief lifecycle smoke

The Task Contract operator flow now has explicit packaged-backend lifecycle
coverage in Electron.

New E2E seed / smoke assets:

- `scripts/seed_task_contract_lifecycle_e2e_workspace.py`
- `electron/tests/smoke/task-contract-lifecycle.spec.ts`

The lifecycle smoke covers:

- seeded draft Mission Brief loading
- inline contract edit from the Mission Brief surface
- `draft -> agreed -> in_progress -> review -> closed`
- explicit close-note capture before closure
- DoD summary visibility after terminal closure

### 2.2 Terminal-state Mission Brief refresh

Mission Brief refresh no longer drops the contract immediately after a terminal
transition.

Landed renderer behavior:

- `useTaskContract()` now tracks the last viewed task id per session
- refresh still prefers `/api/task-contracts/active`
- when `/active` returns `null`, the hook now reloads the last viewed contract
  through `taskContract:get`
- `closed` and `abandoned` contracts remain visible instead of collapsing to
  `No active task contract for this session yet.`

This was required to make terminal-state operator review usable and to keep the
packaged smoke stable for close / abandon scenarios.

### 2.3 Delegation / rollback / rejection governance path

Mission Brief now exposes authority and audience as visible contract metadata,
and packaged-backend governance smoke now covers delegation plus rollback and
rejection transitions.

Landed UI / smoke items:

- Mission Brief authority chip
- Mission Brief audience chip
- `electron/tests/smoke/task-contract-governance.spec.ts`

The governance smoke covers:

- seeded delegated contract visibility (`authority=delegate`,
  `audience=senior_staff`)
- `review -> in_progress` rollback via `Reopen`
- return to `review`
- rejection via `abandoned`
- terminal `abandoned` visibility after the transition

### 2.4 Supplemental regression coverage

Additional non-E2E coverage also landed in this increment:

- `tests/unit/domain/test_task_contract_state_machine.py`
  - `review -> in_progress` reopen validation
  - `draft -> abandoned` rejection validation
- `tests/unit/infrastructure/test_task_contract_telegram.py`
  - `/contract abandon` transition coverage
  - delegated autonomy summary surface coverage

## 3. Verification

Verified in this increment:

- `pytest tests/unit/domain/test_task_contract_state_machine.py tests/unit/infrastructure/test_task_contract_telegram.py tests/unit/application/test_task_contract_usecases.py tests/unit/tools/test_task_contract_tools.py tests/unit/infrastructure/test_task_contract_api_routes.py -q`
  - `39 passed`
- `ruff check` on touched Python files
- `ruff format --check` on touched Python files
- targeted `mypy` on touched Task Contract backend files + lifecycle seed helper
- `python -m compileall src/ds_agent scripts/seed_task_contract_lifecycle_e2e_workspace.py`
- `cd electron && npm run typecheck`
- `cd electron && npm run test:e2e:task-contract`

Non-blocking note:

- the existing Vite chunk-size warning still appears during Electron production
  builds; no new build regression was introduced in this increment

## 4. Current remaining follow-up for 01

The current `01` slice no longer has a broad operator-flow gap.

Remaining follow-up is now limited to optional polish:

- richer realtime subscribe / push behavior for Mission Brief if operator UX
  needs more than the current refresh-on-action and refresh-on-tool-event model
