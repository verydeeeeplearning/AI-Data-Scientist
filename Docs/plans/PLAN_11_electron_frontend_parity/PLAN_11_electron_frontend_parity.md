# Plan 11: Electron Frontend Parity

**Status**: Completed  
**Created**: 2026-04-13  
**Scope**: Electron renderer parity with the current backend runtime and RPC surface

---

## 1. Objective

Bring the Electron frontend up to the level of the current backend so the app
behaves less like a chat shell and more like an operator console for the
autonomous DS runtime.

This plan focuses on frontend work first. Where a phase needs a small backend
exposure to finish cleanly, that dependency is stated explicitly.

---

## 2. Phase Order

1. Phase 00: Policy Runtime Surface
2. Phase 01: Policy Edit Surface
3. Phase 02: Session Continuity and Chat Binding
4. Phase 03: Run and Task Inspection
5. Phase 04: Project Surface and Auth UX
6. Phase 05: Alert and Recovery Timeline

---

## 3. Milestones

### Milestone A: Operator Control

- Phase 00-02 complete
- policy state is visible
- recurring goals and standing orders are editable
- runtime sessions can be opened directly in chat

### Milestone B: Runtime Inspection

- Phase 03 complete
- operators can inspect one run or task in detail

### Milestone C: Workspace and Reliability UX

- Phase 04 complete
- project workflows are visible in Electron
- auth requirements are understandable from the UI

### Milestone D: Live Operations Timeline

- Phase 05 complete
- recovery, pressure, and monitoring signals are visible in Electron
- live timeline history is backed by `runtime.events.list` plus `runtime.alert`

---

## 4. Verification Baseline

Every phase should pass:

```bash
cd electron && npm run typecheck
cd electron && npm run build
python -m pytest tests/e2e/test_ws_e2e.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_api.py -q -p no:cacheprovider
```

If a phase changes backend-wiring assumptions, also run:

```bash
python -m pytest tests/integration/test_runtime_wiring.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/api/ws_handler.py src/ds_agent/gateway/daemon.py
```

---

## 5. Phase Summary

| Phase | Goal | Priority | Status |
|------|------|----------|--------|
| 00 | expose policy state in frontend stores and runtime tab | P0 | completed |
| 01 | let operators create and edit recurring goals and standing orders | P0 | completed |
| 02 | let operators open an existing runtime session in the chat surface | P0 | completed |
| 03 | let operators inspect runs and tasks beyond summary cards | P1 | completed |
| 04 | expose projects and auth-model compatibility in the app | P2 | completed |
| 05 | show recovery / health / pressure / policy signals as an operations timeline | P2 | completed |

---

## 6. Notes

- This plan intentionally starts with policy and session continuity because those
  are the largest gaps between the backend runtime and the Electron operator UX.
- Phase 05 is the only phase that may need extra backend support to become fully
  useful. The other phases can be built directly on the current RPC surface.

---

## 7. Detailed Documents

- [PHASE_00_policy_runtime_surface.md](./PHASE_00_policy_runtime_surface.md)
- [PHASE_01_policy_edit_surface.md](./PHASE_01_policy_edit_surface.md)
- [PHASE_02_session_continuity_chat_binding.md](./PHASE_02_session_continuity_chat_binding.md)
- [PHASE_03_run_task_inspection.md](./PHASE_03_run_task_inspection.md)
- [PHASE_04_project_surface_auth_ux.md](./PHASE_04_project_surface_auth_ux.md)
- [PHASE_05_alert_recovery_timeline.md](./PHASE_05_alert_recovery_timeline.md)
