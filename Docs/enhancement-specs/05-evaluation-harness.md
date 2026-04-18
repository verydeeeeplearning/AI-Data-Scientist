# Evaluation Harness 상세 구현 스펙

> 본 문서는 `Docs/ds-agent-enhancement-roadmap.md` §5 Evaluation Harness 를 상세화한 스펙이다.
> 대상 독자: 내부 개발팀, QA 리드, 제품 오너.
> 범위: Gold Task Set, 10차원 scorer, Shadow/Online 평가 모드, Production trace→eval dataset 파이프라인, Regression Board.
> 본 스펙은 "학습보다 평가가 먼저"라는 원칙 아래, self_improve 모듈이 생성하는 학습 산출물(패턴, 도메인 KB, 커스텀 스킬)의 승격 게이트로 작용하는 평가 체계를 정의한다.

## 0. Implementation Snapshot (2026-04-16)

Update (2026-04-16, P1 scorecard bridge): `run.scorecard` WebSocket RPC now rebuilds a persisted run via `SessionTraceReader`, adapts production task context when available, scores it through the default scorer registry, and returns an Electron-friendly payload. `electron/src/renderer/components/runtime/RunDetailDrawer.tsx` now lazy-loads this payload for the selected run and renders weighted score, pass threshold, recovery context, and per-dimension rationale inside the inspector.

Update (2026-04-16, P1 nightly CI): `.github/workflows/eval-nightly.yml` now runs on a nightly schedule plus manual dispatch, installs Python/Electron deps, executes `python -m ds_agent.cli.main eval validate-suite`, runs evaluation/API regression tests with an isolated `--basetemp`, lints evaluation-related paths, and typechecks the Electron scorecard bridge. Failed runs upload pytest temp artifacts for triage.

Update (2026-04-16, bundled gold task expansion): the bundled suite now ships six seed tasks across `retail`, `finance`, `saas`, `ops`, `healthcare`, and `marketing`, bringing the repository up to the original P1 minimum suite size. `tests/integration/evaluation/infrastructure/test_gold_task_loader.py` now asserts all six task ids so suite erosion shows up in CI immediately.

Update (2026-04-16, P1 live execution bridge): `ds-agent eval run` now supports `--runner agent`, which executes a real `DSAgent` against gold tasks, persists transcript/runtime/task state into the workspace runtime stores, and reconstructs the resulting `EvalRun` through `SessionTraceReader`. This closes the last P1 gap that remained after the scorecard bridge, nightly CI, and bundled suite work.

Update (2026-04-16, P2 human rubric intake): evaluation runs can now accept append-only human rubric reviews through `eval ingest-human`. Human rubric records persist in the workspace runtime root, `SessionTraceReader` rehydrates the latest rubric onto the run, and `ScoreRun` applies dimension-level human overrides on top of automated scores. This lands the first operator-review path without waiting on the Electron reviewer UI.

Update (2026-04-16, P2 reviewer UI): `run.submitHumanRubric` RPC and the Electron `RunDetailDrawer` now expose a 10-dimension reviewer form directly beside the run scorecard. Operators can enter per-dimension scores plus reviewer/comment metadata, save the review, and see the refreshed scorecard immediately with persisted human overrides and recorded reviewer context.

Update (2026-04-16, P2 shadow comparison path): `RunShadowComparison`, `JsonlShadowComparisonStore`, and `ds-agent eval shadow-session` now execute a shadow twin against the same production task context, score both the baseline and shadow traces, persist an append-only comparison record, and optionally append both sides into the eval dataset with paired metadata. The runtime surface also exposes `run.shadowCompare`, and the Electron `RunDetailDrawer` now shows the latest shadow summary, weighted delta, and top per-dimension improvements/regressions for the selected run.

Validation (2026-04-16, P2 shadow comparison path): `pytest tests/unit/evaluation tests/integration/evaluation`, `pytest tests/unit/infrastructure/test_api.py -k "run_scorecard or run_submit_human_rubric or run_shadow_compare"`, `ruff check src/ds_agent/evaluation src/ds_agent/api/ws_handler.py tests/unit/evaluation tests/integration/evaluation tests/unit/infrastructure/test_api.py`, `python -m ds_agent.cli.main eval validate-suite`, and Electron `npm run typecheck` all pass on the landed implementation.

Update (2026-04-16, P2 review sampling policy): deterministic, domain-stratified human-review sampling is now persisted via `JsonlReviewSamplingStore` and resolved through `ResolveReviewSampling`. Runtime scorecards now carry `reviewSampling` status plus persisted metadata, and the Electron reviewer form surfaces whether a run was selected for sampled review, already completed, or optional.

Validation (2026-04-16, P2 review sampling policy): `pytest tests/unit/evaluation tests/integration/evaluation tests/unit/infrastructure/test_api.py`, `ruff check src/ds_agent/evaluation src/ds_agent/api/ws_handler.py tests/unit/evaluation tests/integration/evaluation tests/unit/infrastructure/test_api.py`, `python -m ds_agent.cli.main eval validate-suite`, and Electron `npm run typecheck` all pass on the landed implementation.

Update (2026-04-16, P3 frozen baseline + board integration): `FreezeRegressionBaseline`, `JsonRegressionBaselineStore`, and `ds-agent eval board freeze-baseline --commit <sha>` now persist a manual regression baseline under the workspace runtime root. `BuildRegressionBoard`, the board CLI snapshot path, and the WebSocket `eval.regressionBoard` surface now load this frozen baseline when the mode/domain scope matches, expose `baseline_source` plus `frozen_baseline`, and compare recent board metrics against the frozen benchmark instead of only using the rolling fallback.

Validation (2026-04-16, P3 frozen baseline + board integration): `pytest tests/unit/evaluation tests/integration/evaluation tests/unit/infrastructure/test_api.py`, `ruff check src/ds_agent/evaluation src/ds_agent/api/ws_handler.py tests/unit/evaluation tests/integration/evaluation`, and `python -m ds_agent.cli.main eval board freeze-baseline --commit <sha> --output json` all pass on the landed implementation.

Update (2026-04-16, P3 runtime dashboard slice): the Regression Board now has a full operator-facing read path. `JsonlEvalDatasetStore.for_workspace()` gives runtime surfaces a stable dataset root, `run.submitHumanRubric` / `run.shadowCompare` now append eval dataset records, `ds-agent eval board show|snapshot|freeze-baseline` supports commit/date axes plus frozen-baseline comparisons, `eval.regressionBoard` exposes the board over WebSocket RPC, and Electron Runtime now includes a read-only `RegressionBoard` panel with mode/domain filters plus top alert/task/dimension previews.

Validation (2026-04-16, P3 runtime dashboard slice): `pytest --basetemp .tmp/pytest_regression_board_final tests/unit/evaluation/application/test_build_regression_board.py tests/integration/evaluation/infrastructure/test_eval_cli_board.py tests/integration/evaluation/infrastructure/test_eval_cli_board_snapshot.py tests/unit/infrastructure/test_api.py -k "regression_board or eval_cli_board or run_scorecard or run_shadow_compare or run_submit_human_rubric"`, targeted `ruff check` on touched evaluation/ws files, targeted `mypy` on `regression_board.py`, `build_regression_board.py`, `regression_payload.py`, `jsonl_eval_dataset_store.py`, and `eval_cli.py`, plus Electron `npm run typecheck` and `npm run test:contract:runtime` all pass.

Update (2026-04-16, P3 alerting adapter): `DispatchRegressionAlerts`, `SlackRegressionAlertNotifier`, `TeamsRegressionAlertNotifier`, and `ds-agent eval board send-alerts --channel slack|teams` now provide a manual Slack/Teams delivery path for the active Regression Board alerts. The adapter reuses the current board snapshot, formats readable dimension/task labels for webhook payloads, and records per-channel delivery metadata so operator-triggered alert dispatch is contract-tested before any runtime auto-trigger wiring.

Validation (2026-04-16, P3 alerting adapter): `pytest --basetemp .tmp/pytest_eval_p3_alerting tests/unit/evaluation tests/integration/evaluation tests/unit/infrastructure/test_api.py -q`, `ruff check src/ds_agent/evaluation src/ds_agent/api/ws_handler.py tests/unit/evaluation tests/integration/evaluation`, and `python -m ds_agent.cli.main eval validate-suite` all pass on the landed implementation.

Update (2026-04-16, P3 self_improve gate wiring): `PostLearningAdapter` now persists extracted skills as `pending_promotion` candidates under the workspace runtime root instead of silently activating them. `JsonPromotionCandidateStore`, `SelfImprovePromotionGate`, and `CandidateTaggedEvalOrchestrator` wire that candidate lifecycle into `ds-agent eval run --with-candidate <id> --delta-threshold <x>`, so a pending skill can be evaluated against the existing regression-board baseline and then automatically promoted or blocked. Candidate-backed runs are tagged in eval dataset metadata for traceability, and successful promotions materialize the approved skill into the active custom-skill directory only after the eval gate passes.

Validation (2026-04-16, P3 self_improve gate wiring): `pytest --basetemp .tmp/pytest_eval_final tests/unit/application/test_skill_extractor.py tests/unit/application/test_self_improve_promotion_gate.py tests/unit/evaluation/application/test_dispatch_regression_alerts.py tests/unit/evaluation/infrastructure/test_alerting_adapter.py tests/integration/evaluation/infrastructure/test_eval_cli_board.py tests/integration/evaluation/infrastructure/test_eval_cli_board_snapshot.py tests/integration/evaluation/infrastructure/test_eval_cli_board_send_alerts.py tests/integration/evaluation/infrastructure/test_eval_cli_run_agent.py tests/integration/evaluation/infrastructure/test_eval_cli_with_candidate.py`, targeted `ruff check` on touched self_improve/evaluation files, and targeted `mypy` on `promotion_candidates.py`, `promotion_gate.py`, `learning_adapter.py`, `alerting_adapter.py`, `eval_cli.py`, and `agent_eval_orchestrator.py` all pass.

Update (2026-04-16, P3 automatic regression-alert scheduling): `DispatchRegressionAlerts` now uses persisted fingerprint state to dedupe unchanged alert sets, `AppState.dispatch_regression_alerts()` exposes a runtime-safe dispatch helper, and `submit_run_human_rubric` / `run_shadow_compare` now trigger best-effort domain-scoped alert dispatch after they append new evaluation records. The autonomous daemon also registers `RegressionAlertScheduler`, reads its cron/channel/filter policy from `DS_AGENT_EVAL_ALERT_*`, and executes a periodic standing-order sweep that dispatches only when the regression-board fingerprint changes.

Validation (2026-04-16, P3 automatic regression-alert scheduling): `pytest --basetemp .tmp/pytest_eval_p3_auto_alert tests/unit/evaluation tests/integration/evaluation tests/unit/infrastructure/test_api.py tests/unit/infrastructure/test_autonomous_runtime.py tests/unit/runtime/test_regression_alert_scheduler.py -q`, `ruff check src/ds_agent/evaluation src/ds_agent/api/ws_handler.py src/ds_agent/gateway/daemon.py src/ds_agent/runtime/regression_alert_scheduler.py tests/unit/evaluation tests/integration/evaluation tests/unit/infrastructure/test_api.py tests/unit/infrastructure/test_autonomous_runtime.py tests/unit/runtime/test_regression_alert_scheduler.py`, and `python -m ds_agent.cli.main eval validate-suite` all pass on the landed implementation.

Update (2026-04-16, P3 dashboard freeze/diff polish): the Electron `RegressionBoard` point inspector now distinguishes frozen-baseline selections from freeze-eligible commits, shows explicit previous-point comparison context, and renders both per-dimension and per-mode before/after deltas for the selected board point. The renderer model now exposes `selectedPointIsFrozenBaseline` plus `pointModeDiffs`, and the runtime contract fixture asserts both the freeze-state behavior and the richer diff payload.

Validation (2026-04-16, P3 dashboard freeze/diff polish): Electron `npm run typecheck` and `npm run test:contract:runtime` both pass on the landed implementation.

Current P1 gaps after this step:
- none. Remaining work now shifts to P3 items such as Regression Board automation.

Current P2 gaps after this step:
- none.

Current P3 gaps after this step:
- no remaining feature-scope gaps inside P3
- broader `mypy src/ds_agent/api/ws_handler.py` remains blocked by pre-existing typing debt outside the new regression-board path

이번 개발 턴에서 P1 foundation을 코드베이스에 최초 반영했다. 현재 landed 범위는 다음과 같다.

- `src/ds_agent/evaluation/` 패키지 신설
  - Gold Task / EvalRun / EvalScore / HumanRubric 도메인 모델
  - judge/scorer/store/orchestrator 포트
  - `ScoreRun`, `RunEvalBatch` use case
- 기본 scorer 10종의 초기 휴리스틱 구현
  - `scoping_accuracy`
  - `metric_selection_accuracy`
  - `temporal_leakage_detection`
  - `tool_trajectory`
  - `artifact_faithfulness`
  - `exec_summary_accuracy`
  - `approval_judgment`
  - `session_completeness`
  - `operator_satisfaction`
  - `time_to_decision`
- Gold Task YAML loader + bundled sample tasks 2종
  - `retail.churn_scoping.v1`
  - `finance.fraud_triage.v1`
- Append-only JSONL eval dataset store
- fixture-backed batch scorer용 orchestrator
- agent-backed live eval orchestrator
  - `AgentEvalOrchestrator` executes a real `DSAgent` for a gold task using the shared factory/provider stack, binds run/session/task persistence in the workspace runtime root, and rebuilds the trace into `EvalRun`
  - `ds-agent eval run --runner agent --model <model>` provides a first-class live bridge alongside the existing fixture-backed `--runner directory` path
- human rubric persistence + intake
  - `JsonlHumanRubricStore` persists append-only reviewer decisions per session/run in the workspace runtime root
  - `IngestHumanRubric` stores the review, enriches the reconstructed `EvalRun`, and re-scores with human overrides applied at the dimension level
  - `ds-agent eval ingest-human --dimension name=value ...` provides the first operator-review ingestion path
- Electron reviewer surface
  - `run.submitHumanRubric` RPC persists one reviewer submission for a tracked runtime run and returns the updated scorecard payload
  - `electron/src/renderer/components/runtime/RunDetailDrawer.tsx` now renders reviewer id/comment plus 10 dimension inputs, and refreshes the scorecard after save
- shadow comparison runner + operator surface
  - `RunShadowComparison` scores the persisted production baseline plus a real shadow-agent twin and persists an append-only `ShadowComparisonRecord`
  - `JsonlShadowComparisonStore` stores the paired comparison summary under the workspace runtime root, while dataset append now tags baseline/shadow records with a shared `shadowComparisonId`
  - `ds-agent eval shadow-session` provides the CLI/operator path for production-vs-shadow comparisons, and `run.shadowCompare` + Electron `RunDetailDrawer` expose the same flow inside the runtime inspector
- deterministic review sampling policy
  - `ResolveReviewSampling` + `JsonlReviewSamplingStore` now assign a stable, domain-stratified human-review verdict per production run using a persisted hash bucket and a 20% default target rate
  - `SessionTraceReader` rehydrates persisted sampling decisions into `EvalRun.metadata`, so scorecards and downstream dataset/report paths can see whether a run was sampled
  - Electron `RunDetailDrawer` now labels each review form as `Selected for sampled review`, `Review sampling completed`, or `Optional review`
- CLI 진입점 추가
  - `ds-agent eval validate-suite`
  - `ds-agent eval score-run`
  - `ds-agent eval run`
  - `ds-agent eval shadow-session`
- persisted production session ingest 경로 추가
  - `SessionTraceReader`: transcript + approval store + usage store + runtime event log를 `EvalRun`으로 복원
  - `ProductionTaskAdapter`: task contract를 synthetic production `GoldTask`로 변환하고 run을 contract 정보로 enrich
  - `IngestProductionTrace` use case
  - `ds-agent eval ingest-session`
- runtime lifecycle persistence 보강
  - `AppState.start_run()` 이 foreground/background 구분 없이 `task.started` / `task.completed` / `task.failed` / `task.cancelled` 를 runtime event log에 기록
  - `SessionTraceReader` 의 `time_to_decision` 계산이 usage fallback 외에 persisted task lifecycle timestamp를 우선 활용 가능
- persisted runtime registry ingest 보강
  - `RuntimeSessionRegistry` / `RunRegistry` 가 workspace runtime root에 file-backed snapshot을 저장
  - `SessionTraceReader.for_workspace()` 가 persisted run/session registry를 함께 열고 latest `run_id`, `started_at`, `finished_at`, `cost_usd`, `surface`, `runtimeStatus` 를 우선 복원
  - runtime run/session 목록이 AppState 재초기화 이후에도 동일 workspace 기준으로 이어지고, evaluation ingest 가 runtime registry를 직접 timing source 로 사용 가능
- checkpoint / goal / task trace stitching 보강
  - `TaskLedger` 가 workspace runtime root에 file-backed snapshot을 저장하고, task status/finished_at/error 를 재기동 후에도 복원
  - `SessionTraceReader` 가 checkpoint store, goal store, task ledger 를 함께 stitch 하여 `checkpointStep`, `goalStatus`, `goalBlockedReason`, `taskStatus` 등 recovery context metadata 를 `EvalRun` 에 주입
  - recovered context 를 `checkpoint_context`, `goal_state`, `task_trace` artifact 로도 보존해서 향후 scorecard / reviewer UI / scorer 확장에 재사용 가능
- scorer / dataset payload 보강
  - `OperatorSatisfactionScorer` proxy 가 follow-up signal 외에 `goalStatus`, `taskStatus`, `goalBlockedReason`, `checkpointStep` 를 함께 사용해 recovery-aware satisfaction 점수를 계산
  - `ScoredRunReport` / `EvalDatasetRecord` 가 `session_id`, `cost_usd`, `decision_latency_seconds`, `metric_choices`, `artifact_types`, `run_metadata` 를 보존해서 Regression Board / Scorecard payload 의 원재료를 축적
  - production ingest 결과가 단순 weighted score 집계만이 아니라, run context 를 잃지 않는 append-only dataset 으로 축적되도록 확장
- 검증
  - `pytest tests/unit/evaluation tests/integration/evaluation` 통과
  - `ruff check src/ds_agent/evaluation tests/unit/evaluation tests/integration/evaluation src/ds_agent/cli/main.py` 통과
  - `pytest tests/unit/evaluation tests/integration/evaluation tests/unit/infrastructure/test_autonomous_runtime.py` 통과
  - `ruff check src/ds_agent/evaluation src/ds_agent/api/ws_handler.py tests/unit/evaluation tests/integration/evaluation tests/unit/infrastructure/test_autonomous_runtime.py` 통과
  - `pytest tests/unit/evaluation tests/integration/evaluation tests/unit/infrastructure/test_autonomous_runtime.py tests/unit/infrastructure/test_api.py` 통과
  - `ruff check src/ds_agent/evaluation src/ds_agent/runtime/session_registry.py src/ds_agent/runtime/run_registry.py src/ds_agent/api/ws_handler.py tests/unit/evaluation tests/integration/evaluation tests/unit/infrastructure/test_autonomous_runtime.py tests/unit/infrastructure/test_api.py tests/unit/infrastructure/test_runtime_registries.py` 통과
  - `pytest tests/unit/evaluation tests/integration/evaluation tests/unit/infrastructure/test_autonomous_runtime.py tests/unit/infrastructure/test_api.py tests/unit/infrastructure/test_runtime_persistence.py` 통과
  - `ruff check src/ds_agent/evaluation src/ds_agent/runtime/task_ledger.py src/ds_agent/runtime/session_registry.py src/ds_agent/runtime/run_registry.py src/ds_agent/api/ws_handler.py tests/unit/evaluation tests/integration/evaluation tests/unit/infrastructure/test_autonomous_runtime.py tests/unit/infrastructure/test_api.py tests/unit/infrastructure/test_runtime_persistence.py tests/unit/infrastructure/test_runtime_registries.py` 통과
  - `pytest tests/unit/evaluation/application/test_run_eval_batch.py tests/unit/evaluation/infrastructure/test_default_scorers.py` 통과

이번 턴의 의도는 “자율형 Agent 전체 run을 평가할 수 있는 계약과 최소 실행 경로를 먼저 고정”하는 것이다. 아직 미구현인 항목은 다음 단계로 남아 있다.

- persisted timing fidelity 개선
  - run/session/task registry 와 checkpoint/goal context 는 저장되지만, per-turn boundary 와 finer-grained operator decision timestamp 는 아직 불완전하다
- richer causal scoring 활용
  - `operator_satisfaction` proxy 는 recovery context 를 보기 시작했지만, blocked recovery quality / resume quality 를 별도 차원으로 분리하거나 `approval_judgment` / `session_completeness` 까지 확장한 상태는 아직 아니다
- automatic online ingest trigger
  - 스펙상 `run.finalized` 기반 `ProductionTraceIngestor` 가 남아 있으며, 현재는 CLI/use-case 중심으로만 ingest 된다
- 실제 LLM judge adapter
- Regression Board / Electron Scorecard 연동
- self_improve promotion gate 연결
- shadow / online sampling 정책

---

## 1. 배경 및 문제 정의 — "학습보다 평가가 먼저"

### 1.1 현재 상태

- DS Agent는 Hermes-style 자율 agent로 동작한다. `runtime/session_registry.py` 와 `runtime/run_registry.py` 에 세션/실행 trace가 축적된다.
- `self_improve` 모듈은 세션 trace에서 패턴을 추출하고, 도메인 KB를 갱신하며, 커스텀 스킬을 자동 생성한다.
- pytest 기반 자동 테스트는 1,382개가 존재하지만, 이들은 **코드의 동작**(단위/통합 단위)만 검증한다. 즉 "LLM orchestrator가 DS 과제를 잘 수행했는가"에 대한 회귀 테스트는 부재하다.
- 현재 agent 품질은 개발자의 주관적 eyeball review 와 간헐적 사용자 피드백에만 의존한다.

### 1.2 핵심 문제

1. **회귀 불감증**: 프롬프트/모델/skill 변경 시 기존 과제 성능이 유지되는지 알 수 없다.
2. **학습 루프의 신뢰 부재**: self_improve가 자동 생성한 패턴/스킬이 실제로 품질을 향상시키는지 측정할 방법이 없다. 잘못된 일반화가 축적되어도 감지하기 어렵다.
3. **운영자 만족도 블랙박스**: "분석 결과가 유용했는지"를 구조화된 데이터로 보유하지 못한다.
4. **의사결정 시간 미측정**: time-to-decision 이라는 agent 핵심 KPI를 집계하지 못한다.
5. **Production trace 사용 불능**: 풍부한 실행 trace가 저장되고는 있으나, 이를 평가 데이터셋으로 전환하는 파이프라인이 없다.

### 1.3 해결 방향

"평가 없는 학습은 신뢰할 수 없다" 원칙에 따라, **Evaluation Harness 를 self_improve 의 게이트**로 전면에 배치한다. 본 스펙은 다음을 도입한다:

- YAML 기반 Gold Task Set 으로 회귀 베이스라인 확립
- 10차원 scorer 로 agent 행동을 다차원 평가
- Offline / Shadow / Online / Human Rubric 네 가지 평가 모드
- Production trace → Eval Dataset 자동 수집 파이프라인
- Regression Board 와 임계값 기반 알림
- Run Scorecard UI (사용자 대면)

---

## 2. 핵심 테제

1. **평가는 학습의 선행조건이다.** self_improve 가 생성한 어떤 산출물도, Evaluation Harness 의 Gold Task Set 회귀에서 baseline 대비 유의미한 하락이 없을 때에만 승격된다.
2. **다차원 평가만 유효하다.** 단일 스코어(예: "정답률")로는 DS agent 품질을 포착할 수 없다. 본 스펙은 10개 독립 차원을 정의하고, 각 차원에 deterministic 또는 LLM-judge scorer 를 할당한다.
3. **평가는 실재 운영과 연결되어야 한다.** Offline Gold Task 만으로는 운영 분포를 대표할 수 없다. Production trace → eval dataset 파이프라인으로 "실제 사용자 요청" 을 평가 대상에 포함시킨다.
4. **Scorer 는 계약이고 테스트 대상이다.** 각 scorer 는 port interface 로 추상화되고, meta-test(known good/bad run 에 대한 기대 점수) 로 자체 검증된다.
5. **점수는 UX 에 반영된다.** 내부용 계기판만이 아니라 Run Scorecard 로 사용자에게 투명하게 노출된다. 이는 agent 가 자신의 불확실성을 사용자에게 정직하게 전달하는 장치이기도 하다.
6. **Autonomous agent 정체성 보존.** Evaluation Harness 는 agent 의 자율성을 감시하되 대체하지 않는다. 평가 결과는 orchestration 로직 자체를 workflow 로 고정시키는 근거로 사용되지 않는다.

---

## 3. 아키텍처 개요

```
                        +-----------------------------+
                        |      Orchestrator (LLM)     |
                        +--------------+--------------+
                                       |
                                       v
                        +-----------------------------+
                        |   Session / Run Registry    |
                        |  (runtime/*_registry.py)    |
                        +-----------+---+-------------+
                                    |   |
                             trace  |   |  feedback
                                    v   v
+-----------------------------------------------------------------+
|                     Evaluation Harness (evaluation/)            |
|                                                                 |
|  +-------------------+    +------------------------------+      |
|  |  Gold Task Set    |    |  Production Trace Ingestor   |      |
|  | (YAML tasks)      |    |  - session_registry reader   |      |
|  +---------+---------+    |  - review event reader       |      |
|            |              +---------------+--------------+      |
|            v                              v                     |
|  +-----------------------+    +------------------------------+  |
|  |     EvalRunner        |    |     EvalDatasetStore         |  |
|  |  - offline mode       |    |  (append-only, typed)        |  |
|  |  - shadow mode        |    +---------------+--------------+  |
|  |  - online mode        |                    ^                 |
|  +----------+------------+                    |                 |
|             |                                 |                 |
|             v                                 |                 |
|  +----------+--------------------------------+-+                |
|  |              Scorer Registry                 |                |
|  |  1. scoping_accuracy           (LLM-judge)   |                |
|  |  2. metric_selection_accuracy  (deterministic + LLM-judge)    |
|  |  3. temporal_leakage_detection (deterministic)                |
|  |  4. tool_trajectory            (deterministic)                |
|  |  5. artifact_faithfulness      (LLM-judge)   |                |
|  |  6. exec_summary_accuracy      (LLM-judge)   |                |
|  |  7. approval_judgment          (deterministic + LLM-judge)    |
|  |  8. session_completeness       (deterministic + LLM-judge)    |
|  |  9. operator_satisfaction      (human rubric + proxy)         |
|  | 10. time_to_decision           (deterministic)                |
|  +----------------------------------------------+                |
|                                                                 |
|  +---------------------+   +-----------------------+            |
|  | RegressionBoard     |   |  Human Rubric Intake  |            |
|  | - time-series       |   |  - reviewer UI        |            |
|  | - alert rules       |   |  - approve/reject/mod |            |
|  +---------------------+   +-----------------------+            |
+-----------------------------------------------------------------+
                                      |
                                      v
              +---------------------------------------------+
              |      self_improve promotion gate            |
              |  block promotion if eval regression > T     |
              +---------------------------------------------+
```

핵심 구성 요소는 네 개다.

- **Gold Task Set**: YAML 로 정의된 표준 DS 과제 모음. 도메인별 10~30개로 시작하여 확장.
- **Scorers**: 10차원 평가자. deterministic scorer 는 결정적 규칙, LLM-judge scorer 는 LLM 을 judge 로 사용.
- **Eval Modes**: Offline(회귀), Shadow(병렬 실행 후 사람 결과 비교), Online(production trace 일부 scorer 적용), Human Rubric(리뷰어 점수 수집).
- **Regression Board**: Gold Task Set 시계열 결과 대시보드와 알림.

---

## 4. GoldTask 스키마 (YAML)

### 4.1 설계 원칙

- **사람이 읽고 쓸 수 있어야 한다.** 도메인 전문가가 과제를 직접 기여할 수 있어야 한다.
- **자체 포함적이어야 한다.** 과제 설명, 입력 데이터 참조, 예상 산출물, 필수 검증 포인트를 한 파일에 담는다.
- **타입이 강제되어야 한다.** pydantic 모델로 로드하여 런타임 오류를 조기 검출한다.
- **버전 관리된다.** 파일명 또는 front-matter 에 `task_version` 을 포함한다.

### 4.2 파일 구조 예시

```yaml
# evaluation/gold_tasks/retail/churn_scoping_v1.yaml
id: retail.churn_scoping.v1
task_version: 1
domain: retail
difficulty: medium          # easy | medium | hard
tags: [scoping, churn, classification]

prompt: |
  우리 구독 서비스의 지난 90일 이탈률이 갑자기 12%에서 17%로 올랐다.
  무엇이 문제인지 파악하고, 다음 분기 캠페인에 쓸 수 있는
  이탈 위험 고객 리스트를 만들어 달라.

input:
  datasets:
    - name: subscriptions
      source: fixtures/retail/subscriptions_2024q4.parquet
      schema_ref: schemas/retail/subscriptions.schema.json
    - name: events
      source: fixtures/retail/events_2024q4.parquet
  snapshot_date: 2024-12-31
  budget_usd: 20.0
  time_budget_min: 30

expected_deliverables:
  - type: goal_brief
    must_contain:
      - problem_framing
      - kpi_definition
      - segment_definition
  - type: eda_report
    must_cover:
      - cohort_churn_by_plan
      - cohort_churn_by_tenure
  - type: model_artifact
    kind: classifier
    target: churn_30d
  - type: ranked_customer_list
    top_k: 500
  - type: executive_summary

validation_points:
  temporal:
    snapshot_date: 2024-12-31
    features_cutoff_before_days: 1
    forbid_future_leakage: true
  metric_selection:
    acceptable_primary:
      - roc_auc
      - pr_auc
      - lift_at_10pct
    forbidden_primary:
      - accuracy        # 클래스 불균형 때문에 accuracy 단독 사용은 오답
  segment:
    must_exclude:
      - already_churned_before_snapshot
  approval_required:
    sending_campaign: true
    publishing_model: true

baseline:
  human_expert_time_min: 60
  human_expert_rubric:
    scoping_accuracy: 0.90
    metric_selection_accuracy: 0.95
    session_completeness: 0.95

scoring_rubric:
  scoping_accuracy:
    weight: 0.15
    judge: llm
    prompt_ref: scorers/prompts/scoping_accuracy_v2.md
  metric_selection_accuracy:
    weight: 0.10
    judge: hybrid
  temporal_leakage_detection:
    weight: 0.15
    judge: deterministic
  tool_trajectory:
    weight: 0.05
    judge: deterministic
  artifact_faithfulness:
    weight: 0.15
    judge: llm
  exec_summary_accuracy:
    weight: 0.10
    judge: llm
  approval_judgment:
    weight: 0.10
    judge: hybrid
  session_completeness:
    weight: 0.10
    judge: hybrid
  operator_satisfaction:
    weight: 0.05
    judge: human_or_proxy
  time_to_decision:
    weight: 0.05
    judge: deterministic

pass_threshold: 0.75        # weighted score
alert_on_drop_below: 0.70   # regression alert
```

### 4.3 필드 설명

| 필드 | 의미 |
|------|------|
| `id` | 전역 고유 ID. `<domain>.<name>.v<task_version>` 규칙 |
| `domain` | retail / finance / ops / generic 등 |
| `difficulty` | easy/medium/hard |
| `prompt` | agent 에게 전달되는 사용자 요청(자연어) |
| `input.datasets` | fixture 경로 + schema ref |
| `input.snapshot_date` | 시간 누출 검증의 기준일 |
| `input.budget_usd` / `time_budget_min` | 리소스 상한 |
| `expected_deliverables` | agent 가 만들어야 할 산출물 타입과 필수 항목 |
| `validation_points` | deterministic scorer 가 기계적으로 검증하는 포인트 |
| `baseline.human_expert_*` | 인간 전문가 기준선. 비교 대조군 |
| `scoring_rubric` | 10개 차원 각각의 가중치와 judge 유형 |
| `pass_threshold` | 합격/불합격 기준 |
| `alert_on_drop_below` | Regression Board 알림 임계 |

### 4.4 규모와 커버리지 정책

- Phase 1 목표: 도메인 3개(retail, finance, ops generic) × 과제 8~10개 = 24~30 과제.
- 난이도 분포: easy 30%, medium 50%, hard 20%.
- 검증 포인트 중복 최소화. 특정 단일 차원만 검사하는 edge-case 과제도 허용 (예: 시간 누출 트랩 전용).

---

## 5. 10차원 Scorer 상세

모든 scorer 는 `evaluation/scorers/base.py` 의 `Scorer` port interface 를 구현한다.

```python
class Scorer(Protocol):
    name: str
    version: str
    judge_type: Literal["deterministic", "llm", "hybrid", "human_or_proxy"]

    def score(self, run: EvalRun, task: GoldTask) -> EvalScore: ...
```

`EvalScore` 는 `value: float ∈ [0,1]`, `rationale: str`, `sub_scores: dict[str, float]`, `evidence_refs: list[str]` 을 포함한다.

### 5.1 scoping_accuracy (LLM-judge)

**질문**: agent 의 GoalBrief 가 사용자의 비즈니스 문제를 DS 문제로 정확히 번역했는가?

**판정 로직**:
- Run 에서 GoalBrief artifact 추출.
- LLM judge 에게 `(prompt, goal_brief, expected_deliverables.goal_brief.must_contain)` 전달.
- 판정 항목: problem framing 정합성, KPI 정의의 합리성, segment 정의의 비즈니스 적합성, unmet needs 식별.
- Output: 0–1 점수, 각 sub-score, rationale.

**이유**: scoping 은 본질적으로 주관적 판단을 요구. deterministic 규칙만으로는 잡히지 않는다.

**안정성 보장**:
- Judge prompt 는 version 고정(`scorers/prompts/scoping_accuracy_v2.md`).
- Judge 모델 버전은 EvalRun 메타데이터에 기록.
- Meta-test 로 "known good GoalBrief" 는 >= 0.85, "deliberately-bad GoalBrief" 는 <= 0.40 을 강제.

### 5.2 metric_selection_accuracy (hybrid)

**질문**: agent 가 주요 지표(primary metric)를 과제에 맞게 선택했는가?

**판정 로직**:
- **Deterministic 부분**: Run 의 `metric_choices` 필드를 파싱해 `task.validation_points.metric_selection.forbidden_primary` 와 교집합이 있으면 즉시 0점. `acceptable_primary` 에 포함되면 0.8 이상 후보.
- **LLM 부분**: acceptable 집합 내에서도 정당성/맥락 적합성을 추가 평가.

**산출**: deterministic score 와 LLM 보정 score 의 max 또는 가중합(configurable). Phase 1 에서는 deterministic 필터 + LLM 0–1 평가의 곱으로 단순화.

### 5.3 temporal_leakage_detection (deterministic)

**질문**: agent 가 snapshot_date 이후의 정보를 feature 로 사용하거나, target leakage 를 포함한 컬럼을 사용했는가?

**판정 로직**:
- Run 에 기록된 feature 생성 DSL/SQL 을 정적 분석.
- 기준: feature 의 모든 원천 컬럼에 대해 `timestamp <= snapshot_date - features_cutoff_before_days` 보장.
- target 컬럼과 동일/동의 컬럼이 feature 목록에 있으면 leakage 판정.
- Train/test split 의 시간순 정렬 여부 검사.

**산출**: 위반 0건 → 1.0. 위반 N건 → `max(0, 1 - 0.25 * N)`. 판정 근거는 `evidence_refs` 에 위반한 feature 이름/SQL 포함.

**deterministic 으로 설계한 이유**: leakage 는 재현 가능한 규칙 위반이며 LLM judge 는 오탐/미탐 모두 불안정.

### 5.4 tool_trajectory (deterministic)

**질문**: 도구 호출 순서와 선택이 적절했는가?

**판정 로직**:
- Run 의 `tool_calls` 시퀀스 분석.
- 하위 metric:
  - `redundant_call_ratio`: 동일 인자 반복 호출.
  - `failed_call_ratio`: 오류 반환 호출.
  - `order_violations`: 도메인 규칙 위반 (예: `train_model` 이 `build_features` 없이 선행).
  - `budget_overshoot`: tool cost 합 vs `budget_usd`.
- Output: `1 - weighted_sum(violation_ratios)`.

### 5.5 artifact_faithfulness (LLM-judge)

**질문**: 산출물(노트북 셀 출력, 차트, 표)이 실제 데이터/모델 결과와 일치하며, 본문 주장과 부합하는가?

**판정 로직**:
- Run 에서 final artifact (EDA 리포트, 모델 스코어카드 등) 추출.
- LLM judge 에게 `(artifact_rendered, underlying_metrics, narrative)` 전달.
- 판정 항목:
  - 수치 일치성: 본문 문장에 등장한 수치가 표/로그와 일치.
  - 차트 해석 정합성.
  - 과장/축소 표현 탐지.
- 위반 건별로 감점.

**보조 deterministic check**: 모든 본문 수치를 `\d+(\.\d+)?%?` 정규식으로 추출 → underlying metrics 내 매칭 확인 → 미매칭이면 LLM judge 에 보고.

### 5.6 exec_summary_accuracy (LLM-judge)

**질문**: executive summary 가 과장/축소 없이 핵심 결론, 한계, 다음 액션을 정확히 요약하는가?

**판정 로직**:
- 필수 슬롯: `core_finding`, `confidence`, `limitations`, `recommended_action`.
- LLM judge 가 각 슬롯의 존재/정확성을 0–1 평가.
- 추가 deterministic check: `limitations` 섹션 부재 또는 길이 < 20자 이면 상한 0.5.

### 5.7 approval_judgment (hybrid)

**질문**: 승인 필요 여부(policy gate)를 올바르게 판정했는가?

**판정 로직**:
- **Deterministic**: `task.validation_points.approval_required` 에 열거된 액션 각각에 대해 agent 가 `approval_requested == True` 였는지 검사. 누락 → 심각 감점.
- **LLM**: agent 가 불필요한 승인 요청을 남발했는지(spam 감지) 평가.

### 5.8 session_completeness (hybrid)

**질문**: 업무가 완결되었는가? 반쪽 분석이 아닌가?

**판정 로직**:
- **Deterministic**: `expected_deliverables` 각 항목의 존재 여부 체크리스트.
- **LLM**: deliverable 이 존재하지만 비어있거나 placeholder 인 경우를 탐지.
- 합산: `produced_count / expected_count * quality_mult` 여기서 quality_mult 는 LLM 평가.

### 5.9 operator_satisfaction (human rubric + proxy)

**질문**: 사용자가 추가 작업 없이 결과를 쓸 수 있었는가?

**판정 로직**:
- **Human mode**: 리뷰어가 1–5 Likert + 선택 코멘트 입력.
- **Proxy mode**: human rubric 이 없을 때는 proxy scorer 로 대체. Proxy 는 다음 신호 기반:
  - Run 이후 같은 세션에서 사용자가 재질문/수정요청 이벤트를 발생시켰는가(부정).
  - `approve_final` 이벤트 유무(긍정).
  - 동일 요청을 수동 개입으로 재실행했는가(부정).
- Proxy 는 human rubric 이 도착하면 덮어쓰기(human 우선).

### 5.10 time_to_decision (deterministic)

**질문**: 사용자가 의사결정할 수 있는 상태(final summary + 승인 요청/완료)까지 걸린 시간.

**판정 로직**:
- `elapsed_min = first_decision_ready_event_ts - run_started_at`.
- 정규화: `score = clamp(1 - max(0, elapsed_min - target) / target, 0, 1)` 여기서 target 은 `task.input.time_budget_min`.

### 5.11 요약표

| # | Scorer | Judge Type | 주요 입력 | 안정성 전략 |
|---|--------|------------|-----------|-------------|
| 1 | scoping_accuracy | LLM | GoalBrief | prompt 버전 고정, meta-test |
| 2 | metric_selection_accuracy | Hybrid | metric_choices | deterministic filter + LLM |
| 3 | temporal_leakage_detection | Deterministic | feature DSL, SQL | 정적 분석 |
| 4 | tool_trajectory | Deterministic | tool_calls | 위반율 집계 |
| 5 | artifact_faithfulness | LLM | artifacts | 수치 regex 보조 |
| 6 | exec_summary_accuracy | LLM | executive_summary | 슬롯 체크 |
| 7 | approval_judgment | Hybrid | approval events | deterministic 우선 |
| 8 | session_completeness | Hybrid | deliverables | 체크리스트 + LLM |
| 9 | operator_satisfaction | Human+Proxy | review event | human 우선 |
| 10 | time_to_decision | Deterministic | timestamps | 정규화 공식 |

---

## 6. Evaluation Modes

### 6.1 Mode A — Offline (Gold Task Set 회귀)

- 배치 실행: `ds-agent eval run --suite gold --concurrency 4`.
- 결정적이어야 한다: 동일 commit, 동일 Gold Task, 동일 seed 에서 점수 분산 <= 0.02 목표.
- 실행 결과는 `EvalRun` 으로 저장, `RegressionBoard` 에 시계열 플롯.
- CI 통합: main 브랜치 nightly + PR 라벨 `run-eval` 시 실행.

### 6.2 Mode B — Shadow

- 실제 사용자 요청이 도착하면, 동일 요청을 별도 프로세스에서 shadow agent 에 전달.
- Shadow 결과는 사용자에게 노출되지 않음 (silent).
- 사람이 만든 결과(real run 의 reviewer output) 와 shadow agent 산출물을 비교.
- 사용 사례:
  - 새 모델/프롬프트 후보를 production 배포 전 실제 분포에서 테스트.
  - Gold Task 에 포착되지 않는 도메인 분포 편차 감지.
- 비용 가드: shadow 는 `budget_usd * shadow_factor (default 0.5)` 상한.

### 6.3 Mode C — Online (부분 scorer 적용)

- production 실행 trace 에 대해 deterministic scorer 는 자동 적용:
  - temporal_leakage_detection
  - tool_trajectory
  - time_to_decision
  - approval_judgment (deterministic 부분)
- LLM-judge scorer 는 sampling (기본 10%) 적용. 비용 제어.
- 결과는 RegressionBoard 의 "Online" 축으로 별도 트랙.

### 6.4 Mode D — Human Rubric

- Reviewer UI(Electron) 에서 각 run 에 대해 1–5 Likert 및 10차원 체크리스트 입력.
- 수집률 KPI 관리. 초기 목표: production run 의 20% 이상.
- Human rubric 은 `EvalDatasetStore` 에 라벨로 축적.

### 6.5 모드 간 관계

```
Offline: controlled dataset, controlled cost,  deterministic regression
Shadow : real dataset,       controlled cost,  A/B 후보 검증
Online : real dataset,       minimal  cost,    운영 모니터링
Human  : real+offline,       human cost,       진실값 라벨 축적
```

---

## 7. EvalDataset 저장 구조

### 7.1 축적 데이터

각 `EvalDatasetRecord` 는 다음을 포함한다:

- `record_id: uuid`
- `source_mode: offline|shadow|online|human`
- `session_id: str` (production link)
- `task_ref: str | null` (offline/shadow 일 때 GoldTask id)
- `run_snapshot: EvalRun` (tool_calls, artifacts refs, timestamps 요약)
- `scorer_outputs: list[EvalScore]`
- `human_rubric: HumanRubric | null`
- `created_at`, `commit_sha`, `model_version`, `prompt_version`

### 7.2 저장 매체

- `evaluation/eval_dataset_store.py` 가 port interface 를 정의.
- 기본 구현: append-only JSONL + parquet snapshot(주기적).
- 대용량 artifact 는 외부 blob 스토어(기존 run_registry 의 blob 계층 재사용) 참조.

### 7.3 불변성 원칙

- Record 는 수정 불가. human rubric 추가 시 새 record 를 상위 record 로 링크.
- scorer 버전 업그레이드는 기존 record 를 삭제하지 않고 `rescored_at` 파생 record 생성.

---

## 8. Regression Board

### 8.1 데이터 모델

- x축: `commit_sha` 또는 `date`
- y축: 차원별 평균 score, weighted pass rate
- facet: domain, difficulty, task_id

### 8.2 알림 규칙

| 규칙 | 조건 | 액션 |
|------|------|------|
| Gold suite pass rate drop | 최근 3회 연속 평균이 baseline - 3% 하회 | Slack #ds-agent-alerts |
| Per-dimension regression | 특정 차원 점수가 baseline - 5% 하회 | PR 라벨 `eval-regression` 자동 부착 |
| Single task hard-fail | 과제 점수가 `pass_threshold` 미달 | nightly 요약에 포함 |
| Online mode drift | online score 가 offline score 대비 10%p 이상 | 분포 편차 조사 티켓 생성 |

### 8.3 Baseline 산정

- Baseline 은 최근 14일 중앙값. 단, 첫 2주간은 Phase 1 마지막 안정 버전 고정.
- Baseline 갱신은 수동 "freeze" 커맨드로만: `ds-agent eval board freeze-baseline`.

---

## 9. Run Scorecard (사용자 대면 UI)

Electron `components/runtime/RunScorecard.tsx`.

### 9.1 표시 항목

| 영역 | 항목 | 데이터 소스 | 배지 규칙 |
|------|------|-------------|-----------|
| Task 계약 준수 | deliverables 체크리스트 | session_completeness (deterministic) | 5/5 → green, 부족 시 yellow/red |
| Verifier 결과 | Statistical / Data / Policy / Narrative | 기존 verifier 모듈 | PASS/WARN/FAIL 배지 |
| Confidence | 0–1 | scoring_rubric weighted sum | High>=0.8 / Med>=0.6 / Low |
| Tool trajectory | 총 호출수, redundant, failed | tool_trajectory scorer | redundant>0 → yellow |
| Time-to-decision | 소요 분 vs target | time_to_decision scorer | 초과 시 yellow |
| Budget 소비 | $ 소비 vs 상한 | run_registry | >80% → yellow |
| 사용자 만족 | 리뷰어 점수 | operator_satisfaction (human) | 미수집이면 "pending" |
| 차원별 세부 | 10 dimensions expand | scorer_outputs | rationale tooltip |

### 9.2 UX 원칙

- 점수는 **설명 가능해야 한다**: 클릭 시 rationale + evidence_refs 로 drill-down.
- 점수는 **반박 가능해야 한다**: 사용자가 "disagree" 버튼으로 human rubric 수정 입력.
- 점수는 **대조 가능해야 한다**: 동일 세션 내 이전 run 과 비교 가능한 diff view.

---

## 10. Clean Architecture 매핑

`evaluation/` 는 별도 최상위 패키지로 분리한다. 기존 `domain/`, `application/`, `infrastructure/` 와 수평 관계이되, **domain 참조만 허용**한다. Domain 엔티티를 import 할 수 있지만 application/infrastructure 내부 구현에 의존해서는 안 된다.

```
evaluation/
├── domain/
│   ├── entities/
│   │   ├── gold_task.py        # GoldTask
│   │   ├── eval_run.py         # EvalRun
│   │   ├── eval_score.py       # EvalScore
│   │   └── human_rubric.py     # HumanRubric
│   ├── value_objects/
│   │   ├── judge_type.py
│   │   └── score_value.py      # bounded [0,1]
│   ├── errors/
│   │   └── evaluation_errors.py
│   └── ports/
│       ├── scorer.py           # Scorer protocol
│       ├── eval_dataset_store.py
│       ├── trace_reader.py
│       └── judge_llm.py
│
├── application/
│   ├── use_cases/
│   │   ├── run_eval_batch.py
│   │   ├── score_run.py
│   │   ├── ingest_human_rubric.py
│   │   ├── ingest_production_trace.py
│   │   └── update_regression_board.py
│   ├── dtos/
│   │   ├── eval_request_dto.py
│   │   └── eval_report_dto.py
│   └── services/
│       └── alerting_service.py
│
├── infrastructure/
│   ├── scorers/
│   │   ├── base.py
│   │   ├── scoping_accuracy.py
│   │   ├── metric_selection_accuracy.py
│   │   ├── temporal_leakage_detection.py
│   │   ├── tool_trajectory.py
│   │   ├── artifact_faithfulness.py
│   │   ├── exec_summary_accuracy.py
│   │   ├── approval_judgment.py
│   │   ├── session_completeness.py
│   │   ├── operator_satisfaction.py
│   │   └── time_to_decision.py
│   ├── gold_tasks/
│   │   ├── loader.py            # YAML -> GoldTask
│   │   └── tasks/
│   │       ├── retail/*.yaml
│   │       ├── finance/*.yaml
│   │       └── ops/*.yaml
│   ├── persistence/
│   │   └── jsonl_eval_dataset_store.py
│   ├── ingestion/
│   │   └── session_registry_trace_reader.py
│   ├── judges/
│   │   └── anthropic_judge_llm.py
│   ├── cli/
│   │   └── eval_cli.py
│   └── regression_board/
│       ├── board_builder.py
│       └── alerting_adapter.py
│
└── presentation/
    └── electron_bridge/
        ├── scorecard_payload.py
        └── regression_payload.py

test/
├── unit/evaluation/
│   ├── domain/
│   └── application/
└── integration/evaluation/
    ├── infrastructure/
    └── end_to_end/
```

**의존성 규칙**:
- `evaluation/domain` → 외부 라이브러리 없음 (dataclass/pydantic 선택 가능하되, dataclass 권장).
- `evaluation/application` → `evaluation/domain` 과 DS domain 엔티티 일부(GoalBrief 등) 만 참조.
- `evaluation/infrastructure` → application + domain 에 대한 adapter.
- self_improve 는 evaluation/application 의 use case 를 주입받아 사용 (역방향 import 금지).

---

## 11. 주요 도메인/유스케이스

### 11.1 GoldTask (Entity)

```python
@dataclass(frozen=True)
class GoldTask:
    id: str
    task_version: int
    domain: str
    difficulty: Literal["easy", "medium", "hard"]
    prompt: str
    input: GoldTaskInput
    expected_deliverables: tuple[ExpectedDeliverable, ...]
    validation_points: ValidationPoints
    baseline: Baseline
    scoring_rubric: ScoringRubric
    pass_threshold: float
    alert_on_drop_below: float
```

Invariants:
- `sum(weights for scorers in scoring_rubric) == 1.0 (±1e-6)`
- `pass_threshold >= alert_on_drop_below`
- `task_version >= 1`

### 11.2 EvalRunner (Use Case)

```python
class RunEvalBatch:
    def __init__(
        self,
        orchestrator: OrchestratorPort,
        scorer_registry: ScorerRegistry,
        eval_store: EvalDatasetStore,
        trace_reader: TraceReaderPort,
    ): ...

    def execute(self, request: EvalBatchRequest) -> EvalBatchReport: ...
```

흐름:
1. `GoldTaskLoader` 로 suite 로드.
2. 각 task 를 `OrchestratorPort.run_task(task)` 로 실행 → `EvalRun` 획득.
3. 등록된 모든 scorer 병렬 적용 → `EvalScore` 리스트.
4. `EvalDatasetStore.append(EvalDatasetRecord(...))`.
5. 집계 리포트 반환.

### 11.3 Scorer Port Interface

```python
class Scorer(Protocol):
    name: str
    version: str
    judge_type: JudgeType

    def score(self, run: EvalRun, task: GoldTask) -> EvalScore: ...
```

- Scorer 는 **반드시 순수 함수에 가까워야** 한다. 외부 I/O 는 judge LLM 호출로 한정.
- Scorer 는 `version` 을 bump 하면 새 Scorer 로 취급되고, regression board 는 별도 시리즈.

### 11.4 run_eval_batch (Use Case)

- Input: `EvalBatchRequest(suite, concurrency, scorer_filters, mode)`.
- Output: `EvalBatchReport(total, passed, failed, per_task_scores, per_dimension_means, regressions)`.
- Side effect: EvalDatasetStore 에 append, RegressionBoard 갱신 이벤트 publish.

### 11.5 ingest_human_rubric (Use Case)

- Input: `IngestRubricRequest(session_id, reviewer_id, rubric)`.
- 처리:
  - 기존 record 조회.
  - `HumanRubric` 검증 (모든 필수 차원 입력 여부).
  - operator_satisfaction 차원을 human 값으로 override, proxy 값 보존.
  - 상위 record 생성.
- 보안: reviewer_id 인증, 자기 자신이 생성한 run 을 점수매기는 self-review 방지 정책.

### 11.6 ingest_production_trace (Use Case)

- Input: `session_id`.
- 처리:
  - session_registry / run_registry 에서 trace 획득.
  - Online-safe scorer 만 적용 (deterministic + sampled LLM).
  - EvalDatasetStore 에 mode=online 으로 append.

---

## 12. Production Trace → Eval Dataset 파이프라인

### 12.1 전체 흐름

```
[Production Run]
   |
   v
runtime/session_registry.py  ──┐
runtime/run_registry.py     ──┤  (기존 저장)
                              │
                              v
evaluation/infrastructure/ingestion/session_registry_trace_reader.py
                              │
                              v
ingest_production_trace use case
                              │
  ┌──────────────────────────┼──────────────────────────┐
  v                          v                          v
deterministic scorers   sampled LLM scorers       review event watcher
  │                          │                          │
  └──────────────┬───────────┘                          │
                 v                                      v
       EvalDatasetStore.append(mode=online)     human rubric 저장
                 │                                      │
                 └──────────────┬───────────────────────┘
                                v
                       RegressionBoard (online track)
                                v
                       self_improve 승격 gate
```

### 12.2 Trigger 정책

- production run 이 완료되면 `run.finalized` 이벤트가 발생.
- 이벤트 구독자 `ProductionTraceIngestor` 가 수신 → use case 호출.
- LLM-judge scorer 는 reservoir sampling (10%) + 도메인 stratification.

### 12.3 Review Event Tagging

- 기존 session_registry 의 approve/reject/modify 이벤트를 수집.
- Reviewer UI 에서 10차원 rubric 입력 시 별도 이벤트 발행.
- `ingest_human_rubric` 이 event → record 매핑.

### 12.4 개인정보/민감정보 처리

- production trace 에는 실데이터 프롬프트/결과가 포함된다.
- Eval dataset 저장 시 PII scrubber 파이프를 통과(기존 infrastructure 재사용).
- 저장 위치는 prod blob 과 분리된 eval bucket. 접근권한 별도.

---

## 13. CLI / CI 통합

### 13.1 CLI

- `ds-agent eval run --suite gold [--domain retail] [--concurrency N] [--mode offline]`
- `ds-agent eval score-run --session-id <id> [--scorer temporal_leakage_detection]`
- `ds-agent eval ingest-human --session-id <id> --rubric-file path.yaml`
- `ds-agent eval board snapshot`
- `ds-agent eval board freeze-baseline --commit <sha>`

### 13.2 GitHub Actions

`.github/workflows/eval-nightly.yml`:

```yaml
name: eval-nightly
on:
  schedule:
    - cron: "0 18 * * *"
  workflow_dispatch:
jobs:
  offline-suite:
    steps:
      - checkout
      - setup python, install
      - run: ds-agent eval run --suite gold --concurrency 4
      - run: ds-agent eval board snapshot
      - upload artifact (EvalBatchReport JSON)
      - post summary to PR / Slack on regression
```

추가 PR 워크플로우: label `run-eval` 부착 시 축약 suite(small 도메인) 실행.

### 13.3 self_improve 게이트

- self_improve 가 새 pattern/skill 을 생성하면 `pending_promotion` 상태로 저장.
- `ds-agent eval run --suite gold --with-candidate <id>` 로 후보 포함 회귀.
- baseline 대비 weighted score 가 `-delta_threshold` 미만 하락이면 자동 promote, 그 이상이면 block.

---

## 14. UX — Electron 목업

### 14.1 RunScorecard

- 상단: 과제 개요 (prompt 요약, domain, duration, budget).
- 중앙: 10차원 radar chart (현재 run vs baseline).
- 하단: 차원별 카드.
  - 카드 펼치면 rationale, evidence refs, 관련 artifact 링크.
- Footer: "Disagree with this score" 버튼 → human rubric 입력 폼.

### 14.2 RegressionDashboard

- 왼쪽 사이드바: domain / suite 필터.
- 메인: weighted pass rate 시계열 + 차원별 small multiples.
- 상단 알림 스트립: 최근 regression 이벤트.
- 우측 패널: 선택된 commit 의 diff view (이전 실행 대비 변한 차원 하이라이트).

---

## 15. 구현 Phases (TDD)

### Phase P1 — 기초 (Gold Task + 10 scorer + Scorecard)

목적: 내부 회귀 체계 최소 기능.

현재 상태(2026-04-16):

- 완료
  - evaluation 패키지 골격
  - Gold task YAML loader
  - scorer 10종 초기 버전
  - `ScoreRun`, `RunEvalBatch`
  - `IngestProductionTrace`
  - JSONL eval dataset store
  - `SessionTraceReader` + `ProductionTaskAdapter`
  - `ds-agent eval` CLI 초기 경로 (`validate-suite`, `score-run`, `run`, `ingest-session`)
  - unit/integration test 최소 세트
- 미완료
  - 실제 orchestrator live/offline execution bridge 고도화
  - Scorecard UI payload bridge
  - nightly CI 워크플로우

- RED
  - `tests/unit/evaluation/domain/test_gold_task.py`: invariants.
  - 10 개 scorer 각각에 대해 meta-test: known good run(≥0.85), known bad run(≤0.30) fixture.
  - `tests/unit/evaluation/application/test_run_eval_batch.py`.
- GREEN
  - Domain entities, ports.
  - Gold task YAML loader + 초기 과제 6개 (retail 2, finance 2, ops 2).
  - 10 scorer 구현. LLM-judge 는 stub judge 로도 통과 가능하게 설계(judge port).
  - `run_eval_batch` use case, JSONL EvalDatasetStore.
  - CLI: `eval run`, `eval score-run`.
  - Electron RunScorecard 컴포넌트(정적 데이터 기반).
- REFACTOR
  - scorer 공통 로직(점수 정규화, evidence 포맷) 추출.
  - judge prompt 버전 관리 파일 구조화.
- 완료 기준: nightly CI 에서 offline suite 가 안정적으로 통과, 점수 분산 <=0.02.

### Phase P2 — Shadow eval + Human rubric

- RED
  - shadow runner fixture 기반 테스트: 동일 입력에 대해 production/shadow 분기.
  - `ingest_human_rubric` use case 테스트(권한, 검증, override 규칙).
- GREEN
  - Shadow 실행 브릿지, budget 가드.
  - Reviewer UI(Electron) 에 10차원 rubric 입력 폼.
  - `eval ingest-human` CLI.
  - operator_satisfaction scorer 의 human/proxy 분기.
- REFACTOR
  - trace reader 와 shadow runner 공통 시나리오 코드 정리.
- 완료 기준: production run 의 20% human rubric 수집 가능, shadow 모드로 후보 프롬프트 A/B 가능.

### Phase P3 — Regression Board + 자동 알림

현재 상태(2026-04-16):

- landed
  - Regression Board snapshot / payload / Electron read path
  - frozen baseline persistence (`JsonRegressionBaselineStore`)
  - `ds-agent eval board freeze-baseline --commit <sha>`
  - frozen baseline aware board snapshot / WebSocket payload (`baseline_source`, `frozen_baseline`)
  - regression rule 테스트 (drop below, per-dim regression)
- remaining
  - none. Current P3 feature scope is implemented end-to-end.

- RED
  - regression rule 테스트 (drop below, per-dim regression 탐지).
  - alerting adapter contract test.
- GREEN
  - board_builder: 시계열 집계.
  - alerting_adapter: Slack/Teams webhook.
  - Electron RegressionDashboard.
  - self_improve 승격 게이트 연결 (`--with-candidate`).
- REFACTOR
  - baseline 계산 로직 전략 패턴화.
- 완료 기준: 의도적으로 score 를 떨어뜨리는 PR 이 차단되는 시연. self_improve 승격 블록 시연.

---

## 16. 테스트 전략

### 16.1 Scorer meta-test

- 각 scorer 는 `fixtures/eval/<scorer>/good_run.json`, `bad_run.json` 을 가진다.
- 기대 범위를 assert: good ≥ T_hi, bad ≤ T_lo.
- LLM-judge scorer 의 경우, judge 를 deterministic stub judge 로 대체하여 결정적 테스트 + 별도 smoke test 에서 실제 LLM 호출.

### 16.2 Gold Task smoke

- 각 Gold Task YAML 은 로딩/검증 테스트 필수.
- `pass_threshold` 기준 더미 run 으로 passing path 확인.

### 16.3 EvalDatasetStore contract

- append-only, record 불변성, 재스코어 시 파생 record 규칙.

### 16.4 End-to-End

- minimal suite(2 tasks) 전체 파이프라인: run → scorer → store → board snapshot.

### 16.5 커버리지 목표

- evaluation/domain: >=95%
- evaluation/application: >=90%
- evaluation/infrastructure/scorers: >=85%
- evaluation/infrastructure/cli: >=70%

---

## 17. 의존성 및 통합 지점

| 통합 대상 | 방향 | 설명 |
|-----------|------|------|
| runtime/session_registry.py | read | ingest_production_trace 에서 세션 조회 |
| runtime/run_registry.py | read | tool_calls, artifact refs, timestamps |
| self_improve | read+gate | 후보 승격 gate 로 eval batch 요청 |
| domain/GoalBrief 등 | read | scorer 가 엔티티 접근 (읽기 전용) |
| Electron runtime UI | publish | scorecard_payload, regression_payload |
| Reviewer Auth | read | human rubric 기록자 식별 |
| Anthropic judge LLM | external | LLM-judge scorers |

역방향 의존 금지:
- session_registry/run_registry 가 evaluation 을 import 해서는 안 된다.
- self_improve 는 evaluation 의 use case 인터페이스에만 의존하고, scorer 구현을 직접 import 하지 않는다.

---

## 18. 성공 기준 (DoD)

- **회귀 커버리지**: Gold Task 24+ 개, 3 도메인 × easy/medium/hard 분포 충족.
- **리뷰어 점수 수집률**: production run 의 20% 이상에서 human rubric 수집.
- **스코어 안정성**: 동일 commit/task/seed 재실행 간 weighted score 분산 <= 0.02.
- **회귀 감지 지연**: 의도적 regression 주입 시 첫 nightly 내 알림 발화.
- **self_improve 게이트 적용률**: 신규 pattern/skill 의 100% 가 eval gate 를 통과해야 promote.
- **UX 노출**: 모든 production run 이 Run Scorecard 에 최소 deterministic 차원 + verifier 상태로 표시.
- **문서/온보딩**: 새 과제 기여 가이드 1페이지, scorer 기여 가이드 1페이지.

---

## 19. 리스크 및 롤백

### 19.1 리스크 테이블

| 리스크 | 확률 | 영향 | 완화 |
|--------|------|------|------|
| LLM-judge 불안정성 | High | Med | prompt version 고정, temperature=0, meta-test, majority vote 옵션 |
| Gold Task 편향 | Med | High | 도메인 전문가 검수, shadow 분포 비교 모니터링 |
| 평가 비용 폭증 | Med | Med | LLM scorer sampling, budget 가드, concurrency 제한 |
| self_improve 게이트 오판 | Med | High | `--with-candidate` 결과를 사람이 확인할 수 있는 요약 PR 코멘트 제공 |
| PII 누출 | Low | High | eval bucket 분리, scrubber 적용, 접근 감사 로그 |
| Shadow 비용 폭증 | Med | Med | shadow_factor 상한, 도메인별 sampling |
| Scorer 버전 혼재 | Low | Med | version bump 규칙, regression board 별도 시리즈 |

### 19.2 롤백 전략

- Phase P1 실패 시: scorer 패키지와 CLI 만 제거. Domain/port 는 보존(향후 재시도 대비).
- Phase P2 실패 시: shadow runner feature flag off. human rubric 은 선택적이므로 유지 가능.
- Phase P3 실패 시: alerting/게이트 기능만 disable. board 는 read-only 로 유지.
- 긴급 롤백 플래그: `EVAL_HARNESS_ENABLED=false`. 모든 ingest 경로가 no-op.

---

## 20. Open Questions

1. **Judge LLM 선택**: scoping_accuracy/artifact_faithfulness 에 동일 family 모델을 judge 로 쓸 경우 self-preference bias. 독립 벤더 judge 를 혼합할지?
2. **Shadow 동의 범위**: 사용자 요청을 shadow 로 재실행하는 것에 대해 사용자 동의/옵트아웃 정책 수준은?
3. **Human rubric 인센티브**: 20% 수집률을 달성하기 위한 UX 넛지와 운영 프로세스는?
4. **Gold Task freshness**: 시간이 지나 도메인 분포가 변하면 Gold Task 가 실사용을 대변하지 못한다. 정기 리프레시 주기와 소유권 모델은?
5. **Proxy operator_satisfaction 의 신뢰성**: 재질문 신호를 부정으로 쓰는 것이 실제로 타당한지 실증 필요.
6. **Weighted score vs Pareto**: 단일 weighted score 를 primary 지표로 쓰는 대신, 10차원 Pareto frontier 를 기본으로 하는 것이 학습 시그널로 더 유용할 수 있음.
7. **평가 결과의 사용자 노출 범위**: Run Scorecard 의 모든 차원을 무조건 노출할지, 내부 전용 차원을 분리할지.
8. **Scorer 기여 경로**: 외부 기여자가 새 scorer 를 제안할 수 있는 contribution 절차 필요.
9. **다국어 judge**: 한국어 과제/결과에 대한 judge 품질 검증 프로토콜.
10. **운영자 만족 Likert 와 비즈니스 성과 상관**: operator_satisfaction 점수가 실제 다운스트림 비즈니스 지표와 얼마나 상관 있는지 장기 검증 계획.
