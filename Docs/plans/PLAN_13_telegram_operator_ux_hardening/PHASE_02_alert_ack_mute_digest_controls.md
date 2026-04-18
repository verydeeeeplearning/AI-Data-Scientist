# Phase 02: Alert Acknowledge, Mute, and Digest Controls

**Priority**: P1  
**Status**: Proposed  
**Depends On**: Phase 00-01

---

## 1. Goal

Turn Telegram alert handling into a manageable workflow instead of a passive
firehose.

---

## 2. Current Gap

Telegram can push alerts and show digests, but it still lacks operator control
over alert lifecycle.

Missing today:

- alert acknowledge
- short mute windows
- temporary snooze
- per-chat digest interval
- distinction between "seen" and "unresolved"

---

## 3. Planned Implementation

Primary files:

- `src/ds_agent/runtime/runtime_event_log.py`
- `src/ds_agent/gateway/telegram_runner.py`

New files likely needed:

- `src/ds_agent/runtime/operator_alert_state_store.py`

Implementation items:

- track chat-level alert state:
  - acknowledged event ids
  - mute-until timestamp
  - digest cadence
  - last digest sent
- add commands such as:
  - `/ack`
  - `/mute 30m`
  - `/unmute`
  - `/digest 15m`
  - `/digest now`
- make live pushes consult:
  - mute window
  - severity overrides
  - acknowledgement status
- preserve manual visibility:
  - muted alerts still remain queryable
  - digests summarize what was suppressed

---

## 4. UX Rules

- mute and snooze commands must always be time-bounded by default
- acknowledged alerts should remain recoverable in history
- digests should summarize counts first, then list top actionable items
- critical incidents may intentionally bypass soft mute if policy says so

---

## 5. Verification

Required:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_runtime_persistence.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/gateway/telegram_runner.py \
  src/ds_agent/runtime/runtime_event_log.py
```

Manual checks:

1. Mute a chat, trigger alerts, and confirm live pushes stop temporarily
2. Force `/digest now` and confirm suppressed alerts are summarized
3. Acknowledge an alert and confirm the same event is not re-pushed immediately

---

## 6. Exit Criteria

- Telegram alerts have a lifecycle beyond passive delivery
- operators can acknowledge or mute noise without losing history
- digest behavior is explicit and operator-controlled

---

## Review: 실현 가능성 점검 코멘트 (2026-04-13)

### R1. 텍스트 커맨드만으로 즉시 구현 가능

`/ack`, `/mute 30m`, `/unmute`, `/digest 15m`, `/digest now` 모두
기존 텍스트 커맨드 패턴으로 구현 가능하다. Phase 01(인라인 버튼)이 없어도 동작한다.

다만, Phase 01이 완료되면 알림 메시지에 `[Ack]` `[Mute 30m]` 인라인 버튼을 첨부하여
한 탭으로 처리할 수 있으므로, Phase 01 이후 UX를 점진 개선하는 것이 이상적이다.

### R2. mute-until timestamp와 timezone

`/mute 30m`은 서버 시간 기준 `now + 30min`을 저장하면 되므로 timezone 문제가 없다.
그러나 `/mute until 22:00` 같은 절대 시간 지정이 추가된다면
Phase 00의 preference에 timezone 정보가 필요하다.
1차 구현에서는 상대 시간(`/mute 30m`, `/mute 2h`)만 지원하는 것을 권장한다.

### R3. critical 이벤트의 mute bypass

계획서에 "critical incidents may intentionally bypass soft mute"로 언급되어 있다.
이 bypass 규칙은 PLAN_15 Phase 03(escalation policy)과 공유되어야 하므로,
bypass 판단을 이 Phase에서 하드코딩하지 말고 policy interface로 분리하는 것이 좋다.
