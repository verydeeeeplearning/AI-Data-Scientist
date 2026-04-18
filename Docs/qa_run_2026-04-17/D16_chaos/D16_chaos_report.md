# D16 — Chaos / Recovery Engineer Report

**Agent**: D16 Chaos / Recovery Engineer
**Tier**: 4 (single-process, solo)
**Run date**: 2026-04-17
**Input gate**: Tier 3 Hard Gate PASS (`Docs/qa_run_2026-04-17/TIER3_GATE_DECISION.md`)
**Status**: **PASS** — 8/8 scenarios recovered, 0 silent failures, 0 D16-spawned orphan processes at end-of-run.

---

## Scope

Per `Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md` §7.1 D16:

Eight fault-injection scenarios exercising the runtime recovery contracts:

| # | Scenario | Layer under test |
|:-:|----------|------------------|
| 1 | Mid-session kill (SIGKILL-equivalent) + checkpoint resume | `runtime/startup_recovery.py`, `runtime/checkpoint_store.py` |
| 2 | SQLite write contention (two writers, WAL + `BEGIN IMMEDIATE`) | SQLite adapter path used by persistence stores |
| 3 | Keyring unavailable → in-memory fallback with degraded warning | `infrastructure/secrets/secret_storage.py` |
| 4 | LLM provider network drop → retry/backoff → user-visible error | `providers/` via mocked client |
| 5 | Sandbox disk-full (ENOSPC) → structured JSON error, no crash | `ProcessSandbox` exec path |
| 6 | Clock drift (backward 1h, forward 25h, forward 1d) on Incident overlay | `runtime/authority_overlay.py` |
| 7 | 5 concurrent sessions across surfaces with channel identity isolation | `runtime/channel_identity.py`, `runtime/session_registry.py` |
| 8 | Incident overlay persistence survives app restart | `api/config_manager.py` + `runtime/authority_overlay.py` |

### Out-of-scope (explicit)

- Real keyring disablement on the host (mocked via env / monkeypatch only).
- Real disk-full on host filesystem (fixture `OSError(ENOSPC)` inside sandbox only).
- Real external LLM provider HTTP calls (all simulated).
- Full pytest regression (forbidden by §8.3; scope-isolated scripts only).
- Pre-existing `data/` directory — **NOT TOUCHED**. All fixtures under `.tmp/qa_D16/`.

---

## Methodology

1. **Source import strategy**. Each scenario script prepends `src/` to
   `sys.path` and imports the real runtime modules — we exercise the
   shipped code paths, not mocks of them.
2. **Isolated workspaces**. Each scenario uses its own subdirectory under
   `.tmp/qa_D16/scenario_<N>/`. No shared state between scenarios.
3. **True restart semantics**. Where a scenario's contract is "post-crash
   recovery" or "cross-restart persistence" we use `subprocess.run(...)`
   to launch a fresh Python interpreter — the second process has zero
   in-memory cross-talk with the first.
4. **Abrupt termination**. Scenario 1 uses `os._exit(9)` in the child so
   atexit / finally handlers never run, the hardest possible kill case
   short of real `TerminateProcess`.
5. **Evidence per scenario**. Two artifacts per scenario:
   - `D16_scenario<N>_log.txt` — human-readable timestamped trace.
   - `D16_scenario<N>_recovery.jsonl` — machine-readable record stream
     with a final `{"step": "verdict", "status": "pass|fail"}`.
6. **No-modification principle**. No source file under `src/` was
   modified. No `data/` artifact was touched. `.importlinter`,
   `pyproject.toml`, `uv.lock`, `tests/` untouched.

---

## Results Matrix

| # | Scenario | Verdict | Recovery evidence | Silent fail? |
|:-:|----------|:-------:|-------------------|:------------:|
| 1 | Mid-session kill | PASS | Child `rc=9` (abrupt); fresh `StartupRecovery.recover()` returned `action=resume_recommended` at `step=3` with `recovery.resume` event on `SensorHub`. | No |
| 2 | SQLite write contention | PASS | Two writers, 20 rows each; final DB state has 40 rows with exact `per_writer={'writer-A': 20, 'writer-B': 20}`; zero errors; interleaving transitions ≥1 confirming real concurrency. | No |
| 3 | Keyring unavailable | PASS | `describe_secret_storage()` reports `degraded=True`, `persistent=False`, backend=`in_memory`, plus human-readable warning string. Secret set/get/exists/delete round-trip all succeed. | No |
| 4 | Network drop | PASS | SDK client `max_retries=3` verified; after 3 failed attempts the caller receives a structured `{status:"error", user_message:"Network issue..."}` payload — no silent drop. | No |
| 5 | Disk-full (ENOSPC) | PASS | First sandbox call returns JSON error wrapping `[Errno 28]`; subsequent sandbox call succeeds (`alive:ok`), proving the backend survives. | No |
| 6 | Clock drift | PASS | Five probe points: `-1h`/`start`/`+23h59m`/`+1d`/`+25h`. All produce correct `mode`/`expired`/`remaining_seconds` — no wrap-around, no negative-time silent propagation. | No |
| 7 | 5 concurrent sessions | PASS | 5 unique `session_id`s (1 Telegram DM + 2 forum topics + 1 WS + 1 CLI); `RuntimeSessionRegistry.active_count=5`; per-session checkpoint stores each contain exactly their own session's messages (no cross-contamination); persisted `runtime-sessions.json` contains all 5. | No |
| 8 | Incident overlay restart persistence | PASS | Persist → fresh-process reload at +5min/+12h/+25h returns mode=`incident`/`incident`/`None`, remaining=`86100s`/`43200s`/`-3600s`, expired=`False`/`False`/`True`. Remaining time anchored to persisted `started_at`, never silently refreshed. | No |

**Aggregate**: 8/8 PASS, 0 silent failures.

---

## Failures

None. All eight scenarios produced either (a) fully correct recovery
behaviour, or (b) a structured user-visible error where recovery was
impossible by design (e.g. scenario 4 after 3 exhausted retries,
scenario 5 ENOSPC propagated back as JSON).

---

## Evidence

All evidence lives under `Docs/qa_run_2026-04-17/D16_chaos/`:

```
D16_precheck.txt                       # pre-existing process + lock snapshot
START.json                             # agent metadata
D16_scenario<N>_log.txt                # timestamped trace per scenario (N=1..8)
D16_scenario<N>_recovery.jsonl         # decision records per scenario
D16_chaos_report.md                    # this document
D16_cleanup_report.txt                 # final orphan + filesystem proof
FINAL.json                             # summary metrics
```

Scenario scripts (reproducible, not part of the repo's source tree):
```
.tmp/qa_D16/scenario_<N>.py            # driver
.tmp/qa_D16/scenario_<N>/              # per-scenario workspace
.tmp/qa_D16/_helpers.py                # shared I/O utilities
.tmp/qa_D16/orphan_check.py            # end-of-run orphan detector
```

### How to reproduce a single scenario

```
cd C:\Users\aquap\Desktop\AI_Data_Scientist_Demo
python .tmp/qa_D16/scenario_<N>.py
# Evidence files are re-emitted under Docs/qa_run_2026-04-17/D16_chaos/
```

The scripts are idempotent: each clears its previous log + jsonl before
re-executing, and `reset_workspace()` wipes any stale `.tmp/qa_D16/scenario_<N>/`
contents.

---

## Recommendations

1. **D17 safe to proceed.** No runtime regression found. D17 can use the
   same codebase snapshot (`code_sha256_head=103b6fd5f4e9a29d` per
   `START.json`) as baseline.
2. **Environment hygiene for D17**. Before D17 starts, confirm the
   pre-existing `ds-agent-api.exe pid=193632` (C15 smoke artifact) is
   either intentionally running or terminated — it is outside D16 scope
   but may influence D17 "no-change delta" checks if D17 tries to spawn
   a backend on the same port 18850.
3. **Scenario 4 nuance**. The scenario documented the SDK-level
   `max_retries=3` contract and the user-surface error shape; it did
   NOT exercise progressive backoff timing. If a follow-up run wants
   timing evidence, instrument `anthropic._base_client` / `openai` retry
   hooks and record intervals.
4. **Scenario 7 checkpoint semantics**. `JsonCheckpointStore.save()`
   replaces by `session_id` (one checkpoint per session is always the
   latest step). This is correct behaviour and matches the existing
   `StartupRecovery` contract used in scenario 1, but is worth noting
   in operator-facing docs so an operator is not surprised that "step 1
   evidence" is gone after "step 2" fires.
5. **Scenario 6 / 8 observation — overlay clear is decoupled**. The
   runtime `resolve_authority_overlay` correctly reports `expired=True`
   past the 24h window, but the actual persisted clearing of
   `gateway.authority_overlay` lives in the WS handler
   (`ws_handler.py:_get_effective_authority_overlay` lines 4066–4089).
   Scenario 8 shows the resolve path is restart-safe; the *clear* path
   is tested in integration tests already. No new issue found; note
   for completeness.
6. **Pre-existing issue tracker**. No new RC- or PRE- entries raised
   by D16. The tracker in `HANDOFF_NEXT_AGENT.md §7` is unchanged.

---

## Cleanup Status

- D16-spawned orphan processes at end-of-run: **0**.
- Pre-existing `ds-agent-api.exe pid=193632` (C15 artifact) still
  present — **not** created by D16, must not be killed by D16.
- No lock files (`*.lock`, `*-journal`, `*-wal`, `*-shm`) remain under
  `.tmp/qa_D16/`.
- `data/` directory **untouched** (mtime unchanged, no new files, no
  deletions — verified pre- and post-run).
- All 32 artifacts under `.tmp/qa_D16/` are test fixtures + scripts,
  intentionally retained for D17 evidence reproducibility.

Full filesystem + process inventory is in `D16_cleanup_report.txt`.
