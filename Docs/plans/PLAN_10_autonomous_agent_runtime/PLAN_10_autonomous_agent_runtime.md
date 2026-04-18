# Plan 10: Autonomous Agent Runtime Roadmap

**Status**: Partially Implemented  
**Created**: 2026-04-12  
**Last Updated**: 2026-04-13  
**Dependencies**:

- `Docs/OPENCLAW_AUTONOMOUS_AGENT_ANALYSIS_2026-04-12.md`
- `Docs/OPENCLAW_DS_AGENT_GAP_ANALYSIS_2026-04-12.md`
- `Docs/AUTONOMOUS_AGENT_GAP_ANALYSIS_2026-04-12.md`
- `Docs/ARCHITECTURE.md`

---

## 1. 목적

현재 DS Agent를 `user-triggered foreground app`에서 `Gateway-first autonomous runtime`으로 전환하기 위한 구현 로드맵이다.

이 문서는 상위 인덱스이며, 실제 구현 착수는 각 phase 상세 계획 문서를 기준으로 진행한다.

현재 구현 상태 메모:

- Phase 00~08에 해당하는 기능 조각 대부분은 이미 구현되어 있다.
- 다만 현재 구현은 `auth / persisted store / approval / event surface` 공유까지는 도달했지만,
  `run / session / task`의 live registry는 아직 프로세스별 in-memory state다.
- 따라서 아래 목표 상태는 "이미 완전히 달성된 현재 상태"가 아니라,
  남은 gap을 포함한 target architecture로 읽어야 한다.

---

## 2. 목표 상태

1. Electron, Telegram, CLI가 동일한 runtime substrate를 공유한다.
2. 세션, 실행, 작업, 승인, 목표 상태가 프로세스 재시작 후에도 유지된다.
3. `DSAgent.run()`은 유지하되 그 위에 `goal/run/task/approval/sensor` 계층을 올린다.
4. Telegram은 단순 입력 채널이 아니라 원격 통제 채널이 된다.
5. Electron은 chat shell이 아니라 operator console이 된다.

---

## 3. 비목표

- OpenClaw 수준의 full multi-agent/subagent orchestration
- 완전한 ACP-style child session binding
- 모든 sensor의 1차 구현
- 기존 `DSAgent.run()` 전체 폐기
- 전면적인 frontend 재디자인

핵심 원칙:

> 기존 코어를 버리지 않고, 그 위에 자율형 운영 레이어를 쌓는다.

---

## 4. 구현 순서

1. Phase 00: Shared Runtime Context + Auth Parity
2. Phase 01: Persistent Session/Memory Substrate
3. Phase 02: Unified Session/Run/Task Substrate
4. Phase 03: Goal Store + Working Memory
5. Phase 04: Approval Bus + Telegram Control Surface
6. Phase 05: Autonomous Coordinator + Sensor Hub
7. Phase 06: Electron Operator Console
8. Phase 07: Reflection Quality + Startup Recovery
9. Phase 08: Policy Automation and Deferred Scope

MVP cut line은 **Phase 04 종료 시점**이다.

---

## 5. 마일스톤

### Milestone A: Runtime Parity

- Phase 00 완료
- 모든 surface에서 동일한 credential path 사용

### Milestone B: Controllable Autonomous Runtime

- Phase 01~04 완료
- persistent state + run/task + approval bus 동작
- surface 간 동일 runtime state를 조회/통제 가능

### Milestone C: Proactive Runtime

- Phase 05~07 완료
- sensor 기반 wake-up, goal continuity, startup recovery 동작

---

## 6. 권장 일정

| 구간 | 예상 |
|------|------|
| Phase 00~02 | 2.5 ~ 3주 |
| Phase 03~04 | 2주 |
| MVP 합계 | 약 5주 |
| Phase 05~07 | 추가 2 ~ 3주 |
| 전체 1차 | 약 7 ~ 8주 |

---

## 7. 품질 게이트

각 phase 종료 시 아래 검증을 통과해야 한다.

```bash
pytest tests/ -v
ruff check .
ruff format --check .
mypy src/ds_agent/
cd electron && npx tsc --noEmit
```

추가로 phase별 targeted tests:

- runtime/registry/store 관련 단위 테스트
- WS integration tests
- Telegram integration tests
- restart/recovery tests

---

## 8. 상세 계획 문서

- [PHASE_00_shared_runtime_auth_parity.md](./PHASE_00_shared_runtime_auth_parity.md)
- [PHASE_01_persistent_session_memory.md](./PHASE_01_persistent_session_memory.md)
- [PHASE_02_unified_session_run_task.md](./PHASE_02_unified_session_run_task.md)
- [PHASE_03_goal_store_working_memory.md](./PHASE_03_goal_store_working_memory.md)
- [PHASE_04_approval_bus_telegram_control.md](./PHASE_04_approval_bus_telegram_control.md)
- [PHASE_05_autonomous_coordinator_sensor_hub.md](./PHASE_05_autonomous_coordinator_sensor_hub.md)
- [PHASE_06_electron_operator_console.md](./PHASE_06_electron_operator_console.md)
- [PHASE_07_reflection_recovery.md](./PHASE_07_reflection_recovery.md)
- [PHASE_08_policy_automation.md](./PHASE_08_policy_automation.md)

---

## 9. 권장 파일 체계

```text
src/ds_agent/
├── runtime/
│   ├── provider_factory.py
│   ├── transcript_store.py
│   ├── checkpoint_store.py
│   ├── session_registry.py
│   ├── run_registry.py
│   ├── task_ledger.py
│   ├── goal_store.py
│   ├── working_memory.py
│   ├── approval_store.py
│   ├── coordinator.py
│   ├── sensor_hub.py
│   ├── startup_recovery.py
│   └── sensors/
│       ├── user_input.py
│       ├── file_watch.py
│       ├── schedule.py
│       ├── model_monitor.py
│       └── pipeline_health.py
└── domain/
    └── entities/
        ├── runtime_state.py
        └── goal.py
```

핵심 구분:

- `agent/`: 코어 reasoning/action loop
- `runtime/`: 자율형 운영 substrate
- `api/`, `gateway/`, `electron/`: presentation/control surface

---

## 10. 첫 착수 순서

먼저 아래 다섯 단계까지 끝내고 1차 데모를 만드는 것이 맞다.

1. Phase 00
2. Phase 01
3. Phase 02
4. Phase 03
5. Phase 04

즉:

> 먼저 공유되고, 추적되고, 멈추고, 승인되고, 재개되는 runtime을 만든 뒤  
> 그 위에 스스로 관찰하고 먼저 움직이는 autonomy를 올린다.
