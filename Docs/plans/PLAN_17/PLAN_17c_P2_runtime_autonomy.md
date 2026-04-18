# Phase 2: Runtime Autonomy — 장기 실행·반복 위임 가능

**Status**: Pending
**Started**: -
**Last Updated**: 2026-04-13
**Parent**: `PLAN_17_ROADMAP_MASTER.md`
**선행 조건**: Phase 0 완료 (Memory + Backtrack 필수)
**후행 Phase**: P3 (Enterprise Trust), P5 (Operations)

---

## 1. Overview

### 왜 Runtime Autonomy인가

실제 위임은 한 번의 대화로 끝나지 않는다. 오전에 데이터 정의를 찾고, 오후에 분석하고, 밤에 학습을 돌리고, 다음날 결과를 검토해야 한다. 현재 에이전트는 interactive only — 사용자가 화면 앞에 없으면 아무것도 못 한다.

**진짜 실무 위임 = "다음 주도 알아서 해"**

### 현재 상태

- `AutonomousCoordinator` 코드 존재하지만 **disabled**
- `GoalStore`, `WorkingMemoryStore`, `CheckpointStore` 추상화 존재
- Standing Order 개념은 있으나 실행 엔진이 비활성
- 선형 파이프라인만 지원 (비선형 DAG 미지원)

### 성공 기준

- [ ] Autonomous Runtime 활성화: Background 모드 동작 확인
- [ ] Task Graph: 비선형 실행 (조건부 분기 + 백트래킹) 지원
- [ ] Standing Orders: 반복 위임 실행 (예: 주간 KPI scan)
- [ ] Checkpoint + Resume: 중단 후 재개 정상 동작
- [ ] Subagent Framework: Builder/Validator 분리 기초 구조
- [ ] 기존 테스트 전체 통과 + 신규 테스트 추가

---

## 2. Architecture Decisions (Clean Architecture)

### Layer Mapping

| Layer | Components | Responsibility |
|-------|-----------|---------------|
| **Domain** | `TaskNode` (Entity), `TaskGraph` (Entity), `StandingOrder` (Entity), `SubagentSpec` (VO) | 태스크 노드/그래프 구조, 반복 명령 정의, 서브에이전트 명세 |
| **Application** | `TaskGraphService`, `SchedulerService`, `SubagentOrchestrator`, `CheckpointService` | DAG 실행, 스케줄링, 서브에이전트 조정, 체크포인트 관리 |
| **Infrastructure** | `CronRunner`, `TaskGraphStore`, `StandingOrderStore`, `ProcessSubagent` | 크론 실행, 영구 저장, 프로세스 격리 |
| **Presentation** | `task_graph` tool, `standing_order` tool, `checkpoint` tool | LLM에 노출되는 도구 인터페이스 |

### Key Decisions

| Decision | Rationale | Trade-offs |
|----------|-----------|------------|
| Task Graph를 Entity로 모델링 | 비선형 실행 상태를 명시적으로 관리 | WorkflowTracker와 책임 경계 명확화 필요 |
| Standing Order를 GoalStore 확장으로 | 기존 Goal 인프라 재사용 | Goal과 Standing Order의 생명주기 차이 |
| Subagent를 별도 프로세스로 | 격리 + 독립적 LLM 호출 + 예산 분리 | 프로세스 간 통신 오버헤드 |
| Checkpoint를 JSON snapshot으로 | 단순, 디버깅 용이, 기존 패턴 | 대용량 상태 시 성능 문제 |

### OpenClaw 참조 패턴

| OpenClaw 패턴 | DS Agent 적용 |
|--------------|--------------|
| Cron Tool (`cron-tool.ts`) — "at"/"every"/"cron" 3가지 스케줄 | Standing Order의 trigger 유형 |
| Session Targeting — "main"/"isolated"/"current" | Subagent 실행 세션 정책 |
| Delivery Modes — "announce"/"webhook"/"none" | Standing Order 결과 전달 방식 |
| Failure Alerts — N회 실패 후 에스컬레이션 | Standing Order 실패 처리 |
| Hot Browser Window (5min keep-alive) | Background 작업의 리소스 캐싱 |
| Session TTL + LRU Eviction | 장기 실행 세션 관리 |

---

## 3. Implementation Phases (TDD)

### Phase 2-1: Autonomous Runtime 활성화

**Goal**: 기존 AutonomousCoordinator 코드를 활성화하고 Background 실행 모드 동작 확인

#### RED: Write Failing Tests First

- [ ] **Test 2-1.1**: `AutonomousCoordinator` — 이벤트 수신 시 에이전트 실행 디스패치
  - File: `tests/unit/infrastructure/test_coordinator.py`
  - Scenario: file.created 이벤트 → coordinator가 agent run 디스패치
  - Expected: Tests FAIL (coordinator disabled)

- [ ] **Test 2-1.2**: Background 모드 — 사용자 부재 중 실행 + 완료 알림
  - File: `tests/integration/test_background_mode.py`
  - Scenario: background task 시작 → 완료 → notification 이벤트 emit
  - Expected: Tests FAIL

- [ ] **Test 2-1.3**: Cooldown — 동일 이벤트 반복 시 쿨다운 적용
  - File: `tests/unit/infrastructure/test_coordinator.py`
  - Scenario: 같은 file.created 이벤트 10초 간격으로 3회 → 1회만 디스패치
  - Expected: Tests FAIL

- [ ] **Test 2-1.4**: 예산 분리 — Background 실행의 별도 예산 한도
  - File: `tests/unit/infrastructure/test_coordinator.py`
  - Scenario: background run에 별도 budget_usd 할당 → 소진 시 정상 종료
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 2-1.5**: Coordinator 활성화
  - File: `src/ds_agent/runtime/coordinator.py`
  - 현재 disabled 로직 제거/활성화
  - 이벤트 루프 시작 조건 설정 (config에서 `autonomous.enabled: true`)

- [ ] **Task 2-1.6**: Background 실행 모드 추가
  - File: `src/ds_agent/agent/core.py`
  - `run()` 메서드에 `mode` 파라미터 추가: "interactive" / "background"
  - Background 모드: 콜백을 통한 알림만, 사용자 input 대기 없음

- [ ] **Task 2-1.7**: 알림 시스템 연결
  - 완료 시 `task.completed` 이벤트 emit
  - Telegram/Electron에서 수신하여 사용자 알림

- [ ] **Task 2-1.8**: Config 스키마 확장
  - File: `src/ds_agent/config/schema.py`
  - `AutonomousConfig`: enabled, cooldown_seconds, max_concurrent_runs, budget_per_run_usd

#### Quality Gate

- [ ] Background 실행 시작/완료/알림 동작 확인
- [ ] 쿨다운 동작 확인
- [ ] 기존 interactive 모드 영향 없음

---

### Phase 2-2: Task Graph + Checkpoints

**Goal**: 선형 pipeline → 비선형 DAG 전환, 체크포인트 기반 재개

#### RED: Write Failing Tests First

- [ ] **Test 2-2.1**: `TaskNode` — 노드 생성 및 상태 전이
  - File: `tests/unit/domain/test_task_graph.py`
  - Scenario: TaskNode("eda") → pending → running → completed
  - Expected: Tests FAIL

- [ ] **Test 2-2.2**: `TaskGraph` — DAG 구성 및 실행 순서 결정
  - File: `tests/unit/domain/test_task_graph.py`
  - Scenario: scoping → data_loading → [profiling, eda] (병렬) → feature_eng
  - Expected: Tests FAIL

- [ ] **Test 2-2.3**: 조건부 분기 — 평가 결과에 따른 경로 선택
  - File: `tests/unit/domain/test_task_graph.py`
  - Scenario: evaluation.score < 0.7 → backtrack to feature_eng; else → reporting
  - Expected: Tests FAIL

- [ ] **Test 2-2.4**: 체크포인트 생성 및 복원
  - File: `tests/unit/application/test_checkpoint_service.py`
  - Scenario: modeling 완료 후 checkpoint → 복원 → modeling 다음 단계부터 재개
  - Expected: Tests FAIL

- [ ] **Test 2-2.5**: Experiment Branching — 실험 트리 구조
  - File: `tests/unit/domain/test_task_graph.py`
  - Scenario: exp-001 (baseline) → exp-002 (feature A) + exp-003 (feature B) → 최고 선택
  - Expected: Tests FAIL

- [ ] **Test 2-2.6**: Integration — 전체 비선형 워크플로우
  - File: `tests/integration/test_task_graph_integration.py`

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 2-2.7**: Domain Entities
  - File: `src/ds_agent/domain/entities/task_graph.py`
  - `TaskNode`:
    - id, name, stage, status (pending/running/completed/failed/skipped)
    - dependencies (List[str]), children (List[str])
    - result (Optional[dict]), checkpoint_id (Optional[str])
    - retry_count, max_retries
  - `TaskGraph`:
    - nodes (Dict[str, TaskNode])
    - edges (List[Tuple[str, str]])
    - `get_ready_nodes()` → 모든 의존성이 완료된 노드들
    - `add_conditional_edge(from_node, to_node, condition_fn)`
    - `branch(from_node, branches: List[TaskNode])` → 실험 분기
    - `get_best_branch(metric_key)` → 최고 성능 브랜치

- [ ] **Task 2-2.8**: Application Service
  - File: `src/ds_agent/application/services/task_graph_service.py`
  - `TaskGraphService`:
    - `create_from_workflow(stages)` → 기존 8단계를 DAG로 변환
    - `advance()` → 다음 실행 가능 노드 반환
    - `complete_node(node_id, result)` → 완료 처리 + 조건부 분기 평가
    - `rewind_to(node_id)` → 백트래킹 (BacktrackTriggerHook 연동)
    - `checkpoint()` → 현재 그래프 상태 스냅샷
    - `restore(checkpoint_id)` → 스냅샷에서 복원

- [ ] **Task 2-2.9**: Infrastructure — 영구 저장
  - File: `src/ds_agent/infrastructure/persistence/task_graph_store.py`
  - JSON 파일 기반 (세션별 `data/task_graphs/{session_id}.json`)

- [ ] **Task 2-2.10**: WorkflowTracker 통합
  - 기존 `WorkflowTrackerHook`이 `TaskGraph`와 동기화
  - TaskGraph 노드 완료 → WorkflowTracker stage 업데이트

- [ ] **Task 2-2.11**: `task_graph` Tool (선택적)
  - File: `src/ds_agent/tools/task_graph_tools.py`
  - LLM이 명시적으로 태스크 그래프를 조작할 수 있는 인터페이스
  - Actions: view (현재 그래프 상태), branch (실험 분기), checkpoint (저장)

#### Quality Gate

- [ ] 비선형 실행 동작 확인 (조건부 분기, 백트래킹)
- [ ] 체크포인트 생성/복원 동작 확인
- [ ] 기존 WorkflowTracker 이벤트 호환성 유지

---

### Phase 2-3: Standing Order 실행 엔진

**Goal**: 반복 위임 가능 — 주간 KPI scan, 일일 drift check 등

#### RED: Write Failing Tests First

- [ ] **Test 2-3.1**: `StandingOrder` Entity — 생성 및 검증
  - File: `tests/unit/domain/test_standing_order.py`
  - Scenario: {name, trigger, scope, approval_gate, escalation} → 유효한 Standing Order
  - Expected: Tests FAIL

- [ ] **Test 2-3.2**: Trigger 평가 — cron 표현식 매칭
  - File: `tests/unit/infrastructure/test_cron_runner.py`
  - Scenario: "0 9 * * MON" + 현재 시각 월요일 09:00 → should_trigger = True
  - Expected: Tests FAIL

- [ ] **Test 2-3.3**: 실행 후 결과 전달 — Telegram/Slack 알림
  - File: `tests/unit/infrastructure/test_standing_order_delivery.py`
  - Scenario: KPI 스캔 완료 → 결과 요약 메시지 전송
  - Expected: Tests FAIL

- [ ] **Test 2-3.4**: 에스컬레이션 — 임계치 초과 시 매니저 호출
  - File: `tests/unit/domain/test_standing_order.py`
  - Scenario: KPI 3σ 초과 → escalation 트리거
  - Expected: Tests FAIL

- [ ] **Test 2-3.5**: Standing Order CRUD
  - File: `tests/unit/infrastructure/test_standing_order_store.py`
  - Scenario: create, read, update, delete, list
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 2-3.6**: Domain Entity
  - File: `src/ds_agent/domain/entities/standing_order.py`
  - `StandingOrder`:
    - id, name, description
    - trigger: `CronTrigger` (cron expr + timezone) / `EventTrigger` (event_type, filter)
    - scope: 분석 대상 (KPI 목록, 테이블, 모델 등)
    - approval_gate: 결과 처리 방식 (auto_report / approval_required / notify_only)
    - escalation: 조건 + 대상 + 채널
    - budget_limit_usd: 실행당 예산 한도
    - enabled: bool
    - last_run_at, next_run_at, run_count

- [ ] **Task 2-3.7**: Infrastructure — Cron Runner
  - File: `src/ds_agent/infrastructure/cron_runner.py`
  - `CronRunner`:
    - cron 표현식 파싱 (`croniter` 라이브러리)
    - 다음 실행 시각 계산
    - 실행 트리거 → Coordinator에 이벤트 전달
    - 실패 시 재시도 (max 3회, exponential backoff)

- [ ] **Task 2-3.8**: Application Service
  - File: `src/ds_agent/application/services/scheduler_service.py`
  - `SchedulerService`:
    - `register(order: StandingOrder)`
    - `unregister(order_id)`
    - `evaluate_triggers()` → 현재 시각에 실행할 order 목록
    - `dispatch(order)` → Coordinator 통해 background agent run 시작
    - `record_result(order_id, result)` → 결과 저장 + 전달

- [ ] **Task 2-3.9**: `standing_order` Tool
  - File: `src/ds_agent/tools/standing_order_tools.py`
  - Actions: create, list, update, delete, run_now, view_history
  - LLM이 "매주 월요일 KPI 스캔해줘"라고 하면 standing order 생성

- [ ] **Task 2-3.10**: Delivery 연결
  - 결과를 Telegram/Slack/Electron으로 전달
  - 기존 delivery policy (quiet hours, digest) 적용

#### Quality Gate

- [ ] cron 트리거 정확성 확인
- [ ] Standing Order 생성/실행/결과 전달 전체 흐름 확인
- [ ] 예산 한도 동작 확인
- [ ] 에스컬레이션 동작 확인

---

### Phase 2-4: Subagent Framework

**Goal**: Builder/Validator 분리 — 만드는 agent와 검증하는 agent 분리

#### RED: Write Failing Tests First

- [ ] **Test 2-4.1**: Subagent 생성 및 실행
  - File: `tests/unit/application/test_subagent.py`
  - Scenario: SubagentSpec(role="validator", prompt="검증해줘") → 독립 실행 → 결과 반환
  - Expected: Tests FAIL

- [ ] **Test 2-4.2**: Builder-Validator 상호작용
  - File: `tests/unit/application/test_subagent.py`
  - Scenario: Builder 결과 → Validator에 전달 → 피드백 반환 → Builder 수정
  - Expected: Tests FAIL

- [ ] **Test 2-4.3**: Subagent 예산 격리
  - File: `tests/unit/application/test_subagent.py`
  - Scenario: 메인 에이전트 예산과 별도, subagent 예산 소진 시 메인에 영향 없음
  - Expected: Tests FAIL

- [ ] **Test 2-4.4**: Subagent 결과 통합
  - File: `tests/unit/application/test_subagent.py`
  - Scenario: 2개 subagent 병렬 실행 → 결과 merge → 메인 에이전트에 반환
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 2-4.5**: Domain Value Object
  - File: `src/ds_agent/domain/value_objects/subagent.py`
  - `SubagentSpec`:
    - role: "builder" / "validator" / "reporter" / "operator"
    - prompt: 서브에이전트에 전달할 지시
    - budget_usd: 별도 예산
    - tools: 허용 도구 목록 (optional, default: 부모와 동일)
    - model: LLM 모델 (optional, default: 부모와 동일 또는 저렴한 모델)
    - timeout_seconds: 실행 제한 시간

- [ ] **Task 2-4.6**: Application Service
  - File: `src/ds_agent/application/services/subagent_orchestrator.py`
  - `SubagentOrchestrator`:
    - `spawn(spec: SubagentSpec) → SubagentRun`
    - `wait(run_id) → SubagentResult`
    - `spawn_and_wait(spec) → SubagentResult` (동기 편의)
    - `spawn_parallel(specs: List[SubagentSpec]) → List[SubagentResult]`

- [ ] **Task 2-4.7**: Infrastructure — 프로세스 기반 서브에이전트
  - File: `src/ds_agent/infrastructure/process_subagent.py`
  - 별도 DSAgent 인스턴스를 생성하여 실행
  - 입력: prompt + context (현재 분석 상태 요약)
  - 출력: 구조화된 결과 (JSON)
  - 예산/시간 격리

- [ ] **Task 2-4.8**: DS 특화 역할 프롬프트
  - Validator 프롬프트: "결과를 검증하라. 방법론 오류, 데이터 누수, 과적합 여부 확인."
  - Reporter 프롬프트: "분석 결과를 {청중}용으로 요약하라."
  - Operator 프롬프트: "모델 성능을 모니터링하고 이상 시 보고하라."

#### Quality Gate

- [ ] Subagent 생성/실행/결과 반환 동작 확인
- [ ] 예산 격리 확인 (subagent가 메인 예산 소진 안 함)
- [ ] Builder-Validator 상호작용 시나리오 확인

---

### Phase 2-5: Background Task + Resume

**Goal**: Overnight 모델 훈련 등 장시간 작업 지원

#### RED: Write Failing Tests First

- [ ] **Test 2-5.1**: Background task 시작 및 상태 추적
  - File: `tests/unit/application/test_background_task.py`
  - Scenario: 모델 훈련 background로 시작 → 상태 "running" → 완료 → "completed"
  - Expected: Tests FAIL

- [ ] **Test 2-5.2**: 중단 후 체크포인트에서 재개
  - File: `tests/unit/application/test_background_task.py`
  - Scenario: 실행 중 중단 → checkpoint 저장 → 재시작 → checkpoint에서 이어서 실행
  - Expected: Tests FAIL

- [ ] **Test 2-5.3**: 완료 알림 전달
  - File: `tests/unit/application/test_background_task.py`
  - Scenario: background 완료 → `task.completed` 이벤트 → 사용자 알림
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 2-5.4**: Background Task Manager
  - File: `src/ds_agent/runtime/background_task_manager.py`
  - 비동기 task 큐 관리
  - task 상태 추적: pending → running → completed / failed
  - 주기적 체크포인트 (매 5분 또는 stage 전환 시)

- [ ] **Task 2-5.5**: Resume Logic
  - File: `src/ds_agent/agent/core.py` 확장
  - `run()` 메서드에 `resume_from_checkpoint` 파라미터 추가
  - 체크포인트에서 TaskGraph, WorkingMemory, ExperimentLog 복원

- [ ] **Task 2-5.6**: 알림 이벤트 emit
  - `task.started`, `task.progress`, `task.completed`, `task.failed` 이벤트
  - 진행률: 완료된 TaskGraph 노드 / 전체 노드

#### Quality Gate

- [ ] Background 실행 + 완료 알림 확인
- [ ] 중단 → 재개 정상 동작 확인
- [ ] 메모리 누수 없음 (장시간 실행 안정성)

---

## 4. 실행 모드 매트릭스 (최종)

| 모드 | 설명 | 사용자 입력 | 체크포인트 | 예산 |
|------|------|-----------|-----------|------|
| **Interactive** | 대화형, 즉시 응답 | 실시간 | 선택적 | 세션 예산 |
| **Background** | 사용자 부재 중 실행 | 없음 (완료 알림) | 필수 (5분 주기) | 태스크별 예산 |
| **Scheduled** | Cron 기반 반복 | 없음 | 실행별 | Standing Order 예산 |
| **Event-Driven** | 외부 이벤트 트리거 | 없음 | 선택적 | 이벤트별 예산 |
| **Unattended** | 장기 실행 + failure recovery | 없음 (에스컬레이션만) | 필수 | 일일 예산 |

---

## 5. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Background 실행 비용 폭주 | 중 | 높음 | 태스크별 예산 한도, 일일 총 한도, BudgetGuardHook |
| Standing Order 무한 반복 | 낮음 | 중간 | 최대 실행 횟수 제한, 연속 실패 시 자동 비활성화 |
| Checkpoint 복원 실패 | 중 | 높음 | Checkpoint 무결성 검증, fallback으로 처음부터 재실행 |
| Subagent 간 충돌 | 중 | 중간 | 파일 잠금, workspace 격리, 결과 merge 전략 |
| Task Graph 복잡도 폭발 | 중 | 중간 | 최대 노드 수 제한 (50), depth 제한 (10) |
| Cron 라이브러리 시간대 이슈 | 낮음 | 낮음 | croniter + pytz, UTC 기준 내부 처리 |

---

## 6. Rollback Strategy

### Phase 2-1 (Coordinator 활성화) 실패 시
- config에서 `autonomous.enabled: false` 설정 → 기존 interactive only 복원

### Phase 2-2 (Task Graph) 실패 시
- TaskGraph 비활성화 → 기존 WorkflowTracker의 선형 파이프라인 유지
- 두 시스템이 병존 가능하도록 설계

### Phase 2-3 (Standing Orders) 실패 시
- CronRunner 중지 → Standing Order 미실행
- 기존 기능에 영향 없음

### Phase 2-4 (Subagent) 실패 시
- SubagentOrchestrator 제거 → 기존 single-loop 유지

### Phase 2-5 (Background) 실패 시
- Background 모드 비활성화 → interactive only 유지

---

## 7. Dependencies

### Required Before Starting
- [ ] Phase 0 Memory — Standing Order 이력 저장
- [ ] Phase 0 BacktrackTriggerHook — Task Graph 백트래킹 연동
- [ ] Phase 0 Self-Debugging — Background 실행 중 에러 자동 복구

### External Dependencies

```toml
[project.optional-dependencies]
scheduler = [
    "croniter>=2.0.0",
    "pytz>=2024.1",
]
```

---

## 8. Progress Tracking

- Phase 2-1 (Coordinator 활성화): 0%
- Phase 2-2 (Task Graph + Checkpoints): 0%
- Phase 2-3 (Standing Orders): 0%
- Phase 2-4 (Subagent Framework): 0%
- Phase 2-5 (Background + Resume): 0%
- **Overall Phase 2**: 0%

---

## Notes & Learnings

- [구현 중 발견 사항 기록]
