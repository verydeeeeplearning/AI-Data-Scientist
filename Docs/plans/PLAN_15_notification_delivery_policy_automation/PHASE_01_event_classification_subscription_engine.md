# Phase 01: Event Classification and Subscription Engine

**Priority**: P0  
**Status**: Proposed  
**Depends On**: Phase 00

---

## 1. Goal

Route runtime events using explicit policy evaluation instead of only static
lists and coarse throttles.

---

## 2. Current Gap

The current runtime event flow is useful but relatively simple:

- static push-worthy event kinds
- basic throttles
- limited category semantics

That is not enough for nuanced operator routing.

---

## 3. Planned Implementation

Primary files:

- `src/ds_agent/runtime/runtime_event_log.py`
- `src/ds_agent/gateway/telegram_runner.py`

New files likely needed:

- `src/ds_agent/runtime/event_classifier.py`
- `src/ds_agent/runtime/subscription_engine.py`

Implementation items:

- classify events by:
  - severity
  - category
  - urgency
  - actionability
  - suppressibility
- evaluate subscriptions and policy filters before push
- support routing decisions such as:
  - live push
  - digest only
  - suppress
  - escalate

---

## 4. Runtime Rules

- event classification should be deterministic
- policy evaluation should be explainable in logs or inspection output
- suppression should never make critical failures disappear silently

---

## 5. Verification

Required:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_runtime_persistence.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/runtime src/ds_agent/gateway/telegram_runner.py
```

Manual checks:

1. Trigger representative info, warning, and critical events and inspect routing results
2. Confirm the routing explanation for one suppressed and one escalated event

---

## 6. Exit Criteria

- runtime events are classified and routed by explicit policy
- suppression and escalation are traceable
- delivery routing is no longer just a hard-coded event allowlist

---

## Review: 실현 가능성 점검 코멘트 (2026-04-13)

### R1. 즉시 구현 가능

순수 백엔드 분류/라우팅 로직. Telegram API 추가 불필요.

### R2. 현재 _PUSH_ALERT_KINDS 하드코딩 교체

현재 `telegram_runner.py`의 `_PUSH_ALERT_KINDS`는 frozenset으로 하드코딩되어 있다:
```python
_PUSH_ALERT_KINDS = frozenset({
    "recovery.awaiting_approval",
    "recovery.resume_recommended",
    "pipeline.health.degraded",
    ...
})
```

이 Phase에서 `event_classifier.py`가 이 역할을 대체해야 한다.
기존 하드코딩을 classifier의 기본값으로 옮기고,
`_process_runtime_alerts_once()`가 classifier를 사용하도록 변경.

### R3. PLAN_13 Phase 00의 per-chat subscription과 결합

분류 결과 = (category, severity, urgency, actionability, suppressibility)
subscription 매칭 = per-chat preference의 (subscribed_categories, min_severity)

```python
def should_deliver(event: ClassifiedEvent, pref: ChatPreference) -> DeliveryDecision:
    if event.severity < pref.min_severity:
        return DeliveryDecision.SUPPRESS
    if event.category not in pref.subscribed_categories:
        return DeliveryDecision.DIGEST_ONLY
    if pref.muted_until and now() < pref.muted_until:
        if event.urgency != "critical":
            return DeliveryDecision.SUPPRESS
    return DeliveryDecision.LIVE_PUSH
```

이 결합 로직이 subscription engine의 핵심이다.
