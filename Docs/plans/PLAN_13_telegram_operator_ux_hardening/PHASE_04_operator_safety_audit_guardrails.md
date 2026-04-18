# Phase 04: Operator Safety, Audit, and Recovery Guardrails

**Priority**: P1  
**Status**: Proposed  
**Depends On**: Phase 00-03

---

## 1. Goal

Raise the trust level of Telegram operations by making actions explicit,
traceable, and safe under stale-mobile conditions.

---

## 2. Current Gap

Telegram is already powerful enough to intervene in runtime behavior, but there
is still limited operator governance.

Missing today:

- explicit action audit trail
- stale action rejection outside inline-token scope
- stronger actor and chat confirmation
- structured recovery prompts after failed operator actions

---

## 3. Planned Implementation

Primary files:

- `src/ds_agent/gateway/telegram_runner.py`
- `src/ds_agent/channels/bundled/telegram/plugin.py`

New files likely needed:

- `src/ds_agent/runtime/operator_action_audit.py`

Implementation items:

- log Telegram operator actions with:
  - actor
  - chat
  - thread
  - target run or approval
  - outcome
  - timestamp
- reject unsafe actions when:
  - target state has changed
  - the action was issued in the wrong chat
  - the run or approval is no longer active
- improve user-facing recovery text:
  - what changed
  - what to inspect next
  - which fallback command to use

---

## 4. UX Rules

- failed actions must explain current state, not just say "invalid"
- audit logging is for accountability, not operator shaming
- safety checks should block wrong actions, not slow the normal path excessively
- every recovery hint should point to a concrete next command

---

## 5. Verification

Required:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_runtime_persistence.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/gateway/telegram_runner.py
```

Manual checks:

1. Attempt one stale action and confirm Telegram explains the mismatch
2. Review the audit record for one approval, one stop, and one resume action
3. Confirm normal-path actions are still fast from mobile

---

## 6. Exit Criteria

- Telegram operator actions are auditable
- stale or mismatched actions fail safely
- recovery guidance after action failure is clear and concrete

---

## Review: 실현 가능성 점검 코멘트 (2026-04-13)

### R1. 즉시 구현 가능 — 순수 백엔드 로직

감사 로깅, 상태 검증, 복구 안내 모두 백엔드에서 처리한다.
Telegram의 `from_user.id`와 `chat.id`는 이미 `InboundMessage.sender_id`와
`conversation_id`로 추적되고 있으므로 추가 Telegram API가 필요하지 않다.

### R2. Phase 01(인라인 버튼)의 action token과 연동

Phase 01에서 action token(TTL + idempotency)을 구현하면,
이 Phase의 "stale action rejection"이 자연스럽게 해결된다.
인라인 버튼의 token이 만료되면 callback_query 처리 시
`answerCallbackQuery(text="This action has expired. Use /approvals to check current state.")`
으로 응답하면 된다.

텍스트 커맨드에 대해서는 별도로 target state 검증 로직을 추가해야 한다.
예: `/approve abc123`이 이미 resolved된 approval을 대상으로 하면 거부.

### R3. 감사 로그와 RuntimeEventLog의 관계

`operator_action_audit.py`를 별도로 만들 수도 있지만,
기존 `RuntimeEventLog`에 `category="operator_action"` 이벤트를 기록하는 것이 더 간결하다.
이렇게 하면 PLAN_11의 Electron timeline과 PLAN_15의 event classification에서
operator action을 별도 처리 없이 소비할 수 있다.
