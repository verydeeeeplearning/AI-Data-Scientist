# Phase 4: Artifact & Communication — 다양한 산출물·조직 연동

**Status**: Pending
**Started**: -
**Last Updated**: 2026-04-13
**Parent**: `PLAN_17_ROADMAP_MASTER.md`
**선행 조건**: Phase 1 (Data Autonomy) 완료 (최소), Phase 2 권장
**후행 Phase**: P6 (Advanced Autonomy)

---

## 1. Overview

### 왜 Artifact 확장인가

현업에서 신뢰를 얻는 건 "점수"가 아니라 "남기는 산출물"이다. 같은 분석 결과도:
- 비기술 임원에게는 **executive memo** (1-2 페이지)
- ML 엔지니어에게는 **model card + 코드 PR**
- 팀원에게는 **notebook** (.ipynb)
- PM에게는 **Jira ticket**
- BI 팀에게는 **dashboard spec**

현재 `generate_report`는 markdown/html만 지원. 진짜 delegate 가능한 agent가 되려면 report 외에 SQL/notebook/PR/dashboard spec까지 1급 산출물이어야 한다.

### 성공 기준

- [ ] Notebook (.ipynb) 생성: 코드 + 설명 + 시각화
- [ ] Executive Memo 생성: 1-2 페이지 비기술 요약
- [ ] Dashboard Spec 생성: JSON/YAML 지표 정의
- [ ] 청중별 자동 변환: 같은 분석 결과 → 다른 형태
- [ ] ClaimTraceabilityHook: 보고서 주장-근거 연결 검증
- [ ] Slack/Jira 연동 (기본 수준)

---

## 2. Architecture Decisions (Clean Architecture)

### Layer Mapping

| Layer | Components | Responsibility |
|-------|-----------|---------------|
| **Domain** | `ArtifactSpec` (VO), `AudienceProfile` (VO), `Claim` (Entity) | 산출물 명세, 청중 프로필, 주장-근거 구조 |
| **Application** | `ArtifactGenerator`, `AudienceAdapter`, `ClaimTraceabilityHook` | 산출물 생성 오케스트레이션, 청중 맞춤화, 주장 검증 |
| **Infrastructure** | `NotebookEngine`, `SlideEngine`, `DashboardSpecEngine`, `SlackClient`, `JiraClient` | 실제 파일 생성, 외부 서비스 연동 |
| **Presentation** | `notebook_generate`, `slide_generate`, `dashboard_spec` tools | LLM에 노출되는 도구 |

---

## 3. Implementation Phases (TDD)

### Phase 4-1: Artifact Stack 확장

**Goal**: Notebook, Executive Memo, Dashboard Spec, SQL Artifact 생성

#### RED: Write Failing Tests First

- [ ] **Test 4-1.1**: Notebook 생성 — 코드 + 마크다운 셀 구조
  - File: `tests/unit/infrastructure/test_notebook_engine.py`
  - Scenario: 코드 블록 3개 + 설명 2개 → .ipynb 파일 생성, 유효한 JSON 구조
  - Expected: Tests FAIL

- [ ] **Test 4-1.2**: Executive Memo — 비기술 요약 구조
  - File: `tests/unit/infrastructure/test_artifact_generator.py`
  - Scenario: 분석 결과 → {summary, key_findings, recommendations, risks, next_steps}
  - Expected: Tests FAIL

- [ ] **Test 4-1.3**: Dashboard Spec — JSON/YAML 지표 정의
  - File: `tests/unit/infrastructure/test_dashboard_engine.py`
  - Scenario: 지표 3개 → {metrics: [{name, sql, type, filters}], layout}
  - Expected: Tests FAIL

- [ ] **Test 4-1.4**: SQL Artifact — 문서화된 SQL + 테스트
  - File: `tests/unit/infrastructure/test_artifact_generator.py`
  - Scenario: 분석 쿼리 → {sql, description, schema_yml, tests}
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 4-1.5**: Domain Value Objects
  - File: `src/ds_agent/domain/value_objects/artifact.py`
  - `ArtifactSpec`: type (notebook/memo/dashboard/sql/model_card/slide), format, content_sections, metadata
  - `AudienceProfile`: role (executive/technical/pm/bi/de), technical_level, preferred_format

- [ ] **Task 4-1.6**: NotebookEngine
  - File: `src/ds_agent/infrastructure/artifact/notebook_engine.py`
  - `nbformat` 라이브러리로 .ipynb 생성
  - 셀 유형: markdown (설명), code (실행 코드), output (결과 + 시각화)
  - 메타데이터: kernel_spec, language_info

- [ ] **Task 4-1.7**: DashboardSpecEngine
  - File: `src/ds_agent/infrastructure/artifact/dashboard_engine.py`
  - JSON/YAML 스펙 생성
  - 구조: metrics[], dimensions[], filters[], layout{}
  - Looker/Metabase/Superset 호환 형식 지원 (추후)

- [ ] **Task 4-1.8**: ArtifactGenerator (Application Service)
  - File: `src/ds_agent/application/services/artifact_generator.py`
  - `generate(spec: ArtifactSpec, data: AnalysisResult) → ArtifactOutput`
  - 타입별 엔진 디스패치

- [ ] **Task 4-1.9**: Tool 구현
  - `notebook_generate`: code_blocks, descriptions, output_path → .ipynb
  - `slide_generate`: sections, audience → markdown/HTML slide
  - `dashboard_spec`: metrics, dimensions, format → JSON/YAML

#### Quality Gate

- [ ] 생성된 .ipynb가 Jupyter에서 열기 가능
- [ ] Dashboard spec이 유효한 JSON
- [ ] Executive memo 구조 완전성

---

### Phase 4-2: Audience-Adaptive Reporting

**Goal**: 같은 분석 결과를 청중별로 자동 변환

#### RED: Write Failing Tests First

- [ ] **Test 4-2.1**: Technical → Executive 변환
  - File: `tests/unit/application/test_audience_adapter.py`
  - Scenario: 기술 보고서 → executive memo (전문 용어 제거, 액션 중심)
  - Expected: Tests FAIL

- [ ] **Test 4-2.2**: 다국어 변환 (한→영)
  - File: `tests/unit/application/test_audience_adapter.py`
  - Scenario: 한국어 보고서 → 영어 요약
  - Expected: Tests FAIL

- [ ] **Test 4-2.3**: 상세도 조절
  - File: `tests/unit/application/test_audience_adapter.py`
  - Scenario: full report → 3줄 요약 (Slack용)
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 4-2.4**: AudienceAdapter
  - File: `src/ds_agent/application/services/audience_adapter.py`
  - LLM을 활용한 변환 (별도 subagent 또는 저렴한 모델)
  - 변환 규칙:
    - Executive: "So what?" 중심, 액션 추천, 수치는 최소화
    - Technical: 방법론, 실험 상세, 재현 정보
    - PM: 액션 아이템, 타임라인, 리소스
    - Slack: 3줄 요약 + 핵심 수치 1-2개

- [ ] **Task 4-2.5**: `generate_report` Tool 확장
  - 기존 report_type에 `audience` 파라미터 추가
  - audience="executive" → Executive Memo 자동 생성

#### Quality Gate

- [ ] 각 청중별 출력물 품질 확인
- [ ] 전문 용어 적절히 번역/제거 확인

---

### Phase 4-3: Slack/Jira/Git Integration

**Goal**: 분석 결과를 조직 도구로 직접 전달

#### RED: Write Failing Tests First

- [ ] **Test 4-3.1**: Slack 메시지 전송
  - File: `tests/unit/infrastructure/test_slack_client.py`
  - Scenario: 분석 요약 → Slack 채널로 전송 → 성공 응답
  - Expected: Tests FAIL

- [ ] **Test 4-3.2**: Jira 티켓 생성
  - File: `tests/unit/infrastructure/test_jira_client.py`
  - Scenario: 액션 아이템 → Jira 티켓 생성 → ticket_id 반환
  - Expected: Tests FAIL

- [ ] **Test 4-3.3**: Git PR 생성 (코드 변경 시)
  - File: `tests/unit/infrastructure/test_git_client.py`
  - Scenario: 모델 코드 → branch 생성 → PR 생성
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 4-3.4**: Slack Client (NetworkRunner에서 실행)
  - File: `src/ds_agent/infrastructure/external/slack_client.py`
  - Webhook 또는 Bot Token 기반
  - 메시지 포맷: Block Kit (제목, 섹션, 차트 이미지 링크)

- [ ] **Task 4-3.5**: Jira Client
  - File: `src/ds_agent/infrastructure/external/jira_client.py`
  - REST API 기반
  - 티켓 생성: summary, description, assignee, priority, labels

- [ ] **Task 4-3.6**: Git Client
  - File: `src/ds_agent/infrastructure/external/git_client.py`
  - gitpython 또는 subprocess 기반
  - Branch 생성, 파일 추가, commit, push, PR 생성 (GitHub API)

- [ ] **Task 4-3.7**: 통합 Tool
  - `send_to_slack`: channel, message, blocks (optional)
  - `create_jira_ticket`: summary, description, project, type
  - 모두 Policy-Approved Network Runner에서 실행 + 감사 로그

#### Quality Gate

- [ ] 각 외부 서비스 연동 동작 확인
- [ ] 감사 로그 기록 확인
- [ ] Credential 보안 (환경변수만 참조)

---

### Phase 4-4: ClaimTraceabilityHook

**Goal**: 보고서의 모든 주장이 데이터 근거와 연결되었는지 검증

#### RED: Write Failing Tests First

- [ ] **Test 4-4.1**: 주장-근거 쌍 추출
  - File: `tests/unit/application/test_claim_traceability.py`
  - Scenario: 보고서 텍스트에서 주장 문장 식별 → 근거 데이터/시각화 매핑
  - Expected: Tests FAIL

- [ ] **Test 4-4.2**: 근거 없는 주장 감지
  - File: `tests/unit/application/test_claim_traceability.py`
  - Scenario: "매출이 20% 증가했다" (데이터 근거 없음) → WARNING
  - Expected: Tests FAIL

- [ ] **Test 4-4.3**: 근거 있는 주장 통과
  - File: `tests/unit/application/test_claim_traceability.py`
  - Scenario: "매출이 20% 증가했다 (Figure 3, Table 2 참조)" → PASS
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 4-4.4**: `ClaimTraceabilityHook` 구현
  - File: `src/ds_agent/agent/ds_workflow_hooks.py`
  - Priority: 52 (ExperimentTracker=50 이후)
  - `post_tool_use()`: generate_report 완료 시 결과 분석
  - 주장 감지: 수치 포함 문장, 비교 표현, 추천 문장
  - 근거 매핑: 차트 참조, 테이블 참조, 데이터 출처 링크
  - WARNING: 근거 없는 주장 목록 + 보완 제안

- [ ] **Task 4-4.5**: Claim-Evidence Linker
  - File: `src/ds_agent/application/services/claim_evidence_linker.py`
  - 보고서 파싱 → 주장 추출 → 근거 매핑 → 커버리지 점수

#### Quality Gate

- [ ] 근거 없는 주장 감지 정확성
- [ ] 정상 보고서에 오탐 없음
- [ ] 보고서 품질 점수에 반영

---

## 4. 산출물 매트릭스 (최종)

| 산출물 유형 | 대상 청중 | 형식 | 구현 Phase |
|------------|----------|------|-----------|
| Technical Report | DS/ML 동료 | Markdown/HTML | **기존** (generate_report) |
| Executive Memo | C-level | 1-2 페이지 문서 | P4-1 |
| Model Card | 거버넌스 | 표준 템플릿 | **기존** (generate_report type=model_card) |
| Notebook | 후임 분석가 | .ipynb | P4-1 |
| SQL Artifact | 데이터 엔지니어 | .sql + schema.yml | P4-1 |
| Dashboard Spec | BI 팀 | JSON/YAML | P4-1 |
| Slide Spec | 발표자 | Markdown slide | P4-1 |
| Experiment Report | PM | 구조화된 문서 | P4-2 (audience adaptation) |
| Jira Ticket | PM/개발팀 | Jira 형식 | P4-3 |
| Slack Summary | 팀 전체 | 3줄 메시지 | P4-3 |
| Decision Log | 미래의 자기 자신 | 구조화된 기록 | P3-2 (Lineage) |

---

## 5. Skill 정의

### `narrative-synthesis` Skill

```markdown
# Narrative Synthesis

분석 결과를 설득력 있는 스토리라인으로 구성하는 스킬.

## 스토리 구조
1. **Context**: 왜 이 분석을 했는가 (배경, 질문)
2. **Approach**: 어떻게 분석했는가 (방법론, 데이터)
3. **Findings**: 무엇을 발견했는가 (핵심 인사이트)
4. **So What**: 이것이 왜 중요한가 (비즈니스 임팩트)
5. **Now What**: 다음에 무엇을 해야 하는가 (액션 추천)

## 청중별 강조점
| 청중 | 강조 | 생략 |
|------|------|------|
| Executive | So What, Now What | Approach 상세 |
| Technical | Approach, Findings | 비즈니스 맥락 간소화 |
| PM | Context, Now What (액션) | 기술적 방법론 |
```

### `visualization-choice` Skill

```markdown
# Visualization Choice

데이터 유형·청중·메시지에 맞는 차트를 선택하는 스킬.

## 차트 선택 가이드
| 메시지 유형 | 추천 차트 | 피해야 할 차트 |
|------------|----------|-------------|
| 비교 (A vs B) | Bar chart, Grouped bar | Pie chart (>5개 항목) |
| 추세 (시간) | Line chart | Scatter plot |
| 분포 | Histogram, Box plot | Bar chart |
| 비율/구성 | Stacked bar, Treemap | 3D pie chart |
| 관계 | Scatter plot, Heatmap | Line chart |
| 지리적 | Choropleth map | Bar chart |

## 원칙
- 차트 1개 = 메시지 1개
- Y축은 0부터 시작 (비율 제외)
- 색상은 의미 있게 (빨강=나쁨, 초록=좋음 피하기 — 색맹 고려)
- Executive용: 숫자보다 추세와 비교에 집중
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Notebook 실행 시 다른 결과 | 중 | 중간 | 랜덤 시드 고정, 데이터 스냅샷 포함 |
| Slack/Jira credential 유출 | 낮음 | 높음 | 환경변수만, Policy-Approved Network |
| 외부 서비스 장애 | 중 | 낮음 | 재시도 + fallback (로컬 저장) |
| ClaimTraceability 오탐 | 높음 | 낮음 | WARNING만 (DENY 아님) |
| LLM 기반 변환 품질 | 중 | 중간 | 템플릿 + 후처리 규칙 |

---

## 7. Dependencies

### External Dependencies

```toml
[project.optional-dependencies]
artifacts = [
    "nbformat>=5.0.0",
    "nbconvert>=7.0.0",
]
integrations = [
    "slack-sdk>=3.0.0",
    "jira>=3.0.0",
    "gitpython>=3.1.0",
]
```

---

## 8. Progress Tracking

- Phase 4-1 (Artifact Stack): 0%
- Phase 4-2 (Audience-Adaptive): 0%
- Phase 4-3 (Slack/Jira/Git): 0%
- Phase 4-4 (ClaimTraceability): 0%
- **Overall Phase 4**: 0%

---

## Notes & Learnings

- [구현 중 발견 사항 기록]
