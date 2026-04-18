# Phase 00: Chat Preferences and Subscription Surface

**Priority**: P0  
**Status**: Proposed  
**Depends On**: `PLAN_12` complete

---

## 1. Goal

Give each Telegram operator chat an explicit preference model instead of
hard-coded delivery behavior.

---

## 2. Current Gap

Telegram currently remembers delivery context, but not delivery intent.

Missing today:

- no per-chat severity filter
- no per-chat category subscription
- no approvals-only mode
- no digest preference
- no operator-visible summary of what that chat is subscribed to

Without this, Telegram is usable but not tunable.

---

## 3. Planned Implementation

Primary files:

- `src/ds_agent/gateway/telegram_runner.py`
- `src/ds_agent/channels/bundled/telegram/plugin.py`

New files likely needed:

- `src/ds_agent/runtime/operator_preferences_store.py`

Implementation items:

- add persistent per-chat preferences keyed by:
  - conversation id
  - optional thread id
- support preference fields such as:
  - enabled or muted
  - minimum severity
  - subscribed categories
  - digest mode
  - approvals-only flag
- add Telegram commands:
  - `/notify`
  - `/subscriptions`
  - `/severity`
  - `/digest`
- update alert routing so delivery decisions consult the preference store first

Preference design rule:

- defaults should preserve current behavior
- stored preferences should only narrow or structure delivery, not silently widen it

---

## 4. UX Rules

- the operator must be able to inspect preferences in one command
- every preference-changing command must echo the resulting saved state
- category names should be human-readable, not raw internal enum strings
- muted chats should still allow explicit pull commands like `/alerts`

---

## 5. Verification

Required:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/integration/test_telegram_plugin.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/gateway/telegram_runner.py
```

Manual checks:

1. Set one chat to approvals-only and confirm recovery or pressure alerts stop
2. Lower severity threshold and confirm info-level alerts appear
3. Open `/subscriptions` and confirm the saved state is readable from mobile

---

## 6. Exit Criteria

- Telegram has a real per-chat preference model
- alert routing respects those preferences
- the operator can see and change preferences without touching Electron

---

## Review: 실현 가능성 점검 코멘트 (2026-04-13)

### R1. 즉시 구현 가능 — 특별한 블로커 없음

이 Phase는 순수 백엔드 상태 관리이며, 추가 Telegram API 기능이 필요하지 않다.
모든 커맨드(`/notify`, `/subscriptions`, `/severity`, `/digest`)는 현재 아키텍처의
텍스트 커맨드 패턴으로 즉시 구현할 수 있다.

### R2. preference store 설계 시 고려사항

`operator_preferences_store.py`의 키 설계에서
PLAN_14(thread-aware identity)의 가능성을 미리 고려하면 좋다.

```python
# 키: conversation_id (현재)
# 추후 PLAN_14 적용 시: conversation_id + thread_id
# → PREREQ-3의 session ID 헬퍼와 동일한 키 형식을 사용하면 자연스럽게 호환
```

### R3. PLAN_15와의 관계

이 Phase의 per-chat preference(severity filter, category subscription)는
PLAN_15 Phase 01(event classification + subscription engine)의 **소비자(consumer)**가 된다.
preference store의 인터페이스를 설계할 때 PLAN_15의 classification 결과를
소비할 수 있는 구조로 만드는 것이 좋다.

예: `subscribed_categories: set[str]`와 `min_severity: str` 필드가
PLAN_15의 event classifier 출력과 매칭되어야 한다.
