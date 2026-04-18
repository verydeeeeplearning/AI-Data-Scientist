# Phase 00: Delivery Policy Model and Persistence

**Priority**: P0  
**Status**: Proposed  
**Depends On**: `PLAN_12` complete

---

## 1. Goal

Move delivery behavior from scattered routing conditionals into an explicit,
persistent policy model.

---

## 2. Current Gap

Current delivery behavior is spread across runner logic, throttle rules, and
implicit defaults.

Missing today:

- one policy schema for live push, digest, mute, escalation, and artifact send
- persisted policy state
- operator-visible policy inspection and modification path

---

## 3. Planned Implementation

Primary files:

- `src/ds_agent/gateway/telegram_runner.py`
- `src/ds_agent/runtime/runtime_event_log.py`

New files likely needed:

- `src/ds_agent/runtime/delivery_policy_store.py`
- `src/ds_agent/runtime/delivery_policy_engine.py`

Implementation items:

- define policy objects for:
  - live push
  - digest
  - mute
  - escalation
  - artifact delivery
- persist those objects per operator target or policy scope
- expose inspection commands or RPC hooks for future surfaces

---

## 4. Runtime Rules

- delivery policy must be explicit and serializable
- one engine should evaluate policy; callers should not fork logic casually
- defaults should preserve current behavior until policy is explicitly changed

---

## 5. Verification

Required:

```bash
python -m pytest tests/unit/infrastructure/test_runtime_persistence.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/runtime src/ds_agent/gateway/telegram_runner.py
```

Manual checks:

1. Persist one policy override and verify it survives restart
2. Confirm the absence of a saved policy still preserves current delivery defaults

---

## 6. Exit Criteria

- delivery policy is first-class runtime state
- policy survives restart
- later delivery phases can build on one consistent model

---

## Review: 실현 가능성 점검 코멘트 (2026-04-13)

### R1. 즉시 구현 가능

순수 백엔드 상태 모델. 기존 `JsonPolicyStore` 패턴을 따라
`delivery_policy_store.py`를 만들면 된다.

### R2. PLAN_13 Phase 00과의 인터페이스 설계

PLAN_13 Phase 00에서 per-chat preference를 만들고, 이 Phase에서 delivery policy를 만든다.
두 모델의 관계를 명확히 해야 한다:

- **Per-chat preference** (PLAN_13): 개별 operator chat의 구독 의사 (무엇을 받고 싶은가)
- **Delivery policy** (PLAN_15): 시스템 수준의 전달 규칙 (무엇을 어떻게 보내는가)

최종 전달 결정 = `policy.evaluate(event) ∩ preference.accepts(event)`.
이 교차점이 Phase 01의 subscription engine에서 구현된다.

### R3. policy 스키마 설계 시 Telegram 제한 포함

delivery policy에 아래 Telegram 하드 제한을 **기본 상수**로 포함하는 것을 권장:

```python
@dataclass
class DeliveryPolicyDefaults:
    max_auto_send_file_size_bytes: int = 50 * 1024 * 1024  # Telegram 50MB
    max_auto_send_artifacts_per_run: int = 3
    min_push_interval_seconds: float = 1.0  # Telegram ~1 msg/sec/chat
    max_group_messages_per_minute: int = 20  # Telegram 그룹 제한
```
