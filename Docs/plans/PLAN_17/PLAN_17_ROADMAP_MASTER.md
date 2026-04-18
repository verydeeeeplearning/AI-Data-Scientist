# AI Data Scientist Agent — 고도화 로드맵 마스터 계획

**Status**: Planning
**Created**: 2026-04-13
**Last Updated**: 2026-04-13
**Version**: 1.0.0
**기반 문서**: `Docs/Improvement/ai_ds_agent_capability_roadmap.md`

---

## 1. Executive Summary

### 현재 위치

DS Agent는 **Methodology Autonomy**가 잘 갖춰진 "자율 실행 가능한 분석기"다:
- 14개 Hook (7 builtin + 7 DS-specific)으로 방법론을 코드로 강제
- 19개 DS Tool + 8개 Skill + ProcessSandbox로 안전한 분석 실행
- 11개 LLM Provider + Smart Routing + Budget Tracking
- 1090+ 테스트 통과, Clean Architecture 준수

### 핵심 Gap

"로컬 분석 파이프라인은 강하지만, 조직 안에서 오래 일하는 자율성은 아직 약하다."

| Gap 영역 | 현재 | 목표 |
|----------|------|------|
| Memory | placeholder (핸들러 미구현) | 4계층 inspectable memory |
| Data Access | 로컬 파일만 | Warehouse + API + Catalog |
| Runtime | interactive only | 5가지 실행 모드 (Background, Scheduled, Event-Driven, Unattended) |
| Pipeline | 선형 Stage 1→8 | 비선형 DAG + 백트래킹 |
| Artifacts | markdown/html report만 | 11+ 산출물 유형 |
| Governance | 3-mode supervision | 정책 기반 다차원 승인 |
| Operations | 모니터링 비활성 | Drift/A-B Test/Retrain 자동화 |

### 목표

**Decision Autonomy + Data Autonomy + Operational Autonomy** 확보 →
진짜 delegateable AI Data Scientist 실현

### 차별화 전략

```
┌─────────────────────────────────────────────────────────┐
│  OpenClaw / Hermes / Claude Code에서 가져올 것:          │
│  → Autonomy Runtime (long-running, checkpoints,         │
│    memory, scheduling, subagents, background tasks)     │
│                                                          │
│  DS Agent만의 차별점:                                     │
│  → DS Judgment + Enterprise Trust                        │
│    (methodology harness, domain skills,                 │
│     governed data access, policy-based approval,        │
│     artifact generation, operational monitoring)        │
│                                                          │
│  핵심 포지셔닝:                                           │
│  "범용 자율 에이전트 인프라 + DS 도메인 전문성"             │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 7+1 Agent 역할 매핑

현업 DS 위임에 필요한 7+1 에이전트 역할과 시스템 매핑:

| # | Agent 역할 | 핵심 책임 | 현재 매핑 | 구현 Phase |
|---|-----------|----------|----------|-----------|
| 1 | **Problem Framing** | vague 요청 → 실행 가능한 분석 계약 | Stage 1 (Scoping) + ask_user | Phase 0, 6 |
| 2 | **Data Operations** | 이질적 데이터 소스 탐색·연결·검증 | data_loader (파일만) | Phase 1 |
| 3 | **Analysis Strategy** | 문제 유형별 방법론 선택·실행 계획 | 3 task types | Phase 5, 6 |
| 4 | **Autonomous Runtime** | 장시간·비대화형·재개 가능 실행 | disabled (코드 존재) | Phase 0, 2 |
| 5 | **Collaboration & Artifact** | 청중별 다양한 산출물 생성 | generate_report | Phase 4 |
| 6 | **Governance & Trust** | 재현성·추적성·감사 가능성 | audit + sandbox | Phase 3 |
| 7 | **Organizational Memory** | 세션·프로젝트·조직 지식 축적 | placeholder | Phase 0 |
| 8 | **Continuous Operations** | 배포 후 모니터링·대응 | 비활성 | Phase 5 |

---

## 3. 8개 유연성 축 (Flexibility Axes)

| # | Flexibility 축 | 현재 수준 | 목표 수준 | 달성 Phase |
|---|---------------|----------|----------|-----------|
| 1 | **Goal Flexibility** | 중 (scoping 존재) | 상 (자동 라우팅 + no-model 판단) | P0, P6 |
| 2 | **Data Flexibility** | 하 (file only) | 상 (warehouse + API + catalog) | P1 |
| 3 | **Method Flexibility** | 중 (3 task types) | 상 (7+ 분석 유형) | P5, P6 |
| 4 | **Runtime Flexibility** | 하 (interactive only) | 상 (5가지 실행 모드) | P0, P2 |
| 5 | **Supervision Flexibility** | 중 (3 modes) | 상 (정책 기반 다차원 제어) | P3 |
| 6 | **Deliverable Flexibility** | 하 (report만) | 상 (11+ 산출물 유형) | P4 |
| 7 | **Governance Flexibility** | 중 (audit + sandbox) | 상 (full lineage + policy) | P3 |
| 8 | **Memory Flexibility** | 하 (placeholder) | 상 (4-layer inspectable memory) | P0 |

---

## 4. Phase 전체 구조 & 의존관계

### 4.1 Phase 요약

| Phase | 명칭 | 핵심 목표 | 항목 수 | 예상 규모 |
|-------|------|----------|---------|----------|
| **P0** | Foundation | 자율성의 기본 전제 확보 | 3 | Medium (4-5 phases) |
| **P1** | Data Autonomy | 현업 위임 1순위 병목 해소 | 5 | Large (6-7 phases) |
| **P2** | Runtime Autonomy | 장기 실행·반복 위임 가능 | 5 | Large (6-7 phases) |
| **P3** | Enterprise Trust | 엔터프라이즈 신뢰·거버넌스 | 5 | Large (6-7 phases) |
| **P4** | Artifact & Communication | 다양한 산출물·조직 연동 | 4 | Medium (4-5 phases) |
| **P5** | Operations & Continuous Improvement | 운영·모니터링·도메인 확장 | 5 | Large (6-7 phases) |
| **P6** | Advanced Autonomy | 고급 자율성·분산 컴퓨팅 | 4 | Large (6-7 phases) |

### 4.2 의존관계 그래프

```
Phase 0: Foundation ──────────────────────────────────────┐
  │  (Self-Debugging, Backtrack, Memory)                  │
  │                                                        │
  ├──► Phase 1: Data Autonomy                              │
  │      (Connectors, SQL, Execution Path Separation)      │
  │                                                        │
  ├──► Phase 2: Runtime Autonomy                           │
  │      (Autonomous Runtime, Task Graph, Standing Orders) │
  │      ※ P0 Memory 필수 의존                              │
  │                                                        │
  │    Phase 1 ──┐                                         │
  │    Phase 2 ──┼──► Phase 3: Enterprise Trust            │
  │              │     (Policy Approval, Lineage, PII)     │
  │              │                                         │
  │              ├──► Phase 4: Artifact & Communication    │
  │              │     (Artifact Stack, Reporting, 연동)    │
  │              │                                         │
  │              └──► Phase 5: Operations                  │
  │                    (Drift, A/B Test, Domain Packs)     │
  │                                                        │
  │    Phase 3 ──┐                                         │
  │    Phase 4 ──┼──► Phase 6: Advanced Autonomy           │
  │    Phase 5 ──┘     (Method, Resource, Distributed)     │
  │                                                        │
  └────────────────────────────────────────────────────────┘
```

### 4.3 의존관계 상세

| Phase | 선행 조건 (blockedBy) | 후행 Phase (blocks) |
|-------|----------------------|---------------------|
| **P0** | 없음 (즉시 시작 가능) | P1, P2, P3, P4, P5, P6 |
| **P1** | P0 완료 (Self-Debugging 필요) | P3, P4, P5 |
| **P2** | P0 완료 (Memory + Backtrack 필요) | P3, P5 |
| **P3** | P1, P2 완료 | P6 |
| **P4** | P1 완료 (최소), P2 권장 | P6 |
| **P5** | P1, P2 완료 | P6 |
| **P6** | P3, P4, P5 완료 | 없음 |

### 4.4 병렬 실행 가능 구간

```
Timeline ──────────────────────────────────────────────►

Sprint 1-3:  [═══ P0: Foundation ═══]
Sprint 4-8:  [═══ P1: Data ═══] [═══ P2: Runtime ═══]  ← 병렬 가능
Sprint 9-14: [═══ P3: Trust ═══] [═══ P4: Artifact ═══] [═══ P5: Ops ═══] ← 3개 병렬
Sprint 15+:  [═══ P6: Advanced ═══]
```

---

## 5. Hook 카탈로그 (기존 14 + 신규 10)

### 5.1 기존 Hooks (14개, 유지)

| # | Hook | Priority | 역할 | Layer |
|---|------|----------|------|-------|
| 1 | `AuditLogHook` | 0 | JSONL 감사 로깅 | Governance |
| 2 | `SessionInitHook` | 0 | Safety/DS방법론/Quality 규칙 주입 | Runtime |
| 3 | `ProcessMetricsHook` | 1 | Tool 실행 메트릭 수집 | Runtime |
| 4 | `WorkflowTrackerHook` | 5 | 8단계 워크플로우 추적 | DS Methodology |
| 5 | `PermissionHook` | 10 | Mode + safety 기반 접근 제어 | Governance |
| 6 | `BudgetGuardHook` | 20 | 비용 95% 초과 시 거부 | Runtime |
| 7 | `BaselineGuardHook` | 25 | Baseline 없이 모델링 경고 | DS Methodology |
| 8 | `LeakageDetectionHook` | 30 | 데이터 누수 패턴 스캔 | DS Methodology |
| 9 | `OverfittingDetectorHook` | 35 | Train/test gap >15% 경고 | DS Methodology |
| 10 | `ModelSanityCheckHook` | 40 | 예측 분포/permutation/단일피처 검증 | DS Methodology |
| 11 | `StageQualityHook` | 45 | 단계별 DS 방법론 점수 | DS Methodology |
| 12 | `ProfileResultsHook` | 46 | 프로파일 결과 이벤트 | DS Methodology |
| 13 | `ExperimentTrackerHook` | 50 | 실험 메트릭 추출 및 이벤트 | Memory |
| 14 | `ExecPlanSaveHook` | 55 | 실행 계획 저장 | Runtime |

### 5.2 신규 Hooks (10개, 구현 대상)

| # | Hook | Priority | 역할 | 구현 Phase |
|---|------|----------|------|-----------|
| 1 | `ProblemTypeRouterHook` | 3 | 요청에서 문제 유형 감지 → 워크플로우 경로 제안 | P0 |
| 2 | `MetricContractHook` | 8 | KPI 정의 변경 시 downstream 영향 경고 | P3 |
| 3 | `PIIRedactionHook` | 12 | PII 컬럼 자동 감지 및 마스킹 강제 | P3 |
| 4 | `QueryCostGuardHook` | 15 | SQL 쿼리 비용 추정, 임계치 초과 시 승인 요구 | P1 |
| 5 | `TemporalJoinGuardHook` | 28 | 시간축 조인에서 미래 정보 유출 패턴 탐지 | P1 |
| 6 | `SelfDebugHook` | 33 | 에러 발생 시 자동 진단 → 수정 → 재실행 루프 | P0 |
| 7 | `BacktrackTriggerHook` | 37 | 모델 성능 미달 시 자동 백트래킹 트리거 | P0 |
| 8 | `ExperimentDesignHook` | 42 | 실험 분석에서 power analysis, SRM check 자동 트리거 | P5 |
| 9 | `ClaimTraceabilityHook` | 52 | 보고서 주장-데이터 근거 연결 검증 | P4 |
| 10 | `DriftDetectionHook` | 60 | 운영 중 모델 입력 분포 변화 감지 | P5 |

---

## 6. Skill 확장 로드맵

### 6.1 기존 Skills (8개, 유지)

| Skill | 파일 | 단계 |
|-------|------|------|
| scoping | `skills/builtin/scoping.md` | Stage 1 |
| data-profiling | `skills/builtin/data-profiling.md` | Stage 2-3 |
| eda | `skills/builtin/eda.md` | Stage 4 |
| feature-engineering | `skills/builtin/feature-engineering.md` | Stage 5 |
| modeling | `skills/builtin/modeling.md` | Stage 6 |
| evaluation | `skills/builtin/evaluation.md` | Stage 7 |
| reporting | `skills/builtin/reporting.md` | Stage 8 |
| deployment | `skills/builtin/deployment.md` | Post-Stage |

### 6.2 신규 Skills (Phase별)

#### Phase 0: Foundation Skills

| Skill ID | 설명 |
|----------|------|
| `task-type-routing` | 문제 유형 자동 분류 → 적절한 분석 전략 라우팅 |
| `no-model-decision` | 모델링 불필요 상황 인식 (단순 집계, 정의 문제, 데이터 부족) |
| `self-verification` | 각 단계 완료 후 자체 검증 (출력 유효성, 일관성) |
| `failure-recovery` | 에러 → 진단 → 수정 → 재실행 자율 루프 |

#### Phase 1: Data Autonomy Skills

| Skill ID | 설명 |
|----------|------|
| `sql-planning` | 분석 목적에 맞는 SQL 쿼리 설계 (CTE, window function, pushdown) |
| `schema-reasoning` | 스키마 탐색, 컬럼 의미 추론, source of truth 판별 |
| `temporal-join` | 시간축 정렬, look-ahead bias 방지, event-time vs processing-time |
| `join-strategy` | Fan-out 감지, cardinality 검증, granularity 매칭 |
| `pii-sensitivity` | PII 컬럼 자동 감지, 마스킹/제외 판단 |
| `cost-aware-execution` | 쿼리 비용 추정, 샘플링 전략, pushdown 최적화 |

#### Phase 4: Artifact Skills

| Skill ID | 설명 |
|----------|------|
| `narrative-synthesis` | 분석 결과를 스토리라인으로 구성 |
| `visualization-choice` | 데이터 유형·청중·메시지에 맞는 차트 선택 |
| `recommendation-writing` | 분석 결과 → 구체적 액션 추천 (조건·리스크 포함) |
| `stakeholder-qa` | 예상 질문 생성 및 답변 준비 |
| `claim-evidence-linking` | 모든 주장에 데이터 근거·시각화 연결 |

#### Phase 5: Operations & Domain Skills

| Skill ID | 설명 |
|----------|------|
| `drift-triage` | Drift 감지 후 원인 분류 (데이터 변화/계절성/개념 변화) |
| `retrain-vs-rollback` | Retrain/rollback/no-action 의사결정 프레임워크 |
| `ab-test-analysis` | A/B 테스트 결과 분석, 유의성 판정, 조기 중단 판단 |
| `power-calculation` | 실험 설계에 필요한 표본 크기, 검정력, 효과 크기 산정 |

#### Phase 5: Domain Skill Packs

| Pack | Skills | 도메인 특수 가드레일 |
|------|--------|---------------------|
| **금융** | `financial-ts-modeling`, `risk-metric-suite`, `look-ahead-bias-guard`, `aml-pattern-detection` | Walk-forward validation, 규제 보고 형식, PII 제약 |
| **의료** | `survival-analysis`, `hipaa-compliance`, `clinical-trial-analysis` | Censoring, de-identification, ITT/PP, multiplicity |
| **마케팅** | `uplift-modeling`, `attribution-modeling`, `ltv-prediction` | CATE 추정, 채널 중복, contractual vs non-contractual |

#### Phase 6: Advanced Skills

| Skill ID | 설명 |
|----------|------|
| `hypothesis-ranking` | 가설을 사전 확률·검증 비용·영향도로 우선순위화 |
| `causal-assumption-check` | 인과 추론 가정 (unconfoundedness, SUTVA, overlap) 검증 |
| `uncertainty-quantification` | 예측 불확실성 표현 (conformal prediction, bootstrapping) |
| `resource-aware-planning` | 데이터 크기에 따른 전략 자동 전환 (50GB vs 500KB) |

---

## 7. Tool 확장 로드맵

### 7.1 기존 Tools (19개, 유지)

data_loader, data_profiler, eda_analyzer, feature_engineer, model_trainer, model_evaluator, generate_report, execute_code, file_read, file_write, file_list, ask_user, memory_search, memory_store, skill_list, skill_view, web_search, error_translate, deploy_model

### 7.2 신규 Tools (Phase별)

| Phase | Tool | 설명 |
|-------|------|------|
| P0 | `self_debug` | 에러 진단 → 수정 코드 생성 → 재실행 (최대 N회) |
| P1 | `sql_query` | Governed SQL 쿼리 실행 (read-only, cost guard, timeout) |
| P1 | `schema_inspect` | 데이터 카탈로그/warehouse 스키마 탐색 |
| P1 | `data_catalog_search` | DataHub/Amundsen/dbt docs 검색 |
| P2 | `task_graph` | 비선형 태스크 그래프 관리 (분기, 백트래킹, 병렬) |
| P2 | `standing_order` | Standing order CRUD + 실행 상태 조회 |
| P2 | `checkpoint` | 명시적 체크포인트 생성/복원 |
| P3 | `lineage_capture` | 데이터·코드·모델 출처·변환 이력 기록 |
| P3 | `policy_check` | 작업별 정책 매칭, 승인 필요 여부 판단 |
| P4 | `notebook_generate` | .ipynb 노트북 생성 (코드 + 설명 + 시각화) |
| P4 | `slide_generate` | Executive memo / slide spec 생성 |
| P4 | `dashboard_spec` | BI 대시보드 스펙 (JSON/YAML) 생성 |
| P5 | `drift_monitor` | 모델 입력 분포 변화 감지 (PSI, KL divergence) |
| P5 | `ab_test` | A/B 테스트 설계·분석 (power, SRM, sequential) |
| P6 | `distributed_exec` | Spark/Dask/Ray 분산 실행 어댑터 |

---

## 8. 아키텍처 진화 계획

### 8.1 선형 → 비선형 실행 전환

**현재 (선형)**:
```
Scoping → Data Loading → Profiling → EDA → Feature Eng → Modeling → Evaluation → Reporting
```

**목표 (비선형 DAG)**:
- Stage 간 조건부 분기 (성능 미달 → Feature Eng 또는 EDA로 회귀)
- 새 데이터 필요 시 Data Loading으로 자동 회귀
- Experiment Branching (git branch 스타일 실험 트리)
- 병렬 실험 실행 (예산 내 최대 병렬)

### 8.2 실행 경로 분리 (Execution Path Separation)

**현재**: 단일 ProcessSandbox (requests/socket/subprocess 차단)

**목표**: 3-tier 실행 환경
```
┌────────────────────┐  로컬 분석, 피처 엔지니어링, 모델 훈련
│ Local Analysis     │  (현재 ProcessSandbox 확장)
│ Sandbox            │
└────────────────────┘

┌────────────────────┐  Snowflake/BigQuery/Redshift 쿼리
│ Read-Only          │  읽기 전용, 쿼리 비용 가드, 타임아웃
│ Warehouse Runner   │
└────────────────────┘

┌────────────────────┐  외부 API, Slack/Jira/Git
│ Policy-Approved    │  정책 승인 후 실행, 감사 로그 필수
│ Network Runner     │
└────────────────────┘
```

### 8.3 멀티 에이전트 아키텍처 (Phase 2+)

**현재**: Single-loop orchestrator

**목표**: Builder/Validator 분리
```
Builder/Analyst ──► Validator/Reviewer
       │                    │
       ▼                    ▼
    Reporter            Operator
```

- **Builder**: 가설 생성, 코드 작성, 모델 훈련
- **Validator**: 결과 검증, 방법론 감사, 대안 제시
- **Reporter**: 청중별 산출물 생성
- **Operator**: 모니터링, drift 대응, retrain 트리거

---

## 9. Clean Architecture 레이어 매핑

### 각 Phase의 구현 항목이 속하는 레이어

| 구현 항목 | Domain | Application | Infrastructure | Presentation |
|-----------|--------|-------------|----------------|--------------|
| Self-Debugging Loop | - | SelfDebugService | ErrorTranslator 확장 | - |
| BacktrackTriggerHook | - | Hook (Application rule) | WorkflowTracker 확장 | - |
| Memory 구현 | MemoryEntity | MemoryUseCase | SQLite + FTS5 | memory_search/store tools |
| SQL Connector | QuerySpec VO | QueryExecutionUseCase | Snowflake/BQ adapter | sql_query tool |
| Execution Path Sep. | ExecutionPolicy VO | ExecutionRouter | SandboxFactory | - |
| Task Graph | TaskNode Entity | TaskGraphService | Persistence | task_graph tool |
| Standing Orders | StandingOrder Entity | SchedulerService | CronRunner | standing_order tool |
| Policy-Based Approval | ApprovalPolicy Entity | PolicyEvaluator | ApprovalStore 확장 | - |
| Lineage | LineageRecord Entity | LineageCaptureService | LineageStore | lineage_capture tool |
| Artifact Stack | ArtifactSpec VO | ArtifactGenerator | Template Engine | notebook/slide/dashboard tools |
| Drift Monitoring | DriftMetric VO | DriftAnalyzer | ModelMonitorSensor | drift_monitor tool |
| Domain Skill Packs | - | SkillHub 확장 | Markdown files | skill_list/view |

---

## 10. 리스크 매트릭스

| Risk ID | 리스크 | 확률 | 영향 | 관련 Phase | 완화 전략 |
|---------|--------|------|------|-----------|----------|
| R-01 | Warehouse 연결 시 보안 취약점 | 중 | 높음 | P1 | Read-only 강제, 쿼리 비용 가드, 감사 로그 |
| R-02 | Self-Debugging 무한 루프 | 중 | 중간 | P0 | 최대 재시도 횟수 제한 (N=3), 같은 에러 반복 감지 |
| R-03 | Memory에 틀린 정보 축적 | 높음 | 높음 | P0 | Confidence decay, 인간 리뷰 게이트, 충돌 해결 |
| R-04 | Task Graph 복잡도 폭발 | 중 | 중간 | P2 | 최대 depth 제한, 타임아웃, 리소스 예산 |
| R-05 | PII 유출 | 낮음 | 매우높음 | P1, P3 | PIIRedactionHook, 자동 감지 + 마스킹, 감사 |
| R-06 | Standing Order 비용 폭주 | 중 | 높음 | P2 | Budget per order, 일일 한도, 이상치 알림 |
| R-07 | 비선형 파이프라인 디버깅 어려움 | 높음 | 중간 | P0, P2 | 실행 그래프 시각화, 체크포인트별 스냅샷 |
| R-08 | 다중 Connector 유지보수 부담 | 높음 | 중간 | P1 | 어댑터 패턴, 통합 테스트 스위트 |
| R-09 | 분산 컴퓨팅 환경 설정 복잡도 | 높음 | 낮음 | P6 | 로컬 모드 fallback, 점진적 도입 |
| R-10 | Domain Skill 정확성 | 중 | 높음 | P5 | 도메인 전문가 리뷰, 테스트 케이스, 버전 관리 |

---

## 11. 품질 기준 (전체 Phase 공통)

### Build & Test
- [ ] 프로젝트 빌드 오류 없음
- [ ] 기존 + 신규 테스트 전체 통과
- [ ] 단위 테스트 커버리지 ≥80%
- [ ] Integration 테스트: 핵심 경로 검증

### Clean Architecture
- [ ] Domain 레이어: 외부 의존성 제로
- [ ] Use Case: 포트 인터페이스만 의존 (구현체 직접 import 금지)
- [ ] 의존성 주입: Composition Root에서만
- [ ] 데이터 경계 통과: DTO 사용

### Code Quality
- [ ] `ruff check .` 통과
- [ ] `ruff format --check .` 통과
- [ ] `mypy` 통과 (설정 범위 내)

### Security
- [ ] 신규 보안 취약점 없음
- [ ] PII 처리 정책 준수
- [ ] Secret 노출 없음

---

## 12. 상세 계획 문서 인덱스

| 문서 | 파일명 | 내용 |
|------|--------|------|
| **Phase 0** | `PLAN_17a_P0_foundation.md` | Self-Debugging Loop, BacktrackTriggerHook, Memory 구현 |
| **Phase 1** | `PLAN_17b_P1_data_autonomy.md` | Governed Connectors, SQL Tool, Execution Path Separation |
| **Phase 2** | `PLAN_17c_P2_runtime_autonomy.md` | Autonomous Runtime 활성화, Task Graph, Standing Orders |
| **Phase 3** | `PLAN_17d_P3_enterprise_trust.md` | Policy-Based Approval, Lineage, PII, Reproducibility |
| **Phase 4** | `PLAN_17e_P4_artifact.md` | Artifact Stack 확장, Audience-Adaptive Reporting |
| **Phase 5** | `PLAN_17f_P5_operations.md` | Drift Monitoring, A/B Test, Domain Skill Packs |
| **Phase 6** | `PLAN_17g_P6_advanced.md` | Method Flexibility, Distributed Compute |

---

## 13. 용어 정의 (Quick Reference)

| 용어 | 정의 |
|------|------|
| **PSI** | Population Stability Index — 두 분포 간 안정성 측정. >0.1 경고, >0.2 위험 |
| **CATE** | Conditional Average Treatment Effect — 조건부 평균 처치 효과. Uplift 모델링 핵심 |
| **SRM** | Sample Ratio Mismatch — A/B 테스트에서 실제 vs 예상 샘플 비율 불일치 진단 |
| **SUTVA** | Stable Unit Treatment Value Assumption — 인과 추론의 핵심 가정 (단위 간 간섭 없음) |
| **CTE** | Common Table Expression — SQL 내 임시 결과셋 정의 (WITH 절) |
| **Pushdown** | 쿼리 최적화: 필터/집계를 데이터 소스 가까이에서 실행하여 전송 데이터 최소화 |
| **Fan-out** | 조인 시 1:N 관계로 행 수 폭발. 데이터 품질 리스크 |
| **Walk-forward** | 시계열 검증: 과거로 훈련 → 미래로 테스트하는 sliding/expanding window |
| **Conformal Prediction** | 분포 가정 없이 예측 구간을 생성하는 불확실성 정량화 방법 |
| **Platt Scaling** | 로지스틱 회귀를 사용한 확률 보정 (모델 출력 → 보정된 확률) |
| **Isotonic Regression** | 비모수적 단조 함수로 확률 보정. Platt보다 유연하나 과적합 위험 |
| **dbt** | Data Build Tool — SQL 기반 변환 + 문서화 + 테스트. Semantic layer로 지표 정의 |
| **DataHub/Amundsen** | 데이터 카탈로그 — 테이블/컬럼/소유자/계보를 검색·탐색하는 메타데이터 플랫폼 |
| **Feature Store** | 피처의 중앙 저장소 (Feast, Tecton). 학습/서빙 일관성 보장 |
| **MLflow** | ML 실험 추적 + 모델 레지스트리 + 배포 관리 오픈소스 플랫폼 |
| **Kedro** | Python ML 파이프라인 프레임워크. 재현 가능한 DAG + 데이터 카탈로그 |
| **Prefect** | Python 워크플로우 오케스트레이션. Airflow 대비 코드 우선 + 동적 DAG |
| **Ray** | 분산 컴퓨팅 프레임워크. 데이터 처리 + 학습 + 서빙을 단일 API로 |

---

## 14. 진행 상황 추적

| Phase | 상태 | 진행률 | 시작일 | 완료일 |
|-------|------|--------|--------|--------|
| P0: Foundation | **Complete** | **100%** | 2026-04-13 | 2026-04-14 |
| P1: Data Autonomy | **In Progress** | **40%** | 2026-04-14 | - |
| P2: Runtime Autonomy | **In Progress** | **30%** | 2026-04-14 | - |
| P3: Enterprise Trust | Pending | 0% | - | - |
| P4: Artifact | Pending | 0% | - | - |
| P5: Operations | Pending | 0% | - | - |
| P6: Advanced | Pending | 0% | - | - |
| **Overall** | **Planning** | **0%** | **2026-04-13** | - |

---

## Notes & Learnings

- [구현 중 발견 사항 기록]
- [계획 대비 변경 사항 기록]
