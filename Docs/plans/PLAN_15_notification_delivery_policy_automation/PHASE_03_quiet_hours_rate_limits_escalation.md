# Phase 03: Quiet Hours, Rate Limits, and Escalation

**Priority**: P1  
**Status**: Proposed  
**Depends On**: Phase 00-02

---

## 1. Goal

Balance operator peace with incident urgency through explicit timing and
escalation policy.

---

## 2. Current Gap

Today Telegram has throttling, but not a mature notion of operator availability
or escalation.

Missing today:

- quiet-hours policy
- repeated-failure escalation
- severity-based bypass rules
- stronger rate-limit governance

---

## 3. Planned Implementation

Primary files:

- `src/ds_agent/gateway/telegram_runner.py`
- `src/ds_agent/runtime/runtime_event_log.py`

New files likely needed:

- `src/ds_agent/runtime/escalation_policy.py`
- `src/ds_agent/runtime/delivery_rate_limiter.py`

Implementation items:

- support quiet-hours windows
- let critical incidents bypass quiet-hours when policy says so
- escalate after:
  - repeated failures
  - prolonged blocked state
  - unacknowledged critical incidents
- unify ad hoc throttles into a policy-aware limiter
- define escalation as an application-level override of this system's own
  suppression rules, not as a guarantee of device-level push visibility

---

## 4. Runtime Rules

- quiet-hours must be explicit and inspectable
- escalation should be based on state and repetition, not just raw event count
- critical events must have a documented bypass path inside delivery policy
- rate limiting should reduce noise without masking incidents
- delivery policy should account for Telegram's per-chat and bulk broadcast limits

---

## 5. Verification

Required:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_runtime_persistence.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/runtime src/ds_agent/gateway/telegram_runner.py
```

Manual checks:

1. Enter a quiet-hours window and confirm only the intended events bypass it
2. Trigger repeated critical failures and confirm escalation behavior changes

---

## 6. Exit Criteria

- Telegram respects operator quiet-hours
- escalation behavior is explicit and policy-driven
- rate limiting is part of correctness rather than an incidental throttle

---

## Review: 실현 가능성 점검 코멘트 (2026-04-13)

### R1. 현재 코드에 Telegram 429 핸들링이 전무 — 기존 버그

이 Phase의 rate limit 작업 이전에, **현재 코드에서 이미 Telegram rate limit을 처리하지 않는다**는 점을 인지해야 한다.

현재 동작:
```python
# plugin.py send_text() — 429 에러 시
except Exception as e:
    logger.error("telegram_send_error", error=str(e))
    return DeliveryResult(success=False, error=str(e))
    # → 재시도 없음, retry_after 무시, 메시지 유실
```

이것은 이 Phase의 범위가 아니라 **PLAN_12 수준의 기존 결함**이다.
이 Phase 착수 전에 transport-level retry를 선행으로 구현하거나,
`python-telegram-bot`의 `Application` + `AIORateLimiter` 전환으로 해결해야 한다.

### R2. 두 가지 rate limit 레이어 — 이 Phase의 범위 명확화

| 레이어 | 목적 | 이 Phase의 범위 |
|--------|------|----------------|
| Tier 1: Transport | Telegram 429 방지 (1 msg/sec/chat, 20 msg/min/group, 30 msg/sec 전체) | **범위 밖** — 선행작업 또는 Application 전환으로 해결 |
| Tier 2: Policy | 알림 피로 방지 (quiet-hours, kind별 throttle, escalation) | **이 Phase의 핵심 범위** |

`delivery_rate_limiter.py`가 두 tier를 모두 포함할 수도 있지만,
Tier 1을 프레임워크(`AIORateLimiter`)에 위임하면 이 Phase는 Tier 2에만 집중할 수 있어 더 깔끔하다.

### R3. Telegram rate limit 구체적 수치

Telegram은 공식적으로 정확한 수치를 공개하지 않지만, 커뮤니티 합의:

| 대상 | 제한 | 초과 시 |
|------|------|--------|
| 1:1 채팅 | ~1 msg/sec (짧은 burst 허용) | HTTP 429 + `retry_after` |
| 그룹 | ~20 msg/min | HTTP 429 |
| 전체 (모든 chat 합산) | ~30 msg/sec | HTTP 429 |
| Paid broadcast (BotFather 설정) | 1000 msg/sec | 0.1 Stars/msg 과금 |

현재 `_poll_runtime_alerts()`가 `_operator_chats` 전체에 순차 전송하는데,
operator가 5명이고 chunk가 3개면 한 번에 15개 메시지를 연속 전송하게 된다.
이것은 burst 허용 범위를 초과할 가능성이 높다.

### R4. quiet-hours timezone 처리

quiet-hours를 구현할 때 **operator의 timezone**을 고려해야 한다.
서버 시간 기준으로 quiet-hours를 적용하면 다른 timezone의 operator에게 잘못 적용된다.

권장: per-chat preference에 timezone 필드를 포함하고 (PLAN_13 Phase 00과 연동),
quiet-hours 판단 시 해당 timezone으로 변환.
기본값은 서버 timezone 또는 UTC.

### R5. escalation bypass 시 rate limit과의 충돌

critical 이벤트가 quiet-hours를 bypass할 때,
Telegram transport rate limit까지 bypass할 수는 없다.
escalation 메시지가 rate limit에 걸리면 delivery가 지연될 수 있다.

권장: escalation 메시지는 **우선 큐**에 넣고, 일반 알림보다 먼저 전송하되
Telegram rate limit은 존중하는 방식으로 구현.
