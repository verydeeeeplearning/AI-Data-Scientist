# Phase 02: Unified Session / Run / Task Substrate

**Priority**: P0  
**Milestone**: B  
**Status**: Completed  
**Implemented On**: 2026-04-12

---

## 1. Goal

surface별로 흩어져 있던 실행 상태를 `session`, `run`, `task` 단위로 분리하고,
WebSocket/Electron과 Telegram이 같은 runtime semantics로 추적할 수 있게 만드는 단계다.

핵심은 다음 4가지였다.

- session은 장기 대화 단위로 유지
- run은 한 번의 agent 실행 단위로 명시화
- task는 실제 background asyncio task 상태를 별도로 추적
- 기존 `chat.send` / `chat.abort`는 호환성을 유지하면서 새 `run.*` RPC 위에 얹기

---

## 2. Implemented

### 2.1 New runtime state entities

추가 파일:

- `src/ds_agent/domain/entities/runtime_state.py`
- `src/ds_agent/runtime/session_registry.py`
- `src/ds_agent/runtime/run_registry.py`
- `src/ds_agent/runtime/task_ledger.py`

구현 내용:

- `RuntimeSession`
- `RunState`
- `TaskState`
- `RuntimeStatus` (`running`, `succeeded`, `failed`, `cancelled`)
- session metadata registry
- run lifecycle registry
- background task ledger

### 2.2 WebSocket runtime promotion

수정 파일:

- `src/ds_agent/api/ws_handler.py`

구현 내용:

- `WsRpcHandler`의 handler-local `_running_task` 제거
- `AppState`가 `RuntimeSessionRegistry`, `RunRegistry`, `TaskLedger`를 소유
- `run.start`
- `run.wait`
- `run.abort`
- `run.list`
- 기존 `chat.send`는 `run.start` 호환 래퍼로 동작
- 기존 `chat.abort`는 `run.abort` 호환 래퍼로 동작
- 응답 payload에 `runId`, `status`, `taskId`, `resultPreview`, `costUsd` 포함
- `status.get`에 `activeRuns`, `activeTasks` 추가

### 2.3 Run lifecycle behavior

구현 내용:

- 같은 session에 새 run이 시작되면 기존 running run을 먼저 cancel + wait
- run 완료 시 `succeeded`
- 예외 시 `failed`
- abort 시 `cancelled`
- task ledger도 동일한 terminal state를 보존

### 2.4 Telegram runtime alignment

수정 파일:

- `src/ds_agent/gateway/telegram_runner.py`

구현 내용:

- Telegram runner도 `RunRegistry` + `TaskLedger`를 사용
- `/status`가 session/run 상태를 함께 보여줌
- `/stop`이 현재 대화의 active run을 실제 cancel
- 일반 메시지 처리도 tracked run으로 기록

### 2.5 Session registry typing cleanup

수정 파일:

- `src/ds_agent/api/agent_session_registry.py`

구현 내용:

- callback 타입을 `WsAgentCallbacks`에 고정하지 않고 `AgentCallbacks` protocol로 일반화

---

## 3. Changed Files

새 파일:

- `src/ds_agent/domain/entities/runtime_state.py`
- `src/ds_agent/runtime/session_registry.py`
- `src/ds_agent/runtime/run_registry.py`
- `src/ds_agent/runtime/task_ledger.py`
- `tests/unit/infrastructure/test_runtime_registries.py`

수정 파일:

- `src/ds_agent/api/ws_handler.py`
- `src/ds_agent/api/agent_session_registry.py`
- `src/ds_agent/gateway/telegram_runner.py`
- `tests/unit/infrastructure/test_api.py`
- `tests/e2e/test_ws_e2e.py`
- `tests/unit/infrastructure/test_telegram_runner.py`

---

## 4. Verification

실행:

```bash
python -m pytest tests/unit/infrastructure/test_runtime_registries.py \
  tests/unit/infrastructure/test_api.py \
  tests/e2e/test_ws_e2e.py \
  tests/unit/infrastructure/test_telegram_runner.py \
  tests/unit/infrastructure/test_agent_session_registry.py \
  tests/unit/application/test_session_manager.py \
  -q -p no:cacheprovider \
  --basetemp="C:\Users\aquap\.codex\memories\pytest_phase02_run1"
```

결과:

- `108 passed`

추가 검증:

- `python -m ruff check ...` passed
- `python -m ruff format --check ...` passed
- `python -m mypy src/ds_agent/` failed: this environment has no `mypy` module installed

---

## 5. Compatibility

유지된 호환성:

- 기존 `chat.send`
- 기존 `chat.abort`
- 기존 `chat.history`
- 기존 `status.get`

즉 Electron 프론트는 즉시 깨지지 않고,
필요한 클라이언트부터 점진적으로 `run.*` RPC를 사용할 수 있다.

---

## 6. Remaining Notes

이번 phase에서 해결된 것은 `runtime semantics` 통합이다.

아직 남아 있는 것은 다음과 같다.

- approval / ask_user를 `run` 단위와 결합하는 bus
- daemon restart 이후 run recovery
- goal / sensor / scheduler와 run substrate 연결
- Electron UI에서 `run.list`, `run.wait`, `run.abort`를 직접 활용하는 operator console

또한 현재 구현은 동일한 backend process 안에서의 공통 substrate를 전제로 한다.
별도 프로세스 간 완전한 shared runtime state는 이후 recovery/persistence 단계에서 더 강화해야 한다.
