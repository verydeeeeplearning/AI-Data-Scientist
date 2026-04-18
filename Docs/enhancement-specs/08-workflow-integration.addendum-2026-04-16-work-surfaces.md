# 08 Workflow Integration Addendum (2026-04-16 work surfaces)

## 1. Scope

This addendum records the next `08-workflow-integration` increment after the
P2a and P3a backend/tooling foundation had already landed on 2026-04-16.

The goal of this increment was to start closing the remaining explicit gaps
called out in `README.md` and `08-workflow-integration.md`:

- Electron workflow surface for WorkObjects
- CLI workflow surface for WorkObjects

This increment intentionally focused on read-oriented operator surfaces first.
It did not yet attempt the later `integration health`, `DLQ replay`, or richer
request-source ingestion work.

## 2. Landed

### 2.1 Backend HTTP route for WorkObjects

The backend now exposes a dedicated workflow-integration read surface:

- `GET /api/work-objects`
- `GET /api/work-objects/{work_object_id}`

The route supports:

- filtering by `sessionId`
- filtering by `taskContractId`
- filtering by `phase`
- configurable `timelineLimit` for detail views

This gives Electron a stable, typed read boundary for WorkObject list/detail
queries without reaching into persistence directly.

### 2.2 CLI `ds-agent work ...`

The CLI now has a first-class WorkObject surface:

- `ds-agent work list`
- `ds-agent work show <work_object_id>`

Landed items:

- `src/ds_agent/cli/work_cli.py`
- `src/ds_agent/presentation/work_object_presenters.py`
- `src/ds_agent/cli/main.py` command registration

The list surface supports session/task/phase filtering, and the detail surface
renders request metadata, execution state, external references, follow-up
actions, and the persisted integration timeline.

### 2.3 Electron `WorkObjectPanel`

The Workflow tab now includes a read-only `WorkObjectPanel`.

Landed Electron pieces:

- backend bridge: `ipc.ts`, `preload/index.ts`, `vite-env.d.ts`
- typed renderer models: `types/workObject.ts`
- `useWorkObjects()` session-aware list/detail hook
- `WorkObjectPanel` in the Workflow tab

The panel supports:

- current-session WorkObject list loading
- phase filtering
- local search by WorkObject id / TaskContract id / title
- detail inspection for the selected WorkObject
- persisted integration timeline viewing
- documentation reference and follow-up summary viewing

### 2.4 Contract and route coverage

This increment also added dedicated regression coverage for the new read
surfaces:

- presenter unit tests
- CLI unit tests
- API route unit tests
- Electron contract test for WorkObject panel model/filter helpers

## 3. Verification

Verified in this increment:

- `pytest tests/unit/presentation/test_work_object_presenters.py tests/unit/infrastructure/test_work_cli.py tests/unit/infrastructure/test_work_object_api_routes.py -q`
  - `7 passed`
- `ruff check` on touched Python files
- `ruff format --check` on touched Python files
- targeted `mypy` on `work_object_presenters.py`, `work_cli.py`, `work_objects.py`
- `python -m compileall` on touched Python files
- `cd electron && npm run typecheck`
- `cd electron && npm run test:contract:work-objects`
- `cd electron && npm run build`

Non-blocking note:

- the existing Vite chunk-size warning remains unchanged during Electron builds

## 4. Current remaining follow-up for 08

The current `08` slice no longer lacks a basic operator read surface.

Remaining follow-up is now narrower:

- richer request-source ingestion beyond CLI/Telegram/Electron prompt entry
- `IntegrationSettings` / connector-configuration operator surface
- `ds-agent integration health` and `ds-agent integration replay --event ...`
- packaged end-to-end WorkObject integration flow coverage
- later Email/Calendar/BI and DLQ/replay operations from the original plan
