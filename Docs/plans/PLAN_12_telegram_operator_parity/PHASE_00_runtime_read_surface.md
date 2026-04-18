# Phase 00: Runtime Read Surface

**Priority**: P0  
**Status**: Completed  
**Implemented On**: 2026-04-13  
**Depends On**: current backend only

---

## 1. Goal

Make Telegram useful as a read-only mobile dashboard before adding more write
controls.

Operators should be able to open Telegram and quickly answer:

- is the runtime healthy?
- what is running now?
- which session/chat is blocked?
- are approvals waiting?

---

## 2. Current Gap

Current Telegram commands are minimal:

- `/start`
- `/status`
- `/stop`
- `/approve`
- `/reject`

`/status` only reports:

- active session count
- active run count
- pending approval ids for the current chat

It does not expose:

- run list
- session list
- runtime alert summary
- autonomy profile
- current resource pressure
- recent recovery state

---

## 3. Implemented

### 3.1 Telegram read commands

Modified files:

- `src/ds_agent/gateway/telegram_runner.py`

Implemented:

- `/help` alias for operator command discovery
- expanded `/start` help text with read and control command groups
- richer `/status` summary with:
  - autonomy mode
  - automation profile
  - aggregate session count
  - active run count
  - pending approval count
  - current chat latest run summary
- `/sessions` for recent runtime-visible sessions
- `/runs` for recent runs, scoped to the current chat by default
- `/approvals` for current-chat pending approvals with operator hint text

### 3.2 Mobile formatting rules

Modified files:

- `src/ds_agent/gateway/telegram_runner.py`

Implemented:

- compact line-oriented summaries sized for phone screens
- truncated run message previews and approval prompts
- relative-age labels such as `10s ago`, `5m ago`
- graceful fallback text when there are no runs, approvals, or sessions

### 3.3 Regression coverage

Modified files:

- `tests/unit/infrastructure/test_telegram_runner.py`

Implemented:

- `/help` coverage
- richer `/status` coverage
- `/sessions` coverage
- `/runs` coverage
- `/approvals` coverage
- shared runtime/session registry wiring in the Telegram test harness

Command set after this phase:

- `/start`
- `/help`
- `/status`
- `/sessions`
- `/runs`
- `/approvals`
- `/stop`
- `/approve`
- `/reject`

---

## 4. UX Rules

- keep replies under a few Telegram message chunks
- show newest and most actionable items first
- default to the current chat/session when scope is omitted
- avoid exposing raw JSON or internal field names

---

## 5. Verification

Executed:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_api.py -q -p no:cacheprovider
python -m pytest tests/integration/test_runtime_wiring.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/gateway/telegram_runner.py
python -m ruff check src/ds_agent/channels/bundled/telegram/plugin.py
python -m ruff format --check src/ds_agent/gateway/telegram_runner.py \
  tests/unit/infrastructure/test_telegram_runner.py
```

Result:

- `tests/unit/infrastructure/test_telegram_runner.py`: `20 passed`
- `tests/unit/infrastructure/test_api.py`: `65 passed`
- `tests/integration/test_runtime_wiring.py`: `12 passed`
- `ruff check`: passed
- `ruff format --check`: passed

Manual checks still recommended:

1. Send `/status` from Telegram and verify autonomy/runtime summary
2. Send `/runs` and verify active or recent runs are listed
3. Send `/approvals` and verify pending approvals are readable

---

## 6. Exit Criteria

- Telegram provides a useful runtime read surface
- operators can inspect the current state without opening Electron
- replies stay concise and mobile-readable

---

## 7. Remaining Gap

Still deferred after this phase:

- runtime alert log and digest delivery
- resource pressure from the shared autonomous daemon
- recovery event summaries
- write controls beyond `/stop` and approval resolution

Those require shared daemon/event-log wiring and belong to later phases in
`PLAN_12`.
