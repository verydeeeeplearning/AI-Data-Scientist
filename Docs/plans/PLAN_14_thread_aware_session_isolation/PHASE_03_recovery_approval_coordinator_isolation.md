# Phase 03: Recovery, Approval, and Coordinator Isolation

**Priority**: P1  
**Status**: Proposed  
**Depends On**: Phase 00-02

---

## 1. Goal

Make autonomous and recovery flows respect Telegram thread boundaries just as
strictly as foreground message handling.

---

## 2. Current Gap

Recovery and coordination logic currently assume the existing session identity
model.

After thread-aware persistence is introduced, the remaining risks are:

- wrong approval inbox resurfacing in the wrong topic
- recovery prompts reviving the wrong lane
- autonomous coordinator suppressing or dispatching work at chat scope instead of topic scope

---

## 3. Planned Implementation

Primary files:

- `src/ds_agent/runtime/coordinator.py`
- `src/ds_agent/runtime/startup_recovery.py`
- `src/ds_agent/runtime/approval_store.py`
- `src/ds_agent/gateway/daemon.py`
- `src/ds_agent/gateway/telegram_runner.py`

Implementation items:

- make recovery and resume path thread-aware
- make approval lookup and pending-queue semantics thread-aware by default
- ensure policy suppression and dispatch tracking use the correct thread identity
- ensure alert routing can name the correct thread context

---

## 4. Runtime Rules

- autonomous recovery must not revive a sibling topic accidentally
- approval defaults should resolve in the current topic first
- alert and recovery text must reveal enough identity context for the operator to trust the route

---

## 5. Verification

Required:

```bash
python -m pytest tests/integration/test_runtime_wiring.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/runtime/coordinator.py \
  src/ds_agent/runtime/startup_recovery.py \
  src/ds_agent/gateway/telegram_runner.py
```

Manual checks:

1. Trigger recovery in one topic and confirm another topic remains untouched
2. Create pending approvals in two topics and confirm Telegram defaults to the correct one

---

## 6. Exit Criteria

- recovery and approvals are isolated by topic
- autonomous coordination no longer reasons at the wrong Telegram scope
- operator trust in recovery routing is restored

---

## Review: 실현 가능성 점검 코멘트 (2026-04-13)

### R1. Phase 00~02 완료 전제 시 구현 가능

이 Phase는 Phase 00의 identity 헬퍼와 Phase 02의 namespace migration이 완료된 후의
논리적 확장이다. Telegram API 추가 의존 없음.

### R2. 알림 라우팅의 thread context 전달

`_poll_runtime_alerts()`가 recovery 이벤트를 push할 때,
어떤 thread(토픽)에서 복구가 필요한지를 알림 메시지에 **명시**해야 한다.
현재는 `_delivery_target_for_conversation()`이 마지막으로 본 thread를 반환하는데,
recovery는 특정 토픽의 세션에 대한 것이므로 **이벤트 자체에 thread context가 있어야** 한다.

권장: `RuntimeEventRecord`의 `metadata`에 `thread_id` 필드를 포함하고,
알림 전송 시 해당 thread로 라우팅.
