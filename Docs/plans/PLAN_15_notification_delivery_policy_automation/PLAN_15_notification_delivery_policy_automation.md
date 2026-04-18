# Plan 15: Notification and Delivery Policy Automation

**Status**: Proposed  
**Created**: 2026-04-13  
**Scope**: Automate what gets delivered to operators, when it gets delivered, and how aggressively the system escalates

---

## 1. Objective

`PLAN_12` gave Telegram delivery capability.  
`PLAN_13` is the natural place for mobile UX hardening.  
`PLAN_15` addresses a different concern: delivery intelligence.

The target is a policy layer that decides:

- which events deserve live push
- which should be batched into digests
- which artifacts should be auto-delivered
- when noise suppression should override immediacy
- when escalation should cut through quiet behavior

This plan is about system judgment at the delivery layer.

Implementation note:

- Telegram supports the core primitives needed here: text delivery, file delivery,
  topic-aware routing, command surfaces, and application-level policy decisions.
- But "escalation" can only override this system's own suppression and digest
  rules; it cannot override a user's Telegram mute settings or OS-level
  do-not-disturb behavior.
- Delivery design also needs to respect Telegram cloud Bot API constraints such
  as file-send limits and broadcast/rate-limit behavior.
- For cross-process correctness, outcome and alert delivery should be driven by
  persisted runtime events and delivery-policy state, not only by local in-memory
  run registries.

---

## 2. Why This Plan Exists

Today Telegram delivery mostly follows static routing plus simple throttles.

That is enough for parity, but not enough for long-running autonomous operation:

- some important failures should escalate faster
- some benign churn should batch into digest
- some run outcomes should auto-send reports or plots
- some operators should receive less noise than others
- quiet-hours and urgency policy should be machine-enforced, not ad hoc

---

## 3. Phase Order

1. Phase 00: Delivery Policy Model and Persistence
2. Phase 01: Event Classification and Subscription Engine
3. Phase 02: Run Outcome and Artifact Auto-Delivery
4. Phase 03: Quiet Hours, Rate Limits, and Escalation
5. Phase 04: Digest Orchestration and Delivery Tuning

---

## 4. Milestones

### Milestone A: Policy Foundation

- Phase 00 complete
- delivery behavior is represented as explicit policy, not scattered conditionals

### Milestone B: Smarter Routing

- Phase 01 complete
- event categories, severity, and routing are policy-driven

### Milestone C: Outcome-Aware Delivery

- Phase 02 complete
- useful run outputs can be auto-delivered without operator polling

### Milestone D: Operational Trust

- Phase 03-04 complete
- quiet-hours, escalation, and digests behave predictably and transparently

---

## 5. Verification Baseline

Every phase should pass:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/integration/test_runtime_wiring.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_api.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/runtime src/ds_agent/gateway/telegram_runner.py
```

If a phase touches event persistence or batch scheduling, also run:

```bash
python -m pytest tests/unit/infrastructure/test_runtime_persistence.py -q -p no:cacheprovider
python -m pytest tests/e2e/test_ws_e2e.py -q -p no:cacheprovider
```

---

## 6. Phase Summary

| Phase | Goal | Priority | Status |
|------|------|----------|--------|
| 00 | define and persist delivery policy as first-class runtime state | P0 | proposed |
| 01 | route events using explicit classification and subscription rules | P0 | proposed |
| 02 | auto-deliver useful outcome artifacts and summaries | P1 | proposed |
| 03 | enforce quiet hours, escalation, and stronger rate limiting | P1 | proposed |
| 04 | orchestrate digests and tune delivery quality over time | P1 | proposed |

---

## 7. Notes

- `PLAN_15` should follow `PLAN_13` if the immediate need is Telegram operator ergonomics.
- If thread-level correctness becomes urgent, `PLAN_14` takes precedence.
- Delivery policy logic should remain reusable for future channels, not Telegram-only by design.
- Telegram-specific rate and payload limits should be treated as first-class
  product constraints, not incidental transport details.

---

## 8. Detailed Documents

- [PHASE_00_delivery_policy_model_persistence.md](./PHASE_00_delivery_policy_model_persistence.md)
- [PHASE_01_event_classification_subscription_engine.md](./PHASE_01_event_classification_subscription_engine.md)
- [PHASE_02_run_outcome_artifact_auto_delivery.md](./PHASE_02_run_outcome_artifact_auto_delivery.md)
- [PHASE_03_quiet_hours_rate_limits_escalation.md](./PHASE_03_quiet_hours_rate_limits_escalation.md)
- [PHASE_04_digest_orchestration_delivery_tuning.md](./PHASE_04_digest_orchestration_delivery_tuning.md)

---

## 9. Review: 실현 가능성 점검 코멘트 (2026-04-13)

### 9.1 현재 코드의 가장 큰 갭: Telegram 플랫폼 rate limit 미처리

현재 `TelegramPlugin.send_text()` (plugin.py:85~108)와 `send_file()`은
Telegram의 HTTP 429 응답을 **단순 exception catch → `DeliveryResult(success=False)`** 로 처리한다.
재시도(retry-after) 로직이 없다.

현재 `_poll_runtime_alerts()` (telegram_runner.py)는 여러 operator chat에 연속 전송하는데,
rate limit 대응 없이 반복하면 Telegram이 봇을 일시 차단할 수 있다.

**이 문제는 PLAN_15 이전에, 즉 현재 PLAN_12 코드에서도 이미 존재하는 production 리스크**이다.

### 9.2 두 가지 rate limit 레이어를 구분해야 한다

| 레이어 | 목적 | 제어 주체 |
|--------|------|----------|
| **Transport rate limit** | Telegram 429 방지 | Telegram 서버 (우리가 준수) |
| **Policy rate limit** | 알림 피로 방지 | 우리 시스템 (우리가 설계) |

계획서는 2번(policy)만 다루고 1번(transport)을 명시적으로 다루지 않는다.
Phase 03의 `delivery_rate_limiter.py`가 **두 레이어를 모두 포함**해야 한다:

```python
class DeliveryRateLimiter:
    """Two-tier rate limiter.

    Tier 1 (transport): Telegram API 제한 준수
      - per-chat: ~1 msg/sec
      - per-group: ~20 msg/min
      - global: ~30 msg/sec
      - 429 발생 시 retry_after 대기

    Tier 2 (policy): 알림 정책 준수
      - quiet-hours 차단
      - per-kind throttle
      - escalation override
    """
```

### 9.3 `python-telegram-bot` Application builder로 전환하면 Tier 1이 자동 해결

`python-telegram-bot` v22+의 `AIORateLimiter`는 Telegram 429를 프레임워크 수준에서 처리한다.
PLAN_13에서 callback_query 지원을 위해 `Application` builder 전환이 이미 권장되었으므로,
그 전환이 이루어지면 Tier 1 rate limiting은 자동으로 해결된다.

**권장 착수 순서**:
1. `Application` builder 전환 (PLAN_13 선행작업과 통합)
2. PLAN_15 Phase 00~01 (policy model, classification)
3. PLAN_15 Phase 02 (artifact auto-delivery)
4. PLAN_15 Phase 03 (policy rate limit만 집중)
5. PLAN_15 Phase 04 (digest)

### 9.4 Telegram 파일 전송 제한 — Phase 02에 명시 필요

| 제한 | 값 |
|------|---|
| Bot API 파일 업로드 최대 | **50MB** |
| 일반 파일 다운로드 최대 | **20MB** |
| 메시지당 caption ��대 | **1024자** |
| 메시지당 텍스트 최대 | **4096자** |

Phase 02의 artifact auto-delivery policy에서 파일 크기 체크를 **정책 평가 단계에서** 수행해야 한다.
50MB 초과 파일은 "summary + pull 안내" fallback으로 처리.

### 9.5 escalation의 한계 — 사용자 기대치 관리

계획서의 implementation note에 적혀 있지만 강조한다:
escalation은 **이 시스템의 suppression/digest 규칙만 override**할 수 있다.
사용자의 Telegram 앱 음소거, OS 방해금지 모드, 기기 꺼짐은 override할 수 없다.
이를 operator에게 명확히 전달해야 하며, escalation이 "반드시 전달 보장"으로 오해되지 않아야 한다.
