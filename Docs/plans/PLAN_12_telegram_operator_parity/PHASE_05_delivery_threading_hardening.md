# Phase 05: Delivery, Threading, and Operator Hardening

**Priority**: P2  
**Status**: Completed  
**Implemented On**: 2026-04-13  
**Depends On**: Phase 00-04

---

## 1. Goal

Make Telegram reliable enough to serve as a daily operator surface instead of a
best-effort bot.

---

## 2. Implemented

### 2.1 Thread-aware Telegram delivery

Modified files:

- `src/ds_agent/channels/bundled/telegram/plugin.py`
- `src/ds_agent/gateway/telegram_runner.py`

Implemented:

- Telegram outbound messages now pass `message_thread_id` when a topic/thread is available
- direct command replies, agent progress updates, streamed result chunks, approval messages, and alert pushes now reuse the latest known thread target for that chat
- reused `DSAgent` sessions now refresh their Telegram callbacks so progress and approvals follow the current mobile thread context instead of the thread that first created the session

This closes the biggest operational gap for Telegram topics without changing the
core session model.

### 2.2 Artifact delivery commands

Modified files:

- `src/ds_agent/api/workspace_service.py`
- `src/ds_agent/gateway/telegram_runner.py`
- `src/ds_agent/channels/bundled/telegram/plugin.py`

Implemented:

- `WorkspaceService.get_project_dir(...)`
- `WorkspaceService.resolve_project_file(...)`
- `/artifacts <project_id>` to list project-local files
- `/artifact <project_id> <index>` to send one project file to Telegram
- `/project <id>` now previews a few files and points the operator at the new artifact commands

The mobile operator can now inspect and pull reports, plots, and generated
files directly from Telegram.

### 2.3 Delivery-path hardening

Modified files:

- `src/ds_agent/channels/bundled/telegram/plugin.py`

Implemented:

- file delivery now uses the configured workspace root instead of relying only on process cwd
- `send_file(...)` now supports:
  - caption
  - thread id
  - reply target
- Telegram text chunking now prefers paragraph boundaries before falling back to hard splits

These changes reduce noisy output and make long summaries more readable on a
phone.

### 2.4 Regression coverage

Modified files:

- `tests/unit/infrastructure/test_telegram_runner.py`
- `tests/integration/test_telegram_plugin.py`

Implemented:

- thread-preserving command response coverage
- thread-aware alert delivery coverage
- `/artifacts` listing coverage
- `/artifact` file-send coverage
- Telegram plugin thread-id forwarding coverage
- Telegram plugin file-send context coverage
- paragraph-aware chunking coverage

---

## 3. UX Rules

- operators should stay in the same Telegram topic whenever the platform supports it
- file delivery should tell the operator what is being sent and why
- long outputs should prefer readable chunk boundaries over raw splitting
- alert routing should preserve context, not spray across unrelated mobile views

---

## 4. Verification

Executed:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py \
  tests/integration/test_telegram_plugin.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_api.py \
  tests/integration/test_runtime_wiring.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/api/workspace_service.py \
  src/ds_agent/gateway/telegram_runner.py \
  src/ds_agent/channels/bundled/telegram/plugin.py \
  tests/unit/infrastructure/test_telegram_runner.py \
  tests/integration/test_telegram_plugin.py
python -m ruff format --check src/ds_agent/api/workspace_service.py \
  src/ds_agent/gateway/telegram_runner.py \
  src/ds_agent/channels/bundled/telegram/plugin.py \
  tests/unit/infrastructure/test_telegram_runner.py \
  tests/integration/test_telegram_plugin.py
```

Result:

- `tests/unit/infrastructure/test_telegram_runner.py`: passed
- `tests/integration/test_telegram_plugin.py`: passed
- `tests/unit/infrastructure/test_api.py`: passed
- `tests/integration/test_runtime_wiring.py`: passed
- `ruff check`: passed
- `ruff format --check`: passed

Manual checks still recommended:

1. Use a Telegram topic-enabled chat and confirm replies stay in the same topic
2. Run `/artifacts <project_id>` and fetch one file with `/artifact <project_id> <index>`
3. Trigger a runtime alert after interacting in a topic and confirm push delivery lands in that same topic

---

## 5. Exit Criteria

- Telegram delivery is robust enough for real operator use
- operators can retrieve project files from a phone
- alert and progress messages preserve thread context where Telegram supports it

---

## 6. Notes

- This phase deliberately kept the Telegram UX command-first.
- Session identity remains chat-scoped; this phase hardens delivery routing rather than introducing thread-isolated agent state.
- Per-chat notification preferences are still deferred.

---

## 7. Remaining Gap

Still deferred after this phase:

- per-chat subscription and mute preferences
- inline keyboard actions for common operator workflows
- artifact auto-push heuristics tied to specific run outcomes

Those are post-`PLAN_12` enhancements rather than blockers for Telegram parity.
