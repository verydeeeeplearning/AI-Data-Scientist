# Phase 02: Approval Inbox and Decision UX

**Priority**: P0  
**Status**: Completed  
**Implemented On**: 2026-04-13  
**Depends On**: Phase 00-01

---

## 1. Goal

Make approvals genuinely usable from a phone.

The operator should be able to see what is waiting, understand the request
quickly, and approve or reject without memorizing awkward command syntax.

---

## 2. Implemented

### 2.1 Approval request and resolution messaging

Modified files:

- `src/ds_agent/gateway/telegram_runner.py`

Implemented:

- richer `approval.requested` Telegram notifications with:
  - session
  - run
  - queue position
  - options
  - default answer
  - `/approval <id>` guidance
- richer `approval.resolved` messaging
- unified approval resolution summary across:
  - plain-text reply resolution
  - `/approve`
  - `/reject`

### 2.2 Approval inbox and detail surface

Modified files:

- `src/ds_agent/gateway/telegram_runner.py`

Implemented:

- improved `/approvals` inbox with:
  - queue position
  - run id
  - default answer
  - session label when scope expands to all sessions
- `/approval [id]` detail lookup
- current-chat default behavior when id is omitted
- detail output with:
  - session
  - run
  - status
  - queue position
  - created age
  - question
  - options
  - default
  - response when already resolved

### 2.3 Explicit decision UX

Modified files:

- `src/ds_agent/gateway/telegram_runner.py`

Implemented:

- `reply in plain text` remains the fastest path for the latest pending item in the chat
- `/approve <id> <response>` and `/reject <id> [reason]` remain as reliable fallbacks
- resolution summaries now show remaining pending approvals after each decision

### 2.4 Regression coverage

Modified files:

- `tests/unit/infrastructure/test_telegram_runner.py`

Implemented:

- approval request callback coverage
- `/approvals` queue/default coverage
- `/approval <id>` detail coverage
- richer `/approve` and `/reject` response coverage
- plain-text approval resolution summary coverage

Command set after this phase:

- `/start`
- `/help`
- `/status`
- `/sessions`
- `/runs`
- `/run [id]`
- `/approvals`
- `/approval [id]`
- `/session`
- `/history [count]`
- `/resume`
- `/stop [id]`
- `/approve`
- `/reject`

---

## 3. UX Rules

- approvals should be scannable in one screen
- fallback command UX must still work even if inline actions fail
- approval replies should include enough context to avoid wrong approvals
- rejection should allow an optional short reason

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

- `tests/unit/infrastructure/test_telegram_runner.py`: `27 passed`
- `tests/unit/infrastructure/test_api.py`: `65 passed`
- `tests/integration/test_runtime_wiring.py`: `12 passed`
- `ruff check`: passed
- `ruff format --check`: passed

Manual checks still recommended:

1. Trigger an approval and confirm it appears in Telegram with session/run context
2. Open `/approvals` and inspect one item with `/approval <id>`
3. Approve once with plain text and once with `/approve`
4. Reject once with `/reject`

---

## 5. Exit Criteria

- approvals are easy to discover from Telegram
- approvals can be resolved reliably from a phone
- approval context is clear enough to avoid blind operator decisions

---

## 6. Notes

- Inline keyboard controls were intentionally deferred.
- The current command-first UX already reduces operator friction materially
  without adding callback-query handling to the Telegram plugin.

---

## 7. Remaining Gap

Still deferred after this phase:

- runtime alert and recovery notification routing
- policy and project control from mobile
- thread-aware delivery hardening
- optional inline approval buttons

Those remain in later `PLAN_12` phases.
