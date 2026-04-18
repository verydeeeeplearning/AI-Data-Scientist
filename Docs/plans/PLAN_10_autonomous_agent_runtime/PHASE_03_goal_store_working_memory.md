# Phase 03: Goal Store + Working Memory

**Priority**: P1  
**Milestone**: B  
**Status**: Completed  
**Implemented On**: 2026-04-12

---

## 1. Goal

`session/run/task` 위에 `goal`과 `working memory` 계층을 추가해서,
agent가 지금 무엇을 달성하려는지와 직전 turn에서 무엇이 결정되었는지를
구조적으로 유지하게 만드는 단계다.

이번 phase의 핵심 요구는 다음 4가지였다.

- 사용자 지시를 장기 goal로 승격
- goal lifecycle 상태 보존
- short-horizon working memory 보존
- 다음 turn prompt에 active goal + working memory 자동 주입

---

## 2. Implemented

### 2.1 New goal / working-memory entities

추가 파일:

- `src/ds_agent/domain/entities/goal.py`
- `src/ds_agent/domain/entities/working_memory.py`

구현 내용:

- `GoalStatus`
  - `pending`
  - `in_progress`
  - `blocked`
  - `completed`
  - `cancelled`
- `GoalRecord`
- `SessionWorkingMemory`

### 2.2 New storage ports and runtime stores

추가 파일:

- `src/ds_agent/runtime/goal_store.py`
- `src/ds_agent/runtime/working_memory.py`

수정 파일:

- `src/ds_agent/domain/interfaces/session_state.py`

구현 내용:

- `GoalStore` protocol
- `WorkingMemoryStore` protocol
- `JsonGoalStore`
- `JsonWorkingMemoryStore`
- workspace별 runtime root 아래 file-backed persistence
- agent restart 이후에도 active goal / working memory 복원 가능

### 2.3 Agent runtime wiring

수정 파일:

- `src/ds_agent/agent/core.py`
- `src/ds_agent/agent/factory.py`
- `src/ds_agent/api/ws_handler.py`
- `src/ds_agent/gateway/telegram_runner.py`

구현 내용:

- `create_agent()`가 기본적으로 goal store + working memory store를 생성
- `DSAgent`가 turn 시작 시:
  - active goal 생성/복원
  - goal 상태를 `in_progress`로 전이
  - working memory 초기화
- `DSAgent`가 turn 종료 시:
  - 응답을 기반으로 goal 상태를 갱신
  - working memory summary / next step / pending questions 저장
- WebSocket run path와 Telegram run path가 `runId`를 agent runtime context로 주입

### 2.4 Prompt injection

수정 파일:

- `src/ds_agent/agent/prompt_builder.py`

구현 내용:

- `PromptBuilder`가 매 turn 동적으로 store를 읽음
- system prompt에 다음 섹션을 자동 주입
  - `# Active Goal`
  - `# Working Memory`
- 즉 static prompt가 아니라 persisted runtime state 기반 prompt가 됨

---

## 3. Runtime Behavior

현재 구현 기준 lifecycle은 다음과 같다.

1. 첫 사용자 지시가 들어오면 goal이 생성된다.
2. run 시작 시 goal은 `in_progress`가 된다.
3. 응답이 질문/추가 입력 요청 성격이면 `blocked`가 된다.
4. 응답이 완료/산출물 완료 성격이면 `completed`가 된다.
5. 그 외에는 `in_progress`를 유지한다.

working memory는 매 turn마다 다음을 저장한다.

- active goal id
- last run id
- last user message
- current summary
- next step
- pending questions

---

## 4. Changed Files

새 파일:

- `src/ds_agent/domain/entities/goal.py`
- `src/ds_agent/domain/entities/working_memory.py`
- `src/ds_agent/runtime/goal_store.py`
- `src/ds_agent/runtime/working_memory.py`
- `tests/unit/infrastructure/test_goal_memory_runtime.py`

수정 파일:

- `src/ds_agent/domain/interfaces/session_state.py`
- `src/ds_agent/agent/core.py`
- `src/ds_agent/agent/factory.py`
- `src/ds_agent/agent/prompt_builder.py`
- `src/ds_agent/api/ws_handler.py`
- `src/ds_agent/gateway/telegram_runner.py`
- `tests/unit/application/test_prompt_builder.py`
- `tests/unit/application/test_agent_core.py`
- `tests/integration/test_runtime_wiring.py`

---

## 5. Verification

실행:

```bash
python -m pytest tests/unit/infrastructure/test_goal_memory_runtime.py \
  tests/unit/application/test_prompt_builder.py \
  tests/unit/application/test_agent_core.py \
  tests/unit/application/test_agent_factory.py \
  tests/integration/test_runtime_wiring.py \
  tests/unit/infrastructure/test_api.py \
  tests/e2e/test_ws_e2e.py \
  tests/unit/infrastructure/test_telegram_runner.py \
  -q -p no:cacheprovider \
  --basetemp="C:\Users\aquap\.codex\memories\pytest_phase03_run1"
```

결과:

- `155 passed`

추가 검증:

- `python -m ruff check ...` passed
- `python -m ruff format --check ...` passed
- `python -m mypy src/ds_agent/` failed: this environment has no `mypy` module installed

---

## 6. Notes

이번 phase에서 중요한 점은 `goal`이 planner를 대체하는 것이 아니라,
planner나 coordinator가 나중에 참조할 수 있는 persisted state substrate를 만든 것이라는 점이다.

또한 현재 goal 상태 전이는 휴리스틱 기반이다.
즉:

- 질문/추가 정보 요청 -> `blocked`
- 완료/산출물 완료 표현 -> `completed`
- 그 외 -> `in_progress`

이 휴리스틱은 Phase 05 이후 coordinator / reflection 계층에서 더 정교하게 바꾸는 것이 맞다.

---

## 7. Remaining Gap

아직 남아 있는 것은 다음이다.

- goal priority / multi-goal arbitration
- explicit planner output과 goal state 결합
- sensor/event에서 자동 goal 생성
- approval bus와 blocked goal의 직접 연동
- recovery 시 run ledger와 goal state의 강한 consistency 복구

즉 이번 phase는 `goal memory substrate`까지이며,
다음 phase에서 이 상태를 `approval/control surface`와 묶는 것이 자연스럽다.
