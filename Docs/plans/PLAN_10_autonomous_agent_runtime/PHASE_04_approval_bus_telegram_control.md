# Phase 04: Approval Bus + Telegram Control Surface

**Priority**: P1  
**Milestone**: B  
**Status**: Completed  
**Implemented On**: 2026-04-12

---

## 1. Goal

Replace the placeholder `ask_user` flow with a persisted approval bus that works
across runtime surfaces.

The target outcome for this phase was:

- `ask_user` creates durable approval requests instead of returning a local placeholder
- Telegram can approve, reject, and inspect pending requests
- Electron can list and resolve pending approvals
- approval state survives process restarts

---

## 2. Implemented

### 2.1 Persisted approval state

New files:

- `src/ds_agent/domain/entities/approval.py`
- `src/ds_agent/runtime/approval_store.py`
- `src/ds_agent/runtime/tool_runtime_context.py`

Implemented:

- `ApprovalStatus` with `pending`, `approved`, `rejected`
- `ApprovalRequest` domain record
- `JsonApprovalStore` with file-backed persistence under runtime storage
- `create`, `get`, `list`, `latest_pending_for_session`, `resolve`,
  `wait_for_resolution`, and `pending_count`
- task-local runtime context so tools know the active `sessionId`, `runId`,
  `surface`, event emitter, and approval store

### 2.2 `ask_user` -> approval bus

Modified files:

- `src/ds_agent/tools/user_interaction.py`
- `src/ds_agent/agent/core.py`
- `src/ds_agent/agent/factory.py`

Implemented:

- `ask_user` now creates a persisted approval request when a runtime control
  surface is available
- `approval.requested` and `approval.resolved` events are emitted through the
  existing callback bridge
- approved responses return structured tool output
- rejected approvals return structured tool errors so the agent loop can treat
  them as blocked or rejected work
- CLI keeps the non-blocking fallback behavior when no approval bus is available

### 2.3 WebSocket approval RPCs

Modified files:

- `src/ds_agent/api/agent_session_registry.py`
- `src/ds_agent/api/ws_handler.py`
- `src/ds_agent/api/event_schemas.py`

Implemented:

- shared approval store wiring through the agent factory and session registry
- new RPC methods:
  - `approval.list`
  - `approval.resolve`
- serialized approval payloads exposed to Electron/WebSocket clients
- status payload now includes `pendingApprovals`

### 2.4 Telegram control surface

Modified files:

- `src/ds_agent/gateway/telegram_runner.py`

Implemented:

- Telegram receives approval events and can surface pending requests in chat
- `/approve` and `/reject` commands resolve persisted approvals
- plain message replies can resolve the latest pending approval for that chat
- `/status` now reports pending approvals for the current conversation

### 2.5 Electron approval inbox

New files:

- `electron/src/renderer/components/workflow/ApprovalPanel.tsx`

Modified files:

- `electron/src/renderer/stores/workflowStore.ts`
- `electron/src/renderer/types/events.ts`
- `electron/src/renderer/hooks/useWorkflow.ts`
- `electron/src/renderer/components/layout/Sidebar.tsx`
- `electron/src/renderer/App.tsx`

Implemented:

- workflow store now tracks approval requests
- workflow hook subscribes to approval events and polls `approval.list`
- sidebar workflow tab shows pending approvals
- users can approve with predefined options, submit a response, or reject

---

## 3. Runtime Behavior

The Phase 04 flow is now:

1. Agent calls `ask_user`
2. A persisted approval request is created
3. Electron and Telegram can observe the same approval request
4. One control surface resolves it
5. The tool resumes with the stored response or fails with a rejection error

This is now a real safety boundary, not a placeholder interaction helper.

---

## 4. Changed Files

New files:

- `src/ds_agent/domain/entities/approval.py`
- `src/ds_agent/runtime/approval_store.py`
- `src/ds_agent/runtime/tool_runtime_context.py`
- `electron/src/renderer/components/workflow/ApprovalPanel.tsx`
- `tests/unit/infrastructure/test_approval_bus.py`

Modified files:

- `src/ds_agent/tools/user_interaction.py`
- `src/ds_agent/agent/core.py`
- `src/ds_agent/agent/factory.py`
- `src/ds_agent/api/agent_session_registry.py`
- `src/ds_agent/api/ws_handler.py`
- `src/ds_agent/api/event_schemas.py`
- `src/ds_agent/gateway/telegram_runner.py`
- `electron/src/renderer/stores/workflowStore.ts`
- `electron/src/renderer/types/events.ts`
- `electron/src/renderer/hooks/useWorkflow.ts`
- `electron/src/renderer/components/layout/Sidebar.tsx`
- `electron/src/renderer/App.tsx`
- `tests/unit/infrastructure/test_api.py`
- `tests/unit/infrastructure/test_telegram_runner.py`
- `tests/integration/test_runtime_wiring.py`

---

## 5. Verification

Executed:

```bash
python -m pytest tests/unit/infrastructure/test_approval_bus.py \
  tests/unit/infrastructure/test_api.py \
  tests/unit/infrastructure/test_telegram_runner.py \
  tests/integration/test_runtime_wiring.py \
  tests/e2e/test_ws_e2e.py \
  -q -p no:cacheprovider \
  --basetemp="C:\Users\aquap\.codex\memories\pytest_phase04_final"
```

Result:

- `106 passed`

Additional verification:

- `python -m ruff check ...` passed for the changed Python files
- `python -m ruff format --check ...` passed for the changed Python files
- `npx tsc --noEmit` passed in `electron/`
- `mypy` was not executed because the current environment does not have the
  module installed

---

## 6. Notes

Important decisions in this phase:

- approval state is store-first, not UI-first
- Telegram and Electron resolve the same persisted object
- CLI is intentionally left as a non-blocking fallback surface

That keeps the runtime compatible with the current architecture while still
establishing the cross-surface approval boundary needed for autonomous runs.

---

## 7. Remaining Gap

Still out of scope after Phase 04:

- role-based approval policy
- approval escalation chains
- richer operator audit dashboards
- automatic policy routing between approval types

Those belong to later policy and operator-console phases, not the core approval
bus milestone.
