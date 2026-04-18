# DS Agent 고도화 방안: 자율형 DS → 업무 위임 가능한 DS Colleague

**작성일**: 2026-04-15
**대상 시스템**: DS Agent (AI Data Scientist)
**목표**: 완전한 업무 위임(Full Delegation)이 가능한 기업용 자율형 DS Agent로의 진화
**핵심 테제**: 지금 필요한 것은 더 똑똑한 Agent가 아니라, 더 책임질 수 있는 Agent다.

---

## 0. 현황 진단과 고도화 방향성

### 0.1 현재 시스템의 위치

DS Agent는 이미 "분석을 끝까지 수행하는 실행 엔진"으로서 상당한 성숙도를 보유한다.

- **실행 엔진**: LLM-orchestrator 단일 루프, 35+ 도구, @tool 자기등록
- **지능 계층**: 5-layer 메모리 (Session/Experiment/Code/Domain/Project + Unified), Skill Hub (Builtin 8 + Shared 6), Self-Improve (패턴 추출 → 도메인 KB → 커스텀 스킬 생성)
- **운영 인프라**: 승인/정책/센서/전달 정책 자동화, 스레드 인식 세션 격리, 크래시 복구
- **인터페이스**: CLI·Telegram·Electron 공통 코어, WebSocket JSON-RPC, i18n(ko/en)
- **검증**: 1,382 단위+스모크 테스트, Electron E2E, 패키지 바이너리 스모크

### 0.2 병목 진단

현재 병목은 알고리즘 수나 모델 지능이 아니다. 다음 세 가지에 집중되어 있다.

1. **회사 맥락을 정확히 아는가** — 조직의 metric 정의, 테이블 신뢰도, 비즈니스 캘린더, 과거 의사결정 로그를 agent가 이해하지 못한다.
2. **결과를 믿을 수 있는가** — planner는 있지만 verifier가 없다. 자기 결론을 깨보는 구조가 부재.
3. **조직 프로세스 안으로 들어가는가** — 분석 결과가 노트북에서 끝나고, Jira/Slack/Confluence/BI로 이어지지 않는다.

### 0.3 고도화 원칙

| 원칙 | 설명 |
|------|------|
| **No State Machine** | 기존 "LLM이 유일한 플래너" 철학을 유지. 하드코딩된 워크플로를 추가하지 않는다. |
| **Typed Artifact 확장** | LLM이 항상 생성·갱신해야 하는 구조화된 산출물(GoalBrief, MetricSpec 등)을 늘린다. |
| **3 Stakeholder 동시 만족** | 의뢰자(결과+액션), 리드(품질+리스크 통제), 플랫폼팀(정책 준수+감사 추적). |
| **Accountable Autonomy** | 자율성 확대의 전제는 검증과 책임 구조. "자동화"가 아니라 "위임". |

---

## 1. Task Contract 엔진 — 업무 위임 계약 계층

### 1.1 문제

현재 에이전트는 실행은 잘하지만, 기업에서 더 어려운 것은 **애매한 요청을 정확한 DS 문제로 변환하는 일**이다. "이탈 분석해줘"를 받으면 곧바로 data_loader를 호출하는 것이 아니라, 먼저 업무 계약서를 만들어야 한다.

### 1.2 핵심 Artifact: `TaskContract`

```yaml
# TaskContract Schema (v1)
task_id: "TC-2026-042"
type: churn_analysis  # → MissionPack 매핑 키
status: draft | agreed | in_progress | review | closed

# 업무 정의
business_goal: "Q2 이탈률 1pp 감소를 위한 핵심 이탈 드라이버 식별"
primary_kpi:
  name: monthly_churn_rate
  baseline: 4.2%
  target: 3.2%
  measurement_window: 2026-Q2
secondary_kpis:
  - name: retention_30d
    direction: higher_is_better
decision_owner: "김상무 (Growth팀)"
decision_deadline: 2026-05-15

# 데이터 및 자원 계약
allowed_data_sources:
  - warehouse: snowflake
    schema: growth.user_events
    access_level: read_only
  - warehouse: snowflake
    schema: growth.subscription
    access_level: read_only
forbidden_data:
  - "*.pii_raw.*"
  - "hr.*"
budget:
  max_compute_cost: $50
  max_llm_cost: $20
  max_wall_time: 4h

# 산출물 계약
required_deliverables:
  - type: exec_brief
    audience: executive
    format: pptx
  - type: ds_appendix
    audience: ds_peer
    format: ipynb
  - type: action_proposals
    audience: pm
    format: jira_tickets
    count: 3

# 자율성 경계
agent_will_do:
  - 데이터 로딩 및 프로파일링
  - EDA 및 피처 엔지니어링
  - 모델 학습 및 평가
  - 리포트 초안 작성
agent_will_ask:
  - 피처 정의 모호성 해소
  - 비즈니스 컨텍스트 확인 (예: 최근 프로모션 이벤트)
agent_will_escalate:
  - 민감 데이터 접근 필요 시
  - 모델 성능이 baseline 대비 개선 없을 시
  - 배포/외부 전송 액션

# 검증 기준
definition_of_done:
  - 주요 이탈 드라이버 3개 이상 식별
  - 통계적 유의성 검증 (p < 0.05)
  - 실행 가능한 액션 제안 3건
  - 리뷰어 승인
rollback_rule: "배포 후 7일 내 이탈률 증가 시 자동 롤백"
```

### 1.3 하위 Artifact 체계

TaskContract 안에서 LLM이 생성·갱신하는 typed artifact들:

| Artifact | 역할 | 생성 시점 |
|----------|------|-----------|
| **GoalBrief** | 비즈니스 목표 → DS 문제 변환. KPI, 비교 기준, 의사결정 시점, 기대 산출물 | Task 시작 시 |
| **MetricSpec** | 각 metric의 정의, 계산식, 소스 테이블, owner, refresh 주기 | 데이터 탐색 후 |
| **DatasetManifest** | 사용 데이터셋 목록, 스키마, freshness, 신뢰도 등급, 접근 권한 | 데이터 로딩 후 |
| **AssumptionLog** | 에이전트가 묻지 않고 진행한 가정, 검증 상태, 리스크 수준 | 분석 전 과정 |
| **ReviewVerdict** | 각 검증 단계(통계/데이터/정책/서술)의 pass/warn/fail 결과 | 검증 완료 시 |
| **DeliveryPack** | audience별 산출물 번들 + 전달 채널 + 후속 액션 | 분석 완료 시 |

### 1.4 구현 위치

| 컴포넌트 | 위치 | 변경 내용 |
|----------|------|-----------|
| TaskContract 도메인 모델 | `domain/entities/` | Pydantic 스키마, 상태 전이 규칙 |
| TaskContract 유즈케이스 | `application/usecases/` | create, negotiate, agree, close |
| TaskContract 저장소 | `infrastructure/persistence/` | SQLite 테이블, 마이그레이션 v5 |
| TaskContract 도구 | `tools/task_contract_tools.py` | LLM이 호출하는 CRUD 도구 |
| prompt_sections 확장 | `agent/prompt_sections.py` | 시스템 프롬프트에 현재 contract 컨텍스트 주입 |
| Electron UI | `electron/src/renderer/components/mission/` | MissionBriefPanel, ContractEditor |

### 1.5 UX 흐름

```
사용자: "이번 분기 churn 분석해줘"
    ↓
Agent: GoalBrief 초안 생성 → MissionBriefPanel에 렌더링
    ↓
사용자: 카드 확인, "allowed_data에 마케팅 캠페인 데이터도 추가해줘" 수정
    ↓
Agent: TaskContract agreed 상태로 전환 → 분석 시작
    ↓
(분석 중) AssumptionLog 실시간 갱신, 사용자는 언제든 조회 가능
    ↓
Agent: ReviewVerdict 생성 → 검증 통과 시 DeliveryPack 생성
    ↓
사용자: 산출물 확인, 승인 → TaskContract closed
```

---

## 2. Enterprise Semantic Memory — 조직 의미론 grounding

### 2.1 문제

기업에서 가장 많이 깨지는 지점은 "SQL을 못 짜서"가 아니라 **metric 정의가 조직마다 다르기 때문**이다. 같은 "이탈률"이라도 팀마다 정의가 다르고, 같은 테이블이라도 신뢰도와 refresh 주기가 다르다.

현재 `domain_kb`는 자유 형식 insight 저장에 머물러 있다. 이를 **조직이 공인한 의미론적 기억**으로 승격시켜야 한다.

### 2.2 Semantic Layer 아키텍처

```
┌─────────────────────────────────────────────────────┐
│  Semantic Memory Layer (domain_kb 확장)              │
│                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ Metric      │  │ Business     │  │ Verified    │ │
│  │ Catalog     │  │ Glossary     │  │ Query       │ │
│  │             │  │              │  │ Patterns    │ │
│  └──────┬──────┘  └──────┬───────┘  └──────┬──────┘ │
│         └────────────────┼─────────────────┘         │
│                          ▼                            │
│  ┌─────────────────────────────────────────────┐     │
│  │ Data Trust Registry                          │     │
│  │ - 테이블 신뢰도 등급 (Gold/Silver/Bronze)    │     │
│  │ - Column-level lineage                       │     │
│  │ - Refresh SLA & freshness                    │     │
│  │ - Access policy & PII classification         │     │
│  │ - Approved join paths                        │     │
│  └──────┬──────────────────────────────────────┘     │
│         ▼                                            │
│  ┌─────────────────────────────────────────────┐     │
│  │ Organizational Context                       │     │
│  │ - Fiscal / campaign / freeze calendar        │     │
│  │ - Team ownership map                         │     │
│  │ - Past decision log                          │     │
│  │ - "이 팀은 어떤 metric으로 승인하는가"       │     │
│  │ - Negative knowledge (실패 이력 + 이유)      │     │
│  └─────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────┘
```

### 2.3 Metric Catalog 스키마

```yaml
# metric_catalog/monthly_churn_rate.yaml
metric_id: monthly_churn_rate
display_name: "월간 이탈률"
owner: growth_team
definition: "당월 구독 해지 고객 수 / 전월 말 활성 구독 고객 수"
calculation:
  numerator:
    table: growth.subscription
    filter: "event_type = 'cancel' AND event_date BETWEEN month_start AND month_end"
  denominator:
    table: growth.subscription
    filter: "status = 'active' AS OF last_day_of_prev_month"
grain: monthly
direction: lower_is_better
typical_range: [0.02, 0.08]
related_metrics: [retention_30d, ltv, arpu]
caveats:
  - "프로모션 기간 중 일시적 하락 주의 — 프로모션 종료 후 반등 패턴 존재"
  - "B2B/B2C 세그먼트 분리 필수 — 혼합 시 Simpson's paradox 위험"
verified_queries:
  - id: vq_churn_001
    description: "월간 이탈률 기본 쿼리"
    sql: |
      SELECT DATE_TRUNC('month', cancel_date) AS month,
             COUNT(DISTINCT user_id)::FLOAT / 
             LAG(COUNT(DISTINCT CASE WHEN status='active' THEN user_id END)) 
               OVER (ORDER BY month)
      FROM growth.subscription
      GROUP BY 1
    last_verified: 2026-03-15
    verified_by: "이수진 (Analytics Lead)"
```

### 2.4 Semantic Query 우선 아키텍처

**핵심 설계: raw SQL을 1차 수단이 아니라 fallback으로 내린다.**

```
사용자 질의: "지난 분기 이탈률이 어떻게 됐어?"
    ↓
[1] semantic_query 도구
    → Metric Catalog에서 "이탈률" 매칭
    → verified_query 패턴 활용
    → 정의·owner·caveat 자동 첨부
    ↓ (매칭 실패 시)
[2] sql_tools (fallback)
    → schema introspection 기반 SQL 생성
    → ⚠️ "이 쿼리는 공인 metric 정의가 아닌 추론 기반입니다" 경고 태깅
```

### 2.5 Data Trust Registry

| 등급 | 기준 | Agent 행동 |
|------|------|-----------|
| **Gold** | 공인 소스, SLA 준수, lineage 완비, owner 명시 | 자율 사용 가능 |
| **Silver** | 정기 갱신되지만 lineage 불완전 또는 owner 미지정 | 사용 가능, caveat 첨부 |
| **Bronze** | 비정기 갱신, 스키마 불안정, 검증 이력 없음 | 사용자 확인 후 사용, 경고 표시 |
| **Untrusted** | 출처 불명, PII 미분류, 접근 정책 미설정 | 사용 불가, 에스컬레이션 |

### 2.6 구현 위치

| 컴포넌트 | 위치 | 변경 내용 |
|----------|------|-----------|
| MetricCatalog | `memory/metric_catalog.py` | YAML/JSON 기반 metric 정의 저장·검색 |
| BusinessGlossary | `memory/business_glossary.py` | 용어 사전, 동의어 매핑, FTS 연동 |
| DataTrustRegistry | `memory/data_trust_registry.py` | 테이블/컬럼 신뢰도, lineage, SLA |
| VerifiedQueryStore | `memory/verified_query_store.py` | 검증된 쿼리 패턴 저장·매칭 |
| OrgContextStore | `memory/org_context_store.py` | 캘린더, 팀 맵, 의사결정 로그 |
| semantic_query 도구 | `tools/semantic_query.py` | Metric Catalog 우선 쿼리 생성 |
| Skill: domain-pack-enterprise | `skills/domain/` | 조직별 semantic pack 로드 |
| Electron: MetricSourcePanel | `electron/.../components/semantic/` | 숫자 아래 정의·출처·owner 표시 |

### 2.7 외부 연동 로드맵

| Phase | 대상 | 연동 방식 |
|-------|------|-----------|
| P0 | Postgres (현재 GA) | 현행 유지 |
| P1 | BigQuery / Snowflake | `integration_tools` 확장, 스키마 메타데이터 자동 수집 |
| P1 | dbt Semantic Layer | MetricFlow API 연동, metric 정의 동기화 |
| P2 | Databricks Unity Catalog | Column-level lineage, ABAC 정책 import |
| P2 | Looker / Tableau | Golden query 패턴 import, 비즈니스 glossary 동기화 |
| P3 | Custom semantic layer | 자체 YAML 기반 metric definition → MetricCatalog 매핑 |

---

## 3. Verifier Orchestrator — 검증 체계

### 3.1 문제

현재 시스템에는 planner(LLM)는 있지만 독립적인 verifier가 없다. `temporal_join_guard_hook`과 `query_cost_guard_hook`이 씨앗으로 존재하지만, 이들은 개별 guard에 불과하다. **"자기 결론을 체계적으로 깨보는 구조"**가 필요하다.

### 3.2 4-Layer Verifier 아키텍처

```
┌─────────────────────────────────────────────────────┐
│  Verifier Orchestrator                               │
│  (agent/verifier_orchestrator.py)                    │
│                                                       │
│  ┌─────────────────────────────────────────────┐     │
│  │ Layer 1: Statistical Verifier               │     │
│  │ - Data leakage detection (train/val 오염)   │     │
│  │ - Temporal split robustness                 │     │
│  │ - Subgroup stability (segment별 성능 편차)  │     │
│  │ - Baseline comparison (naive model 대비)    │     │
│  │ - Power analysis / sample size adequacy     │     │
│  │ - Class imbalance impact assessment         │     │
│  │ - Multicollinearity check                   │     │
│  │ - Overfitting detection (train-val gap)     │     │
│  │ - Multiple testing correction               │     │
│  │ - Effect size & practical significance      │     │
│  └─────────────────────────────────────────────┘     │
│                                                       │
│  ┌─────────────────────────────────────────────┐     │
│  │ Layer 2: Data Verifier                      │     │
│  │ - Schema contract validation                │     │
│  │ - Freshness & SLA compliance                │     │
│  │ - Null/spike anomaly detection              │     │
│  │ - Join validity & cardinality check         │     │
│  │ - Distribution drift (vs 학습 데이터)       │     │
│  │ - Referential integrity                     │     │
│  └─────────────────────────────────────────────┘     │
│                                                       │
│  ┌─────────────────────────────────────────────┐     │
│  │ Layer 3: Policy Verifier                    │     │
│  │ - PII exposure check                        │     │
│  │ - Access scope validation                   │     │
│  │ - Cost budget compliance                    │     │
│  │ - Risky action detection                    │     │
│  │ - Retention policy compliance               │     │
│  │ - Write side-effect preview                 │     │
│  └─────────────────────────────────────────────┘     │
│                                                       │
│  ┌─────────────────────────────────────────────┐     │
│  │ Layer 4: Narrative Verifier                 │     │
│  │ - Claim-evidence alignment                  │     │
│  │ - Overstatement / hedge detection           │     │
│  │ - Causal language appropriateness           │     │
│  │ - Metric citation accuracy                  │     │
│  │ - Recommendation feasibility                │     │
│  └─────────────────────────────────────────────┘     │
│                                                       │
│  ──────────── Aggregation ────────────               │
│  ReviewVerdict = {                                    │
│    overall: pass | warn | fail,                       │
│    layers: [...],                                     │
│    blocking_issues: [...],                            │
│    confidence_score: 0.0~1.0,                         │
│    confidence_rationale: "...",                        │
│    recommended_actions: [...]                          │
│  }                                                    │
└─────────────────────────────────────────────────────┘
```

### 3.3 Confidence Scoring 체계

모든 결과물에 자동으로 태깅되는 확신도 점수:

| 등급 | 점수 범위 | 의미 | Agent 행동 |
|------|-----------|------|-----------|
| **High** | 0.8–1.0 | 충분한 데이터, 안정적 metric, 검증 통과 | 결과 전달 + 액션 제안 |
| **Medium** | 0.5–0.8 | 일부 caveat 존재, 추가 검토 권장 | 결과 전달 + caveat 명시 + 리뷰 요청 |
| **Low** | 0.2–0.5 | 주요 가정 미검증, 데이터 품질 이슈 | 중간 결과만 전달 + 에스컬레이션 |
| **Insufficient** | 0.0–0.2 | 결론 불가 | 분석 중단 + 사유 보고 + 대안 제시 |

### 3.4 기존 Hook과의 관계

현재 26개 훅 중 검증 관련 훅을 Verifier Orchestrator로 통합:

| 기존 훅 | Verifier Layer 매핑 | 변경 |
|---------|---------------------|------|
| `temporal_join_guard_hook` | Statistical Verifier | 흡수, 확장 |
| `query_cost_guard_hook` | Policy Verifier | 흡수 |
| `governance_hooks` | Policy Verifier | 연동 |
| `self_debug_hook` | (유지) | Verifier와 별도 — 런타임 디버깅 용도 |
| `ds_workflow_hooks` | Statistical + Data Verifier | 일부 흡수 |

### 3.5 Skeptical Review 프로세스

```
분석 완료 직전
    ↓
Verifier Orchestrator 실행
    ↓
각 Layer 독립 실행 (병렬 가능)
    ↓
ReviewVerdict 생성
    ↓
    ├── overall: pass → DeliveryPack 생성 진행
    ├── overall: warn → 결과에 caveat 첨부, 사용자에게 warn 표시
    └── overall: fail → 분석 결론 보류, blocking issues 보고
                         → 자동 수정 시도 또는 사용자 개입 요청
```

### 3.6 구현 위치

| 컴포넌트 | 위치 |
|----------|------|
| VerifierOrchestrator | `agent/verifier_orchestrator.py` |
| StatisticalVerifier | `tools/verifiers/statistical.py` |
| DataVerifier | `tools/verifiers/data.py` |
| PolicyVerifier | `tools/verifiers/policy.py` |
| NarrativeVerifier | `tools/verifiers/narrative.py` |
| ReviewVerdict 모델 | `domain/entities/review_verdict.py` |
| ConfidenceScorer | `agent/confidence_scorer.py` |
| Electron UI | `components/workflow/QualityPanel` 확장 — pass/warn/fail 배지 |

---

## 4. Autonomy Control Plane — 3축 자율성 제어

### 4.1 문제

현재 `auto / supervised / step-by-step` 3모드는 전역 스위치다. 기업 환경에서는 "read-only SQL은 자율, 민감 테이블 접근은 승인, 모델 배포는 이중 승인"처럼 **행동 유형별 세분화된 자율성 매트릭스**가 필요하다.

### 4.2 3축 모드 체계

Mode를 단일 enum이 아니라 3개 독립 축으로 분리한다.

#### 축 1: Authority Mode (자율성 수준)

| 모드 | 설명 | 외부 Side Effect | 승인 정책 |
|------|------|------------------|-----------|
| **Shadow** | 끝까지 수행하지만 외부 side effect 없음 | ❌ | 불필요 |
| **Supervised** | 모든 핵심 액션 전 승인 | 승인 후 | 모든 액션 |
| **Delegate** | 반복적 저위험 액션은 자동, 고위험만 승인 | 조건부 | 고위험만 |
| **Autopilot** | 인증된 playbook 안에서 자동 실행 | 정책 범위 내 | boundary 이탈 시만 |
| **Incident** | 속도 우선, 설명 축약, 알림 강화 | 긴급 실행 | 사후 보고 |
| **Freeze** | read-only, 외부 write 금지 | ❌ | 해제 전까지 |

#### 축 2: Audience Profile (사용자 적응)

| 프로필 | Tone | 설명 Depth | 기본 산출물 | Challenge Level | 불확실성 표현 |
|--------|------|-----------|------------|-----------------|--------------|
| **Junior Mentor** | 교육적, 친절 | 매우 상세 — "왜 이걸 선택했는지" 포함 | 체크리스트 + 설명 노트 + 코드 주석 | 낮음 — 보수적 승인 임계값 | 명시적 ("이 결과는 ~이유로 불확실합니다") |
| **Peer DS** | 동료적, 간결 | 중간 — 대안과 trade-off 포함 | 재현 가능한 artifact (노트북, SQL) | 중간 — 대안 2-3개 제시 | 기술적 ("CI: [0.72, 0.81], p=0.03") |
| **Senior / Staff** | 단단하고 짧게 | 핵심만 — 가정, 리스크, decision point | 의사결정 메모 + diff | 높음 — scope 재정의까지 역제안 | 요약형 ("high confidence, one caveat") |
| **Executive** | 비즈니스 중심 | 최소 — impact, risk, ETA, needed decision | 1-page brief + 액션 카드 | 의사결정 초점 | 직관적 ("🟢 안전 / 🟡 검토 필요 / 🔴 위험") |
| **Auditor** | provenance 중심 | 매우 상세 — 데이터 출처, 정책, 승인 이력 | 감사 추적 문서 + lineage | 제로 — 사실만 기술 | 정량적 + 정책 참조 |

**구현**: `prompt_sections.py`에 audience_profile 파라미터를 받는 persona 템플릿 레이어 추가. prompt_builder가 현재 TaskContract의 audience 설정에 따라 자동 선택.

#### 축 3: Mission Pack (업무 패키지)

기존 `skills/`의 markdown 스킬을 "기술 조각"에서 "업무 패키지"로 승격.

```yaml
# skills/missions/weekly-kpi-triage.yaml
name: weekly-kpi-triage
display_name: "주간 KPI 이상치 진단"
description: "주요 KPI 이상 감지 시 원인 분석 및 액션 제안"

# 기본 Authority & Audience
authority_default: delegate
audience_default: senior

# 데이터 범위
allowed_data_domains: [growth, sales, marketing]
required_semantic_metrics: [monthly_churn_rate, revenue_per_user, dau]

# 필수 검증
required_checks:
  - schema_drift
  - temporal_leakage
  - baseline_compare
  - subgroup_stability
  - causal_assumption_check

# 필수 산출물
required_artifacts:
  - exec_brief     # Executive 요약
  - ds_appendix    # DS 상세 분석
  - jira_ticket    # 후속 액션 티켓

# 자동 에스컬레이션 조건
auto_escalate_when:
  - confidence_low
  - deploy_needed
  - sensitive_data_detected
  - anomaly_severity: critical

# 성공 기준
success_criteria:
  - issue_classified
  - root_cause_identified
  - owner_assigned
  - next_action_proposed

# 연결되는 스킬
skills_required:
  - builtin/eda
  - builtin/evaluation
  - shared/hypothesis-ranking
  - shared/causal-assumption-check
```

### 4.3 Action-Level Autonomy Matrix

Authority Mode가 전역이 아니라 액션 클래스별로 적용:

| Action Class | Shadow | Supervised | Delegate | Autopilot |
|-------------|--------|------------|----------|-----------|
| Read-only SQL (Gold table) | ✅ auto | ✅ auto | ✅ auto | ✅ auto |
| Read-only SQL (Bronze table) | ✅ auto | ⚠️ ask | ⚠️ ask | ⚠️ ask |
| 민감 테이블 접근 | ❌ skip | 🔒 approve | 🔒 approve | 🔒 approve |
| Feature engineering | ✅ auto | ✅ auto | ✅ auto | ✅ auto |
| Model training | ✅ auto | ⚠️ ask | ✅ auto | ✅ auto |
| Artifact 초안 작성 | ✅ auto | ✅ auto | ✅ auto | ✅ auto |
| Jira ticket 생성 | ❌ skip | 🔒 approve | ⚠️ ask | ✅ auto |
| Slack 메시지 전송 | ❌ skip | 🔒 approve | 🔒 approve | ⚠️ ask |
| Staging 실험 배포 | ❌ skip | 🔒 approve | 🔒 approve | ⚠️ ask |
| Production 모델 배포 | ❌ skip | 🔒🔒 dual | 🔒🔒 dual | 🔒 approve |
| 외부 이메일 발송 | ❌ skip | 🔒 approve | 🔒 approve | 🔒 approve |

### 4.4 Autonomy Certification (Playbook 승급 제도)

Autopilot은 "켜짐/꺼짐"이 아니라 **playbook별 승급 제도**로 운영:

```yaml
# Certification Requirements per MissionPack
certification:
  name: weekly-kpi-triage
  current_level: delegate
  autopilot_requirements:
    - shadow_runs_passed: 10      # Shadow 모드에서 10회 성공
    - critical_violations: 0       # 중대 정책 위반 0건
    - verifier_avg_score: ≥ 0.85  # Verifier 평균 점수
    - rollback_rehearsal: passed   # 롤백 리허설 통과
    - owner_approvals: ≥ 2        # 오너 2명 이상 승인
  certification_history:
    - date: 2026-03-01
      level: shadow → supervised
      approved_by: "박경순 이사"
    - date: 2026-03-20
      level: supervised → delegate
      approved_by: "조상덕 책임"
  next_review: 2026-06-01
```

### 4.5 구현 위치

| 컴포넌트 | 위치 |
|----------|------|
| AuthorityMode enum | `domain/value_objects/authority_mode.py` |
| AudienceProfile enum + templates | `agent/prompt_sections.py` (확장) |
| MissionPack loader | `skills/mission_pack_loader.py` |
| AutonomyPolicy engine | `runtime/autonomy_policy.py` (policy_engine 확장) |
| ActionClassifier | `runtime/action_classifier.py` |
| AutonomyCertification store | `runtime/autonomy_certification_store.py` |
| Electron: PolicyStudio | `components/settings/PolicyStudio.tsx` |
| Electron: CertificationBoard | `components/runtime/CertificationBoard.tsx` |

---

## 5. Evaluation Harness — Agent 성과 관리

### 5.1 문제

현재 self_improve가 패턴 추출, 도메인 KB, 커스텀 스킬 생성까지 자동화한 건 강점이다. 그러나 "학습"보다 "평가"가 먼저 강화되어야 한다. 평가 없는 학습은 신뢰할 수 없다.

### 5.2 평가 체계

```
┌─────────────────────────────────────────────────────┐
│  Evaluation Harness                                  │
│                                                       │
│  ┌─────────────────────────────────────────────┐     │
│  │ Gold Task Set                                │     │
│  │ - 도메인별 표준 분석 과제 10~30개            │     │
│  │ - 예상 결과, 필수 검증 포인트, 시간 기준     │     │
│  │ - 정기 회귀 테스트로 사용                    │     │
│  └─────────────────────────────────────────────┘     │
│                                                       │
│  ┌─────────────────────────────────────────────┐     │
│  │ Evaluation Dimensions (10개)                 │     │
│  │                                              │     │
│  │ 1. Scoping accuracy                          │     │
│  │    - GoalBrief가 비즈니스 문제를 정확히       │     │
│  │      DS 문제로 변환했는가?                    │     │
│  │ 2. Metric selection accuracy                  │     │
│  │    - 올바른 KPI를 선택했는가?                 │     │
│  │ 3. Temporal leakage detection                 │     │
│  │    - 시간 누출을 감지/방지했는가?             │     │
│  │ 4. Tool trajectory appropriateness            │     │
│  │    - 도구 호출 순서와 선택이 적절했는가?      │     │
│  │ 5. Artifact faithfulness                      │     │
│  │    - 산출물이 분석 결과를 정확히 반영하는가?  │     │
│  │ 6. Executive summary accuracy                 │     │
│  │    - 요약이 과장/축소 없이 정확한가?          │     │
│  │ 7. Approval judgment accuracy                 │     │
│  │    - 승인 필요 여부를 올바르게 판정했는가?    │     │
│  │ 8. Session completeness                       │     │
│  │    - 업무가 완결되었는가? (반쪽 분석 아닌가?) │     │
│  │ 9. Operator satisfaction                      │     │
│  │    - 사용자가 추가 작업 없이 결과를 쓸 수     │     │
│  │      있었는가?                                │     │
│  │ 10. Time-to-decision                          │     │
│  │    - 의사결정까지 소요 시간                   │     │
│  └─────────────────────────────────────────────┘     │
│                                                       │
│  ┌─────────────────────────────────────────────┐     │
│  │ Evaluation Modes                             │     │
│  │                                              │     │
│  │ A. Offline: Gold Task Set 회귀 테스트         │     │
│  │ B. Shadow: 실제 요청을 shadow 모드로 실행     │     │
│  │    → 사람 결과와 비교                        │     │
│  │ C. Online: Production trace에 scorer 적용     │     │
│  │ D. Human Rubric: 리뷰어가 점수 부여          │     │
│  │    → eval dataset으로 축적                   │     │
│  └─────────────────────────────────────────────┘     │
│                                                       │
│  ┌─────────────────────────────────────────────┐     │
│  │ Regression Board                             │     │
│  │ - Gold Task Set 결과 시계열                   │     │
│  │ - 차원별 점수 변화 추적                      │     │
│  │ - 성능 하락 시 자동 알림                     │     │
│  └─────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────┘
```

### 5.3 Production Trace → Eval Dataset 파이프라인

```
Production 실행
    ↓
session_registry + run_registry에 trace 저장
    ↓
사용자/리뷰어 피드백 (approve/reject/modify)
    ↓
review event를 eval label로 태깅
    ↓
eval dataset에 축적
    ↓
scorer가 새 모델/설정 변경 시 회귀 테스트에 사용
```

### 5.4 Run Scorecard UX

| 항목 | 표시 |
|------|------|
| Task Contract 준수 | ✅ 5/5 deliverables 완료 |
| Verifier 결과 | 🟢 Statistical PASS / 🟡 Data WARN(freshness) / 🟢 Policy PASS / 🟢 Narrative PASS |
| Confidence | 0.82 (High) |
| Tool trajectory | 12 calls, 0 redundant, 0 failed |
| Time-to-decision | 23분 (target: 30분 이내) |
| Budget 소비 | $8.40 / $20 (42%) |
| 사용자 만족 | ⭐⭐⭐⭐ (리뷰어 점수) |

### 5.5 구현 위치

| 컴포넌트 | 위치 |
|----------|------|
| GoldTaskSet | `evaluation/gold_tasks/` (YAML 기반 과제 정의) |
| EvalRunner | `evaluation/eval_runner.py` |
| EvalScorer (10개 차원) | `evaluation/scorers/` |
| EvalDatasetStore | `evaluation/eval_dataset_store.py` |
| RegressionBoard | `evaluation/regression_board.py` |
| Electron: RunScorecard | `components/runtime/RunScorecard.tsx` |
| Electron: RegressionDashboard | `components/runtime/RegressionDashboard.tsx` |

---

## 6. Decision OS — 재현성 및 실험-배포 폐쇄 루프

### 6.1 문제

기업에서는 "좋은 분석"보다 "다시 돌릴 수 있는 분석"이 더 오래 남는다. 현재 experiment_log와 project_store가 있지만, "지난주 실행과 비교", "같은 조건으로 재실행", "이 실험을 production 후보로 승격"이 체계적이지 않다.

### 6.2 아키텍처

```
┌─────────────────────────────────────────────────────┐
│  Decision OS                                         │
│                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ Feature      │  │ Experiment   │  │ Model      │ │
│  │ Registry     │  │ Tracker      │  │ Registry   │ │
│  │              │  │ (확장)       │  │            │ │
│  │ - 피처 정의  │  │ - 가설 기록  │  │ - 버전 관리│ │
│  │ - 변환 로직  │  │ - 비교 뷰    │  │ - alias    │ │
│  │ - 메타데이터 │  │ - 승격 게이트│  │ - lineage  │ │
│  │ - 의존 테이블│  │ - 롤백 체크  │  │ - 서빙 설정│ │
│  │ - 버전 관리  │  │              │  │            │ │
│  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘ │
│         └─────────────────┼────────────────┘         │
│                           ▼                           │
│  ┌─────────────────────────────────────────────┐     │
│  │ Run Diff Engine                              │     │
│  │ - 두 실행 간 입력/설정/결과/metric 차이      │     │
│  │ - 코드 diff + 데이터 drift + metric delta    │     │
│  └──────┬──────────────────────────────────────┘     │
│         ▼                                            │
│  ┌─────────────────────────────────────────────┐     │
│  │ Promotion Gate                               │     │
│  │ - staging → production 승격 체크리스트        │     │
│  │ - Verifier 결과, A/B 결과, rollback plan      │     │
│  │ - 승인 체인 (DS → Lead → MLOps)              │     │
│  └──────┬──────────────────────────────────────┘     │
│         ▼                                            │
│  ┌─────────────────────────────────────────────┐     │
│  │ Post-Deploy Monitor                          │     │
│  │ - 성능 추적 (drift, metric 변화)             │     │
│  │ - 자동 재학습 trigger                        │     │
│  │ - Rollback 자동 실행 조건                    │     │
│  └─────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────┘
```

### 6.3 Feature Registry 스키마

```yaml
feature_id: f_user_activity_30d
display_name: "30일 사용자 활동 점수"
version: 2
description: "최근 30일간의 로그인, 거래, 고객센터 접촉을 가중합산한 활동 지표"
transformation_logic: |
  SELECT user_id,
         0.5 * login_count_30d + 
         0.3 * transaction_count_30d + 
         0.2 * support_contact_count_30d AS activity_score
  FROM user_features
source_tables:
  - growth.user_logins
  - growth.transactions
  - support.contacts
owner: "이수진 (Analytics Lead)"
created_at: 2026-03-01
used_in_experiments: [exp_churn_001, exp_churn_003]
statistics:
  mean: 42.3
  median: 38.1
  p95: 89.7
  null_rate: 0.02
point_in_time_safe: true
```

### 6.4 Run Diff 예시 (UX)

```
┌──────────────────────────────────────────────────┐
│  Run Diff: exp_churn_003 vs exp_churn_002        │
│                                                    │
│  Input Changes:                                    │
│  + feature: f_user_activity_30d (v2, was v1)      │
│  + feature: f_campaign_exposure (new)              │
│  - feature: f_raw_login_count (removed)            │
│                                                    │
│  Config Changes:                                   │
│    learning_rate: 0.05 → 0.03                      │
│    max_depth: 6 → 8                                │
│                                                    │
│  Metric Delta:                                     │
│    F1-macro: 0.79 → 0.83 (+0.04) ✅               │
│    AUC:      0.85 → 0.88 (+0.03) ✅               │
│    FP rate:  0.12 → 0.09 (-0.03) ✅               │
│                                                    │
│  Verifier:                                         │
│    Statistical: PASS (no leakage, stable subgroups)│
│    Data:        PASS                                │
│    Policy:      PASS                                │
│                                                    │
│  [승격 요청]  [동일 조건 재실행]  [롤백 시뮬레이션]│
└──────────────────────────────────────────────────┘
```

### 6.5 Shared Skill의 검토 탭 승격

현재 shared skill에 있는 `backtesting`, `causal-assumption-check`, `uncertainty-quantification`, `retrain-vs-rollback`은 내부 prompt asset에 머물러 있다. 이들을 유저가 보는 **검토 탭**으로 끌어올린다.

| Skill | 검토 탭 표시 |
|-------|------------|
| `backtesting` | "시간 분할 안정성: 3개 fold 중 2개에서 일관된 결과" |
| `causal-assumption-check` | "인과 리스크: 이 추천은 상관 기반이며, confounding 가능성 존재" |
| `uncertainty-quantification` | "불확실성 범위: 예측 구간 [3.1%, 5.2%], 중앙값 4.2%" |
| `retrain-vs-rollback` | "권장: 재학습 (drift 크기 < threshold, 데이터 충분)" |

### 6.6 구현 위치

| 컴포넌트 | 위치 |
|----------|------|
| FeatureRegistry | `memory/feature_registry.py` |
| ExperimentTracker (확장) | `memory/experiment_log.py` 확장 |
| ModelRegistry | `memory/model_registry.py` |
| RunDiffEngine | `application/usecases/run_diff.py` |
| PromotionGate | `application/usecases/promotion_gate.py` |
| PostDeployMonitor | `runtime/post_deploy_monitor.py` |
| Electron: RunDiffPanel | `components/runtime/RunDiffPanel.tsx` |
| Electron: PromotionGateModal | `components/runtime/PromotionGateModal.tsx` |
| Electron: ReviewTab | `components/workflow/ReviewTab.tsx` |

---

## 7. Stakeholder Communication Engine — audience별 산출물

### 7.1 문제

기업 DS는 결과를 맞히는 사람보다 **사람을 움직이는 사람**에 가깝다. 같은 분석 결과를 대상에 따라 다른 형태·깊이·행동 방식으로 전달해야 한다.

### 7.2 DeliveryPack 구조

```yaml
delivery_pack:
  task_id: TC-2026-042
  generated_at: 2026-04-15T14:30:00Z
  confidence: 0.82

  artifacts:
    - type: exec_brief
      audience: executive
      format: pptx
      content_policy:
        max_pages: 3
        structure: [situation, finding, impact, recommendation, decision_needed]
        technical_detail: minimal
        chart_count: 2~3
      delivery_channel: email + slack_dm

    - type: pm_action_memo
      audience: pm
      format: markdown → notion_page
      content_policy:
        structure: [summary, next_actions, eta, trade_offs, dependencies]
        include_jira_links: true
      delivery_channel: slack_channel

    - type: ds_experiment_note
      audience: ds_peer
      format: ipynb
      content_policy:
        structure: [hypothesis, methodology, results, caveats, reproducibility]
        include_code: true
        include_verifier_results: true
      delivery_channel: git_pr

    - type: ml_handoff_spec
      audience: ml_engineer
      format: markdown
      content_policy:
        structure: [model_card, serving_config, monitoring_setup, rollback_plan]
        include_feature_registry_refs: true
      delivery_channel: confluence + jira_ticket

    - type: audit_trail
      audience: auditor
      format: pdf
      content_policy:
        structure: [data_provenance, access_log, policy_compliance, approval_chain, lineage]
        speculative_claims: forbidden
      delivery_channel: compliance_system
```

### 7.3 PPTX 자동 생성

현재 artifact_tools가 ipynb/pdf/docx/xlsx를 내보내지만 **슬라이드 덱 자동 생성**이 빠져 있다. 기업 환경에서 DS 결과물의 최종 형태는 대부분 PPT다.

```
분석 완료
    ↓
DeliveryPack 생성 시 exec_brief 요청 감지
    ↓
reporting 스킬 + audience=executive 템플릿
    ↓
pptx 생성 파이프라인:
    1. 구조 결정 (situation/finding/impact/recommendation)
    2. 차트 렌더링 (matplotlib → 이미지)
    3. pptxgenjs 또는 python-pptx로 슬라이드 조립
    4. 디자인 시스템 적용 (Deloitte #86BC25 등 조직별 커스텀)
    ↓
artifact_tools에 pptx export 추가
```

### 7.4 구현 위치

| 컴포넌트 | 위치 |
|----------|------|
| DeliveryPack 모델 | `domain/entities/delivery_pack.py` |
| AudienceRenderer | `application/usecases/audience_renderer.py` |
| PptxExporter | `tools/artifact_tools.py` 확장 |
| DeliveryRouter | `runtime/outcome_delivery.py` 확장 |
| Electron: AudienceSelector | `components/workflow/AudienceSelector.tsx` |

---

## 8. Workflow Integration — 조직 프로세스 연결

### 8.1 문제

실제 회사에서 DS는 노트북 안에서 끝나지 않는다. 분석 결과가 Jira ticket, Slack thread, Confluence 문서, Git PR, BI 대시보드, 이메일/캘린더로 이어져야 업무가 "끝난" 것이다.

### 8.2 Work Object 모델

모든 업무를 하나의 Work Object로 추적:

```
┌─────────────────────────────────────────────────────┐
│  Work Object (TaskContract의 실행 추적 뷰)           │
│                                                       │
│  ┌─── Request ─────────────────────────────────┐     │
│  │ Source: Slack #growth-analytics              │     │
│  │ Requestor: 김상무                            │     │
│  │ Original: "이번 분기 churn 좀 분석해줘"     │     │
│  └─────────────────────────────────────────────┘     │
│              ↓                                        │
│  ┌─── Execution ───────────────────────────────┐     │
│  │ TaskContract: TC-2026-042                    │     │
│  │ Runs: [run_001, run_002, run_003]            │     │
│  │ Current Phase: Review                        │     │
│  └─────────────────────────────────────────────┘     │
│              ↓                                        │
│  ┌─── Documentation ──────────────────────────┐     │
│  │ Confluence: "Q2 Churn Analysis Report"       │     │
│  │ Git PR: ds-experiments/#142                  │     │
│  │ Notion: Growth Weekly Note (auto-updated)    │     │
│  └─────────────────────────────────────────────┘     │
│              ↓                                        │
│  ┌─── Follow-up Actions ──────────────────────┐     │
│  │ Jira: GROWTH-1234 "재가입 캠페인 설계"      │     │
│  │ Jira: GROWTH-1235 "가격 민감도 AB 테스트"   │     │
│  │ Calendar: "Churn Review Meeting" (05/15)     │     │
│  │ Slack: @김상무 결과 요약 DM 전송 완료       │     │
│  └─────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────┘
```

### 8.3 Integration 우선순위

| Phase | 대상 | 연동 방식 | 이유 |
|-------|------|-----------|------|
| P0 | Slack | Webhook + Bot API | 요청 수집 + 결과 전달의 주 채널 |
| P0 | Jira | REST API | 후속 액션 티켓 자동 생성 |
| P1 | Confluence / Notion | REST API | 분석 문서 자동 게시 |
| P1 | Git (GitHub/GitLab) | API | 노트북/코드 PR 자동 생성 |
| P2 | Email / Calendar | SMTP + CalDAV | 리뷰 미팅 스케줄링, 결과 메일 |
| P2 | BI (Looker/Tableau) | API | 대시보드 주석 추가, 지표 업데이트 |
| P3 | Asana / Monday.com | REST API | 프로젝트 관리 도구 연동 |

### 8.4 구현 위치

| 컴포넌트 | 위치 |
|----------|------|
| WorkObject 모델 | `domain/entities/work_object.py` |
| IntegrationHub | `infrastructure/external/integration_hub.py` |
| SlackConnector | `infrastructure/external/slack_connector.py` |
| JiraConnector | `infrastructure/external/jira_connector.py` |
| ConfluenceConnector | `infrastructure/external/confluence_connector.py` |
| GitConnector | `infrastructure/external/git_connector.py` |
| integration_tools 확장 | `tools/integration_tools.py` |

---

## 9. Async Portfolio Manager — 비동기 업무 큐

### 9.1 문제

완전 delegation은 채팅 세션 하나를 잘 도는 것보다 **여러 업무를 동시에 소유하는 것**에 가깝다.

### 9.2 업무 상태 모델

```
┌─────────────────────────────────────────────────────┐
│  Portfolio Manager                                    │
│                                                       │
│  ┌─── Active ──────────────────────────────────┐     │
│  │ TC-042: Churn Analysis (Running, 23min)      │     │
│  │ TC-043: Revenue Forecast Refresh (Running)   │     │
│  └─────────────────────────────────────────────┘     │
│                                                       │
│  ┌─── Waiting ─────────────────────────────────┐     │
│  │ TC-044: Pricing AB Test (데이터 도착 대기)   │     │
│  │ TC-045: Fraud Model Retrain (승인 대기)      │     │
│  └─────────────────────────────────────────────┘     │
│                                                       │
│  ┌─── Monitoring ──────────────────────────────┐     │
│  │ TC-038: Churn Model v2 (배포 후 7일째)       │     │
│  │ TC-039: Pricing Model v1.3 (안정, 14일째)    │     │
│  └─────────────────────────────────────────────┘     │
│                                                       │
│  ┌─── Playbook Candidates ─────────────────────┐     │
│  │ TC-042 패턴 → weekly-kpi-triage 승격 검토    │     │
│  └─────────────────────────────────────────────┘     │
│                                                       │
│  Scheduling Rules:                                    │
│  - SLA: P0 tasks < 4h, P1 < 1 business day          │
│  - Quiet hours: 22:00~08:00 (알림만 차단, 실행 계속)│
│  - Change window: 화~목 10:00~16:00 (배포 허용)     │
│  - 동시 실행: max 3 active tasks                     │
└─────────────────────────────────────────────────────┘
```

### 9.3 구현 위치

기존 `runtime/` 모듈 활용:

| 기존 모듈 | 확장 내용 |
|-----------|-----------|
| `task_ledger.py` | 업무 상태 모델 (Active/Waiting/Monitoring/Candidate) |
| `run_registry.py` | 동시 실행 제한, 우선순위 큐 |
| `standing_order_tools.py` | 모니터링 상태 업무의 정기 체크 |
| `delivery_policy_store.py` | Quiet hours, change window 정책 |
| `background_task_manager.py` | 비동기 실행 스케줄러 |
| `checkpoint_store.py` | 대기 → 재개 시 상태 복구 |

---

## 10. Self-Improvement 거버넌스 — 학습 결과의 책임 있는 승격

### 10.1 문제

현재 self_improve가 자동으로 패턴·KB·스킬을 생성하는 것은 좋지만, 기업 환경에서는 자동 학습 결과가 바로 조직 표준이 되면 위험하다.

### 10.2 Learning Lifecycle

```
패턴/KB/스킬 추출 (자동)
    ↓
proposed 상태로 Learning Inbox에 등록
    ↓
리뷰어가 검토:
  - 어떤 프로젝트에서 추출됐는가?
  - 어떤 지표에서 검증됐는가?
  - 기존 지식과 충돌하지 않는가?
    ↓
    ├── approve → promote (조직 표준으로 승격)
    ├── modify → 수정 후 재검토
    └── reject → archive (사유 기록)
    ↓
(승격 후)
정기 재검증 스케줄 등록
    ↓
성능 하락 또는 환경 변화 감지 시 deprecate
```

### 10.3 구현 위치

| 컴포넌트 | 위치 |
|----------|------|
| LearningInbox | `self_improve/learning_inbox.py` |
| LearningReviewStore | `infrastructure/persistence/learning_review_store.py` |
| 기존 self_improve 확장 | 상태 필드 추가: proposed/approved/deprecated |
| Electron: LearningInbox | `components/settings/LearningInbox.tsx` |

---

## 11. 우선순위 로드맵

### Phase 0 (P0) — 업무 위임의 기초 (4~6주)

| ID | 영역 | 핵심 산출물 | 의존성 |
|----|------|------------|--------|
| P0-E01 | TaskContract 엔진 | TaskContract 스키마, CRUD 도구, prompt 통합 | 없음 |
| P0-E02 | GoalBrief + AssumptionLog | Typed artifact 2종, 자동 생성 로직 | P0-E01 |
| P0-E03 | Audience Profile (prompt layer) | 5종 persona 템플릿, prompt_sections 확장 | 없음 |
| P0-E04 | Authority Mode 확장 | 6종 모드, action-level autonomy matrix | 기존 policy_engine |
| P0-E05 | Verifier Layer 1~2 | Statistical + Data Verifier, ReviewVerdict | 기존 hooks |
| P0-E06 | Confidence Scoring | 자동 태깅, QualityPanel 배지 | P0-E05 |

### Phase 1 (P1) — 조직 신뢰 구축 (6~8주)

| ID | 영역 | 핵심 산출물 | 의존성 |
|----|------|------------|--------|
| P1-E01 | Metric Catalog + Glossary | YAML 기반 metric 정의, 검색, 검증 쿼리 | 없음 |
| P1-E02 | Semantic Query 도구 | Metric Catalog 우선 쿼리, SQL fallback | P1-E01 |
| P1-E03 | Data Trust Registry | 테이블 신뢰도 등급, freshness SLA | P1-E01 |
| P1-E04 | Verifier Layer 3~4 | Policy + Narrative Verifier | P0-E05 |
| P1-E05 | MissionPack 체계 | YAML 기반 업무 패키지, skill 승격 | P0-E01, P0-E04 |
| P1-E06 | DeliveryPack + PPTX 생성 | audience별 산출물, 슬라이드 자동 생성 | P0-E03 |
| P1-E07 | Eval Harness 기초 | Gold Task Set, 10차원 scorer, Run Scorecard | P0-E05 |

### Phase 2 (P2) — 재현성과 연결 (8~12주)

| ID | 영역 | 핵심 산출물 | 의존성 |
|----|------|------------|--------|
| P2-E01 | Feature Registry | 피처 버전 관리, 메타데이터, 재사용 | 없음 |
| P2-E02 | Run Diff Engine | 실행 간 비교, 승격 게이트, 롤백 체크 | 기존 experiment_log |
| P2-E03 | Autonomy Certification | Playbook 승급 제도, 이력 관리 | P0-E04, P1-E05 |
| P2-E04 | Slack + Jira 연동 | 요청 수집, 결과 전달, 티켓 자동 생성 | P1-E06 |
| P2-E05 | Org Context Store | 캘린더, 팀 맵, 의사결정 로그 | P1-E01 |
| P2-E06 | Post-Deploy Monitor | 성능 추적, 재학습 trigger, 자동 롤백 | P2-E02 |
| P2-E07 | Shadow Eval + Human Rubric | Production trace → eval dataset 파이프라인 | P1-E07 |

### Phase 3 (P3) — 자율 운영 (12주+)

| ID | 영역 | 핵심 산출물 | 의존성 |
|----|------|------------|--------|
| P3-E01 | Async Portfolio Manager | 다중 업무 큐, SLA, 스케줄링 | P2-E03 |
| P3-E02 | Confluence/Notion/Git 연동 | 문서 자동 게시, PR 생성 | P2-E04 |
| P3-E03 | Self-Improvement 거버넌스 | Learning Inbox, 승격/폐기 흐름 | 기존 self_improve |
| P3-E04 | BigQuery/Snowflake/Databricks 연동 | Catalog/lineage import | P1-E03 |
| P3-E05 | Regression Board | Gold Task 시계열, 자동 알림 | P2-E07 |
| P3-E06 | Review Inbox + Reviewer Queue | 검토 이벤트 → eval label 전환 | P2-E07, P1-E07 |
| P3-E07 | Project Control Tower | 전체 업무 대시보드, 상태 총괄 | P3-E01 |

### 의도적으로 뒤로 미루는 것

| 항목 | 이유 |
|------|------|
| 모델/알고리즘 종류 추가 | 현재 modeling 도구로 충분. 병목이 아님. |
| Swarm형 Multi-Agent | 단일 agent의 책임 구조가 먼저. 복잡도 대비 ROI 낮음. |
| Self-Improve → Production 직접 쓰기 | 거버넌스 없이 자동 적용은 위험. P3에서 거버넌스와 함께. |
| 새 채널 UI 확대 | CLI·Telegram·Electron 3종이면 충분. |
| Provider 추가 | 이미 8+ provider, 100+ via LiteLLM. 병목이 아님. |

---

## 12. 모듈 매핑 요약

각 고도화 영역이 현재 코드베이스의 어디에 꽂히는지 한 눈에 보기:

```
src/ds_agent/
├── agent/
│   ├── core.py                          # (유지) 단일 루프
│   ├── prompt_builder.py                # 확장: TaskContract 컨텍스트 주입
│   ├── prompt_sections.py               # 확장: Audience Profile 페르소나 템플릿
│   ├── verifier_orchestrator.py         # [신규] 4-layer 검증 오케스트레이터
│   ├── confidence_scorer.py             # [신규] 확신도 자동 태깅
│   └── budget_tracker.py               # (유지)
│
├── domain/
│   ├── entities/
│   │   ├── task_contract.py             # [신규] 업무 위임 계약
│   │   ├── delivery_pack.py             # [신규] audience별 산출물 번들
│   │   ├── review_verdict.py            # [신규] 검증 결과
│   │   ├── work_object.py              # [신규] 업무 추적 객체
│   │   └── ...
│   └── value_objects/
│       ├── authority_mode.py            # [신규] 6종 자율성 모드
│       └── ...
│
├── application/
│   └── usecases/
│       ├── task_contract_*.py           # [신규] 계약 CRUD
│       ├── audience_renderer.py         # [신규] audience별 렌더링
│       ├── run_diff.py                  # [신규] 실행 간 비교
│       └── promotion_gate.py            # [신규] 승격 게이트
│
├── memory/
│   ├── (기존 5계층 유지)
│   ├── metric_catalog.py               # [신규] KPI 정의 저장소
│   ├── business_glossary.py            # [신규] 비즈니스 용어 사전
│   ├── data_trust_registry.py          # [신규] 테이블 신뢰도 레지스트리
│   ├── verified_query_store.py         # [신규] 검증된 쿼리 패턴
│   ├── org_context_store.py            # [신규] 조직 컨텍스트
│   ├── feature_registry.py             # [신규] 피처 레지스트리
│   └── model_registry.py              # [신규] 모델 레지스트리
│
├── tools/
│   ├── (기존 35+ 도구 유지)
│   ├── task_contract_tools.py          # [신규] 계약 관련 도구
│   ├── semantic_query.py               # [신규] Metric Catalog 우선 쿼리
│   └── verifiers/                      # [신규] 4종 검증기
│       ├── statistical.py
│       ├── data.py
│       ├── policy.py
│       └── narrative.py
│
├── skills/
│   ├── (기존 builtin/shared/domain/custom 유지)
│   └── missions/                       # [신규] MissionPack YAML
│       ├── weekly-kpi-triage.yaml
│       ├── experiment-design.yaml
│       ├── forecasting-refresh.yaml
│       ├── churn-playbook.yaml
│       ├── fraud-investigation.yaml
│       ├── pricing-diagnosis.yaml
│       └── model-health-guardian.yaml
│
├── runtime/
│   ├── (기존 30+ 모듈 유지)
│   ├── autonomy_policy.py              # [신규] 행동별 자율성 매트릭스
│   ├── action_classifier.py            # [신규] 액션 클래스 분류
│   ├── autonomy_certification_store.py # [신규] 승급 이력
│   └── post_deploy_monitor.py          # [신규] 배포 후 모니터링
│
├── self_improve/
│   ├── (기존 패턴/KB/스킬 추출 유지)
│   └── learning_inbox.py              # [신규] 학습 결과 검토 큐
│
├── evaluation/                         # [신규 디렉터리]
│   ├── gold_tasks/                     # 표준 과제 YAML
│   ├── scorers/                        # 10차원 채점기
│   ├── eval_runner.py
│   ├── eval_dataset_store.py
│   └── regression_board.py
│
├── infrastructure/
│   └── external/                       # [신규/확장]
│       ├── integration_hub.py
│       ├── slack_connector.py
│       ├── jira_connector.py
│       ├── confluence_connector.py
│       └── git_connector.py
│
electron/src/renderer/components/
├── mission/                            # [신규]
│   ├── MissionBriefPanel.tsx
│   └── ContractEditor.tsx
├── semantic/                           # [신규]
│   └── MetricSourcePanel.tsx
├── runtime/                            # 확장
│   ├── RunScorecard.tsx               # [신규]
│   ├── RunDiffPanel.tsx               # [신규]
│   ├── CertificationBoard.tsx         # [신규]
│   ├── RegressionDashboard.tsx        # [신규]
│   └── ReviewInbox.tsx                # [신규]
├── workflow/                           # 확장
│   ├── QualityPanel.tsx               # 확장: Verifier 결과 배지
│   ├── ReviewTab.tsx                  # [신규]
│   └── AudienceSelector.tsx           # [신규]
├── settings/                           # 확장
│   ├── PolicyStudio.tsx               # [신규]
│   └── LearningInbox.tsx              # [신규]
└── dashboard/                          # [신규]
    └── ProjectControlTower.tsx
```

---

## 13. 결론

한 문장으로 정리하면 이렇다.

> **DS Agent의 다음 진화는 "더 똑똑한 분석"이 아니라 "업무 위임 OS"다.**
> 업무 계약(TaskContract), 조직 의미론(Semantic Memory), 검증 체계(Verifier), 자율성 등급화(Autonomy Control Plane), 성과 관리(Eval Harness)가 갖춰지면, 이 에이전트는 "분석을 수행하는 손"에서 "회사 맥락을 이해하고, 결과를 책임지고, 조직 프로세스 안에서 일하는 DS 동료"로 전환된다.

현재 시스템의 강점 — LLM-orchestrator 단일 루프, 35+ 도구, 5계층 메모리, 승인/정책/런타임, Clean Architecture — 은 이 모든 고도화의 견고한 기반이다. 새로 만드는 것이 아니라, 이미 있는 인프라 위에 **책임 구조**를 얹는 작업이다.
