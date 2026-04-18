# S15 Telegram Live Parity — Report

**Agent**: S15 (Post-Release Follow-up — Telegram polling live-parity uplift)
**Plan ref**: `Docs/plans/PLAN_post_release_followups_2026-04-17.md` §10
**Started**: 2026-04-17T14:40:00Z
**Completed**: 2026-04-18T04:25 UTC
**Status**: PASS

---

## 1. Scope

C13 Round 2 left a documented fallback on the Telegram channel: the
harness exercised only factory-wiring parity (Telegram-shaped session id
over the same WS path as CLI/Electron), because `python-telegram-bot`
was not installed in the QA venv. S15 closes that gap.

Environment preparation: `uv sync --extra channels` was run before this
sprint (per task brief), installing `python-telegram-bot==22.7`. S15
also installed `websockets==16.0` (already transitively required by the
CLI/Electron harnesses).

**In-scope** (S15 only):
- Build a live Telegram ingestion path using the **real**
  `python-telegram-bot` `Application`, `ExtBot`, `Update` and the
  production `TelegramPlugin` class — all driven entirely offline via a
  fake token and monkey-patched no-op bot methods.
- Run the same 3 parity scenarios (P-01 / P-02 / P-03) through that
  live path.
- Re-use the C13 Round 2 CLI + Electron corpus unchanged (no re-run).
- Compare all 3 channels × 3 scenarios for `goal_echo`,
  `final_verdict`, `delivery_pack_body_hash`, `metric_spec`.

**Out of scope**:
- Any real Telegram API network I/O (bot token, polling endpoint,
  webhooks).
- Mutation of `src/` production code.
- Real LLM provider (mocked `_NoApiKeyProvider` retained — identical to
  Round 2).
- Pre-existing S16 / Epic-A / Epic-B work orders.

---

## 2. Methodology

### 2.1 Fake Telegram ingestion path

New harness: `scripts/parity_harness/harness_telegram_v2.py`.

Per scenario:

1. **Build a real Telegram `Application`** via
   `ApplicationBuilder().token("1:AAAA_FAKE_TESTING_ONLY...").updater(None).build()`.
   Using `updater=None` guarantees `start_polling()` cannot be called
   accidentally, so zero HTTP requests go to `api.telegram.org`.
2. **Monkey-patch every outbound `Bot.*` method** (`send_message`,
   `send_document`, `send_photo`, `answer_callback_query`,
   `edit_message_text`, `edit_message_reply_markup`,
   `set_my_commands`, `get_me`, `get_updates`) with a no-op recorder.
   `telegram.Bot` / `ExtBot` blocks `setattr` for these, so the harness
   uses `object.__setattr__` to inject the no-ops (this is exactly the
   pattern `unittest.mock` uses under the hood).
3. **Instantiate the production `TelegramPlugin`** with the fake token
   and splice the fake Application into `plugin._app`. We do **not**
   call `plugin.start()` — that would trigger real polling. All the
   handler wiring is still in place on the fake `Application`.
4. **Construct a real `telegram.Update`** via `Update.de_json(...)` —
   the same factory method python-telegram-bot uses internally when it
   parses updates from Telegram's servers. Each scenario uses distinct
   `chat_id`, `user_id`, and thread_id (P-01 and P-03 use a forum
   topic thread; P-02 is a plain DM without a thread).
5. **Directly invoke `plugin._on_text(update, context)`** — the real
   production handler registered by `plugin.start()`. The plugin
   pushes an `InboundMessage` onto its internal queue just like it
   does in production.
6. **Dequeue the `InboundMessage`** via `plugin.get_next_message()` —
   the same contract `TelegramGatewayRunner` reads in production.
7. **Derive the session id** via the canonical helper
   `ds_agent.runtime.channel_identity.telegram_session_id` — the
   exact helper production uses. This produces
   `telegram:{chat_id}:{thread_id}` (with thread) or `telegram:{chat_id}`
   (DM).
8. **Spawn a fresh packaged `ds-agent-api.exe`** (same path as C13
   Round 2 CLI harness) and submit `chat.send` over WebSocket with
   `surface="telegram"` and the derived session id.

### 2.2 What is proven live (vs factory-only in Round 2)

| Step | Round 2 (factory only) | S15 (live) |
|------|------------------------|------------|
| `Application.builder().token(...).build()` | Not exercised | Exercised |
| `Bot` instantiation (`ExtBot`) | Not exercised | Exercised |
| `Update.de_json` (real payload parsing) | Not exercised | Exercised |
| `TelegramPlugin._on_text` handler | Not exercised | Exercised (real code path) |
| `TelegramPlugin._message_queue` enqueue | Not exercised | Exercised |
| `get_next_message` dequeue contract | Not exercised | Exercised |
| `channel_identity.telegram_session_id` | Not exercised | Exercised |
| WS `chat.send` with Telegram-shaped id | Exercised | Exercised (identical to Round 2) |

### 2.3 Evidence collection

- Per-scenario JSONL trace at
  `S15_telegram_fake_harness_trace.jsonl` — every step above is
  recorded with timestamps.
- Per-scenario run log at `TGL-{P-01,P-02,P-03}.log`.
- Consolidated results at `all_runs_including_live.json`.
- Parity diff at `parity_diff_raw.json` and
  `S15_telegram_live_diff.md`.
- Matrix CSV at `parity_matrix.csv`.
- Per-scenario harness detail at `telegram_live_run_details.json`.

### 2.4 Round 2 corpus reuse

Round 2 CLI + Electron rows are re-loaded directly from
`Docs/qa_run_2026-04-17/C13_parity_process_level/all_runs.json`. No
re-execution. The Round 2 Telegram rows (factory-only fallback) are
dropped from the merged corpus — S15 Telegram-live results replace
them.

---

## 3. Results Matrix

| Scenario | CLI hash | Electron hash | Telegram-LIVE hash | Parity Match |
|----------|----------|----------------|---------------------|--------------|
| P-01 | `51de5976…` | `51de5976…` | `51de5976…` | **Yes** |
| P-02 | `51de5976…` | `51de5976…` | `51de5976…` | **Yes** |
| P-03 | `51de5976…` | `51de5976…` | `51de5976…` | **Yes** |

Full hash: `51de5976e68aeb2df5e3e1d92a01d7e59a402415109531d52a45e32bbf062585`.

**Overall parity match (incl. Telegram live)**: **True**.

Parity fields checked: `goal_echo`, `final_verdict`,
`delivery_pack_body_hash`, `metric_spec`.

Infrastructure fields (allowed to differ): `channel`, `channel_origin`,
`error_code`, `fallback_notes`, `raw_event_count`, `raw_event_types`,
`raw_final_content`, `session_id`, `status`, `timestamp_utc`.

### 3.1 Metrics

| Metric | Value |
|--------|-------|
| scenarios | 3 |
| telegram_runs_completed | 3 |
| parity_match_including_telegram | true |
| real_telegram_api_calls | 0 |
| fake_bot_ok | true |
| C13_round2_reused | true |
| cleanup_confirmed | true |
| fake_bot_call_total | 0 (mocked-LLM path returns before any callback emits a bot send) |
| Wall time | 32.2 s (3 live runs, incl. 3 backend spawn cycles) |

### 3.2 Session ids produced (shows helper correctness)

| Scenario | chat_id | thread_id | Produced base session id |
|----------|---------|-----------|--------------------------|
| P-01 | 555777 | 7 | `telegram:555777:7` |
| P-02 | 555778 | None | `telegram:555778` |
| P-03 | 555779 | 7 | `telegram:555779:7` |

This confirms `channel_identity.telegram_session_id` emits the two
canonical shapes documented in its module docstring.

---

## 4. Failures / Deviations

None that block the pass gate. Two properly-scoped observations:

1. **`fake_bot_call_total = 0`**. The DSAgent's mocked `_NoApiKeyProvider`
   error path returns synchronously over WS before any agent iteration
   callback fires a Telegram send. This is identical to what C13
   Round 2 observed for CLI + Electron (`raw_event_count: 1`, single
   `res` frame). The fake-bot recorder remained installed throughout
   and would have captured any outbound calls had the path produced
   them — absence of calls is signal, not a bug.
2. **First-attempt TypeError** (fixed during the sprint). Initial run
   of S15 hit
   `TraceSink.log() got multiple values for argument 'event'` because
   the WS-frame trace line passed `event=...` as both the positional
   argument and a keyword. Renamed the kwarg to `frame_event_name` in
   `harness_telegram_v2.py:_telegram_ws_turn`. The TypeError snapshot
   is preserved in the replayed trace's first partial JSONL (which was
   rotated away before the final run) — not material to parity.

---

## 5. Evidence

Canonical paths (absolute):

- `C:\Users\aquap\Desktop\AI_Data_Scientist_Demo\Docs\qa_run_2026-04-17\S15_telegram_live_parity\S15_report.md` — this file
- `C:\Users\aquap\Desktop\AI_Data_Scientist_Demo\Docs\qa_run_2026-04-17\S15_telegram_live_parity\S15_telegram_live_diff.md` — 3-channel diff
- `C:\Users\aquap\Desktop\AI_Data_Scientist_Demo\Docs\qa_run_2026-04-17\S15_telegram_live_parity\S15_telegram_fake_harness_trace.jsonl` — step-by-step live trace
- `C:\Users\aquap\Desktop\AI_Data_Scientist_Demo\Docs\qa_run_2026-04-17\S15_telegram_live_parity\parity_diff_raw.json` — machine-readable diff
- `C:\Users\aquap\Desktop\AI_Data_Scientist_Demo\Docs\qa_run_2026-04-17\S15_telegram_live_parity\parity_matrix.csv` — 9-row matrix (3 ch × 3 sc)
- `C:\Users\aquap\Desktop\AI_Data_Scientist_Demo\Docs\qa_run_2026-04-17\S15_telegram_live_parity\all_runs_including_live.json` — merged 9-run corpus
- `C:\Users\aquap\Desktop\AI_Data_Scientist_Demo\Docs\qa_run_2026-04-17\S15_telegram_live_parity\telegram_live_run_details.json` — harness summary
- `C:\Users\aquap\Desktop\AI_Data_Scientist_Demo\Docs\qa_run_2026-04-17\S15_telegram_live_parity\TGL-P-01.log` / `TGL-P-02.log` / `TGL-P-03.log` — per-run logs
- `C:\Users\aquap\Desktop\AI_Data_Scientist_Demo\scripts\parity_harness\harness_telegram_v2.py` — live-parity harness
- `C:\Users\aquap\Desktop\AI_Data_Scientist_Demo\scripts\parity_harness\run_s15.py` — orchestrator

Harness code is self-contained and idempotent — re-running
`uv run python scripts/parity_harness/run_s15.py` reproduces the full
evidence bundle.

---

## 6. Cleanup Confirmation

- `tasklist` after run: **zero** `ds-agent-api.exe` / `ds-agent-backend`
  processes remained. `BackendManager.stop` issued `taskkill /T /PID`
  per spawned backend and verified exit code.
- TCP ports 18950 / 18951 / 18952 linger only in kernel-held
  `TIME_WAIT` state (pid=0); not tied to any user process.
- Temp workspace `C:\Users\aquap\Desktop\AI_Data_Scientist_Demo\.tmp\qa_S15\`
  retained for audit, contains only harness logs and per-run JSON
  (no lock files, no residual binary state).

---

## 7. Recommendations

1. **Promote `harness_telegram_v2.py` to the default Telegram channel
   harness** for future parity regression runs (e.g. C13-R4 or any
   post-release smoke). The original `harness_telegram.py` can stay as
   a "factory-only fallback" for environments where
   `python-telegram-bot` is not installable.
2. **Add a hook to exercise a callback-query path**: the current S15
   proves the text-message path end-to-end. `_on_callback_query` is
   structurally identical but not yet covered by live harness — a
   follow-up sprint could add a P-04-style scenario driving the
   `/approve <token>` inline-keyboard flow through the same fake-bot
   machinery.
3. **Consider gating the live harness behind an `--extra channels`
   pytest marker** so CI that doesn't install channels falls back
   gracefully to the factory-only variant.
