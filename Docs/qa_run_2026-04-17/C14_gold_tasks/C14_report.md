# C14 — Scenario Runner: Gold Tasks (offline, mocked)

**Tier**: 3
**Duration**: ~5 min
**Status**: pass (self_pass_declaration=false — final authority D18)
**Code SHA**: git-unavailable

## 1. Scope

Evaluation Harness **offline** mode applied to all six bundled gold tasks
under `src/ds_agent/evaluation/infrastructure/gold_tasks/tasks/`:

| domain | task file | difficulty |
|---|---|---|
| finance | `finance/fraud_triage_v1.yaml` | hard |
| healthcare | `healthcare/readmission_triage_v1.yaml` | hard |
| marketing | `marketing/lead_scoring_pipeline_v1.yaml` | medium |
| ops | `ops/inventory_restock_risk_v1.yaml` | medium |
| retail | `retail/churn_scoping_v1.yaml` | medium |
| saas | `saas/trial_conversion_scoping_v1.yaml` | medium |

Production modules under test (read-only; zero source modifications):

- `src/ds_agent/evaluation/infrastructure/gold_tasks/loader.py` — YAML suite loader.
- `src/ds_agent/evaluation/infrastructure/scorers/registry.py::build_default_scorers` — 10-dim scorer registry.
- `src/ds_agent/evaluation/infrastructure/scorers/*.py` — 10 dimension scorers (scoping, metric_selection, temporal_leakage, tool_trajectory, artifact_faithfulness, exec_summary, approval_judgment, session_completeness, operator_satisfaction, time_to_decision).
- `src/ds_agent/evaluation/application/use_cases/score_run.py` — `ScoreRun`.
- `src/ds_agent/evaluation/application/use_cases/build_regression_board.py` — `BuildRegressionBoard`, `FreezeRegressionBaseline`.
- `src/ds_agent/evaluation/application/use_cases/dispatch_regression_alerts.py` — `DispatchRegressionAlerts`.
- `src/ds_agent/evaluation/infrastructure/persistence/jsonl_eval_dataset_store.py`, `json_regression_baseline_store.py`.
- `src/ds_agent/evaluation/infrastructure/cli/eval_cli.py::run_eval_command` — `ds-agent eval board …` surface.

Out of scope (per HANDOFF §4.6):
- Pre-existing `test_semantic_ports_are_runtime_checkable` fail.
- mypy 3-count in `lineage_capture_service.py`, `reproducibility_exporter.py`.
- C13 parity / C15 packaging concerns (other Tier 3 agents).

## 2. Methodology

### 2.1 Scoped pytest (evaluation subtree)

Per HANDOFF §4.5 (no full regression on Windows), scoped pytest only:

```
pytest tests/unit/evaluation/ tests/integration/evaluation/ -v --tb=short \
       --junitxml=Docs/qa_run_2026-04-17/C14_gold_tasks/junit.xml
```

Result: **40 passed in 4.00s** (0 failures, 0 errors). JUnit captured at
`junit.xml`. Covers all default-scorer unit tests, `RunEvalBatch`,
`BuildRegressionBoard`, `FreezeRegressionBaseline`,
`DispatchRegressionAlerts`, `SlackRegressionAlertNotifier`,
`TeamsRegressionAlertNotifier`, the full `ds-agent eval` CLI integration
suite, and `GoldTaskLoader` for the six bundled YAMLs.

### 2.2 Gold-task execution harness

`.tmp/qa_C14/run_gold_tasks.py` loads the six YAMLs via `GoldTaskLoader`, then
for each task:

1. Builds a synthetic `EvalRun` whose `goal_brief`, `expected_deliverables`
   artifacts, `metric_choices`, `approvals`, `tool_calls`, temporal anchors,
   and operator feedback satisfy the task's own `validation_points` and
   `expected_deliverables`. Metric value is a conservative `0.82`.
2. Calls `ScoreRun(build_default_scorers()).execute(run, task)`. Because the
   harness does NOT supply a `JudgeLLM`, LLM-dimension scorers gracefully
   fall back to their deterministic heuristic path — **no real LLM API is
   contacted**, matching the C14 constraint.
3. Appends the `ScoredRunReport` to a `JsonlEvalDatasetStore` backed by
   `.tmp/qa_C14/eval_dataset.jsonl`. Nothing under `data/` or the real
   workspace is touched.
4. Emits per-domain `C14_traces/<domain>.jsonl` with one `run` event and ten
   `score` events per task (11 rows × 6 domains = 66 rows total).

### 2.3 Regression board + baseline freeze

- `BuildRegressionBoard(eval_store, baseline_store).execute(axis="commit",
  task_catalog=tasks)` built a snapshot with 6 records, zero alerts, and
  rolling-baseline delta_score=0.000.
- `FreezeRegressionBaseline(…).execute(commit_sha="c14-baseline-sha")`
  persisted a frozen baseline to `.tmp/qa_C14/regression_baseline.json`
  (`records=6`, `score=0.990`, `pass_rate=100%`).
- Harness also compared current dimension means against a prior
  `C14_prior_baseline.json` per the C14 spec. **No prior baseline** was
  found — per fallback, current means were written as the baseline freeze
  candidate and the regression gate passed by default on first run.

### 2.4 Alert dispatch (mocked)

No webhook HTTP was ever invoked. Two flows:

- **Primary**: `DispatchRegressionAlerts(board_builder, notifiers=(mock_slack, mock_teams)).execute(channels=("slack", "teams"))` on the clean green
  dataset. Snapshot had 0 alerts, so no `notifier.notify` call was made;
  a 64-char SHA-256 fingerprint was still returned.
- **Forced probe**: a separate `probe_dataset.jsonl` was built by copying
  the six passing records and appending a synthetic `weighted_score=0.10`
  record for `finance.fraud_triage.v1`. Running dispatch on that dataset
  fired **12 alerts** — the in-memory mock slack + mock teams notifiers both
  captured the payloads and returned `RegressionAlertDelivery` stubs with
  `response="mocked-200"`. This proves the `RegressionAlertNotifier` port is
  reached end-to-end.

### 2.5 `ds-agent eval board …` CLI

Executed from a shell and captured raw output:

- `ds-agent eval board show --dataset .tmp/qa_C14/eval_dataset.jsonl --baseline .tmp/qa_C14/regression_baseline.json --output text` → text snapshot captured in `C14_cli_board_show.txt`.
- Same with `--output json` → captured in `C14_cli_board_show.json`.
- `ds-agent eval board freeze-baseline --commit c14-cli-sha` → captured in `C14_cli_freeze_baseline.txt`; writes a new baseline-ID row to the baseline JSON.
- `ds-agent eval board send-alerts --channel slack --channel teams` with
  `DS_AGENT_EVAL_SLACK_WEBHOOK_URL=http://127.0.0.1:1/mock` and
  `DS_AGENT_EVAL_TEAMS_WEBHOOK_URL=http://127.0.0.1:1/mock` (both non-routable
  loopback) → CLI exited 0 with `dispatched alerts: 0 across 0 channel(s)` —
  the guard in `DispatchRegressionAlerts` short-circuits when
  `snapshot.alerts` is empty, so no real HTTP was attempted. Evidence in
  `C14_cli_send_alerts.txt`.

## 3. Results

- **domains_run: 6 / 6**
- **tasks_passed: 6 / 6** (all `weighted_score=0.990`, above task thresholds
  0.73–0.76)
- **max_abs_dimension_delta: 0.000** (no prior baseline — freeze candidate)
- **baseline_exists: false** (first C14 run)
- **alert_dispatch_ok: true** (forced probe received on both mock channels)

Detailed tables are in `C14_regression_report.md`. Per-domain weighted score
is 0.990 across all six domains (metric_selection dimension is 0.900 because
the chosen acceptable primary metric is not mentioned verbatim inside the
final_summary narrative, per the scorer heuristic; this is by fixture design
and does not indicate regression).

## 4. Failures and Anomalies

No in-scope failures. Observations that are NOT C14 defects:

- `ds-agent eval board send-alerts` on a clean green suite silently
  produces "dispatched alerts: 0 across 0 channel(s)" regardless of how many
  notifiers are configured. That is correct short-circuit behaviour
  (`if not snapshot.alerts: return early`), but the wording is easy to
  confuse with a dispatch failure — recommend adding "no alerts to dispatch"
  line in the CLI printer (non-blocking, NOTE only).
- `metric_selection_accuracy = 0.90` is the natural ceiling of the
  deterministic fallback even with a perfect metric choice, because the
  scorer rewards +0.05 per mention up to +0.10 only if the metric token also
  appears inside `final_summary`. The C14 synthetic run intentionally uses a
  clean summary template — documenting this so future baselines do not
  misread it as regression.
- No prior baseline JSON existed at `C14_prior_baseline.json`, so the
  delta-vs-prior gate is vacuously passed on this first C14 execution. The
  freeze candidate has been persisted for subsequent runs.

Out-of-scope pre-existing (per HANDOFF §4.6): not re-exercised.

## 5. Evidence Index

| Artifact | Location |
|---|---|
| START marker | `Docs/qa_run_2026-04-17/C14_gold_tasks/START.json` |
| FINAL marker | `Docs/qa_run_2026-04-17/C14_gold_tasks/FINAL.json` |
| Main C14 report (this file) | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_report.md` |
| Regression report | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_regression_report.md` |
| Summary JSON | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_summary.json` |
| Eval board snapshot (JSON) | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_eval_board_snapshot.json` |
| Regression delta payload | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_regression_delta.json` |
| Baseline freeze candidate | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_prior_baseline.json` |
| Alert dispatch evidence | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_alert_dispatch.json` |
| Per-domain traces | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_traces/{finance,healthcare,marketing,ops,retail,saas}.jsonl` |
| Scoped pytest JUnit | `Docs/qa_run_2026-04-17/C14_gold_tasks/junit.xml` |
| CLI board show text | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_cli_board_show.txt` |
| CLI board show JSON | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_cli_board_show.json` |
| CLI freeze-baseline | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_cli_freeze_baseline.txt` |
| CLI send-alerts | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_cli_send_alerts.txt` |
| Harness script | `.tmp/qa_C14/run_gold_tasks.py` |
| Eval dataset JSONL | `.tmp/qa_C14/eval_dataset.jsonl` |
| Frozen baseline JSON | `.tmp/qa_C14/regression_baseline.json` |

## 6. Constraints honored

- No source modifications — read-only audit.
- No real LLM API calls — scorers fall back to deterministic heuristic when
  `judge=None`.
- No real Slack/Teams webhook calls — in-memory mock notifier implementing
  the `RegressionAlertNotifier` Protocol. CLI `send-alerts` invocation used
  non-routable loopback URL and short-circuited on empty `snapshot.alerts`.
- No full-regression pytest — scoped to `tests/unit/evaluation/` +
  `tests/integration/evaluation/` per HANDOFF §4.5.
- No `data/` mutation — all persistence scoped to `.tmp/qa_C14/`.
- No C13 / C15 territory touched.
- `self_pass_declaration=false` — final authority is D18.

## 7. Recommendations (non-blocking)

1. In `_print_regression_alert_dispatch`, explicitly print "no alerts —
   skipping webhook delivery" when `report.deliveries` is empty AND
   `report.snapshot.alerts` is empty, so CLI operators don't mistake the
   no-alerts happy path for a dispatch failure.
2. Consider persisting a *canonical* `baseline.json` under
   `src/ds_agent/evaluation/infrastructure/baselines/` (or similar) so that
   first-time QA runs have a real prior baseline to compare against, rather
   than always taking the "freeze candidate" fallback.
3. The `metric_selection_accuracy` scorer's "+0.05 per mention in summary"
   heuristic is undocumented; add a one-line `rationale` note in the scorer
   so QA fixtures can hit 1.0 cleanly when intended.
