# 01 Task Contract Addendum (2026-04-16 assumption verify + smoke)

## 1. Scope

This addendum records the latest `01-task-contract` polish increment after the
core Phase 1-5 implementation had already landed.

The goal of this increment was to close one of the remaining operator-surface
gaps from `01-task-contract.md`:

- Electron assumption verify action
- Packaged-backend Mission Brief smoke coverage for the operator flow

## 2. Landed

### 2.1 Backend assumption verification path

The Task Contract subsystem now supports explicit assumption verification
instead of a read-only `AssumptionDrawer`.

Landed items:

- `VerifyAssumptionDTO`
- `VerifyAssumptionUseCase`
- `task_contract.assumption_verified` event emission
- `TaskContractContainer.verify_assumption`
- `POST /api/task-contracts/{task_id}/assumptions/{entry_id}/verify`
- `verify_assumption` tool surface

Behavior:

- verification is optimistic-lock protected via `expected_version`
- the selected `AssumptionEntry` is marked `verified=True`
- `verification_note` is stored on the entry
- the parent TaskContract version is incremented

### 2.2 Electron operator surface

`MissionBriefPanel` and `AssumptionDrawer` now expose an actual operator action:

- open the Assumptions drawer from Mission Brief
- enter an optional verification note
- mark one assumption as verified
- refresh the active TaskContract and remove the entry from the open-assumption count

Landed wiring:

- Electron main IPC: `taskContract:verifyAssumption`
- preload bridge + typed renderer surface
- `useTaskContract().verifyAssumption(...)`
- Mission Brief success/error handling and test ids for smoke automation

### 2.3 E2E seed + smoke coverage

The isolated packaged-backend E2E seed now includes one high-risk open
assumption on the seeded TaskContract.

New smoke coverage:

- `electron/tests/smoke/task-contract-assumptions.spec.ts`
- opens the seeded runtime session
- switches to the Workflow tab
- opens Mission Brief assumptions
- submits a verification note
- confirms the open-assumption count drops from `1` to `0`

The existing autonomy smoke also remains green after the updated seed path.

## 3. Verification

Verified in this increment:

- `pytest tests/unit/application/test_task_contract_usecases.py tests/unit/tools/test_task_contract_tools.py tests/unit/infrastructure/test_task_contract_api_routes.py -q`
  - `24 passed`
- `ruff check` on touched Python files
- `ruff format --check` on touched Python files
- targeted `mypy` on touched Task Contract backend files + seed helper
- `python -m compileall src/ds_agent scripts/seed_autonomy_e2e_workspace.py`
- `cd electron && npm run typecheck`
- `cd electron && npm run test:e2e:task-contract`
- `cd electron && npm run test:e2e:autonomy`

## 4. Current remaining follow-up for 01

The current `01` slice is no longer blocked on assumption verification.

This section was superseded later on 2026-04-16 by the lifecycle/governance
increment recorded in
`01-task-contract.addendum-2026-04-16-lifecycle-governance.md`.

At the time of this addendum, remaining follow-up was:

- broader Mission Brief lifecycle E2E coverage (`draft -> edit -> agree -> closed`)
- explicit rejection / rollback / delegation scenarios from the original `01` checklist
- optional realtime subscribe/push polish if the Mission Brief operator surface
  needs richer live updates than the current refresh-on-action path
