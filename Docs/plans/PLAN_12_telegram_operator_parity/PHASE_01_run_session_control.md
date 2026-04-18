# Phase 01: Run and Session Control

**Priority**: P0  
**Status**: Completed  
**Implemented On**: 2026-04-13  
**Depends On**: Phase 00

---

## 1. Goal

Allow Telegram operators to do more than "stop the latest thing."

Mobile control should support targeted run/session actions with enough context
to avoid blind intervention.

---

## 2. Implemented

### 2.1 Run control and inspection

Modified files:

- `src/ds_agent/gateway/telegram_runner.py`

Implemented:

- `/stop [id]` support for explicit run-id targeting
- `/run [id]` for run detail lookup
- current-chat default behavior when ids are omitted
- run detail output with:
  - session
  - status
  - prompt preview
  - task id
  - error or result preview
  - cost when available

### 2.2 Session context surfaces

Modified files:

- `src/ds_agent/gateway/telegram_runner.py`

Implemented:

- `/session` summary for the current chat
- `/history [count]` for recent user/assistant turns
- transcript/checkpoint read-path usage for mobile inspection
- session summary output with:
  - latest run
  - checkpoint step
  - active goal state
  - pending approval count
  - working-memory summary
  - suggested next step
  - recovery note when present

### 2.3 Resume semantics

Modified files:

- `src/ds_agent/gateway/telegram_runner.py`

Implemented:

- `/resume` for intentional continuation of the current chat
- resume prompt construction from:
  - checkpoint step
  - active goal
  - working-memory summary
  - next-step hint
  - latest-run status
- shared run execution path for both normal Telegram messages and command-triggered resume

### 2.4 Regression coverage

Modified files:

- `tests/unit/infrastructure/test_telegram_runner.py`

Implemented:

- `/run` detail coverage
- `/session` summary coverage
- `/history [n]` coverage
- `/resume` coverage
- `/stop <run_id>` coverage
- persisted transcript/checkpoint/goal/memory test wiring

Command set after this phase:

- `/start`
- `/help`
- `/status`
- `/sessions`
- `/runs`
- `/run [id]`
- `/session`
- `/history [count]`
- `/approvals`
- `/resume`
- `/stop [id]`
- `/approve`
- `/reject`

---

## 3. UX Rules

- never require operators to memorize hidden ids when a current-chat default exists
- when ids are needed, always echo them in read commands first
- stop actions should confirm what was stopped
- resume actions should explain what context is being resumed

---

## 4. Verification

Executed:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_api.py -q -p no:cacheprovider
python -m pytest tests/integration/test_runtime_wiring.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/gateway/telegram_runner.py \
  src/ds_agent/channels/bundled/telegram/plugin.py
python -m ruff format --check src/ds_agent/gateway/telegram_runner.py \
  tests/unit/infrastructure/test_telegram_runner.py
```

Result:

- `tests/unit/infrastructure/test_telegram_runner.py`: `25 passed`
- `tests/unit/infrastructure/test_api.py`: `65 passed`
- `tests/integration/test_runtime_wiring.py`: `12 passed`
- `ruff check`: passed
- `ruff format --check`: passed

Manual checks still recommended:

1. Start a run from Telegram and inspect it with `/run`
2. Stop the latest run and then stop by explicit run id
3. Check `/session`, `/history`, and `/resume`

---

## 5. Exit Criteria

- Telegram can inspect and control runs intentionally
- Telegram can expose current session context without Electron
- mobile stop/resume flows are understandable and low-risk

---

## 6. Remaining Gap

Still deferred after this phase:

- approval detail lookup and lower-friction decision UX
- runtime alert and recovery notification routing
- policy and project control from mobile
- thread-aware delivery hardening

Those remain in later `PLAN_12` phases.
