# Phase 01: Thread-Keyed Session and Run Isolation

**Priority**: P0  
**Status**: Proposed  
**Depends On**: Phase 00

---

## 1. Goal

Make live Telegram execution state isolated per topic or thread, not just per
chat.

---

## 2. Current Gap

Telegram delivery can already preserve thread context, but session creation is
still chat-scoped.

That means:

- one topic can inherit another topic's live agent
- active run lookup is chat-wide
- stop and resume semantics can target the wrong operational lane

---

## 3. Planned Implementation

Primary files:

- `src/ds_agent/gateway/session_manager.py`
- `src/ds_agent/gateway/telegram_runner.py`
- `src/ds_agent/runtime/run_registry.py`

Implementation items:

- change Telegram session keys to use the canonical thread-aware identity
- make `run.start`, `run.abort`, `run.wait`, and `run.list` reflect that identity
- ensure stop, resume, and approval lookup default to the correct thread lane
- make delivery-target tracking complement session identity instead of papering over it

Scope boundary:

- this phase is about live runtime isolation
- it does not yet migrate persisted legacy stores

---

## 4. Runtime Rules

- one Telegram topic must map to one runtime session lane
- no command should default across sibling topics unless explicitly requested
- run and task inspection should expose thread identity where relevant

---

## 5. Verification

Required:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/integration/test_runtime_wiring.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/gateway/session_manager.py src/ds_agent/gateway/telegram_runner.py
```

Manual checks:

1. Start two Telegram topic sessions in the same chat and confirm independent runs
2. Stop one topic and confirm the sibling topic keeps running

---

## 6. Exit Criteria

- Telegram live execution is isolated by topic
- run control commands no longer bleed across topics
- delivery context and runtime identity align

---

## Review: 실현 가능성 점검 코멘트 (2026-04-13)

### R1. `SessionManager` 키 변경 — 가장 깊은 변경점

현재 `session_manager.py:43`:
```python
key = f"{channel_id}:{conversation_id}"
```

이것이 **모든 live 세션의 식별자**를 결정한다. thread_id를 포함하면:
```python
key = f"{channel_id}:{conversation_id}:{thread_id or ''}"
# 또는 Phase 00의 channel_identity 헬퍼 사용
```

**주의**: `get_or_create()` 시그니처에 `thread_id` 파라미터를 추가해야 하며,
이는 `TelegramGatewayRunner._execute_agent_turn()`의 호출부에 영향을 준다.

### R2. 동시 실행 격리 검증

두 토픽에서 동시에 에이전트를 실행할 때:
- 각 토픽이 **별도의 DSAgent 인스턴스**를 받는지
- 한 토픽의 `/stop`이 다른 토픽의 run을 멈추지 않는지
- `RunRegistry.latest_for_session()`이 올바른 session_id로 조회하는지

이 세 가지를 통합 테스트로 검증해야 한다.
현재 `test_telegram_runner.py`는 단일 채팅 시나리오만 다루므로 **멀티토픽 테스트 케이스를 추가**해야 한다.

### R3. 기존 세션 정리 문제

`SessionManager.cleanup_idle()`은 세션 키 기반으로 동작한다.
키 형식이 바뀌면, 이전 형식으로 생성된 세션이 cleanup에서 제외될 수 ��다.
마이그레이션 윈도우 동안 양쪽 형식의 세션이 공존한다는 점을 고려해야 한다.
