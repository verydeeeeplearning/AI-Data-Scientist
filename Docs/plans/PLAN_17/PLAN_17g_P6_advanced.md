# Phase 6: Advanced Autonomy — 고급 자율성·분산 컴퓨팅

**Status**: Pending
**Started**: -
**Last Updated**: 2026-04-13
**Parent**: `PLAN_17_ROADMAP_MASTER.md`
**선행 조건**: Phase 3, 4, 5 완료
**후행 Phase**: 없음 (최종 Phase)

---

## 1. Overview

### 왜 Advanced Autonomy인가

Phase 0~5로 **현업 위임의 80%**를 커버한다. Phase 6은 나머지 20% — "더 다양한 분석", "더 큰 데이터", "더 스마트한 에이전트"를 위한 고급 기능이다.

- **Method Flexibility**: 3가지 분석 유형 → 7+가지로 확장
- **Resource-Aware Planning**: 500KB vs 50GB에 따른 전략 자동 전환
- **Cross-Session Improvement**: 프로젝트 간 학습으로 점점 나아지는 에이전트
- **Distributed Compute**: Spark/Dask/Ray로 대규모 데이터 처리

### 성공 기준

- [ ] 7가지 이상 분석 유형 라우팅 (Forecasting, Anomaly, Uplift, Causal, Ranking 포함)
- [ ] 데이터 크기별 자동 전략 전환 (샘플링 → 프로토타이핑 → 풀 데이터)
- [ ] Cross-session improvement: 이전 프로젝트 패턴 자동 활용
- [ ] 분산 컴퓨팅 어댑터 최소 1개 (Ray 또는 Dask)

---

## 2. Architecture Decisions (Clean Architecture)

### Layer Mapping

| Layer | Components | Responsibility |
|-------|-----------|---------------|
| **Domain** | `AnalysisType` (VO), `ResourceProfile` (VO), `ImprovementInsight` (Entity) | 분석 유형 분류, 리소스 프로파일, 개선 인사이트 |
| **Application** | `AnalysisTypeRouter`, `ResourcePlanner`, `CrossSessionLearner` | 분석 라우팅, 리소스 계획, 세션 간 학습 |
| **Infrastructure** | `SparkAdapter`, `DaskAdapter`, `RayAdapter`, `VectorMemoryStore` | 분산 컴퓨팅 어댑터, 벡터 기반 메모리 |
| **Presentation** | `distributed_exec` tool, 기존 tools 확장 | 분산 실행 도구 |

---

## 3. Implementation Phases (TDD)

### Phase 6-1: Method Flexibility 확장

**Goal**: Forecasting, Anomaly Detection, Uplift, Causal Inference, Ranking, Segmentation 지원

#### RED: Write Failing Tests First

- [ ] **Test 6-1.1**: AnalysisTypeRouter — 문제 유형 자동 분류
  - File: `tests/unit/application/test_analysis_router.py`
  - Scenario: "왜 매출이 떨어졌지?" → analysis_type = "diagnosis"
  - Scenario: "다음 달 매출 예측해줘" → analysis_type = "forecasting"
  - Scenario: "이 실험 결과 분석해줘" → analysis_type = "experimentation"
  - Expected: Tests FAIL

- [ ] **Test 6-1.2**: 분석 유형별 스킬 자동 활성화
  - File: `tests/unit/application/test_analysis_router.py`
  - Scenario: type="forecasting" → backtesting, time-series-backtest 스킬 활성화
  - Expected: Tests FAIL

- [ ] **Test 6-1.3**: ProblemTypeRouterHook — 세션 시작 시 자동 분류
  - File: `tests/unit/application/test_problem_router_hook.py`
  - Scenario: 사용자 첫 메시지 → 문제 유형 감지 → 워크플로우 경로 제안
  - Expected: Tests FAIL

- [ ] **Test 6-1.4**: 분석 유형별 품질 가드레일 차이
  - File: `tests/unit/application/test_analysis_router.py`
  - Scenario: forecasting → walk-forward 필수; experimentation → SRM check 필수
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 6-1.5**: Domain Value Object
  - File: `src/ds_agent/domain/value_objects/analysis_type.py`
  - `AnalysisType`:
    - type: prediction / diagnosis / forecasting / anomaly_detection / segmentation / experimentation / causal_inference / ranking
    - required_skills: List[str]
    - required_guards: List[str]
    - typical_artifacts: List[str]
    - workflow_template: str (비선형 DAG 템플릿)

- [ ] **Task 6-1.6**: AnalysisTypeRouter
  - File: `src/ds_agent/application/services/analysis_type_router.py`
  - 키워드 기반 분류 + LLM 보조 분류
  - 분류 결과 → 스킬 활성화 + 가드레일 설정 + 워크플로우 템플릿 선택

- [ ] **Task 6-1.7**: `ProblemTypeRouterHook`
  - File: `src/ds_agent/agent/builtin_hooks.py`
  - Priority: 3 (최초 세션에서만 실행)
  - `on_session_init()`: 사용자 첫 메시지 분석 → 분류 결과를 시스템 프롬프트에 주입

- [ ] **Task 6-1.8**: 분석 유형별 스킬 추가
  - `hypothesis-ranking.md`: 가설 우선순위화
  - `causal-assumption-check.md`: SUTVA, unconfoundedness, overlap 검증
  - `uncertainty-quantification.md`: Conformal prediction, bootstrapping
  - `backtesting.md`: Walk-forward, expanding window validation

- [ ] **Task 6-1.9**: 분석 유형별 워크플로우 템플릿
  - 각 분석 유형에 맞는 TaskGraph 템플릿 정의
  - 예: forecasting = scoping → data_loading → profiling → temporal_eda → backtesting_setup → modeling → backtesting → reporting

#### Quality Gate

- [ ] 7가지 분석 유형 정확히 분류
- [ ] 각 유형별 스킬 활성화 확인
- [ ] 워크플로우 템플릿 동작 확인

---

### Phase 6-2: Resource-Aware Planning

**Goal**: 데이터 크기·리소스에 따른 자동 전략 전환

#### RED: Write Failing Tests First

- [ ] **Test 6-2.1**: 데이터 크기 감지 → 전략 결정
  - File: `tests/unit/application/test_resource_planner.py`
  - Scenario: 500KB CSV → strategy = "direct" (pandas 직접 처리)
  - Scenario: 5GB Parquet → strategy = "sample_first" (1% 샘플 → 프로토 → 풀)
  - Scenario: 50GB → strategy = "distributed" (Spark/Dask/Ray)
  - Expected: Tests FAIL

- [ ] **Test 6-2.2**: 자동 샘플링 전략
  - File: `tests/unit/application/test_resource_planner.py`
  - Scenario: 10M 행 → 층화 샘플링 1% → 프로토타이핑 → 검증 → 풀 데이터
  - Expected: Tests FAIL

- [ ] **Test 6-2.3**: 메모리 추정 및 OOM 방지
  - File: `tests/unit/application/test_resource_planner.py`
  - Scenario: 예상 메모리 8GB > 사용 가능 4GB → 샘플링 권고
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 6-2.4**: Domain Value Object
  - File: `src/ds_agent/domain/value_objects/resource_profile.py`
  - `ResourceProfile`: data_size_bytes, row_count, column_count, available_memory_bytes, available_cpus
  - `ExecutionStrategy`: direct / sample_first / chunked / distributed

- [ ] **Task 6-2.5**: ResourcePlanner
  - File: `src/ds_agent/application/services/resource_planner.py`
  - 전략 결정 매트릭스:
    | 데이터 크기 | 행 수 | 전략 | 설명 |
    |-----------|------|------|------|
    | < 100MB | < 500K | direct | pandas 직접 처리 |
    | 100MB~1GB | 500K~5M | sample_first | 10% 샘플 → 프로토 → 풀 |
    | 1GB~10GB | 5M~50M | chunked | 청크 처리 + 스트리밍 집계 |
    | > 10GB | > 50M | distributed | Spark/Dask/Ray |

- [ ] **Task 6-2.6**: 샘플링 유틸리티
  - File: `src/ds_agent/tools/sampling_utils.py`
  - 층화 샘플링 (타겟 비율 유지)
  - 시간 기반 샘플링 (최근 N일)
  - 랜덤 샘플링 (seed 고정)

- [ ] **Task 6-2.7**: `resource-aware-planning` Skill
  - File: `src/ds_agent/skills/builtin/resource-aware-planning.md`
  - "데이터 크기를 먼저 확인하고, 전략을 결정한 후 시작하라"

#### Quality Gate

- [ ] 전략 결정 정확성 (데이터 크기별)
- [ ] 샘플링 품질 (대표성 유지)
- [ ] OOM 방지 동작 확인

---

### Phase 6-3: Cross-Session Improvement

**Goal**: 프로젝트 간 학습으로 점점 나아지는 에이전트 (Hermes 스타일)

#### RED: Write Failing Tests First

- [ ] **Test 6-3.1**: 이전 프로젝트 패턴 자동 활용
  - File: `tests/unit/application/test_cross_session.py`
  - Scenario: churn 프로젝트 A 완료 → 새 churn 프로젝트 B 시작 → A의 유효 피처셋 제안
  - Expected: Tests FAIL

- [ ] **Test 6-3.2**: 실패 패턴 회피
  - File: `tests/unit/application/test_cross_session.py`
  - Scenario: 이전에 "random split for time series" → 실패 기록 → 새 프로젝트에서 경고
  - Expected: Tests FAIL

- [ ] **Test 6-3.3**: Memory 기반 컨텍스트 주입
  - File: `tests/unit/application/test_cross_session.py`
  - Scenario: 세션 시작 시 관련 과거 프로젝트 메모리 자동 검색 → 프롬프트에 주입
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 6-3.4**: CrossSessionLearner
  - File: `src/ds_agent/application/services/cross_session_learner.py`
  - 프로젝트 완료 시:
    1. 성공 패턴 추출 (유효한 피처, 효과적 모델, 좋은 시각화)
    2. 실패 패턴 추출 (에러 원인, 잘못된 접근법)
    3. 도메인 지식 업데이트 (조직 KPI 정의, 데이터 관계)
    4. Memory에 저장 (type=project, confidence=1.0)
  - 세션 시작 시:
    1. 사용자 요청에서 키워드 추출
    2. Memory 검색 (project + domain type)
    3. 관련 인사이트를 시스템 프롬프트에 주입

- [ ] **Task 6-3.5**: PostProjectLearner 확장
  - 기존 `self_improve/post_project.py` 확장
  - 프로젝트 종료 시 자동 회고 (retrospective)
  - "이 프로젝트에서 뭘 배웠는가?" 구조화

- [ ] **Task 6-3.6**: Prompt Builder 확장
  - `PromptBuilder`에 memory context 섹션 추가
  - "과거 유사 프로젝트에서의 학습:" 섹션

- [ ] **Task 6-3.7**: 벡터 기반 Memory 검색 (선택적)
  - File: `src/ds_agent/memory/vector_store.py`
  - 임베딩 모델로 메모리 항목 벡터화
  - 유사도 기반 검색 (기존 FTS5 보완)
  - 의존성: `sentence-transformers` 또는 LLM 임베딩 API

#### Quality Gate

- [ ] 이전 프로젝트 패턴 활용 확인
- [ ] 실패 패턴 경고 동작 확인
- [ ] 컨텍스트 주입 품질 확인 (관련성, 토큰 효율성)

---

### Phase 6-4: Distributed Compute

**Goal**: Spark/Dask/Ray 지원으로 대규모 데이터 처리

#### RED: Write Failing Tests First

- [ ] **Test 6-4.1**: Dask 어댑터 — pandas 코드를 Dask로 자동 변환
  - File: `tests/unit/infrastructure/test_dask_adapter.py`
  - Scenario: pandas DataFrame 처리 코드 → Dask DataFrame으로 변환 → 동일 결과
  - Expected: Tests FAIL

- [ ] **Test 6-4.2**: Ray 어댑터 — HPO 병렬화
  - File: `tests/unit/infrastructure/test_ray_adapter.py`
  - Scenario: Optuna HPO → Ray Tune으로 분산 실행 → 동일 최적 파라미터
  - Expected: Tests FAIL

- [ ] **Test 6-4.3**: Fallback — 분산 환경 없을 때 로컬 실행
  - File: `tests/unit/infrastructure/test_distributed_fallback.py`
  - Scenario: Ray 미설치 → graceful fallback to local pandas
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 6-4.4**: Domain Interface
  - File: `src/ds_agent/domain/interfaces/distributed.py`
  - `DistributedExecutor` Protocol:
    - `execute(code, data_path) → result`
    - `is_available() → bool`

- [ ] **Task 6-4.5**: Dask Adapter
  - File: `src/ds_agent/infrastructure/distributed/dask_adapter.py`
  - pandas → Dask DataFrame 자동 전환
  - 청크 기반 처리로 OOM 방지
  - 로컬 클러스터 또는 원격 스케줄러 지원

- [ ] **Task 6-4.6**: Ray Adapter
  - File: `src/ds_agent/infrastructure/distributed/ray_adapter.py`
  - Ray Tune 연동: HPO 병렬화
  - Ray Data: 대규모 데이터셋 처리
  - Ray Train: 분산 학습 (선택적)

- [ ] **Task 6-4.7**: `distributed_exec` Tool
  - File: `src/ds_agent/tools/distributed_tools.py`
  - ResourcePlanner가 "distributed" 전략 결정 시 자동 활성화
  - Parameters: code, backend (dask/ray/spark), data_path

- [ ] **Task 6-4.8**: Graceful Fallback
  - 분산 라이브러리 미설치 시 자동 로컬 실행
  - WARNING 메시지: "Dask/Ray 미설치, 로컬 pandas로 실행 중. 대용량 데이터는 OOM 위험."

#### Quality Gate

- [ ] 분산 실행 결과 정확성 (로컬과 동일)
- [ ] Fallback 동작 확인
- [ ] 성능 향상 확인 (대용량 데이터 기준)

---

## 4. 분석 유형별 라우팅 매트릭스 (최종)

| 문제 유형 | 키워드 | 핵심 방법론 | 필수 스킬 | 필수 가드레일 | 주요 산출물 |
|-----------|--------|-----------|----------|-------------|-----------|
| **Prediction** | 예측, predict | Baseline → ML → HPO | modeling, evaluation | baseline, overfitting | Model + model card |
| **Diagnosis** | 왜, 원인, 하락 | Metric decomposition, cohort | root-cause-tree, cohort-drill-down | cross-check | Root-cause tree + actions |
| **Forecasting** | 예보, forecast | ARIMA/Prophet/ML hybrid | backtesting, time-series | walk-forward, temporal-join | Forecast + uncertainty |
| **Anomaly** | 이상, 비정상 | SPC, Isolation Forest, DBSCAN | drift-triage, threshold-policy | false-positive-rate | Alert spec + threshold |
| **Experimentation** | A/B, 실험 | Power analysis, sequential | power-calculation, ab-test | SRM, novelty-effect | Experiment report + decision |
| **Segmentation** | 세그먼트, 군집 | Clustering, RFM, behavioral | cohort-drill-down | stability, actionability | Segment definitions |
| **Causal** | 효과, 인과 | Uplift, DiD, IV, SCM | causal-assumption-check | SUTVA, overlap | Treatment effect + caveats |
| **Ranking** | 순위, 랭킹 | Learning to Rank, BPR | ndcg-evaluation | position-bias | Ranked list + metrics |

---

## 5. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| 분석 유형 오분류 | 중 | 높음 | LLM 보조 분류 + 사용자 확인 단계 |
| 벡터 검색 품질 낮음 | 중 | 중간 | FTS5 + 벡터 하이브리드, fallback |
| 분산 환경 설정 복잡도 | 높음 | 중간 | 로컬 fallback, 점진적 도입 |
| Cross-session 오래된 패턴 적용 | 중 | 중간 | Confidence decay, 날짜 기반 필터 |
| 대규모 데이터 비용 | 중 | 높음 | 비용 추정 + 승인 게이트 |

---

## 6. Dependencies

### External Dependencies

```toml
[project.optional-dependencies]
distributed = [
    "dask[complete]>=2024.1.0",
    "ray[tune,data]>=2.9.0",
]
vector_search = [
    "sentence-transformers>=2.2.0",
    "lancedb>=0.5.0",
]
```

---

## 7. Progress Tracking

- Phase 6-1 (Method Flexibility): 0%
- Phase 6-2 (Resource-Aware Planning): 0%
- Phase 6-3 (Cross-Session Improvement): 0%
- Phase 6-4 (Distributed Compute): 0%
- **Overall Phase 6**: 0%

---

## Notes & Learnings

- [구현 중 발견 사항 기록]
