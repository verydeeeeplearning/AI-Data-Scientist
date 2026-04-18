# 06. Decision OS — 재현성 및 실험-배포 폐쇄 루프

> 본 문서는 `Docs/ds-agent-enhancement-roadmap.md` §6 "Decision OS"를 구현 착수 가능한 수준으로 상세화한 스펙이다. Feature Registry, Experiment Tracker 확장, Model Registry, Run Diff Engine, Promotion Gate, Post-Deploy Monitor를 도입하여 "실험 → 비교 → 승격 → 모니터링 → 재학습/롤백"의 폐쇄 루프(closed loop)를 형성하고, 내부 prompt asset에 머물러 있던 shared skill을 사용자 대면 Review Tab으로 승격한다.

Latest update (2026-04-16): Phase 1 is complete, Phase 2 foundation is landed, Phase 3 run-diff core is in code, Phase 4 model-registry/promotion-gate foundation is landed, and the Phase 5 post-deploy automation path plus daemon-wide scheduler registration are now landed. The repo now has `Feature` domain entities, feature-registry errors/ports, a YAML loader, a SQLite-backed `SqliteFeatureRegistryStore`, `RegisterFeatureUseCase`, `FeatureRegistryContainer`, and the `register_feature` tool, plus typed `ExperimentRun` / `DiffableRun` entities, structured `ExperimentLog.record_extended()`, `get_run()`, `list_runs()`, and `to_diffable()` paths, deterministic `RunDiff` entities, `RunDiffEngine`, the `compare_runs` tool, `Model` / `PromotionDecision` entities, SQLite-backed model-registry and promotion-decision stores, a YAML rollback-plan loader, `PromotionGate`, the `request_promotion` tool, `PostDeploySnapshot` / `PostDeployMonitorState` entities, a SQLite-backed deploy-monitor store, a runtime `PostDeployMonitor`, workspace snapshot ingestion, runtime alert emission, `DecisionOsMonitorScheduler`, environment-driven trigger policies, automatic candidate retrain creation, automatic rollback execution via the promotion gate, and daemon startup/tick wiring that auto-registers and executes the monitor from `AutonomousDaemon`. Verification currently includes a targeted **9 passed** Phase 1 suite, a **22 passed** experiment-tracker compatibility suite, a **26 passed** run-diff suite, a **15 passed** promotion-gate suite, a **16 passed** post-deploy automation suite, a **27 passed** daemon/runtime integration suite, and a combined **66 passed** Decision OS regression suite with daemon wiring. Review Tab/UI surfaces in this spec are still pending.

Latest update addendum (2026-04-16): Phase 6 review-surface foundation is now landed. The repo now also has WebSocket `decisionOs.overview`, `decisionOs.compareRuns`, `decisionOs.requestPromotion`, and `decisionOs.getPostDeployStatus` handlers in `api/ws_handler.py`, AppState-backed Decision OS container access for those RPC paths, runtime-event emission for review-triggered promotion requests, targeted API coverage for the new surface, and an Electron Sidebar `Review` tab with overview, run-diff, promotion-request, and post-deploy monitor panels wired through the shared WebSocket provider. Verification for this increment includes a targeted **4 passed** Decision OS review API suite, `ruff check`, `ruff format --check`, and Electron `npm run typecheck`. Structured shared-skill `review_artifacts_json` persistence and dedicated modal/card polish remain pending.

Latest update addendum (2026-04-16): Phase 6 now also has shared-skill review-artifact persistence and Review-card rendering landed. The repo now also has typed `ReviewArtifact` domain entities for `backtesting`, `causal-assumption-check`, `uncertainty-quantification`, and `retrain-vs-rollback`, `ExperimentRun.review_artifacts`, JSONL `review_artifacts_json` persistence with upsert/read paths in `ExperimentLog`, Decision OS review-artifact use cases plus `record_review_artifact` / `get_review_artifacts` tool bindings, targeted API coverage that seeds and returns stored review artifacts, and an Electron `ReviewTab` section that renders stored shared-skill cards with missing-artifact placeholders for gaps. Verification for this increment includes a targeted **15 passed** Decision OS review-artifact suite, `ruff check`, `ruff format --check`, targeted `mypy`, and Electron `npm run typecheck`. Remaining Phase 6 scope is automatic prompt/hook capture of shared-skill outputs plus dedicated modal polish.

Latest update addendum (2026-04-16): Phase 6 now also has automatic shared-skill prompt/hook capture landed. The repo now also has a hidden `DS_REVIEW_ARTIFACTS` response contract, typed parsing and cleanup for machine-readable review-artifact payloads, a new final-response hook stage in `agent/hooks.py`, a built-in `ReviewArtifactCaptureHook` wired through the default agent factory, and automatic persistence of captured shared-skill artifacts into the matching Decision OS experiment runs while stripping the hidden block from the visible assistant response. Verification for this increment includes targeted capture suites at **4 passed** and **4 passed**, plus `ruff check`, `ruff format --check`, and targeted `mypy`. Remaining Phase 6 scope is dedicated modal/card polish.

Latest update addendum (2026-04-16): Phase 6 now also has dedicated modal/card polish landed. The repo now also has shared Decision OS review UI model/primitives in Electron, a dedicated `SharedSkillReviewPanel`, a dedicated `RunDiffPanel`, a dedicated `PromotionGateModal`, richer run-diff detail cards, promotion-gate modal launch from both overview and run-diff surfaces, and a proper narrative toggle for shared-skill review cards instead of always-expanded text. Verification for this increment includes Electron `npm run typecheck` and `npm run build`. Remaining explicit quality-gate scope for full Phase 6 completion is the end-to-end Decision OS review flow scenario.
Latest update addendum (2026-04-16): Phase 6 now also has the explicit review-flow quality gate landed. The repo now also has WebSocket `decisionOs.resolvePromotion` and `decisionOs.applyPromotion` handlers in `api/ws_handler.py`, AppState wiring for approval-step resolution plus approved-decision alias application, an `ApplyPromotionUseCase` in the promotion gate, an Electron Review-tab apply CTA for approved decisions, and a targeted full-flow regression that executes `compareRuns -> requestPromotion -> resolvePromotion x3 -> applyPromotion -> post-deploy sweep -> getPostDeployStatus` with runtime-event assertions. Verification for this increment includes new promotion-apply unit coverage, targeted Decision OS API review-flow coverage, `ruff check`, `ruff format --check`, targeted `mypy`, and Electron `npm run typecheck`.
Latest update addendum (2026-04-16): Phase 6 now also has the packaged-backend Review-tab smoke quality gate landed. The repo now also has isolated Decision OS workspace seeding via `scripts/seed_decision_os_e2e_workspace.py`, an Electron smoke flow in `electron/tests/smoke/decision-os-review.spec.ts`, stable Review-tab test ids across overview / shared-skill / diff / promotion / post-deploy panels, a `PromotionGateModal` refresh-state fix so successful requests do not clear their result panel on overview refresh, and a hardened `DriftAnalyzer` import path that no longer requires `numpy` / `pandas` / `scipy` at packaged-backend module-import time. Verification for this increment includes targeted drift/post-deploy suites at **8 passed**, targeted Decision OS API suites at **6 passed**, `ruff check`, `ruff format --check`, `python scripts/build_backend.py`, targeted `mypy` for `src/ds_agent/application/services/drift_analyzer.py`, Electron `npm run typecheck`, and `npm run test:e2e:decision-os`. Broader `api/ws_handler.py` mypy debt remains outside this increment.
Latest update addendum (2026-04-16): Section 21 open questions are now closed with explicit design defaults. Decision OS will use git-backed Feature Registry YAML as the canonical source of truth with local SQLite/runtime caches, no internal mini A/B store, `manual_only` as the default automation posture, sampled snapshot-based drift computation inside the DS Agent runtime, URI-based external artifact storage, duplicate approvers allowed for small-team approval chains, gate-time reproducibility plus limited nightly checks for deployed aliases, finite retired-artifact retention with indefinite metadata retention, mandatory `schema_version` on review artifacts, and dry-run-first rollback validation without requiring mirrored traffic. There are no remaining design blockers inside the current `06` scope.

---

## 1. 배경 및 문제 정의 — "좋은 분석보다 다시 돌릴 수 있는 분석"

### 1.1 현재 상태

- `memory/experiment_log.py`: 실험 결과를 SQLite에 기록하지만 "입력 feature 스냅샷", "동일 조건 재실행", "버전 간 비교"가 구조화되어 있지 않다.
- `memory/project_store.py`: 프로젝트/대화 단위 아티팩트만 보관하며, 모델·피처·실험의 lineage를 추적하지 않는다.
- `skills/shared/`: `backtesting`, `causal-assumption-check`, `uncertainty-quantification`, `retrain-vs-rollback` 스킬이 존재하지만 LLM prompt asset에 그쳐 사용자가 그 결과를 재확인하거나 의사결정에 활용하기 어렵다.
- Electron 앱에는 "지금 실행"과 "단일 결과"만 있고, "지난주와 무엇이 달라졌나", "이 실험을 production 후보로 올릴까" 같은 의사결정 UI가 없다.

### 1.2 문제

기업 환경에서 분석의 장기 가치는 "분석의 품질"이 아니라 "3개월 뒤에도 동일 조건으로 재현할 수 있는가"에서 나온다. 다음 장면들이 현재 DS Agent에서는 체계적으로 지원되지 않는다.

1. "지난주 `exp_churn_002`와 이번주 `exp_churn_003`의 차이를 보여줘."
2. "이 실험을 production 후보로 승격하고 싶어. 승인 체인과 체크리스트를 정의해줘."
3. "배포 후 2주 동안 metric이 얼마나 변했지? drift 기반 재학습 trigger는?"
4. "동일 입력·동일 config로 지금 다시 돌리면 같은 결과가 나오나?" (point-in-time reproducibility)

### 1.3 목표

- 모든 실험에 대해 **재현 가능성(reproducibility)** 을 1급 시민으로 둔다. 입력 feature 스냅샷, config, 코드 커밋, 난수 seed, 데이터 절단 시각까지 기록.
- 실험 간 **차이(run diff)** 를 기계적으로 계산 가능한 구조로 만든다.
- 실험 → 승격 → 배포 → 모니터링 → 재학습/롤백의 **폐쇄 루프** 를 하나의 도메인 서비스("Decision OS")로 통합한다.
- shared skill을 **Review Tab** 으로 승격하여, LLM이 사람에게 의사결정 근거를 명시적으로 제시한다.

### 1.4 비범위

- 대규모 MLOps 플랫폼(MLflow, Kubeflow, Vertex AI 등) 대체가 아니다. 내부 실험·승격 의사결정을 기록·추적하는 경량 레이어다.
- 실제 배포 인프라(서빙, 오케스트레이션)는 외부 시스템을 가정한다. Decision OS는 "승격 결정"과 "배포 후 신호 수집"만 담당한다.

---

## 2. 핵심 테제

1. **Reproducibility is a feature, not a hope.** 실험은 기본적으로 재현 가능해야 하며, 재현 불가능성은 명시적으로 tagging 된다.
2. **Diff is the primary lens.** 두 실험을 비교할 때, 입력·config·결과·verifier 결과·metric 모두를 한 번에 diff 할 수 있어야 한다.
3. **Promotion is human × policy.** 승격은 정책(자동 게이트) + 사람(승인 체인)의 합성이지, 자동화만으로도, 수동만으로도 충분하지 않다.
4. **Post-deploy feedback closes the loop.** 배포 후 관측한 drift / metric 변화가 다음 실험의 가설로 되돌아와야 한다.
5. **Shared skills are decisions, not asides.** backtesting / causal / uncertainty / retrain-vs-rollback은 요약 한 줄이 아니라, 의사결정 카드로 승격한다.
6. **LLM orchestrates, humans approve.** LLM은 진단·추천·초안을 담당하고, 승격·롤백 결정은 사람의 명시적 승인으로만 발생한다.

---

## 3. 아키텍처 전체 다이어그램

```
┌─────────────────────────────────────────────────────────────────┐
│  Decision OS                                                     │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Feature      │    │ Experiment   │    │ Model        │       │
│  │ Registry     │◄──►│ Tracker      │◄──►│ Registry     │       │
│  │              │    │ (확장)        │    │              │       │
│  │ - 정의/버전  │    │ - hypothesis │    │ - version    │       │
│  │ - transform  │    │ - method     │    │ - alias      │       │
│  │ - source     │    │ - result     │    │ - lineage    │       │
│  │ - stats      │    │ - verifier   │    │ - serve cfg  │       │
│  │ - used_in    │    │ - artifacts  │    │ - snapshot   │       │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘       │
│         └───────────────────┼───────────────────┘                │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Run Diff Engine                                          │    │
│  │  compare(run_a, run_b) → RunDiff                         │    │
│  │   - FeatureSetDiff / ConfigDiff / MetricDelta            │    │
│  │   - VerifierDiff / DataDriftDiff / CodeRefDiff           │    │
│  └──────────────────────┬──────────────────────────────────┘    │
│                         ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Promotion Gate                                           │    │
│  │  evaluate(candidate_run, target_stage) → PromotionDecision│   │
│  │   - Policy checks (metric threshold, verifier PASS)      │    │
│  │   - A/B result injection                                 │    │
│  │   - Rollback plan validation                             │    │
│  │   - Approval chain (DS → Lead → MLOps)                   │    │
│  └──────────────────────┬──────────────────────────────────┘    │
│                         ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Post-Deploy Monitor                                      │    │
│  │  periodic_sweep() → DeployState                          │    │
│  │   - Drift / metric tracking                              │    │
│  │   - Auto-retrain trigger                                 │    │
│  │   - Auto-rollback under condition                        │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘

Consumers (UI / LLM tools)
  - Electron: RunDiffPanel, PromotionGateModal, ReviewTab
  - LLM tools: register_feature, compare_runs, request_promotion,
               get_post_deploy_status
```

- 좌측 3개 레지스트리는 **domain/memory 계층** 으로, Pydantic 도메인 모델 + SQLite 저장소.
- Run Diff Engine, Promotion Gate는 **application use case** 로, 도메인 객체를 입력받아 결정/차이 객체를 반환.
- Post-Deploy Monitor는 **runtime adapter** 로, `runtime/` 스케줄러에 주기 태스크를 등록.
- Review Tab은 **presentation 계층** 에서 shared skill의 산출물을 사용자 카드로 렌더링.

---

## 4. Feature Registry 상세

### 4.1 목적

"이 실험은 어떤 피처의 어떤 버전을 사용했는가?"를 중앙에서 관리. 로드맵 §6.3의 YAML 예시를 Pydantic 모델 + SQLite 테이블 + YAML import/export로 구현한다.

### 4.2 Pydantic 스키마 (domain)

```python
# src/domain/entities/feature.py
from pydantic import BaseModel, Field
from typing import Literal

class FeatureStatistics(BaseModel):
    mean: float | None = None
    median: float | None = None
    p95: float | None = None
    null_rate: float | None = None
    distinct_count: int | None = None
    last_computed_at: str  # ISO8601

class Feature(BaseModel):
    feature_id: str  # e.g., "f_user_activity_30d"
    display_name: str
    version: int  # monotonic per feature_id
    description: str
    transformation_logic: str  # SQL / pseudo-code
    source_tables: list[str]  # ["growth.user_logins", ...]
    owner: str
    created_at: str  # ISO8601
    statistics: FeatureStatistics
    point_in_time_safe: bool
    alias: Literal["stable", "experimental", "deprecated"] = "experimental"
    used_in_experiments: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

class FeatureRef(BaseModel):
    feature_id: str
    version: int  # resolved at experiment start time
```

### 4.3 YAML 표현

로드맵 §6.3의 YAML을 그대로 수용한다. `registry/features/{feature_id}.yaml`에 저장하여 git-diff 가능. 등록 시 YAML → Pydantic 검증 → SQLite upsert.

### 4.4 Point-in-time 안전성

- `point_in_time_safe: true` 는 "학습 시점에 미래 정보가 섞이지 않았는가"를 뜻한다.
- Feature Registry는 해당 피처의 `transformation_logic`을 기반으로 **leakage 체커(정적 휴리스틱 + LLM 검토)** 를 수행. 로드맵 §3의 Statistical Verifier와 연계.
- `point_in_time_safe: false` 인 피처는 실험에서 사용될 때 경고 뱃지와 함께 기록된다.

### 4.5 버전/alias 관리

- `version`은 feature_id별 monotonic integer. `transformation_logic`이나 `source_tables`가 변하면 반드시 증가.
- `alias`는 `stable | experimental | deprecated`의 3단계. `deprecated` 피처가 새로운 실험에서 참조되면 Verifier가 WARN을 발행.
- 별도 `alias` 전이 기록 테이블(`feature_alias_history`)을 두어 "언제부터 stable로 승격되었는가"를 감사 가능하게 한다.

### 4.6 source_tables 의존

- `source_tables` 목록은 §02 Semantic Memory의 `SchemaCatalog`와 FK. 존재하지 않는 테이블을 참조하면 등록 자체가 실패.
- SchemaCatalog 변경 시 "이 테이블을 참조하는 피처" 역조회(reverse lookup)가 가능해야 한다.

### 4.7 통계 메타데이터

- `statistics`는 등록 시 1회 + 주기 sweep(예: 주 1회)으로 갱신.
- Post-Deploy Monitor는 이 기준선과 현재 분포의 KS / PSI를 비교하여 drift를 감지.

### 4.8 `used_in_experiments` 역참조

- Experiment Tracker가 실험 종료 시 `used_in_experiments`를 append. 이 참조는 "피처 폐기 전 영향 분석"에 사용된다.
- LLM tool `list_features_affecting(experiment_id)` / `list_experiments_using(feature_id)` 두 방향 조회를 제공.

---

## 5. Experiment Tracker 확장

### 5.1 기존 `experiment_log.py`와의 관계

- 기존 스키마(`experiments` 테이블)를 파괴하지 않는다. migration v9에서 컬럼 추가 + 부속 테이블 추가로 확장.
- 기존 `ExperimentRun` 엔티티를 다음과 같이 확장.

```python
class Hypothesis(BaseModel):
    statement: str
    rationale: str
    expected_effect: str  # "F1 >= 0.82"

class Method(BaseModel):
    model_family: str  # "xgboost", "lightgbm", "logreg"
    hyperparameters: dict
    train_window: tuple[str, str]  # (start, end) ISO8601
    eval_window: tuple[str, str]
    random_seed: int
    code_ref: str  # git sha / notebook hash

class RunResult(BaseModel):
    metrics: dict[str, float]  # {"f1_macro": 0.83, "auc": 0.88, ...}
    confusion_matrix: dict | None = None
    plots: list[str] = Field(default_factory=list)  # file uris

class ExperimentRun(BaseModel):
    run_id: str
    experiment_group: str  # e.g., "exp_churn"
    sequence: int  # 001, 002, 003 내 그룹
    hypothesis: Hypothesis
    method: Method
    feature_refs: list[FeatureRef]
    data_snapshot_uri: str  # 재현 가능한 데이터 포인터
    result: RunResult
    verifier_report_id: str | None = None  # §03 Verifier 산출물 참조
    created_at: str
    owner: str
    status: Literal["running", "succeeded", "failed", "archived"]
    parent_run_id: str | None = None  # 재실행 / 파라미터 변형
    promotion_state: Literal[
        "none", "candidate", "staging", "production", "retired"
    ] = "none"
```

### 5.2 비교 뷰 데이터 모델

Run Diff Engine이 사용하는 입력 형태. Experiment Tracker는 `ExperimentRun`을 "비교 가능 형태"로 내보내는 `to_diffable()` 메서드를 제공.

```python
class DiffableRun(BaseModel):
    run_id: str
    feature_set: dict[str, int]  # feature_id → version
    config: dict  # hyperparameters + method 일부
    metrics: dict[str, float]
    verifier_summary: dict[str, Literal["PASS", "WARN", "FAIL"]] | None
    code_ref: str
    data_snapshot_uri: str
```

### 5.3 재현 가능 실행 단위

- `ExperimentRun`은 "다시 돌리면 같은 결과가 나와야 한다"는 규약을 가진다.
- 재현 불가능성을 유발하는 요소(예: 외부 API 호출, system time 의존)는 `method.nondeterminism_notes`에 명시.
- 재현 성공/실패는 `reproducibility_status` 필드에 `unknown | reproduced | diverged` 로 표기.

---

## 6. Model Registry 상세

### 6.1 목적

"어떤 모델이, 어떤 실험에서 나왔고, 지금 어디에 배포되어 있는가"를 추적.

### 6.2 스키마

```python
class ModelArtifact(BaseModel):
    uri: str  # file/object store path
    format: Literal["pickle", "onnx", "torchscript", "sql", "json"]
    size_bytes: int
    checksum: str  # sha256

class ServingConfig(BaseModel):
    runtime: Literal["batch", "online", "embedded"]
    input_schema: dict  # JSON Schema
    output_schema: dict
    feature_refs: list[FeatureRef]
    latency_budget_ms: int | None = None
    throughput_budget_qps: int | None = None

class Model(BaseModel):
    model_id: str  # "m_churn_xgb"
    version: int
    alias: Literal["challenger", "champion", "canary", "retired"]
    lineage_run_id: str  # 어떤 experiment run에서 왔는가
    artifact: ModelArtifact
    serving: ServingConfig
    created_at: str
    promoted_at: str | None = None
    retired_at: str | None = None
    description: str
```

### 6.3 alias 의미

- `challenger`: staging에서 A/B 중. 아직 production 트래픽 없음.
- `champion`: 현재 production 주 모델.
- `canary`: 소수 트래픽에 노출 중(예: 5%).
- `retired`: 제거 대상. Post-Deploy Monitor는 `retired`에 대한 drift 알람을 발행하지 않음.

alias 전이는 반드시 Promotion Gate를 통과해야 한다. 직접 SQL로 alias를 변경하는 것은 금지(DB 트리거로 차단).

### 6.4 Lineage

- `lineage_run_id` 는 `ExperimentRun.run_id`에 대한 FK.
- 역방향 조회: `list_models_from_run(run_id)`.
- 로드맵 §6.4의 "exp_churn_003 → m_churn_xgb v5"처럼 실험 ↔ 모델 연결을 사용자에게 항상 노출.

### 6.5 서빙 설정 메타데이터

- `ServingConfig.input_schema` 는 배포된 모델이 받는 입력의 JSON Schema. Post-Deploy Monitor는 실제 입력 분포를 이 스키마에 대조.
- `feature_refs` 는 학습 시 사용된 FeatureRef 목록. runtime drift 판정 시 Feature Registry의 통계 기준선과 비교.

---

## 7. Run Diff Engine

### 7.1 목적

두 `ExperimentRun`(또는 하나의 run과 기준 baseline)을 입력받아, 입력·설정·결과·verifier·코드·데이터의 차이를 단일 `RunDiff` 객체로 반환.

### 7.2 API

```python
# src/application/usecases/run_diff.py
class RunDiffEngine:
    def __init__(
        self,
        experiment_tracker: ExperimentTracker,
        feature_registry: FeatureRegistry,
        verifier_store: VerifierStore,  # §03
    ) -> None: ...

    def compare(self, run_a_id: str, run_b_id: str) -> RunDiff: ...
```

### 7.3 `RunDiff` 스키마

```python
class FeatureSetDiff(BaseModel):
    added: list[FeatureRef]
    removed: list[FeatureRef]
    version_changed: list[tuple[str, int, int]]  # (feature_id, from_v, to_v)

class ConfigDiff(BaseModel):
    changed: dict[str, tuple]  # key → (from, to)
    added: dict[str, object]
    removed: dict[str, object]

class MetricDelta(BaseModel):
    metric: str
    from_value: float
    to_value: float
    delta: float
    direction: Literal["better", "worse", "neutral"]
    significance_note: str | None = None  # "paired t-test p=0.03"

class VerifierDiff(BaseModel):
    statistical: tuple[str, str]  # ("PASS","PASS") 식
    data: tuple[str, str]
    policy: tuple[str, str]
    new_findings: list[str]  # B에서 새로 등장한 finding
    resolved_findings: list[str]  # A에 있었으나 B에 없음

class RunDiff(BaseModel):
    run_a_id: str
    run_b_id: str
    feature_set: FeatureSetDiff
    config: ConfigDiff
    metrics: list[MetricDelta]
    verifier: VerifierDiff
    code_ref: tuple[str, str]
    data_snapshot: tuple[str, str]
    summary_markdown: str  # LLM이 생성한 한 페이지 요약
```

### 7.4 알고리즘

1. **FeatureSetDiff**: `DiffableRun.feature_set` 딕셔너리 집합 차. 버전만 다른 경우 `version_changed`에 분류.
2. **ConfigDiff**: `DiffableRun.config` 재귀 비교(중첩 dict 지원). `tuple/list`는 원소 단위가 아닌 값 단위 비교.
3. **MetricDelta**: 공통 metric에 대해 `to - from`. direction은 metric 메타데이터(Semantic Memory §02의 MetricCatalog)에서 `higher_is_better`를 조회하여 결정.
4. **VerifierDiff**: `VerifierReport`(§03)의 category 상태 비교 + finding id 집합 차.
5. **Summary**: 위 4개를 템플릿에 주입하여 LLM에게 1-page markdown 요약 생성(선택적; 캐시됨).

### 7.5 차트 및 테이블 뷰

- 테이블: FeatureSetDiff(추가/삭제/버전변경), ConfigDiff(key-value), MetricDelta.
- 차트: MetricDelta 바 차트(녹색=better / 빨강=worse), 시계열 metric 라인 차트(같은 experiment_group 내 sequence 전체).

---

## 8. Promotion Gate

### 8.1 목적

"staging → production 승격" 같은 stage 전이를 정책 기반 자동 체크 + 사람 승인의 합성으로 처리.

### 8.2 정책 체크리스트

다음이 모두 통과되어야 자동 gate가 열린다(수동 강제 override는 별도 로그).

| 항목 | 기준 |
|------|------|
| Verifier 전체 PASS | Statistical / Data / Policy 모두 PASS (§03) |
| 주요 metric ≥ baseline | champion 대비 하락 없음 (허용오차 설정) |
| A/B 결과 존재 | challenger alias로 N일 이상 가동된 결과 |
| Rollback plan 존재 | `rollback_plan.yaml` 파일이 있고 검증됨 |
| Feature alias | 사용된 피처 중 `deprecated` 없음 |
| Reproducibility | `reproducibility_status in {unknown, reproduced}`; `diverged` 이면 차단 |
| Uncertainty 범위 | `uncertainty-quantification` skill 결과 범위가 허용 구간 내 |

### 8.3 API

```python
# src/application/usecases/promotion_gate.py
class PromotionGate:
    def evaluate(
        self,
        candidate_run_id: str,
        target_stage: Literal["staging", "production", "canary"],
        approvers: list[str],  # user ids
    ) -> PromotionDecision: ...

    def approve(self, decision_id: str, approver: str, note: str) -> PromotionDecision: ...
    def reject(self, decision_id: str, approver: str, reason: str) -> PromotionDecision: ...
```

### 8.4 `PromotionDecision` 스키마

```python
class PolicyCheck(BaseModel):
    name: str
    status: Literal["pass", "warn", "fail", "skipped"]
    detail: str

class Approval(BaseModel):
    role: Literal["DS", "Lead", "MLOps"]
    approver: str
    decided_at: str
    note: str
    status: Literal["approved", "rejected"]

class PromotionDecision(BaseModel):
    decision_id: str
    candidate_run_id: str
    candidate_model_id: str
    target_stage: str
    policy_checks: list[PolicyCheck]
    approvals: list[Approval]
    chain_state: Literal[
        "pending_DS", "pending_Lead", "pending_MLOps",
        "approved", "rejected", "expired"
    ]
    rollback_plan_ref: str
    created_at: str
    resolved_at: str | None = None
```

### 8.5 승인 체인

- 기본 체인: `DS → Lead → MLOps`. 각 역할별로 1명 이상 승인 필요(프로젝트 설정으로 조정 가능).
- 체인 중 하나라도 `reject` → 즉시 `rejected`. 이후 승격은 새로운 `decision_id`로 재시작.
- 체인 만료(예: 7일 무응답) → `expired`, 알림 재발송.

### 8.6 A/B 결과 주입

- `evaluate`는 선택적으로 `ab_report: ABResult` 인자를 받음.
- `ABResult`는 외부 실험 플랫폼 또는 자체 runtime에서 수집한 uplift / p-value / sample size.
- 결과가 통계적 유의성 미달이면 `warn`으로 표시, 사람 승인으로만 돌파 가능.

### 8.7 Rollback plan 검증

- `rollback_plan.yaml` 은 다음 필드를 포함해야 한다.
  - `previous_champion_model_id`
  - `traffic_shift_procedure`
  - `health_check_queries` (SQL / metric id 목록)
  - `estimated_rollback_time_sec`
  - `owner`
- Gate는 YAML 스키마 검증 + `previous_champion_model_id` 존재 확인.

---

## 9. Post-Deploy Monitor

### 9.1 목적

승격되어 실제 배포된 모델·피처의 성능과 데이터 분포를 추적하고, 정책 기반 자동 재학습 / 자동 롤백을 trigger.

### 9.2 runtime 통합

- `runtime/post_deploy_monitor.py`에 `PostDeployMonitor` adapter 구현.
- 기존 runtime 스케줄러(주기 작업 dispatcher)에 `deploy_monitor_sweep` job을 등록(기본 15분 주기, 환경 변수로 조정).
- job은 `champion`, `canary` alias 모델 전체에 대해 수행.

### 9.3 관측 항목

| 관측 | 계산 | 기준 |
|------|------|------|
| Feature drift | 학습 기준선 대비 PSI / KS | PSI > 0.2 → warn, > 0.3 → alert |
| Prediction drift | champion 출력 분포 변화 | p95 이동 > 설정값 |
| Metric 변화 | 외부 레이블 feedback 기반 | F1 / AUC 하락폭 > N |
| Latency / QPS | 서빙 메트릭 | SLO 위반 |

### 9.4 자동 trigger 규칙

- **Auto-retrain**: drift > alert & 충분한 신규 데이터 존재 → `retrain-vs-rollback` skill 실행 → 추천이 "retrain"이면 새 experiment run 자동 생성(candidate 상태).
- **Auto-rollback**: metric 급락(예: F1 하락 > 0.05 in 24h) & rollback plan 존재 → `PromotionGate.auto_rollback(decision_id)` 호출 → 승인 체인을 건너뛰되 사후 감사 로그 남김.
- 사용자는 "수동 확인만 허용" / "자동 재학습만 허용" / "자동 롤백 허용" 3단계로 정책 조정 가능. §04 Autonomy Control Plane과 직접 연동.

### 9.5 상태 저장

- `deploy_monitor_state` 테이블에 최근 sweep 결과 저장(모델별 time-series).
- 알람 발생 시 `runtime_events`(§04)로 event 발행.

---

## 10. Review Tab 승격

### 10.1 현재 상태

`skills/shared/` 산하 스킬은 LLM이 내부적으로 호출하여 답변에 녹이지만, 사용자가 "어떤 가정을 검토했나", "불확실성이 어디서 왔나"를 재확인할 UI가 없다.

### 10.2 승격 원칙

- 각 스킬은 **구조화된 산출물(JSON)** 을 반환하도록 계약을 확장한다. 기존 prompt asset의 자유 텍스트는 `narrative` 필드로 유지하되, 구조화 필드를 병기한다.
- 각 산출물은 ReviewTab의 **카드 컴포넌트** 로 매핑된다.

### 10.3 스킬별 산출물과 카드

| Skill | 구조화 산출물 | ReviewTab 카드 |
|-------|-------------|----------------|
| `backtesting` | `BacktestResult { folds: list[FoldResult], consistency_score: float }` | "시간 분할 안정성" 카드 — fold별 막대, 일관성 점수, 경고 |
| `causal-assumption-check` | `CausalReview { risks: list[CausalRisk], confounders: list[str], is_causal: bool }` | "인과 리스크" 카드 — 가정 목록, 상관/인과 뱃지 |
| `uncertainty-quantification` | `UncertaintyReport { intervals: dict, methodology: str }` | "불확실성 범위" 카드 — interval 플롯 + 방법론 |
| `retrain-vs-rollback` | `RetrainVsRollback { recommendation: Literal[...], rationale: str, evidence: list[str] }` | "재학습 vs 롤백" 카드 — 추천 + 근거 링크 |

### 10.4 데이터 흐름

1. 실험 실행 시 해당 스킬이 호출되면, 결과는 `ExperimentRun.review_artifacts`에 JSON으로 저장.
2. ReviewTab은 run_id를 열쇠로 `review_artifacts`를 조회하여 카드 렌더링.
3. Promotion Gate는 이 산출물을 policy check의 근거로 재사용(예: `uncertainty` 범위가 임계 초과면 warn).

### 10.5 표시 문구(로드맵 §6.5)

- "시간 분할 안정성: 3개 fold 중 2개에서 일관된 결과"
- "인과 리스크: 이 추천은 상관 기반이며, confounding 가능성 존재"
- "불확실성 범위: 예측 구간 [3.1%, 5.2%], 중앙값 4.2%"
- "권장: 재학습 (drift 크기 < threshold, 데이터 충분)"

위 문구는 구조화 필드로부터 템플릿 생성되어 카드 상단 요약에 표시된다.

---

## 11. Clean Architecture 매핑

| 레이어 | 컴포넌트 | 비고 |
|--------|----------|------|
| Domain | `Feature`, `ExperimentRun`, `Model`, `RunDiff`, `PromotionDecision`, `ReviewArtifact` | 외부 의존성 0. pydantic 모델만. |
| Domain 인터페이스 (ports) | `FeatureRegistryPort`, `ExperimentTrackerPort`, `ModelRegistryPort`, `VerifierStorePort`, `RuntimeEventBusPort` | 추상 인터페이스. |
| Application use cases | `RunDiffEngine`, `PromotionGate`, `RegisterFeature`, `RequestPromotion`, `GetPostDeployStatus` | 포트만 의존. |
| Infrastructure | `SqliteFeatureRegistry`, `SqliteModelRegistry`, `SqliteExperimentTracker` 확장, `YamlFeatureImporter`, `PostDeployMonitor` runtime adapter | SQLite / 파일시스템 / 스케줄러. |
| Presentation | Electron `RunDiffPanel`, `PromotionGateModal`, `ReviewTab` + LLM tool bindings | 사용자 대면. |
| Composition root | `src/infrastructure/config/container.py` | DI 주입. |

검증 체크:

- [ ] `src/domain/**` 어느 파일도 `sqlite3`, `sqlalchemy`, `fastapi`, `telegram` 등을 import하지 않는다.
- [ ] `src/application/usecases/**` 는 포트 인터페이스만 import한다.
- [ ] LLM tool 구현체는 `src/infrastructure/api/tools/` 에 위치하며, use case를 호출할 뿐 비즈니스 로직을 포함하지 않는다.

---

## 12. SQLite 스키마 (migration v9)

`migrations/v9_decision_os.sql`. 기존 `experiments` 테이블은 파괴하지 않고 컬럼 추가 + 신규 테이블 생성.

```sql
-- 12.1 Feature Registry
CREATE TABLE feature_registry (
    feature_id    TEXT NOT NULL,
    version       INTEGER NOT NULL,
    display_name  TEXT NOT NULL,
    description   TEXT,
    transformation_logic TEXT NOT NULL,
    source_tables TEXT NOT NULL,           -- JSON array
    owner         TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    statistics    TEXT NOT NULL,           -- JSON FeatureStatistics
    point_in_time_safe INTEGER NOT NULL,   -- 0/1
    alias         TEXT NOT NULL CHECK(alias IN ('stable','experimental','deprecated')),
    tags          TEXT NOT NULL DEFAULT '[]',
    yaml_uri      TEXT,
    PRIMARY KEY (feature_id, version)
);

CREATE TABLE feature_alias_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_id    TEXT NOT NULL,
    version       INTEGER NOT NULL,
    from_alias    TEXT NOT NULL,
    to_alias      TEXT NOT NULL,
    changed_at    TEXT NOT NULL,
    changed_by    TEXT NOT NULL,
    note          TEXT
);

CREATE TABLE feature_usage (
    feature_id    TEXT NOT NULL,
    version       INTEGER NOT NULL,
    experiment_run_id TEXT NOT NULL,
    PRIMARY KEY (feature_id, version, experiment_run_id)
);

-- 12.2 Experiment Tracker 확장
ALTER TABLE experiments ADD COLUMN hypothesis_json TEXT;
ALTER TABLE experiments ADD COLUMN method_json TEXT;
ALTER TABLE experiments ADD COLUMN feature_refs_json TEXT;
ALTER TABLE experiments ADD COLUMN data_snapshot_uri TEXT;
ALTER TABLE experiments ADD COLUMN verifier_report_id TEXT;
ALTER TABLE experiments ADD COLUMN parent_run_id TEXT;
ALTER TABLE experiments ADD COLUMN promotion_state TEXT NOT NULL DEFAULT 'none';
ALTER TABLE experiments ADD COLUMN reproducibility_status TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE experiments ADD COLUMN review_artifacts_json TEXT;

-- 12.3 Model Registry
CREATE TABLE model_registry (
    model_id      TEXT NOT NULL,
    version       INTEGER NOT NULL,
    alias         TEXT NOT NULL CHECK(alias IN ('challenger','champion','canary','retired')),
    lineage_run_id TEXT NOT NULL,
    artifact_json TEXT NOT NULL,
    serving_json  TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    promoted_at   TEXT,
    retired_at    TEXT,
    description   TEXT,
    PRIMARY KEY (model_id, version)
);

-- alias 중복 방지(champion은 model_id별 1개)
CREATE UNIQUE INDEX ux_model_alias_champion
  ON model_registry(model_id)
  WHERE alias = 'champion';

-- 12.4 Promotion Decisions
CREATE TABLE promotion_decisions (
    decision_id   TEXT PRIMARY KEY,
    candidate_run_id TEXT NOT NULL,
    candidate_model_id TEXT NOT NULL,
    target_stage  TEXT NOT NULL,
    policy_checks_json TEXT NOT NULL,
    approvals_json TEXT NOT NULL DEFAULT '[]',
    chain_state   TEXT NOT NULL,
    rollback_plan_ref TEXT,
    created_at    TEXT NOT NULL,
    resolved_at   TEXT
);

-- 12.5 Post-Deploy Monitor
CREATE TABLE deploy_monitor_state (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id      TEXT NOT NULL,
    model_version INTEGER NOT NULL,
    observed_at   TEXT NOT NULL,
    feature_drift_json TEXT NOT NULL,  -- {feature_id: {psi, ks}}
    prediction_drift_json TEXT,
    metric_snapshot_json TEXT,
    serving_metrics_json TEXT,
    alert_level   TEXT NOT NULL CHECK(alert_level IN ('ok','warn','alert'))
);

CREATE INDEX ix_deploy_state_model
  ON deploy_monitor_state(model_id, model_version, observed_at);

-- 12.6 Run Diff 캐시(선택)
CREATE TABLE run_diff_cache (
    run_a_id TEXT NOT NULL,
    run_b_id TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    diff_json TEXT NOT NULL,
    PRIMARY KEY (run_a_id, run_b_id)
);
```

### 12.7 마이그레이션 전략

- 기존 `experiments` 행은 신규 컬럼이 `NULL`. Experiment Tracker의 읽기 경로에서 `NULL → 기본 Hypothesis/Method`로 정규화.
- `point_in_time_safe`, `promotion_state` 등 Boolean/Enum 컬럼은 기본값 보수적으로 설정.
- `migrations/rollback/v9_decision_os_down.sql` 에 역마이그레이션 작성.

---

## 13. 주요 도구 및 유스케이스

### 13.1 LLM 도구

모든 도구는 `src/infrastructure/api/tools/` 에 등록되고, `@tool` 데코레이터로 노출. 응답은 Pydantic 모델의 `.model_dump()`.

```python
@tool
def register_feature(yaml_uri: str) -> dict:
    """
    Feature YAML을 읽어 Feature Registry에 등록(또는 버전 업).
    반환: {"feature_id", "version", "alias", "validation_warnings": [...]}
    """

@tool
def compare_runs(run_a_id: str, run_b_id: str) -> dict:
    """
    두 실험 run의 RunDiff를 반환.
    반환: RunDiff.model_dump()
    """

@tool
def request_promotion(
    candidate_run_id: str,
    target_stage: Literal["staging","production","canary"],
    approvers: list[str],
    rollback_plan_ref: str,
) -> dict:
    """
    Promotion Gate를 생성하고 정책 체크를 수행. 승인 체인은 pending 상태로 반환.
    반환: PromotionDecision.model_dump()
    """

@tool
def get_post_deploy_status(model_id: str, window: str = "7d") -> dict:
    """
    최근 window 내 Post-Deploy Monitor 요약. drift / metric / alert.
    반환: {"model_id", "model_version", "summary": {...}, "alerts": [...]}
    """
```

추가 보조 도구(선택):

- `list_features_affecting(experiment_id)`
- `list_experiments_using(feature_id)`
- `approve_promotion(decision_id, approver, note)`
- `reject_promotion(decision_id, approver, reason)`
- `trigger_rollback(model_id, reason)` — 자동 롤백 정책 하에서만 허용.

### 13.2 Use case 클래스

- `RegisterFeatureUseCase`
- `CompareRunsUseCase` (내부에서 `RunDiffEngine` 호출)
- `RequestPromotionUseCase`
- `ApprovePromotionUseCase` / `RejectPromotionUseCase`
- `GetPostDeployStatusUseCase`

### 13.3 Runtime 태스크

- `PostDeployMonitor.sweep()` — 스케줄러가 주기 호출.
- `AutoRetrainTrigger.run_if_needed()` — sweep 결과를 받아 retrain 실행 여부 결정.
- `AutoRollbackTrigger.run_if_needed()` — metric 급락 감지 시 실행.

---

## 14. UX 흐름

### 14.1 RunDiffPanel (`components/runtime/RunDiffPanel.tsx`)

로드맵 §6.4의 박스를 Electron UI로 구현.

```
┌──────────────────────────────────────────────────────────┐
│  Run Diff: exp_churn_003 vs exp_churn_002                │
│  [재계산] [LLM 요약]   상태: succeeded vs succeeded      │
│----------------------------------------------------------│
│  Input Changes                                            │
│  + f_user_activity_30d (v2, was v1)                       │
│  + f_campaign_exposure (new)                              │
│  - f_raw_login_count (removed)                            │
│                                                           │
│  Config Changes                                           │
│    learning_rate: 0.05 → 0.03                             │
│    max_depth: 6 → 8                                       │
│                                                           │
│  Metric Delta                                             │
│    F1-macro: 0.79 → 0.83 (+0.04) better                   │
│    AUC:      0.85 → 0.88 (+0.03) better                   │
│    FP rate:  0.12 → 0.09 (-0.03) better                   │
│                                                           │
│  Verifier                                                 │
│    Statistical: PASS (no leakage, stable subgroups)       │
│    Data:        PASS                                      │
│    Policy:      PASS                                      │
│                                                           │
│  [승격 요청]  [동일 조건 재실행]  [롤백 시뮬레이션]        │
└──────────────────────────────────────────────────────────┘
```

- 상단 헤더: 두 run의 `experiment_group`·`sequence`·상태·코드 커밋.
- "LLM 요약": `RunDiff.summary_markdown`을 lazy fetch.
- "승격 요청" 클릭 → `PromotionGateModal` 오픈.
- "동일 조건 재실행" → `parent_run_id = run_b_id` 로 신규 run 생성, 실험 큐에 투입.
- "롤백 시뮬레이션" → Post-Deploy Monitor의 health check 쿼리를 dry-run.

### 14.2 PromotionGateModal (`components/runtime/PromotionGateModal.tsx`)

- 좌: 정책 체크 리스트(녹색/노랑/빨강 뱃지 + 상세 펼침).
- 우: 승인 체인 타임라인. 각 역할별 상태와 승인 버튼.
- 하단: rollback plan 요약 + `edit plan` 링크.
- 체인 상태가 `approved`가 되면 Model Registry alias를 실제로 변경하는 CTA("적용")가 등장. 적용은 사용자 명시 클릭에서만 발생.

### 14.3 ReviewTab (`components/workflow/ReviewTab.tsx`)

- 4개 카드 슬롯: Backtesting / Causal / Uncertainty / Retrain-vs-Rollback.
- 카드 없음 상태: "이 실험에 대해 <skill> 실행" CTA.
- 각 카드는 `review_artifacts_json`에서 매칭되는 산출물을 렌더링. 구조화 필드 상단 요약 + "원문 보기"(narrative) 토글.

### 14.4 CLI / Telegram 노출

- CLI: `ds-agent diff <run_a> <run_b>`, `ds-agent promote <run_id> --stage staging`, `ds-agent deploy-status <model_id>`.
- Telegram: PromotionGate 생성 시 승인자에게 inline 버튼(Approve/Reject). 버튼 콜백이 `approve_promotion` 도구 호출.

---

## 15. 기존 모듈과의 관계

| 기존/타 스펙 | 관계 |
|--------------|------|
| `memory/experiment_log.py` | migration v9로 스키마 확장. 기존 read 경로는 호환 유지. |
| `memory/project_store.py` | 실험 run과 project의 FK는 그대로. 승격 이벤트를 project timeline에 노출. |
| §01 TaskContract | `ExperimentRun.method.code_ref`, `data_snapshot_uri`는 TaskContract의 재현성 필드와 1:1. Promotion Gate는 TaskContract 만족 여부를 policy check 항목으로 재사용. |
| §02 Semantic Memory | `MetricCatalog`는 MetricDelta의 `direction` 결정에 사용. `SchemaCatalog`는 Feature Registry `source_tables`의 존재 검증에 사용. |
| §03 Verifier/Orchestrator | `VerifierReport`는 Promotion Gate의 policy check 및 RunDiff `VerifierDiff`의 원천. |
| §04 Autonomy Control Plane | Post-Deploy Monitor의 자동 trigger 정책(재학습/롤백 허용 단계)을 Autonomy Plane이 결정. |
| §05 Evaluation Harness | Harness 결과는 Promotion Gate의 "metric ≥ baseline" 체크에 직접 주입. |
| `skills/shared/*` | Review Tab 승격 대상. 스킬 계약을 구조화 산출물로 확장. |

---

## 16. 구현 Phases (TDD, P2 우선)

총 6개 phase, 각 3–5시간. 전후 phase는 독립 롤백 가능.

### Phase 1. Domain & Feature Registry (RED → GREEN → REFACTOR)

- Status (2026-04-16): Foundation landed. Implemented files include `src/ds_agent/domain/entities/feature.py`, `src/ds_agent/domain/interfaces/feature_registry.py`, `src/ds_agent/application/services/feature_registry_usecases.py`, `src/ds_agent/infrastructure/importers/yaml_feature_importer.py`, `src/ds_agent/infrastructure/persistence/feature_registry_store.py`, `src/ds_agent/infrastructure/feature_registry_container.py`, and `src/ds_agent/tools/feature_registry_tools.py`. Targeted verification: `tests/unit/domain/test_feature_entity.py`, `tests/unit/application/test_feature_registry_usecases.py`, `tests/unit/infrastructure/test_feature_registry_store.py`, `tests/unit/tools/test_feature_registry_tools.py` all green (`9 passed`).
- RED: `tests/unit/domain/test_feature_entity.py`, `tests/unit/application/test_register_feature.py`. YAML → Pydantic 검증, SchemaCatalog 참조 실패, 중복 버전 거부 등.
- GREEN: `domain/entities/feature.py`, `application/usecases/register_feature.py`, `infrastructure/persistence/sqlite_feature_registry.py`, migration v9의 Feature Registry 섹션만 적용.
- REFACTOR: YAML 파서를 별도 어댑터 분리, 공통 validator 추출.
- Quality gate: coverage ≥ 85% (domain+application), clean arch 자동 검사 스크립트 통과.

### Phase 2. Experiment Tracker 확장

- Status (2026-04-16): Foundation landed. Implemented files include `src/ds_agent/domain/entities/experiment.py` and `src/ds_agent/memory/experiment_log.py`, with typed `ExperimentRun`, `DiffableRun`, legacy-record normalization, and structured `record_extended()/get_run()/list_runs()/to_diffable()` support. Compatibility verification: `tests/unit/domain/test_experiment_entity.py`, `tests/unit/infrastructure/test_experiment_log_extended.py`, `tests/unit/infrastructure/test_experiment_registry.py`, `tests/unit/application/test_reproducibility.py`, and `tests/integration/test_memory_modules.py` (`22 passed`).
- RED: 기존 실험 기록 테스트 유지 + 확장 필드 라운드트립 테스트, `to_diffable()` 테스트.
- GREEN: 스키마 alter, Tracker에 `record_extended()` 추가, 구 경로는 default 처리.
- REFACTOR: Tracker 인터페이스를 port로 추출, 기존 코드 의존성 교체.
- Quality gate: 기존 189 테스트 전부 그린 유지.

### Phase 3. Run Diff Engine

- Status (2026-04-16): Foundation landed. Implemented files include `src/ds_agent/domain/entities/run_diff.py`, `src/ds_agent/application/ports/run_diff_support.py`, `src/ds_agent/application/services/run_diff_usecases.py`, `src/ds_agent/infrastructure/decision_os_container.py`, and `src/ds_agent/tools/decision_os_tools.py`. The current implementation delivers deterministic feature/config/metric/verifier/code/data diffs plus a generated markdown summary and the `compare_runs` tool surface. Verification: `tests/unit/application/test_run_diff_usecases.py`, `tests/unit/tools/test_decision_os_tools.py`, plus compatibility regression over the structured tracker path (`26 passed` total targeted suite).
- RED: 합성 fixture 2개(run A/B)로 FeatureSetDiff / ConfigDiff / MetricDelta / VerifierDiff 기대값 테스트.
- GREEN: `application/usecases/run_diff.py` 구현, 캐시 경로는 optional.
- REFACTOR: Diff 계산을 순수 함수로 분리, LLM 요약 경로는 adapter.
- Quality gate: diff는 deterministic(동일 입력 → 동일 출력) 테스트 포함.

### Phase 4. Model Registry & Promotion Gate

- Status (2026-04-16): Foundation landed. Implemented files include `src/ds_agent/domain/entities/model.py`, `src/ds_agent/domain/entities/promotion.py`, `src/ds_agent/domain/interfaces/model_registry.py`, `src/ds_agent/application/ports/promotion_gate_support.py`, `src/ds_agent/application/services/promotion_gate_usecases.py`, `src/ds_agent/infrastructure/importers/yaml_rollback_plan_loader.py`, `src/ds_agent/infrastructure/persistence/model_registry_store.py`, `src/ds_agent/infrastructure/persistence/promotion_decision_store.py`, plus updated `src/ds_agent/infrastructure/decision_os_container.py` and `src/ds_agent/tools/decision_os_tools.py`. The current implementation delivers SQLite-backed model registry + promotion-decision persistence, rollback-plan YAML validation, core verifier/baseline/rollback/feature/reproducibility policy checks, explicit DS → Lead → MLOps approval transitions, and the `request_promotion` tool surface. Verification: `tests/unit/application/test_promotion_gate_usecases.py`, `tests/unit/infrastructure/test_model_registry_store.py`, `tests/unit/infrastructure/test_promotion_decision_store.py`, and `tests/unit/tools/test_decision_os_tools.py` (`15 passed`), plus the combined Decision OS regression suite through Phase 4 (`48 passed`).
- RED: Gate policy check 각 항목별 독립 테스트(verifier PASS/FAIL, metric 기준 미달, rollback plan 누락, deprecated feature 사용 등), 승인 체인 전이 테스트.
- GREEN: `domain/entities/model.py`, `model_registry` 테이블, `application/usecases/promotion_gate.py`. alias 유일성 제약은 DB 인덱스로.
- REFACTOR: policy check 목록을 plug-in 구조로(각 check = 별도 함수).
- Quality gate: 승인 체인의 모든 상태 전이가 테스트에 포함, reject 후 재시도 경로 확인.

### Phase 5. Post-Deploy Monitor + 자동 trigger

- Status (2026-04-16): Automation path plus daemon wiring landed. Implemented files include `src/ds_agent/domain/entities/post_deploy.py`, `src/ds_agent/application/dtos/post_deploy.py`, `src/ds_agent/application/ports/post_deploy_support.py`, `src/ds_agent/application/services/post_deploy_usecases.py`, `src/ds_agent/application/services/promotion_gate_usecases.py`, `src/ds_agent/infrastructure/persistence/deploy_monitor_state_store.py`, `src/ds_agent/infrastructure/persistence/promotion_decision_store.py`, `src/ds_agent/runtime/post_deploy_monitor.py`, `src/ds_agent/runtime/decision_os_scheduler.py`, `src/ds_agent/runtime/sensors/schedule.py`, and `src/ds_agent/gateway/daemon.py`, plus updated `src/ds_agent/infrastructure/decision_os_container.py` and `src/ds_agent/tools/decision_os_tools.py`. The current implementation delivers persisted post-deploy time-series state, workspace JSON snapshot ingestion, drift/metric/SLO sweep evaluation, remediation recommendation synthesis, runtime alert emission, environment-driven trigger policy resolution, automatic retrain candidate creation in `ExperimentLog`, automatic rollback execution via `AutoRollbackUseCase`, a scheduler adapter for periodic sweeps, background-runtime startup registration of the Decision OS standing order, and schedule-tick execution through `ScheduleSensor` without spawning a separate Decision OS agent run. Verification: `tests/unit/application/test_promotion_gate_usecases.py`, `tests/unit/infrastructure/test_promotion_decision_store.py`, `tests/unit/runtime/test_post_deploy_monitor.py`, `tests/unit/runtime/test_decision_os_scheduler.py`, `tests/unit/infrastructure/test_policy_runtime.py`, and `tests/unit/infrastructure/test_autonomous_runtime.py` (`27 passed` targeted runtime/automation suite), plus the combined Decision OS regression suite with daemon wiring (`66 passed`).
- RED: drift 샘플 분포로 PSI/KS 경계값 테스트, metric 급락 시 auto-rollback trigger 테스트, autonomy 설정별 on/off 테스트.
- GREEN: `runtime/post_deploy_monitor.py`, sweep job 등록, `deploy_monitor_state` 쓰기.
- REFACTOR: trigger 정책을 전략 패턴으로, §04 Autonomy Plane과의 인터페이스 정리.
- Quality gate: 실시간 job을 모킹한 통합 테스트 포함.

### Phase 6. Review Tab 승격 & UI 와이어

- RED: 각 shared skill에 대해 구조화 산출물 JSON 스키마 계약 테스트. Electron 컴포넌트의 렌더링 스냅샷 테스트.
- GREEN: 스킬 응답 확장, `review_artifacts_json` 저장, `RunDiffPanel`/`PromotionGateModal`/`ReviewTab` 구현, LLM tool 바인딩.
- REFACTOR: 카드 컴포넌트를 공통 레이아웃(제목, 요약, 뱃지, 원문 토글)로 통일.
- Status (2026-04-16): Phase 6 is complete. The repo now has `decisionOs.*` WebSocket RPC handlers in `api/ws_handler.py` for overview, compare, request, resolve, apply, and post-deploy status flows; AppState Decision OS container wiring; typed `ReviewArtifact` entities; `ExperimentRun.review_artifacts` / `review_artifacts_json` persistence; `record_review_artifact` / `get_review_artifacts` tool bindings; a hidden `DS_REVIEW_ARTIFACTS` response contract; final-response hook execution in the agent lifecycle; shared Electron review UI model/primitives; a dedicated `SharedSkillReviewPanel`; a dedicated `RunDiffPanel`; a dedicated `PromotionGateModal`; narrative toggles for review cards; an approved-decision apply CTA in `ReviewTab`; and a targeted full-flow regression covering `compare -> request -> approve -> apply -> post-deploy alert`. Section 21 now records the fixed design defaults, so the current `06` scope has no remaining implementation or design blockers.
- Quality gate: landed. Targeted regression covers the end-to-end scenario "실험 → diff → 승격 요청 → 승인 → 배포(alias apply) → post-deploy 알람".

---

## 17. 테스트 전략

### 17.1 재현성 테스트

- `tests/reproducibility/test_run_idempotency.py`: 동일 TaskContract + 동일 feature_refs + 동일 seed로 2회 실행 → `MetricDelta.delta == 0` (허용오차 내).
- `tests/reproducibility/test_feature_version_lock.py`: 실험은 시작 시 feature version을 lock. 중간에 Feature Registry가 변경되어도 실험 결과에 영향 없음.
- `tests/reproducibility/test_data_snapshot_pointer.py`: `data_snapshot_uri`가 해제/손실되면 `reproducibility_status = unknown`으로 전이.

### 17.2 Diff 정확도

- Golden fixture 기반. `fixtures/run_diff/{case}/run_a.json`, `run_b.json`, `expected_diff.json`.
- 엣지 케이스: 빈 교집합, 순서가 다른 feature 집합, 중첩 dict config, metric 일부만 존재, verifier 누락.

### 17.3 Promotion Gate 정책

- 각 policy check의 pass/warn/fail × 승인 체인 상태 전이 조합에 대한 파라메터화 테스트.
- `auto_rollback` 경로: approval chain 우회 + 감사 로그 기록 확인.

### 17.4 Post-Deploy Monitor

- 합성 drift 시나리오(gradual / sudden / seasonal)에 대해 PSI/KS 임계 동작 검증.
- Autonomy 설정(수동/재학습만/완전자동)별 trigger 분기 테스트.

### 17.5 E2E

- `tests/e2e/test_decision_os_happy_path.py`: 실험 2회 → diff → promotion(staging) → post-deploy OK → promotion(production) → drift 발생 → auto-retrain → 신규 candidate 생성.
- 실패 경로: verifier FAIL → promotion 차단, metric 급락 → auto-rollback.

### 17.6 Clean Architecture 정적 검사

- `tests/arch/test_dependency_rule.py`: `domain/` 모듈이 `infrastructure/` / `presentation/` / `runtime/`을 import하지 않음을 AST 스캔.
- `application/` 에서 `infrastructure/` 직접 import 금지.

---

## 18. 의존성 및 통합 지점

### 18.1 외부 라이브러리

- `pydantic`(기존), `PyYAML`(신규 의존), `scipy`(드리프트 통계; 기존 사용 시 재사용), `numpy`.
- UI: 기존 Electron 스택(React/TS). 신규 컴포넌트는 기존 디자인 토큰 재사용.

### 18.2 내부 통합

- 스케줄러: `runtime/scheduler`에 `deploy_monitor_sweep`, `auto_retrain_trigger`, `auto_rollback_trigger` 등록.
- 메시지: §04 runtime events 버스로 `promotion.*`, `deploy.*` 이벤트 발행.
- LLM 도구 레지스트리: `src/infrastructure/api/tools/__init__.py` 에 신규 도구 등록.

### 18.3 외부 시스템(선택)

- 사내 A/B 실험 플랫폼이 있을 경우 `ABResult` import adapter를 `infrastructure/external/ab_platform.py`에 둔다. 없으면 CLI로 수동 업로드.
- 서빙 메트릭: Prometheus/DataDog adapter를 선택적으로. 기본 구현은 내부 `deploy_monitor_state` 에 쓰기만.

---

## 19. 성공 기준 (DoD)

| 영역 | 지표 | 목표 |
|------|------|------|
| 재현성 | `reproducibility_status = reproduced` 비율 | ≥ 85% (최근 30일 실험 기준) |
| 재현 가능 실행 비율 | TaskContract + data_snapshot + feature lock 3요소 충족 실험 비율 | ≥ 95% |
| 승격 리드타임 | PromotionDecision 생성 → resolved 평균 | ≤ 3 영업일 |
| 자동 롤백 성공률 | 자동 트리거된 롤백 중 성공 비율 | ≥ 95% |
| Run Diff 활용 | 주간 diff 호출 수 / 총 실험 수 | ≥ 0.6 |
| Review Tab 커버리지 | 4개 shared skill 전부 구조화 산출물 및 카드 제공 | 100% |
| 테스트 | 신규 기능 커버리지 | 도메인 ≥ 90%, 애플리케이션 ≥ 85% |
| 감사 | PromotionDecision · auto-rollback 감사 로그 누락 | 0건 |

---

## 20. 리스크 및 롤백

### 20.1 리스크

| 리스크 | 확률 | 영향 | 완화 |
|--------|------|------|------|
| 기존 `experiments` 스키마 확장으로 기존 조회 경로 파손 | 중 | 높음 | migration은 ADD COLUMN + default. 읽기 경로에 NULL 정규화. |
| Feature Registry YAML 관리 부담 증가 | 중 | 중 | YAML 변경 시 자동 version bump + PR 링크. 초기 bootstrap 스크립트 제공. |
| Promotion Gate 정책이 과도해 승격 속도 저하 | 중 | 중 | 정책을 플러그인화하여 프로젝트별 on/off. P0 정책(verifier PASS, rollback plan) 외에는 warn로 설정 가능. |
| 자동 롤백 오발동 | 저 | 높음 | Autonomy Plane에서 기본값은 "수동 승인"로. 자동 모드 enable 시 최소 2개 metric 동시 위반 요구. |
| Drift 계산이 큰 데이터에서 무겁다 | 중 | 중 | 샘플링 + 점진적 통계. sweep 주기 기본 15분, 데이터 크기 따라 점증. |
| Run Diff LLM 요약 비용 | 저 | 저 | 요약은 사용자 요청 시에만 생성 + 캐시. |

### 20.2 롤백 전략

- Phase별 독립 롤백. migration v9의 down 스크립트(`v9_decision_os_down.sql`)로 신규 테이블 드롭 + 추가 컬럼 제거.
- Experiment Tracker 확장만 유지하고 Promotion/Post-Deploy만 롤백하는 부분 롤백도 지원(플래그 `features.decision_os.promotion_gate = false`).
- UI는 feature flag (`ui.decision_os.*`)로 토글. 실패 시 탭/모달 비활성화.

---

## 21. Resolved Design Decisions

1. **Feature Registry 저장 위치**
Decision: `registry/features/*.yaml` in the workspace/repository is the canonical source of truth. The SQLite Feature Registry remains a derived read/cache layer only, and Electron/local surfaces must edit or generate YAML rather than create an alternate local truth.

2. **A/B 플랫폼 연동**
Decision: Decision OS will not own an internal mini A/B result store. A/B evidence enters through external adapters when available or through explicit manual import/attachment when not; absent evidence remains a policy signal (`warn`/`skipped`) instead of triggering a second experiment system inside Decision OS.

3. **자동 액션의 권한 모델**
Decision: shipping default remains `manual_only`. Auto-retrain may create a new candidate run only when the trigger mode is explicitly switched to `auto_retrain` or `auto_rollback`; auto-rollback is allowed only in `auto_rollback`; promotion apply remains an explicit operator action from the review surface.

4. **대용량 feature statistics 계산 위치**
Decision: Decision OS computes PSI/KS and related drift statistics inside the DS Agent runtime from materialized monitoring snapshots or sampled extracts. Upstream warehouse jobs may prepare those extracts, but Decision OS itself does not run heavy ad-hoc warehouse-wide statistical scans.

5. **Model artifact 저장소**
Decision: model binaries stay outside the database and are referenced through `artifact.uri`. The primary abstraction is URI-based external storage, with object storage as the recommended production backend and local filesystem URIs allowed for single-node development and demos.

6. **승격 체인 축약 허용 여부**
Decision: the logical approval chain remains `DS -> Lead -> MLOps` for audit consistency, but duplicate identities are allowed in the approver list. Small teams may therefore reuse the same human across multiple steps without a separate chain-compression mode; the audit log still records which logical role was approved at each step.

7. **Reproducibility verification 자동화**
Decision: reproducibility verification is mandatory at gate time for promotion candidates and selective at night. Nightly automation is limited to `champion` / `canary` models and promotion-approved-but-not-yet-applied candidates; there is no blanket nightly rerun for every historical experiment.

8. **Retired 모델 보존 기간**
Decision: retired model metadata, promotion decisions, and monitor history are retained indefinitely for auditability. Artifacts stay hot for 90 days, move to archive through day 365, and may be purged after that unless they are pinned by an active rollback plan, incident hold, or explicit operator retention override.

9. **Shared skill 버전 관리**
Decision: every `review_artifact` payload must carry an explicit `schema_version`, starting with `v1`. Read paths are responsible for forward-migrating older payloads before rendering; any breaking shape change must ship with a migrator before the new writer becomes the default.

10. **롤백 시나리오의 깊이**
Decision: the required rollback quality bar is rollback-plan validation plus health-check dry-run validation and staged alias/application execution. Traffic mirroring or full staging replay is treated as an optional adapter-specific enhancement, not a mandatory Decision OS quality gate for the current scope.

## 21A. Historical Open Questions (Resolved)

The questions below are retained as historical context only. The active defaults for implementation are the ten decisions in Section 21 above.

1. **Feature Registry 저장 위치**: YAML을 git 리포에 둘 것인가, Electron 앱 로컬에 둘 것인가, 혼합(원천=git, 로컬 캐시)인가. 팀 규모에 따라 결정 필요.
2. **A/B 플랫폼 연동**: 사내 플랫폼이 없을 경우, 간이 A/B 스토어를 Decision OS 내부에 둘지(스코프 확대) vs. 수동 입력만 허용할지.
3. **자동 재학습의 권한 모델**: Post-Deploy Monitor가 "실험을 스스로 생성"할 수 있게 둘 때, Autonomy Plane의 어느 레벨 이상이어야 허용할지(§04와 조율).
4. **대용량 feature statistics 갱신**: 통계 sweep을 외부 warehouse에서 수행할지, 내부 샘플링으로 끝낼지.
5. **Model artifact 저장소**: 로컬 파일 vs. 객체 스토리지(S3/GCS) 어댑터를 어디까지 추상화할지.
6. **승격 체인의 역할 수**: 소규모 팀(1~2인)일 때 `DS = Lead = MLOps` 동일인 허용 규칙.
7. **Reproducibility verification 자동화**: "같은 입력으로 재실행" 검증을 nightly job으로 자동화할지, 사용자 요청 시에만 할지.
8. **Retired 모델의 보존 기간**: retired 상태 유지 기간과, 그 이후 artifact/metadata 아카이빙 정책.
9. **Shared skill 버전 관리**: Review Tab 산출물 스키마가 바뀌면 과거 실험의 카드가 깨질 수 있음. 스키마 버전 + migrator 전략 필요 여부.
10. **롤백 시뮬레이션의 깊이**: health_check 쿼리 dry-run만 할지, 스테이징 환경에서 실제 트래픽 미러링까지 지원할지.

---

## 부록 A. 폴더 구조(요약)

```
src/
├── domain/
│   ├── entities/
│   │   ├── feature.py
│   │   ├── model.py
│   │   └── experiment.py                # 확장
│   ├── value_objects/
│   │   ├── feature_ref.py
│   │   ├── run_diff.py
│   │   └── promotion_decision.py
│   └── interfaces/
│       ├── feature_registry_port.py
│       ├── experiment_tracker_port.py
│       ├── model_registry_port.py
│       └── verifier_store_port.py
│
├── application/
│   └── usecases/
│       ├── register_feature.py
│       ├── run_diff.py
│       ├── promotion_gate.py
│       ├── request_promotion.py
│       ├── approve_promotion.py
│       └── get_post_deploy_status.py
│
├── infrastructure/
│   ├── persistence/
│   │   ├── sqlite_feature_registry.py
│   │   ├── sqlite_model_registry.py
│   │   └── sqlite_experiment_tracker.py  # 확장
│   ├── importers/
│   │   └── yaml_feature_importer.py
│   └── api/tools/
│       ├── register_feature_tool.py
│       ├── compare_runs_tool.py
│       ├── request_promotion_tool.py
│       └── get_post_deploy_status_tool.py
│
├── runtime/
│   ├── post_deploy_monitor.py
│   ├── auto_retrain_trigger.py
│   └── auto_rollback_trigger.py
│
└── presentation/electron/
    ├── components/runtime/RunDiffPanel.tsx
    ├── components/runtime/PromotionGateModal.tsx
    └── components/workflow/ReviewTab.tsx

migrations/
├── v9_decision_os.sql
└── rollback/v9_decision_os_down.sql

registry/
└── features/*.yaml
```

## 부록 B. 용어집

- **Feature**: 모델 학습/추론에 쓰이는 파생 변수. 정의 + 변환 로직 + 메타데이터를 포함.
- **Experiment Run**: 하나의 재현 가능한 학습/평가 실행 단위. hypothesis/method/result/artifacts로 구성.
- **Model**: Serving 가능한 학습 산출물. 버전과 alias(champion/challenger/canary/retired)를 가짐.
- **Run Diff**: 두 Experiment Run의 구조적 차이(입력·설정·결과·verifier·코드·데이터).
- **Promotion Decision**: 특정 run을 target_stage로 승격하는 결정. 정책 체크 + 승인 체인 + rollback plan을 가짐.
- **Deploy Monitor State**: 배포된 모델의 drift / metric / serving 관측치 스냅샷.
- **Review Artifact**: shared skill이 반환하는 구조화 산출물. ReviewTab의 카드로 렌더링됨.
- **Reproducibility Status**: `unknown | reproduced | diverged`. 실험이 재현 가능한지에 대한 명시적 상태.

---

본 스펙은 구현 착수의 입력이다. Phase 1–6을 순서대로 TDD로 수행하며, 각 phase의 quality gate를 통과할 때까지 다음 phase로 넘어가지 않는다. Clean Architecture 의존성 규칙 위반이 하나라도 감지되면 해당 phase는 자동 실패로 간주한다.
