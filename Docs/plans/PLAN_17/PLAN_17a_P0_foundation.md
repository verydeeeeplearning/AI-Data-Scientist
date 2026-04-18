# Phase 0: Foundation — 자율성의 기본 전제 확보

**Status**: Complete
**Started**: 2026-04-13
**Last Updated**: 2026-04-14
**Parent**: `PLAN_17_ROADMAP_MASTER.md`
**선행 조건**: 없음 (즉시 시작 가능)
**후행 Phase**: P1, P2, P3, P4, P5, P6 (모든 Phase의 기반)

---

## 1. Overview

### 왜 Phase 0이 먼저인가

Phase 0은 이후 모든 Phase의 **기본 전제(prerequisite)**다. 세 가지 핵심 역량 없이는 어떤 고도화도 반쪽짜리가 된다:

1. **Self-Debugging Loop** — 에러가 나면 멈추는 에이전트는 자율적이지 않다
2. **BacktrackTriggerHook** — 선형 파이프라인만 가능하면 비선형 탐색이 불가하다
3. **Memory 구현** — 세션 간 학습이 안 되면 조직 내 축적이 불가하다

### 성공 기준

- [ ] 에이전트가 tool 에러 발생 시 자율적으로 진단 → 수정 → 재실행 (최대 3회)
- [ ] 모델 성능 미달 시 Feature Engineering 또는 EDA로 자동 백트래킹
- [ ] `memory_search` / `memory_store` tool이 실제 동작하여 세션 간 지식 축적
- [ ] 기존 1090+ 테스트 전체 통과 + 신규 테스트 추가
- [ ] 코드 커버리지 ≥80% (신규 코드)

---

## 2. Architecture Decisions (Clean Architecture)

### Layer Mapping

| Layer | Components | Responsibility |
|-------|-----------|---------------|
| **Domain** | `SelfDebugDecision` (VO), `BacktrackDecision` (VO), `MemoryEntry` (Entity) | 에러 분류 규칙, 백트래킹 조건, 메모리 엔트리 구조 |
| **Application** | `SelfDebugHook`, `BacktrackTriggerHook`, `MemorySearchUseCase`, `MemoryStoreUseCase` | 에러 진단 오케스트레이션, 백트래킹 트리거, 메모리 CRUD |
| **Infrastructure** | `ErrorTranslator` 확장, `WorkflowTracker` 확장, SQLite + FTS5 | 에러 번역, 워크플로우 상태 변경, 영구 저장 |
| **Presentation** | 기존 tool interface 활용 (`memory_search`, `memory_store`) | LLM에 노출되는 도구 인터페이스 |

### Key Decisions

| Decision | Rationale | Trade-offs |
|----------|-----------|------------|
| Self-Debug를 Hook으로 구현 | 기존 Hook 아키텍처 재사용, 모든 tool에 자동 적용 | Hook 실행 순서 관리 복잡도 증가 |
| 백트래킹을 WorkflowTracker 확장으로 | 기존 stage tracking 인프라 활용 | 비선형 상태 전이 로직 추가 필요 |
| Memory를 SQLite + FTS5로 | 이미 ExperimentLog/DomainKB가 같은 패턴 | 벡터 검색 없이 키워드 검색만 (Phase 6에서 확장 가능) |
| 재시도 최대 3회 제한 | 무한 루프 방지 vs 충분한 자율성 | 복잡한 에러는 3회로 부족할 수 있음 |

---

## 3. 현재 코드 분석 — 확장 포인트

### 3.1 Self-Debugging 관련

**현재 에러 처리 흐름** (`agent/core.py`):
```
Tool 실행 → 에러 발생 → ErrorTranslator (DS 맥락 진단) → 에러 메시지를 LLM에 반환
                                                        → LLM이 다음 행동 결정 (보장 없음)
```

**문제**: LLM이 에러를 보고 "자율적으로" 수정할 수도 있지만, 구조적으로 보장되지 않는다.
같은 에러를 반복하거나, 에러를 무시하고 다음 단계로 넘어갈 수 있다.

**확장 포인트**:
- `core.py:198-200` — 개별 tool 에러 격리 지점. 여기서 Self-Debug 루프 진입
- `core.py:272` — `_is_tool_error()` 에러 감지 함수. 에러 분류 로직 확장
- `core.py:286-287` — post-hook learning trigger. 에러 패턴 학습에 활용
- `builtin_hooks.py` — 기존 Hook 등록 패턴 참조 (priority 기반)

### 3.2 Backtracking 관련

**현재 워크플로우 추적** (`ds_workflow_hooks.py:26-107`):
```python
# Tool → Stage 매핑 (선형)
TOOL_STAGE_MAP = {
    "data_loader": "data_loading",
    "train_model": "modeling",
    # ...
}
# Stage 상태: "pending" → "running" → "done"/"error"
```

**문제**: Stage 상태가 단방향(pending → running → done). "done" → "running" 역전이 없음.

**확장 포인트**:
- `ds_workflow_hooks.py:53-107` — `WorkflowTrackerHook`. 상태 전이 로직에 역전이 추가
- `ds_workflow_hooks.py:95-103` — `get_completeness()`. 백트래킹 시 completeness 재계산
- `builtin_hooks.py:280-340` — `OverfittingDetectorHook`. 성능 미달 감지 → 백트래킹 트리거 연결

### 3.3 Memory 관련

**현재 상태** (`tools/memory_tools.py`):
```python
# memory_search: "[NOT IMPLEMENTED]" — Returns empty results
# memory_store: No-op until wired to runtime
```

**이미 구현된 영구 저장소**:
- `ExperimentLog` (JSONL) — 실험 기록 (append-only, thread-safe)
- `CodeRegistry` (JSON) — 코드 패턴 (use count tracking)
- `DomainKB` — 도메인 지식 (confidence decay 0.95^months)
- `ProjectStore` — 프로젝트 메타데이터

**확장 포인트**:
- `memory/experiment_log.py` — `get_experiments()`, `get_best_experiment()` 존재
- `memory/code_registry.py` — `search()` 메서드 존재 (키워드 매칭)
- `memory/domain_kb.py` — confidence decay 로직 존재
- `tools/memory_tools.py:36-122` — tool 인터페이스 shell 존재, 핸들러만 구현하면 됨
- `self_improve/post_project.py` — `PostProjectLearner` 가 이미 학습 파이프라인 오케스트레이션

---

## 4. OpenClaw/Hermes 참조 패턴

### Memory 시스템 참조 (OpenClaw)

| OpenClaw 패턴 | DS Agent 적용 |
|--------------|--------------|
| Managed Markdown Blocks — regex 마커로 md 파일 섹션 업데이트 | DomainKB에 마크다운 기반 지식 저장 고려 |
| LanceDB 벡터 검색 | Phase 6에서 임베딩 기반 검색 확장 (현재는 FTS5 키워드) |
| `MemoryFlushPlan` — 메모리 정리/압축 전략 | Memory curation: 오래된 항목 decay, 중복 제거 |
| `appendMemoryHostEvent()` — 메모리 작업 이력 추적 | 메모리 변경 감사 로그 |
| 하이브리드 검색 (키워드 + 벡터) | SQLite FTS5 (키워드) 우선 → Phase 6에서 벡터 추가 |

### Self-Debugging 참조 (Claude Code)

| Claude Code 패턴 | DS Agent 적용 |
|-----------------|--------------|
| 에러 → 진단 → 수정 → 재실행 자율 루프 | SelfDebugHook: post_tool_use에서 에러 감지 → 수정 코드 생성 → 재실행 |
| 같은 에러 반복 감지 → 다른 접근 시도 | 에러 시그니처 해싱 → 동일 에러 2회 이상 시 전략 전환 |
| 최대 재시도 제한 → 사용자 에스컬레이션 | max_retries=3, 초과 시 `ask_user`로 에스컬레이션 |

---

## 5. Implementation Phases (TDD)

### Phase 0-1: Self-Debugging Loop

**Goal**: 에이전트가 tool 에러 발생 시 자율적으로 진단 → 수정 → 재실행

#### RED: Write Failing Tests First

- [ ] **Test 0-1.1**: `SelfDebugHook`이 tool 에러 감지 시 `debug_attempt` 이벤트 emit
  - File: `tests/unit/application/test_self_debug_hook.py`
  - Scenario: `execute_code` 에러 결과 → hook이 에러 분류 + 수정 제안 생성
  - Expected: Tests FAIL (Hook 미구현)

- [ ] **Test 0-1.2**: 에러 시그니처 해싱으로 동일 에러 반복 감지
  - File: `tests/unit/application/test_self_debug_hook.py`
  - Scenario: 같은 TypeError 2회 발생 → `repeated_error` 플래그 True
  - Expected: Tests FAIL

- [ ] **Test 0-1.3**: 최대 재시도 횟수(3) 초과 시 에스컬레이션
  - File: `tests/unit/application/test_self_debug_hook.py`
  - Scenario: 3회 실패 후 4번째 시도 → `ESCALATE` 결과 반환
  - Expected: Tests FAIL

- [ ] **Test 0-1.4**: 성공적 수정 후 재시도 카운터 리셋
  - File: `tests/unit/application/test_self_debug_hook.py`
  - Scenario: 에러 → 수정 성공 → 새 에러 → 카운터 1 (0 아님)
  - Expected: Tests FAIL

- [ ] **Test 0-1.5**: Integration — core.py에서 SelfDebugHook 동작
  - File: `tests/integration/test_self_debug_integration.py`
  - Scenario: 모의 LLM + 에러 tool → SelfDebugHook 개입 → 수정 코드 재실행
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 0-1.6**: `SelfDebugHook` 구현
  - File: `src/ds_agent/agent/builtin_hooks.py` (또는 별도 파일)
  - 구현 내용:
    - `post_tool_use()`: 에러 감지 → 에러 분류 (DataError / CodeBug / EnvError)
    - 에러 시그니처 해싱 (에러 타입 + 핵심 메시지)
    - 재시도 카운터 관리 (세션 수준)
    - 수정 제안 생성 (ErrorTranslator 확장)
    - 에스컬레이션 판단 (max_retries 초과 또는 동일 에러 반복)

- [ ] **Task 0-1.7**: Domain Value Object 정의
  - File: `src/ds_agent/domain/value_objects/self_debug.py`
  - `SelfDebugDecision`: action (RETRY / ESCALATE / SKIP), error_category, suggestion, attempt_count

- [ ] **Task 0-1.8**: Factory에 Hook 등록
  - File: `src/ds_agent/agent/factory.py`
  - `SelfDebugHook` priority=33 으로 등록

- [ ] **Task 0-1.9**: 이벤트 emit 연결
  - `debug.attempt` 이벤트: {tool_name, error_category, attempt, suggestion}
  - `debug.escalation` 이벤트: {tool_name, error_history, reason}

#### REFACTOR: Clean Up Code

- [ ] Task 0-1.10: 에러 분류 로직을 ErrorTranslator와 통합
- [ ] Task 0-1.11: 중복 코드 제거, 명명 일관성 확인

#### Quality Gate

- [ ] TDD compliance verified (테스트 먼저 작성됨)
- [ ] Build passes
- [ ] All tests pass (기존 1090+ 포함)
- [ ] Linting clean (`ruff check .`)
- [ ] Clean Architecture: SelfDebugDecision은 Domain layer, Hook은 Application layer
- [ ] Clean Architecture: Hook이 Infrastructure를 직접 import하지 않음
- [ ] No security issues
- [ ] Manual testing: 의도적 에러 코드 실행 → 자동 수정 → 성공 확인

---

### Phase 0-2: BacktrackTriggerHook

**Goal**: 모델 성능 미달 시 Feature Engineering 또는 EDA로 자동 백트래킹

#### RED: Write Failing Tests First

- [ ] **Test 0-2.1**: 성능 미달 감지 시 백트래킹 대상 stage 결정
  - File: `tests/unit/application/test_backtrack_hook.py`
  - Scenario: evaluation 결과 accuracy < baseline → backtrack_to = "feature_eng"
  - Expected: Tests FAIL

- [ ] **Test 0-2.2**: 백트래킹 depth 제한 (최대 2회)
  - File: `tests/unit/application/test_backtrack_hook.py`
  - Scenario: feature_eng → modeling → evaluation (미달) → feature_eng → modeling → evaluation (미달) → 3번째는 STOP
  - Expected: Tests FAIL

- [ ] **Test 0-2.3**: WorkflowTracker 상태 역전이
  - File: `tests/unit/application/test_backtrack_hook.py`
  - Scenario: evaluation "done" → backtrack → feature_eng "running", modeling "pending"
  - Expected: Tests FAIL

- [ ] **Test 0-2.4**: 백트래킹 시 이전 시도 context 보존
  - File: `tests/unit/application/test_backtrack_hook.py`
  - Scenario: 백트래킹 시 "이전 시도에서 accuracy=0.72, 이유: overfitting" 정보 포함
  - Expected: Tests FAIL

- [ ] **Test 0-2.5**: Integration — 워크플로우 전체 흐름에서 백트래킹
  - File: `tests/integration/test_backtrack_integration.py`
  - Scenario: 전체 파이프라인 시뮬레이션, evaluation 미달 → 자동 회귀 → 재시도
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 0-2.6**: Domain Value Object 정의
  - File: `src/ds_agent/domain/value_objects/backtrack.py`
  - `BacktrackDecision`: target_stage, reason, previous_attempts (list), should_stop (bool)

- [ ] **Task 0-2.7**: `BacktrackTriggerHook` 구현
  - File: `src/ds_agent/agent/ds_workflow_hooks.py` (기존 파일에 추가)
  - Priority: 37 (OverfittingDetector=35 이후, ModelSanityCheck=40 이전)
  - 구현 내용:
    - `post_tool_use()`: evaluation 결과에서 성능 메트릭 추출
    - Baseline 대비 성능 비교 (BaselineGuardHook 연계)
    - 백트래킹 대상 결정 로직:
      - Overfitting → Feature Engineering (피처 축소/정규화)
      - Underfitting → EDA (데이터 재탐색) 또는 Modeling (모델 변경)
      - Data quality issue → Data Loading (새 데이터)
    - `backtrack.trigger` 이벤트 emit

- [ ] **Task 0-2.8**: WorkflowTracker 확장 — 역전이 지원
  - File: `src/ds_agent/agent/ds_workflow_hooks.py`
  - `rewind_to_stage(target_stage)`: target 이후 stage를 "pending"으로 리셋
  - 히스토리 보존: 이전 시도 기록을 backtrack_history에 저장

- [ ] **Task 0-2.9**: 시스템 프롬프트에 백트래킹 컨텍스트 주입
  - `SessionInitHook` 확장: 백트래킹 히스토리가 있으면 프롬프트에 포함
  - "이전 시도: [피처셋 A, accuracy=0.72, overfitting]. 다른 접근을 시도하라."

- [ ] **Task 0-2.10**: Factory에 Hook 등록
  - File: `src/ds_agent/agent/factory.py`

#### REFACTOR: Clean Up Code

- [ ] Task 0-2.11: BacktrackTriggerHook과 OverfittingDetectorHook 중복 로직 통합
- [ ] Task 0-2.12: WorkflowTracker 상태 전이 로직을 별도 state machine으로 추출

#### Quality Gate

- [ ] TDD compliance verified
- [ ] Build passes
- [ ] All tests pass
- [ ] Linting clean
- [ ] Clean Architecture: BacktrackDecision은 Domain layer
- [ ] Clean Architecture: Hook은 WorkflowTracker의 인터페이스만 사용
- [ ] No security issues
- [ ] Manual testing: 의도적으로 낮은 성능 모델 → 자동 백트래킹 → 재시도 확인

---

### Phase 0-3: Memory 구현

**Goal**: `memory_search` / `memory_store` tool을 실제 동작하게 구현, 4계층 메모리 구조 기반

#### RED: Write Failing Tests First

- [ ] **Test 0-3.1**: `memory_store` — 메모리 항목 저장
  - File: `tests/unit/infrastructure/test_memory_store.py`
  - Scenario: {type: "domain", key: "churn_definition", content: "..."} 저장 → 성공
  - Expected: Tests FAIL

- [ ] **Test 0-3.2**: `memory_search` — 키워드 검색
  - File: `tests/unit/infrastructure/test_memory_search.py`
  - Scenario: "churn" 검색 → 저장된 churn_definition 반환
  - Expected: Tests FAIL

- [ ] **Test 0-3.3**: Memory type별 격리
  - File: `tests/unit/infrastructure/test_memory_store.py`
  - Scenario: session/project/domain/global 각각 저장 → type 필터링 검색
  - Expected: Tests FAIL

- [ ] **Test 0-3.4**: Confidence decay 적용
  - File: `tests/unit/infrastructure/test_memory_search.py`
  - Scenario: 6개월 전 저장 항목 → confidence = 원래값 × 0.95^6
  - Expected: Tests FAIL

- [ ] **Test 0-3.5**: 중복 감지 및 업데이트
  - File: `tests/unit/infrastructure/test_memory_store.py`
  - Scenario: 같은 key로 재저장 → 기존 항목 업데이트 (새 항목 생성 아님)
  - Expected: Tests FAIL

- [ ] **Test 0-3.6**: FTS5 전문 검색
  - File: `tests/unit/infrastructure/test_memory_search.py`
  - Scenario: "customer lifetime value prediction" → "ltv-prediction" 관련 항목 검색
  - Expected: Tests FAIL

- [ ] **Test 0-3.7**: Memory 삭제/수정
  - File: `tests/unit/infrastructure/test_memory_store.py`
  - Scenario: 특정 메모리 항목 삭제 또는 내용 수정
  - Expected: Tests FAIL

- [ ] **Test 0-3.8**: Integration — agent가 memory tool 사용
  - File: `tests/integration/test_memory_integration.py`
  - Scenario: 세션 1에서 memory_store → 세션 2에서 memory_search → 결과 반환
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 0-3.9**: Domain Entity 정의
  - File: `src/ds_agent/domain/entities/memory.py`
  - `MemoryEntry`: id, type (session/project/domain/global), key, content, tags, confidence, created_at, updated_at, source_session_id

- [ ] **Task 0-3.10**: Domain Interface 정의
  - File: `src/ds_agent/domain/interfaces/memory.py`
  - `MemoryStore` Protocol: store(), search(), get(), update(), delete(), list_by_type()
  - `MemorySearchPort` Protocol: search(query, type, max_results) → List[MemoryEntry]

- [ ] **Task 0-3.11**: Infrastructure — SQLite + FTS5 구현
  - File: `src/ds_agent/memory/unified_store.py`
  - 테이블 스키마:
    ```sql
    CREATE TABLE memories (
      id TEXT PRIMARY KEY,
      type TEXT NOT NULL,        -- session/project/domain/global
      key TEXT NOT NULL,
      content TEXT NOT NULL,
      tags TEXT,                  -- JSON array
      confidence REAL DEFAULT 1.0,
      source_session_id TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE VIRTUAL TABLE memories_fts USING fts5(
      key, content, tags, content='memories', content_rowid='rowid'
    );
    ```
  - 구현: store(), search() (FTS5 MATCH), get(), update(), delete()
  - Confidence decay: search 시 `confidence * (0.95 ^ months_since_update)` 적용
  - 중복 감지: key + type 조합 unique → UPSERT

- [ ] **Task 0-3.12**: Application Use Case 구현
  - File: `src/ds_agent/application/use_cases/memory.py`
  - `MemorySearchUseCase`: query 파싱, type 필터링, 결과 정렬 (confidence × relevance)
  - `MemoryStoreUseCase`: 입력 검증, 중복 체크, 저장

- [ ] **Task 0-3.13**: Tool 핸들러 구현
  - File: `src/ds_agent/tools/memory_tools.py` (기존 placeholder 교체)
  - `memory_search`: query, memory_type (선택), max_results (기본 5) → 결과 리스트
  - `memory_store`: type, key, content, tags (선택) → 저장 확인

- [ ] **Task 0-3.14**: 기존 Memory 시스템 통합
  - `ExperimentLog` → 자동으로 memories 테이블에 project type으로 동기화
  - `CodeRegistry` → 자동으로 memories 테이블에 global type으로 동기화
  - `DomainKB` → 자동으로 memories 테이블에 domain type으로 동기화

- [ ] **Task 0-3.15**: Factory 연결
  - File: `src/ds_agent/agent/factory.py`
  - `UnifiedMemoryStore` 인스턴스 생성 + memory tools에 주입
  - `MemoryQueryService` 교체

- [ ] **Task 0-3.16**: Inspectable API
  - 사용자가 `memory_search(query="*", memory_type="domain")` 으로 전체 도메인 지식 조회 가능
  - 삭제/수정 지원

#### REFACTOR: Clean Up Code

- [ ] Task 0-3.17: 기존 ExperimentLog/CodeRegistry/DomainKB와 UnifiedMemoryStore 간 중복 제거
- [ ] Task 0-3.18: 메모리 관련 이벤트 emit 통합 (`memory.stored`, `memory.searched`)

#### Quality Gate

- [ ] TDD compliance verified
- [ ] Build passes
- [ ] All tests pass
- [ ] Linting clean
- [ ] Clean Architecture: MemoryEntry는 Domain, SQLite 구현은 Infrastructure
- [ ] Clean Architecture: Tool은 Use Case만 호출, 직접 SQLite 접근 안 함
- [ ] Clean Architecture: Use Case는 MemoryStore Protocol만 의존
- [ ] No security issues (메모리에 credential 저장 방지)
- [ ] Manual testing: store → search → 결과 확인, 세션 재시작 후 검색 가능

---

## 6. 신규 Skill 정의

### 6.1 `task-type-routing` Skill

```markdown
# Task Type Routing

문제 유형을 자동 분류하고 적절한 분석 전략을 라우팅하는 스킬.

## 문제 유형 분류
| 유형 | 키워드 | 라우팅 |
|------|--------|--------|
| 예측 (Prediction) | "예측", "predict", "forecast" | modeling 중심 워크플로우 |
| 진단 (Diagnosis) | "왜", "원인", "하락", "why" | EDA + root-cause 중심 |
| 실험 (Experimentation) | "A/B", "실험", "효과" | experiment design 중심 |
| 세그먼테이션 | "세그먼트", "군집", "분류" | clustering + profiling |
| 모니터링 | "drift", "모니터링", "이상" | operations 중심 |
| 리포팅 | "보고서", "요약", "대시보드" | reporting 중심 |
| No-Model | "정의", "집계", "현황" | 단순 집계/시각화 |

## No-Model Decision 기준
- 데이터가 충분하지 않을 때 (N < 100)
- 문제가 정의의 문제일 때 ("매출이 뭔가요?")
- 단순 집계로 답이 나올 때 ("지난달 DAU는?")
- 모델보다 비즈니스 룰이 적합할 때
```

### 6.2 `self-verification` Skill

```markdown
# Self-Verification

각 분석 단계 완료 후 자체 검증을 수행하는 스킬.

## 검증 체크리스트
1. **출력 유효성**: 결과 파일이 존재하는가? 비어있지 않은가?
2. **수치 일관성**: 합계/비율이 맞는가? NaN/Inf가 없는가?
3. **논리적 일관성**: 결론이 데이터와 일치하는가?
4. **재현 가능성**: 같은 입력으로 같은 결과가 나오는가?
5. **경계 조건**: 극단값, 빈 데이터, 단일 클래스에서 에러 없는가?
```

### 6.3 `failure-recovery` Skill

```markdown
# Failure Recovery

에러 발생 시 자율적으로 진단하고 수정하는 스킬.

## 에러 분류
| 카테고리 | 예시 | 대응 |
|---------|------|------|
| DataError | FileNotFound, 인코딩, 스키마 불일치 | 경로/인코딩 수정, 스키마 확인 |
| CodeBug | TypeError, IndexError, ValueError | 코드 수정 후 재실행 |
| EnvError | OOM, timeout, 패키지 미설치 | 리소스 조정 또는 에스컬레이션 |
| LogicError | 잘못된 조인, 누수, 잘못된 메트릭 | EDA 회귀, 방법론 재검토 |

## Self-Debugging Loop
1. 에러 메시지 파싱 → 카테고리 분류
2. 유사 에러 이력 검색 (memory)
3. 수정 코드 생성
4. 수정 타당성 검증 (같은 실수 반복 방지)
5. 재실행 (최대 3회)
6. 실패 시 에스컬레이션 (ask_user)
```

---

## 7. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Self-Debugging 무한 루프 | 중 | 높음 | 최대 3회 재시도, 같은 에러 해시 반복 감지, 비용 가드 연동 |
| 백트래킹 무한 반복 | 중 | 중간 | 최대 2회 백트래킹 제한, 백트래킹 히스토리 기록 |
| Memory에 틀린 정보 축적 | 높음 | 높음 | Confidence decay, 충돌 감지, 사용자 수정 가능 |
| FTS5 검색 품질 낮음 | 중 | 중간 | Phase 6에서 벡터 검색 추가 계획 |
| 기존 테스트 깨짐 | 낮음 | 높음 | 기존 Hook 동작에 영향 없도록 priority 배치 |

---

## 8. Rollback Strategy

### Phase 0-1 (Self-Debugging) 실패 시
- `SelfDebugHook`을 factory에서 등록 해제 (한 줄 삭제)
- 기존 에러 처리 흐름 복원 (변경 없음)

### Phase 0-2 (Backtracking) 실패 시
- `BacktrackTriggerHook`을 factory에서 등록 해제
- WorkflowTracker의 역전이 로직은 사용되지 않으면 무해

### Phase 0-3 (Memory) 실패 시
- `memory_search` / `memory_store`를 다시 placeholder로 교체
- `UnifiedMemoryStore` 는 독립 모듈이므로 제거 용이
- 기존 ExperimentLog/CodeRegistry/DomainKB는 영향 없음

---

## 9. Progress Tracking

- Phase 0-1 (Self-Debugging): 100%
- Phase 0-2 (Backtracking): 100%
- Phase 0-3 (Memory): 100%
- **Overall Phase 0**: 100%

---

## Notes & Learnings

- SelfDebugHook: ErrorTranslator와 패턴이 유사하나 용도가 다름 (rich format vs concise suggestion). 강제 통합 불필요.
- BacktrackTriggerHook: rewind_tracker_to_stage()를 별도 함수로 분리하여 WorkflowTracker 내부 수정 최소화.
- UnifiedMemoryStore: store() 시 entry의 원래 timestamps를 보존해야 confidence decay가 정확히 동작함.
- 기존 MemoryQueryService와 UnifiedMemoryStore 이중 구조 유지 — legacy 검색은 MemoryQueryService, 신규 4-layer 검색은 UnifiedMemoryStore.
- Hook 수: 14 → 16 (SelfDebugHook priority=33, BacktrackTriggerHook priority=37 추가).
- 1083/1083 테스트 통과 (기존 환경 이슈 4개 제외 — 공유 JSON 상태 누적).
