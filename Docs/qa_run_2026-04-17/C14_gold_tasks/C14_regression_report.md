# C14 — Gold Tasks Regression Report

**Tier**: 3
**Status**: pass (baseline freeze candidate — no prior baseline on disk)
**Code SHA**: git-unavailable
**Baseline mode**: first-run → `C14_prior_baseline.json` written as candidate
for subsequent runs.

## 1. Summary

All six bundled gold-task domains were executed offline through
`ScoreRun(build_default_scorers())` with **mocked** provider (scorers fall back
to deterministic heuristics when `judge=None`). No real LLM or webhook was
invoked at any point.

| metric | value |
|---|---|
| domains_run | 6 / 6 |
| tasks_run | 6 / 6 |
| tasks_passed | 6 / 6 |
| max_abs_dimension_delta | 0.000 (no prior baseline) |
| baseline_exists | false (first C14 run) |
| alert_dispatch_ok | true (primary + forced probe) |

## 2. Per-domain weighted scores

| domain | task_id | weighted_score | pass_threshold | passed |
|---|---|---:|---:|:---:|
| finance | finance.fraud_triage.v1 | 0.990 | 0.74 | yes |
| healthcare | healthcare.readmission_triage.v1 | 0.990 | 0.76 | yes |
| marketing | marketing.lead_scoring_pipeline.v1 | 0.990 | 0.74 | yes |
| ops | ops.inventory_restock_risk.v1 | 0.990 | 0.73 | yes |
| retail | retail.churn_scoping.v1 | 0.990 | 0.75 | yes |
| saas | saas.trial_conversion_scoping.v1 | 0.990 | 0.74 | yes |

## 3. Per-dimension means (across all 6 tasks)

| dimension | mean | judge |
|---|---:|---|
| scoping_accuracy | 1.000 | llm (fallback) |
| metric_selection_accuracy | 0.900 | hybrid |
| temporal_leakage_detection | 1.000 | deterministic |
| tool_trajectory | 1.000 | deterministic |
| artifact_faithfulness | 1.000 | llm (fallback) |
| exec_summary_accuracy | 1.000 | llm (fallback) |
| approval_judgment | 1.000 | hybrid |
| session_completeness | 1.000 | hybrid |
| operator_satisfaction | 1.000 | human_or_proxy (proxy) |
| time_to_decision | 1.000 | deterministic |

All 10 dimensions from the 10-dim scorer set are present for every task.
`metric_selection_accuracy` is 0.90 because the chosen primary metric is
acceptable but not also mentioned inside the `final_summary` text (per scorer
heuristic); this is by design of the fixture and does not indicate regression.

## 4. Regression delta vs prior baseline

**No prior baseline** was found at
`Docs/qa_run_2026-04-17/C14_gold_tasks/C14_prior_baseline.json` before this
run. Per the C14 spec fallback, the current dimension means have been written
to that path as a **baseline freeze candidate**, and the delta has been
recorded as 0.0 across all dimensions with `status="baseline freeze candidate"`.

The bundled `BuildRegressionBoard` also rolled a window-based baseline from
the in-dataset records; its `overall.delta_score = 0.000` and
`overall.delta_pass_rate = 0.000`, and zero alerts fired under the primary
dispatch, which is the expected green state.

Regression gate (per C14 spec `delta <= 0.05 for all dimensions`): **PASS by
default** on first run; subsequent C14 runs will compute real deltas against
`C14_prior_baseline.json` and the harness will set `regression_free=false` if
any dimension drops more than 5pp.

## 5. Alert dispatch mock receipt

Two flows were exercised, both with in-memory mock notifiers (zero real HTTP
calls):

1. **Primary dispatch** on the clean 6-domain dataset — snapshot has 0
   alerts, `DispatchRegressionAlerts` returned a 64-char SHA-256 fingerprint
   and no `deliveries`. This is the expected no-regression path.
2. **Forced-probe dispatch** — a separate probe dataset was constructed with
   a synthetic low-score record (`weighted_score=0.10`) appended after the 6
   passing records. The probe dispatcher fired **12 alerts** (combination of
   `single_task_hard_fail` + `dimension_regression` kinds) which both mock
   notifiers (slack + teams) captured and returned
   `RegressionAlertDelivery` stubs with response `mocked-200`.

`forced_alert_mock_received = true` ⇒ alert dispatch wiring reaches the
notifier port. Real webhook URLs were **never** contacted; the mock notifier
writes to an in-memory list only.

## 6. CLI evidence (`ds-agent eval board …`)

Captured in this folder:
- `C14_cli_board_show.txt` — `ds-agent eval board show` output.
- `C14_cli_board_show.json` — same, `--output json`.
- `C14_cli_freeze_baseline.txt` — `ds-agent eval board freeze-baseline`
  (commit=`c14-cli-sha`) confirmed and wrote the baseline JSON.
- `C14_cli_send_alerts.txt` — `ds-agent eval board send-alerts --channel
  slack --channel teams` with fake local-loopback webhook URLs; CLI correctly
  took the no-alerts path and reported `dispatched alerts: 0 across 0
  channel(s)` **without** invoking either webhook HTTP call (guarded by the
  empty `snapshot.alerts` check in `DispatchRegressionAlerts`). The `DS_AGENT_EVAL_{SLACK,TEAMS}_WEBHOOK_URL` environment variables were set to
  non-routable `http://127.0.0.1:1/mock` strictly to let `build_configured_regression_alert_notifiers` populate; since no alerts
  fired, neither was called.

## 7. Artifacts referenced by this report

| Artifact | Path |
|---|---|
| Evaluation board snapshot | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_eval_board_snapshot.json` |
| Regression delta payload | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_regression_delta.json` |
| Baseline freeze candidate | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_prior_baseline.json` |
| Alert dispatch evidence | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_alert_dispatch.json` |
| Per-domain traces | `Docs/qa_run_2026-04-17/C14_gold_tasks/C14_traces/{domain}.jsonl` |
| CLI board show (text/json) | `C14_cli_board_show.txt` / `.json` |
| CLI freeze-baseline | `C14_cli_freeze_baseline.txt` |
| CLI send-alerts | `C14_cli_send_alerts.txt` |
| Scoped pytest JUnit | `Docs/qa_run_2026-04-17/C14_gold_tasks/junit.xml` |
| Harness script | `.tmp/qa_C14/run_gold_tasks.py` |
