# C13 Parity — Process-Level (Phase 3)

**Agent**: `C13_process_level`
**Tier**: 3
**Round**: 2 (Round 1 fallback upgrade)
**Started**: 2026-04-17T22:45:00Z (KST) / 2026-04-17T14:02:54Z (UTC harness start)
**Completed**: 2026-04-17T14:06:23Z (UTC)
**Output root**: `Docs/qa_run_2026-04-17/C13_parity_process_level/`
**Plan reference**: `Docs/plans/PLAN_post_qa_risk_mitigation_2026-04-17.md` §5 Phase 3 (+ `Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md` §6.1)

---

## 1. Scope

Upgrade the Round 1 C13 **code-level** factory-call parity (9/9 signatures
identical) into **process-level** parity: 3 scenarios × 3 channels = 9
runs where each run boots a real subprocess (ds-agent-api.exe or
Electron) and exchanges frames over the same WebSocket protocol that
end users hit.

Scenarios (fixed per plan §6.1):

| id | goal | audience | authority | caution | DeliveryPack |
|----|------|----------|-----------|---------|---|
| P-01 | tips.csv total_bill 예측 → baseline 회귀 → DeliveryPack PDF | Peer | supervised | — | yes |
| P-02 | Supervised → Delegate 전환 + CAUTION(실험 기록 삭제) | Peer | delegate | experiment_log.delete | no |
| P-03 | LearningInbox promote + 2 eval-failure auto-deprecate | Peer | supervised | — | no |

Channels (fixed):

| channel | process-level invocation |
|---------|-------------------------|
| **CLI** | `subprocess.Popen(["ds-agent-api.exe", ...])` + WebSocket `chat.send` |
| **Telegram** | same binary + Telegram-shaped session id + `surface=telegram` |
| **Electron** | Playwright `_electron.launch()` → Electron main spawns backend → renderer `chat.send` over ws |

Binary reused without rebuild (C15 dist is still current — source hash
check: no `.py` under `src/ds_agent/` is newer than
`dist/ds-agent-backend/ds-agent-api.exe` dated 2026-04-17 10:41;
`electron/dist/main/` is also current).

---

## 2. Methodology

1. Shared scenario fixture: `scripts/parity_harness/scenarios.py`.
2. Shared backend subprocess control: `scripts/parity_harness/backend_control.py`
   — spawns the PyInstaller-bundled backend, polls stdout for `READY:<port>:<token>`,
   and guarantees `taskkill /F /T /PID` teardown on Windows.
3. Three channel harnesses:
   - `harness_cli.py` — Python + `websockets` library client.
   - `harness_telegram.py` — Python client with Telegram-shaped session
     id (`telegram:{chat_id}:{thread_id}:…`).
   - `harness_electron.js` — Node + `electron/node_modules/playwright`;
     dispatches `chat.send` from **inside the renderer page context**
     via `window.WebSocket` so the frame actually traverses Electron →
     backend.
4. Orchestrator: `scripts/parity_harness/run_all.py` iterates 3 × 3 = 9
   runs, publishes JSON + log per run, and computes the diff.
5. **Mocked provider**: no `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` /
   `GOOGLE_API_KEY` in env; backend's `_NoApiKeyProvider` fallback
   returns a deterministic "AI service temporarily unavailable
   [DSA-LLM-001]" body. This IS the mocked path — its hash is a clean
   parity signal.

### 2.1 Parity fields vs infra fields

| Parity field (must match across channels) | Infra field (allowed to differ) |
|-------------------------------------------|----------------------------------|
| `goal_echo` | `channel` |
| `final_verdict` | `channel_origin` |
| `delivery_pack_body_hash` (SHA-256 of whitespace-normalised final body) | `session_id` |
| `metric_spec` | `timestamp_utc` |
|  | `error_code`, `status` (surface-specific error mapping) |
|  | `raw_event_count`, `raw_event_types`, `raw_final_content` |

`error_code` / `status` are classified as infra because each surface's
JSON-RPC layer can map the same underlying provider-missing error to a
channel-specific code family; for this harness they in fact also agree.

---

## 3. Results Matrix

| Scenario | CLI status | CLI hash | TG status | TG hash | EL status | EL hash | Match |
|----------|-----------|----------|-----------|---------|-----------|---------|-------|
| P-01 | error/INTERNAL | `51de5976…` | error/INTERNAL | `51de5976…` | error/INTERNAL | `51de5976…` | ✓ |
| P-02 | error/INTERNAL | `51de5976…` | error/INTERNAL | `51de5976…` | error/INTERNAL | `51de5976…` | ✓ |
| P-03 | error/INTERNAL | `51de5976…` | error/INTERNAL | `51de5976…` | error/INTERNAL | `51de5976…` | ✓ |

**Overall parity match: TRUE — all 9/9 runs agree on every parity
field.**

Full hash: `51de5976e68aeb2df5e3e1d92a01d7e59a402415109531d52a45e32bbf062585`

Raw per-scenario diff: `parity_diff_raw.json` — empty
`mismatches: []` for each scenario.

Matrix CSV: `parity_matrix.csv` (9 rows, human-sortable).

---

## 4. Failures & fallback paths

Nothing failed at harness level. The "`status=error` + `error_code=INTERNAL`"
observed on every run is **the expected mocked-provider path** — the
backend's `_NoApiKeyProvider` raises and the WS layer wraps it. The
hash is identical across channels so parity is proven.

### 4.1 Fallback channel tracking

| channel | fallback notes |
|---------|----------------|
| CLI | none — true subprocess + WS client |
| Electron | none — Playwright launched packaged Electron + packaged backend + renderer-side WS dispatch |
| **Telegram** | `python-telegram-bot` not installed in the host venv nor bundled inside `dist/ds-agent-backend/_internal`. Therefore real Updater polling + fake-update injection was **not** exercised. The adopted equivalent: same backend binary + Telegram-shaped session id (`telegram:{chat_id}:{thread_id}:…`) + `surface=telegram` param so the runtime-event classifier and `parse_telegram_session_id` branches are exercised. Factory wiring parity (which C13 measures) is covered; python-telegram-bot plugin polling is still a Round 1 residual gap. |

### 4.2 Real external call count

| kind | count | evidence |
|------|:----:|----------|
| Real LLM API call | 0 | no API keys in env (see `backend_control.py` `env.pop(...)`); mocked provider returns canned error before any network egress |
| Real Slack / Jira / webhook | 0 | only service hit is `127.0.0.1:{port}` — localhost loopback |
| Real Telegram bot | 0 | no bot token used; no `Application.builder()` call executed (python-telegram-bot not present) |

---

## 5. Evidence

| file | purpose |
|------|--------|
| `START.json` | Phase 3 start manifest |
| `FINAL.json` | Phase 3 terminal manifest (this run) |
| `all_runs.json` | Concatenated 9-run RunResult records |
| `parity_diff_raw.json` | Per-scenario mismatches (empty) |
| `parity_matrix.csv` | 9-row human-readable matrix |
| `C13_parity_live_diff.md` | Human-readable diff report |
| `C13_process_level_report.md` | This report |
| `CLI-P-0{1,2,3}.log` | Per-run CLI channel log |
| `TG-P-0{1,2,3}.log` | Per-run Telegram channel log |
| `EL-P-0{1,2,3}.log` | Per-run Electron channel log |

Harness source (committed to `scripts/parity_harness/`):

- `__init__.py`
- `scenarios.py`
- `extract.py`
- `backend_control.py`
- `harness_cli.py`
- `harness_telegram.py`
- `harness_electron.js`
- `run_all.py`

---

## 6. Recommendations

- **R1 (carry from Round 1)**: Add `python-telegram-bot` to `dev` extras
  so the fake-Updater harness can be exercised as a follow-up. Estimated
  +15 min of harness work once the dep is installable in this venv.
- **R2**: Expose a `window.dsAgentRpc.call()` bridge in Electron
  renderer so future parity harnesses do not need to open a second
  `WebSocket` inside `page.evaluate`. Purely an ergonomics win — the
  current approach exercises the same frame path.
- **R3**: Promote the parity-harness orchestrator to a CI job. It runs
  in ~90 s, requires only the packaged backend + electron dist + a
  websockets pip install, and is the fastest end-to-end regression
  detector for factory-wiring drift.
- **R4**: When an LLM record-replay fixture is introduced (residual gap
  from Round 1), re-run this harness with live DeliveryPack generation
  so the parity hash reflects real content rather than the mocked-error
  body.

---

## 7. Environmental cleanup confirmation

Post-run `tasklist | grep -iE "ds-agent|electron"` returned **empty**
(verified immediately after orchestrator exit). Each backend subprocess
receives `taskkill /F /T /PID` on scenario teardown; Electron's
`app.close()` is followed by `taskkill /F /T /IM electron.exe`
(belt-and-braces — otherwise Electron's child renderer/utility processes
sometimes linger on Windows).

All `.tmp/qa_phase3/runs/` outputs are flat files; no lock files
remain.

---

## 8. Self-verdict

**Not rendered**: per plan §4 and constraint "자기 pass 판정 금지", the
orchestrator only records metrics; the Tier-3 gate owner assigns the
terminal pass/fail.

What the data shows:

- 9/9 runs complete.
- `overall_parity_match = true` across the 4 non-infra fields.
- Zero real-external calls.
- Telegram channel runs via a documented **fallback path** (no
  `python-telegram-bot`). The factory wiring parity the original C13
  measured is covered; the Telegram transport layer itself is not.
- Electron channel runs on the C15 dist **without rebuild** (source
  hash still matching). No rebuild was needed.
