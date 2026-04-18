# Phase 05: Alert and Recovery Timeline

**Priority**: P2  
**Status**: Completed  
**Depends On**: implemented via `runtime.events.list` and `runtime.alert`

---

## 1. Goal

Show recovery, health, pressure, and policy-dispatch signals as a runtime
operations timeline inside Electron.

---

## 2. Delivered Backend Exposure

This phase added a small backend runtime-event substrate so Electron can render
an actual operations timeline instead of summary chips only.

New backend pieces:

- `src/ds_agent/runtime/runtime_event_log.py`
- `runtime.events.list` RPC in `src/ds_agent/api/ws_handler.py`
- `runtime.alert` broadcast from `AppState.record_runtime_event(...)`
- coordinator and daemon wiring for:
  - `recovery.*`
  - `pipeline.health.degraded`
  - `model.monitor.degraded`
  - `system.resource.*`
  - policy dispatch / suppression decisions

---

## 3. Implemented Frontend Surface

New files:

- `electron/src/renderer/stores/runtimeEventStore.ts`
- `electron/src/renderer/hooks/useRuntimeEvents.ts`
- `electron/src/renderer/components/runtime/RuntimeAlertsPanel.tsx`

Modified files:

- `electron/src/renderer/hooks/useRuntime.ts`
- `electron/src/renderer/components/runtime/GatewayStatusPanel.tsx`
- `electron/src/renderer/components/runtime/SessionsPanel.tsx`
- `electron/src/renderer/components/layout/Sidebar.tsx`
- `electron/src/renderer/App.tsx`

Delivered behavior:

- `useRuntimeEvents(...)` now hydrates the timeline from `runtime.events.list`
- live `runtime.alert` broadcasts update Electron without waiting for the next poll
- `RuntimeAlertsPanel` shows recovery, health, pressure, policy, and approval events
- alerts can open the linked session or inspect the linked run
- `GatewayStatusPanel` now shows recovered session count, warning count, and latest alert
- `SessionsPanel` now shows recent alert counts per session

---

## 4. Verification

Executed:

```bash
cd electron && npm run typecheck
cd electron && npm run build
python -m pytest tests/unit/infrastructure/test_api.py tests/integration/test_runtime_wiring.py tests/e2e/test_ws_e2e.py -q -p no:cacheprovider --basetemp='C:\Users\aquap\.codex\memories\pytest_electron_phase05_1'
python -m ruff check src/ds_agent/api/app.py src/ds_agent/api/ws_handler.py src/ds_agent/gateway/daemon.py src/ds_agent/runtime/coordinator.py src/ds_agent/runtime/runtime_event_log.py tests/unit/infrastructure/test_api.py
```

Result:

- `npm run typecheck`: passed
- `npm run build`: passed
- `pytest ...`: `93 passed`
- `ruff check ...`: passed
- `vite build` still reports the existing chunk-size warning, but the build succeeds

---

## 5. Exit Criteria

- Electron shows a runtime timeline, not only summary counters
- recovery and health signals are understandable by an operator
- each alert is traceable to a session, run, or policy decision when possible
