# Plan 12: Telegram Operator Parity

**Status**: Substantially Completed  
**Created**: 2026-04-13  
**Scope**: Turn Telegram from a basic input bot into a mobile operator surface for the autonomous DS runtime, while keeping full live cross-process parity explicitly out of scope

---

## 1. Objective

Bring Telegram close to the same operational tier as the current backend runtime
and the now-completed Electron operator console.

The target is not "chat with the agent from Telegram."  
The target is "control the agent from a phone."

That means Telegram should become usable for:

- checking runtime health
- inspecting sessions and runs
- resolving approvals
- receiving recovery and alert notifications
- changing a small set of autonomy controls without opening Electron

Implementation note:

- This plan is complete in the sense that Telegram now has a practical operator command surface.
- It does **not** mean a separate Telegram process shares the same live in-memory
  `session / run / task` registries as a separate API/Electron process.
- Telegram currently shares persisted runtime state such as approvals, transcripts,
  checkpoints, policy state, projects, and runtime events, and it can control the
  runs owned by the Telegram gateway process itself.

---

## 2. Current State

Today `src/ds_agent/gateway/telegram_runner.py` already has:

- one-chat-one-session routing
- run execution
- `/status`
- `/stop`
- `/approve`
- `/reject`

But it still lacks:

- read-only runtime inspection commands
- mobile-friendly run/session summaries
- first-class approval inbox UX
- runtime alert subscriptions and digests
- policy/project control from Telegram
- thread/topic-aware delivery and artifact delivery ergonomics

---

## 3. Phase Order

1. Phase 00: Runtime Read Surface
2. Phase 01: Run and Session Control
3. Phase 02: Approval Inbox and Decision UX
4. Phase 03: Alert Notification and Digest Routing
5. Phase 04: Policy and Project Mobile Control
6. Phase 05: Delivery, Threading, and Operator Hardening

---

## 4. Milestones

### Milestone A: Mobile Visibility

- Phase 00 complete
- Telegram can show runtime, session, run, and approval summaries

### Milestone B: Mobile Intervention

- Phase 01-02 complete
- Telegram can stop work, inspect context, and resolve approvals cleanly

### Milestone C: Mobile Operations

- Phase 03-04 complete
- Telegram receives runtime alerts and can persist a limited set of autonomy controls

### Milestone D: Production-Grade Channel

- Phase 05 complete
- Telegram delivery is robust enough for daily operator use

---

## 5. Verification Baseline

Every phase should pass:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_api.py -q -p no:cacheprovider
python -m pytest tests/integration/test_runtime_wiring.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/gateway/telegram_runner.py src/ds_agent/channels/bundled/telegram/plugin.py
```

If a phase touches shared runtime/event surfaces, also run:

```bash
python -m pytest tests/e2e/test_ws_e2e.py -q -p no:cacheprovider
cd electron && npm run typecheck
```

---

## 6. Phase Summary

| Phase | Goal | Priority | Status |
|------|------|----------|--------|
| 00 | expose runtime/session/run/approval summaries to Telegram | P0 | completed |
| 01 | make Telegram a real run/session control surface | P0 | completed |
| 02 | make approvals mobile-first and low-friction | P0 | completed |
| 03 | route runtime alerts and recovery signals to Telegram | P1 | completed |
| 04 | allow a limited set of policy/project controls from mobile | P1 | completed |
| 05 | harden delivery, topic routing, and artifact notifications | P2 | completed |

---

Status note:

- The table above marks Telegram operator UX phases as implemented.
- It does not claim full cross-process sharing of live `run / session / task` state.

## 7. Notes

- This plan assumes the persisted runtime/event surfaces from `PLAN_10` and the
  Electron operator UX from `PLAN_11` are available.
- Telegram should stay command-first in the early phases.
- Inline keyboards are useful, but should be added only where they reduce operator friction materially.
- Mobile control should expose only high-signal actions, not every backend knob.

---

## 8. Detailed Documents

- [PHASE_00_runtime_read_surface.md](./PHASE_00_runtime_read_surface.md)
- [PHASE_01_run_session_control.md](./PHASE_01_run_session_control.md)
- [PHASE_02_approval_inbox_decision_ux.md](./PHASE_02_approval_inbox_decision_ux.md)
- [PHASE_03_alert_notification_digest.md](./PHASE_03_alert_notification_digest.md)
- [PHASE_04_policy_project_mobile_control.md](./PHASE_04_policy_project_mobile_control.md)
- [PHASE_05_delivery_threading_hardening.md](./PHASE_05_delivery_threading_hardening.md)
