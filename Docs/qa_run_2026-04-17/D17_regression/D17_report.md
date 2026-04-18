# D17 — Evaluation Regression Board Operator

**Tier**: 4
**Date**: 2026-04-17
**Status**: **pass** (self-declaration withheld — final authority is D18)
**No-Go trigger fired**: **false** (Path 1 delta precisely zero)

---

## Scope

Exercise the evaluation regression board, baseline freeze, alert dispatch, and
scheduled daemon paths against the C14 gold-task corpus with zero source
modifications. Five independent verification paths per PRE_RELEASE plan §7.2:

1. **No-change delta** — rerun with identical inputs, demand 10-dim delta = 0.
2. **Synthetic regression** — inject +1% via monkeypatch only; single-dim reflection.
3. **Alert dispatch** — synthetic low-score → mock Slack+Teams webhook reception.
4. **Daemon schedule** — `RegressionAlertScheduler` cron-like standing order.
5. **Baseline freeze / rollback** — byte-level restore after candidate overwrite.

Out-of-scope files and paths were not touched. No `data/` mutation.
No real LLM calls (scorers built with `judge=None` deterministic fallback).
No real Slack/Teams webhooks (mock notifiers only).

---

## Methodology

- **Baseline pin**: The C14 candidate baseline
  `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_prior_baseline.json` (frozen at
  1776389343.1079757, `baseline_candidate_commit_sha=c14-baseline-sha`) is
  consumed as the pinned baseline for Paths 1 and 2.
- **Corpus**: 6 bundled gold tasks (finance, healthcare, marketing, ops,
  retail, saas) loaded via `GoldTaskLoader` from
  `src/ds_agent/evaluation/infrastructure/gold_tasks/tasks`.
- **Run builder**: Byte-identical to C14's `.tmp/qa_C14/run_gold_tasks.py`
  `_build_run(task)` — same metric, value, approvals, tool calls, summary,
  decision-ready timestamps — so deterministic heuristic scorers return the
  same `EvalScore.value` set as C14.
- **Workspace isolation**: All datasets/baselines in `.tmp/qa_D17/`. Report
  evidence in `Docs/qa_run_2026-04-17/D17_regression/`.
- **Path 2 injection mechanics**: `_PerturbScorer` wraps a real scorer
  instance and adds `delta` to the returned `EvalScore.value` (clamped to
  `[0,1]` exactly as `base.clamp_score`). No source edited.
- **Path 3 forced probe**: Reuses C14's pattern — append one synthetic failing
  `EvalDatasetRecord` (weighted_score=0.10) to force at least one
  `single_task_hard_fail` alert and multiple `dimension_regression` alerts.
- **Path 4 scheduler**: In-memory `_InMemoryStandingOrderStore` +
  `_FakeCronRunner` (next run = after+60s) + `SchedulerService` +
  `RegressionAlertScheduler.register()` + `run_due(now=t+120s)` to force the
  cron trigger. Dispatch is stubbed (`fake_dispatch`) to verify scheduler
  invocation without crossing use-case boundaries.
- **Path 5 rollback**: `FreezeRegressionBaseline` writes v1 → snapshot raw
  bytes → re-freeze with a different commit_sha (v2) → restore v1 bytes →
  diff by sha256 + raw-bytes + reload-via-store commit match.
- **Determinism spot-check**: Scored the corpus twice in-process and compared
  every dim value across the two runs. `identical=true`, `max_diff=0.0`.

---

## Results matrix

| Path | Check | Result |
|---|---|---|
| 1 | `max_abs_dimension_delta` vs C14 baseline | **0.0** |
| 1 | `delta_precisely_zero` (tol 1e-9) | **true** |
| 1 | cross-run byte parity (extra determinism probe) | identical, max_diff=0.0 |
| 2A | headroom case (metric_selection_accuracy, base=0.9, +0.01) | observed Δ=+0.01 exact, others quiet |
| 2B | ceiling case (tool_trajectory, base=1.0, +0.01) | observed Δ=0 (clamped), others quiet |
| 2 | `injected_reflects_single_dim` | **true** |
| 3 | synthetic probe alert count | 12 (1× pass_rate_drop, 1× single_task_hard_fail, 10× dimension_regression) |
| 3 | mock Slack + Teams payloads captured | true |
| 3 | dispatch fingerprint length (sha256) | 64 |
| 3 | `alert_dispatch_ok` | **true** |
| 4 | Standing order registered `evaluation_regression_alerts` | true |
| 4 | Cron expression preserved `*/30 * * * *` | true |
| 4 | `run_due(now=t+120s)` fires | true |
| 4 | `dispatch` called once with expected kwargs | true |
| 4 | Scheduler history row recorded | 1 |
| 4 | `daemon_ok` | **true** |
| 5 | Freeze v1 sha256 ↔ candidate v2 sha256 differ | true (mutated) |
| 5 | Rollback restores original sha256 | true |
| 5 | Raw bytes equal to snapshot | true |
| 5 | Reload-via-store commit_sha matches frozen | true |
| 5 | `rollback_byte_level_restored` | **true** |

---

## Path 1 detail — No-change delta (the §10.3 No-Go guard)

Baseline pin (from C14):

```
scoping_accuracy             1.0
metric_selection_accuracy    0.9
temporal_leakage_detection   1.0
tool_trajectory              1.0
artifact_faithfulness        1.0
exec_summary_accuracy        1.0
approval_judgment            1.0
session_completeness         1.0
operator_satisfaction        1.0
time_to_decision             1.0
```

D17 rerun result (same inputs, same scorer registry, `judge=None`):

```
scoping_accuracy             1.0   Δ=0.0
metric_selection_accuracy    0.9   Δ=0.0
temporal_leakage_detection   1.0   Δ=0.0
tool_trajectory              1.0   Δ=0.0
artifact_faithfulness        1.0   Δ=0.0
exec_summary_accuracy        1.0   Δ=0.0
approval_judgment            1.0   Δ=0.0
session_completeness         1.0   Δ=0.0
operator_satisfaction        1.0   Δ=0.0
time_to_decision             1.0   Δ=0.0
```

`max_abs_dimension_delta = 0.0`, `tolerance = 1e-9`. **delta_precisely_zero = true.**
No-Go trigger per §10.3 **NOT fired**.

Cross-run probe (scored the corpus twice in the same process) confirmed
`identical=true` and `max_diff=0.0` across every (task, dim) pair — the
heuristic-fallback scorers are byte-deterministic given byte-identical input.

---

## Path 2 detail — Synthetic regression

Two sub-cases to prove the injection plumbing is faithful AND observable:

**Case A — headroom (`metric_selection_accuracy`, base=0.9, +0.01)**
- Expected observed Δ = `min(1.0, 0.9+0.01) - 0.9 = 0.01`.
- Actual observed Δ = `0.010000000000000009` (float epsilon OK under 1e-9).
- All other 9 dims: Δ=0.0.

**Case B — ceiling (`tool_trajectory`, base=1.0, +0.01)**
- Expected observed Δ = `min(1.0, 1.0+0.01) - 1.0 = 0.0` (clamp).
- Actual observed Δ = 0.0.
- All other 9 dims: Δ=0.0.

Conclusion: the injected signal is reflected exactly where it has headroom and
correctly clamped at the ceiling — and, critically, never bleeds into other
dimensions. Zero source bytes changed; perturbation is a pure scorer-instance
wrapper installed after `build_default_scorers()`.

---

## Path 3 detail — Alert dispatch (mocked)

- Start: score all 6 gold tasks into `d17_alert_dataset.jsonl` (clean pass).
- Forced probe: append one `EvalDatasetRecord` with weighted_score=0.10 and
  every dim at 0.10 for `finance.fraud_triage.v1`.
- Build the board and dispatch through `(MockNotifier('slack'),
  MockNotifier('teams'))`.
- Result: 12 alerts — `pass_rate_drop` (high), `single_task_hard_fail` (high),
  10 × `dimension_regression` (medium) — captured by **both** mock notifiers.
  The DispatchRegressionAlerts use case produced a full sha256 fingerprint.

Persisted payloads: `D17_alert_payload_samples/slack_captured.json`,
`D17_alert_payload_samples/teams_captured.json`,
`D17_alert_payload_samples/dispatch_report.json`.

---

## Path 4 detail — Daemon schedule

- `ds-agent-daemon` console entrypoint confirmed present in
  `.venv/Lib/site-packages/ds_agent-0.1.0.dist-info/entry_points.txt`
  (target `ds_agent.gateway.daemon:main`).
- `RegressionAlertScheduler` in
  `src/ds_agent/runtime/regression_alert_scheduler.py` wired into daemon.py
  imports.
- Registered standing order `evaluation_regression_alerts` with cron
  `*/30 * * * *`, session id `evaluation:d17`, channels `('slack','teams')`,
  mode `offline`.
- `run_due(now=t+120s)` returned a non-None report.
- Stub `fake_dispatch` invoked once with the expected kwargs
  (`channels=('slack','teams')`, `mode='offline'`, `domain=None`,
  `recent_window=3`, `baseline_window_days=14`, `skip_if_unchanged=True`,
  `dispatch_source='schedule'`).
- 1 scheduler history row recorded (`status=completed`, summary
  `Regression alert sweep found no active board alerts.`).

Full trace: `D17_daemon_trace.txt`.

---

## Path 5 detail — Baseline freeze / rollback byte-level

```
sha256(before freeze overwrite):   ef5054fd2bf8816af8ec86ac9452fe7d996972749b6cf6b047224dc9d58aceee
sha256(after candidate overwrite): d4a5abf524ba93926e5f77173260aa4034ec68964c499317ce5e2a71d028a38e
sha256(after rollback restore):    ef5054fd2bf8816af8ec86ac9452fe7d996972749b6cf6b047224dc9d58aceee
mutated by candidate:              True
byte-level restored == original:   True
raw bytes equal:                   True
reload via store commit matches:   True
```

Full trace: `D17_freeze_rollback_diff.txt`.

---

## Failures

None. All five paths pass.

No new failures outside the D17 scope. Pre-existing Windows environment
constraints (no `fastapi`, `numpy` in this venv) prevented exercising the
`ds-agent eval board ...` **CLI entry point** as an additional surface; the
direct use-case calls (which this harness exercises) are the semantically
load-bearing path and were verified. C14 already captured the CLI text output
evidence (`C14_cli_board_show.txt`, `C14_cli_freeze_baseline.txt`,
`C14_cli_send_alerts.txt`); D17 extends that coverage at the
application-layer level for the identical baseline.

---

## Evidence

Files produced by this agent:

- `Docs/qa_run_2026-04-17/D17_regression/START.json`
- `Docs/qa_run_2026-04-17/D17_regression/D17_no_change_delta.json`
- `Docs/qa_run_2026-04-17/D17_regression/D17_synthetic_regression.json`
- `Docs/qa_run_2026-04-17/D17_regression/D17_regression_diff.json`
- `Docs/qa_run_2026-04-17/D17_regression/D17_daemon_trace.txt`
- `Docs/qa_run_2026-04-17/D17_regression/D17_freeze_rollback_diff.txt`
- `Docs/qa_run_2026-04-17/D17_regression/D17_alert_payload_samples/slack_captured.json`
- `Docs/qa_run_2026-04-17/D17_regression/D17_alert_payload_samples/teams_captured.json`
- `Docs/qa_run_2026-04-17/D17_regression/D17_alert_payload_samples/dispatch_report.json`
- `Docs/qa_run_2026-04-17/D17_regression/D17_report.md` (this file)
- `Docs/qa_run_2026-04-17/D17_regression/FINAL.json`
- Driver: `.tmp/qa_D17/run_d17.py`
- Workspace datasets/baselines: `.tmp/qa_D17/d17_*.jsonl`, `.tmp/qa_D17/d17_*.json`, `.tmp/qa_D17/d17_freeze_baseline.snapshot.bytes`
- Baseline reference consumed: `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_prior_baseline.json`

---

## Recommendations

1. **Release Gate decision (D18)**: Path 1 `delta_precisely_zero=true` means
   the §10.3 No-Go trigger does not fire. The regression board is safe to
   carry into the Tier 4 sign-off bundle.
2. **Regression baseline freeze**: Treat
   `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_prior_baseline.json` as the
   official pre-GA baseline. D17 independently produced byte-identical dim
   means against it.
3. **CLI environmental gap (non-blocking)**: The packaged `ds-agent` console
   script requires `fastapi`+`numpy` at import time even for `eval board …`
   subcommands because `ds_agent.cli.main` eagerly imports API routers and
   workflow services. Consider lazy imports so the evaluation CLI surface
   can run in a minimal pre-release env; post-beta.
4. **Perturb Harness (optional)**: `_PerturbScorer` in `.tmp/qa_D17/run_d17.py`
   is a useful regression-probe pattern; consider promoting a read-only
   variant into `tests/evaluation/` as a canary for non-determinism audits.
5. **Orphan hygiene**: None created. Environment is the same as at D17 start.

---

## Self-pass declaration

**Not declared.** Per QA protocol, D18 Release Readiness Auditor holds the
final pass authority.
