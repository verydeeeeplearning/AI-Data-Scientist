# Phase 04: Policy and Project Mobile Control

**Priority**: P1  
**Status**: Completed (Config-Persist Control Surface)  
**Implemented On**: 2026-04-13  
**Depends On**: Phase 00-03

---

## 1. Goal

Expose a small, safe subset of policy and project controls from Telegram so the
operator can adjust autonomy behavior from a phone without opening Electron.

In this phase, "adjust" means "persist operator intent into shared config/state".
It does not mean hot-reconfiguring every already-running backend process.

---

## 2. Implemented

### 2.1 Policy summary and detail commands

Modified files:

- `src/ds_agent/gateway/telegram_runner.py`

Implemented:

- `/policy` summary with:
  - autonomy enabled or disabled
  - current automation profile
  - recurring goal count
  - standing order count
  - project count
- `/goals` summary for recurring goals
- `/orders` summary for standing orders
- compact mobile formatting for recurring-goal intervals and prompts

### 2.2 Safe autonomy control from Telegram

Modified files:

- `src/ds_agent/gateway/telegram_runner.py`

Implemented:

- `/autonomy on|off`
- `/profile manual|balanced|aggressive`
- config persistence through the shared YAML config file
- post-mutation echo that shows resulting state
- explicit note that already-running backends may need reload to apply

This keeps Telegram useful for operator intervention while avoiding deceptive
"live reconfigure" behavior across already-running processes.

### 2.3 Lightweight project control

Modified files:

- `src/ds_agent/api/workspace_service.py`
- `src/ds_agent/gateway/telegram_runner.py`

Implemented:

- `WorkspaceService.get_project(...)` helper so Telegram does not reach into
  project-store internals directly
- `/projects` summary
- `/project <id>` detail lookup
- `/project create <name>` for low-friction mobile setup

The mobile surface remains intentionally narrow: create and inspect are in
scope; richer project editing stays better suited to Electron.

### 2.4 Regression coverage

Modified files:

- `tests/unit/infrastructure/test_telegram_runner.py`

Implemented:

- `/policy` summary coverage
- `/autonomy` config-persistence coverage
- `/profile` config-persistence coverage
- `/goals` summary coverage
- `/orders` summary coverage
- `/projects` summary coverage
- `/project create` and `/project <id>` detail coverage

---

## 3. UX Rules

- Telegram should expose only high-signal, low-risk controls
- state-changing commands must echo the resulting saved state
- project replies should stay short enough for a phone screen
- complex policy editing remains deferred to richer surfaces

---

## 4. Verification

Executed:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_api.py -q -p no:cacheprovider
python -m pytest tests/integration/test_runtime_wiring.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/api/workspace_service.py \
  src/ds_agent/gateway/telegram_runner.py \
  tests/unit/infrastructure/test_telegram_runner.py
python -m ruff format --check src/ds_agent/api/workspace_service.py \
  src/ds_agent/gateway/telegram_runner.py \
  tests/unit/infrastructure/test_telegram_runner.py
```

Result:

- `tests/unit/infrastructure/test_telegram_runner.py`: passed
- `tests/unit/infrastructure/test_api.py`: passed
- `tests/integration/test_runtime_wiring.py`: passed
- `ruff check`: passed
- `ruff format --check`: passed

Manual checks still recommended:

1. Change `/autonomy` from a real Telegram chat and confirm the saved config is used after restart
2. Inspect `/policy`, `/goals`, and `/orders` from a phone
3. Create a project with `/project create <name>` and inspect it with `/project <id>`

---

## 5. Exit Criteria

- Telegram can inspect project and policy state without Electron
- Telegram can save a minimal safe subset of autonomy controls
- saved mobile changes are explicit, concise, and hard to misuse

---

## 6. Notes

- Config mutations are persisted, not hot-pushed into already-running backends.
- Telegram still remains command-first.
- Richer recurring-goal or standing-order editing is still deferred.

---

## 7. Remaining Gap

Still deferred after this phase:

- thread/topic-aware delivery
- artifact-aware delivery and notifications
- inline buttons for common operator actions
- per-chat subscriptions and notification preferences

Those remain in `PLAN_12 Phase 05`.
