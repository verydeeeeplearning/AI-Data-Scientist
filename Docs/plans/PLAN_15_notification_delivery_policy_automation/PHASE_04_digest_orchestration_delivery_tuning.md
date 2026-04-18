# Phase 04: Digest Orchestration and Delivery Tuning

**Priority**: P1  
**Status**: Proposed  
**Depends On**: Phase 00-03

---

## 1. Goal

Make digest delivery a first-class operational product rather than a simple
"recent alerts" dump.

---

## 2. Current Gap

Current digest behavior is reactive and command-driven.

Missing today:

- scheduled digests
- digest prioritization
- deduped recurring issue summaries
- delivery quality feedback loops

---

## 3. Planned Implementation

Primary files:

- `src/ds_agent/gateway/telegram_runner.py`
- `src/ds_agent/runtime/runtime_event_log.py`

Potentially needed:

- `src/ds_agent/runtime/digest_scheduler.py`
- `src/ds_agent/runtime/digest_builder.py`

Implementation items:

- define digest cadences such as:
  - hourly
  - morning
  - end-of-day
  - on-demand
- build digest sections by priority:
  - unresolved incidents
  - recent recoveries
  - suppressed noise summary
  - suggested next actions
- optionally track operator feedback or open rate proxies for tuning

---

## 4. Delivery Rules

- digests should summarize decisions, not just list raw events
- repeated incidents should roll up rather than spam
- a digest should tell the operator what matters now
- tuning should be conservative and auditable
- digest cadence must still respect Telegram send-rate constraints and avoid bursty catch-up spam

---

## 5. Verification

Required:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_runtime_persistence.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/runtime src/ds_agent/gateway/telegram_runner.py
```

Manual checks:

1. Trigger several heterogeneous events and inspect one digest output
2. Confirm the digest highlights unresolved incidents before low-priority churn
3. Confirm repeated events are summarized, not repeated verbatim

---

## 6. Exit Criteria

- digests are scheduled and policy-aware
- digest content is prioritized and deduplicated
- operator-facing delivery quality is measurably better than raw alert history

---

## Review: 실현 가능성 점검 코멘트 (2026-04-13)

### R1. 구현 가능 — 기존 패턴 확장

현재 `_poll_runtime_alerts()` 백그라운드 태스크와 동일한 패턴으로
`_poll_digests()` 태스크를 추가하면 된다.

### R2. digest 메시지 길이와 chunking

digest는 여러 이벤트를 요약하므로 4096자를 초과할 수 있다.
기존 `chunk_text()`가 이를 처리하지만, digest가 여러 메시지로 분할되면
모바일에서 하나의 "요약"으로 인식되기 어렵다.

권장: digest를 **4096자 이내로 설계**하는 것을 우선. 이벤트가 많으면:
- unresolved incidents: 상위 3건 상세 + "외 N건"
- recoveries: 건수만
- suppressed: 건수만 + 가장 빈번한 카테고리

### R3. "morning" / "end-of-day" cadence의 timezone

Phase 03의 quiet-hours와 동일한 문제.
per-chat preference에 timezone이 포함되어야 "morning 09:00" digest가 의미를 갖는다.
기본값은 UTC로 하되, operator가 설정 가능해야 한다.

### R4. 기존 `/alerts` 커맨드와의 관계

현재 `/alerts [n]`은 최근 이벤트를 raw로 나열한다.
digest가 도입되면 `/alerts`는 "raw 이벤트 목록"으로,
digest는 "curated 요약"으로 역할이 분리되어야 한다.
두 가지가 혼동되지 않도록 UX에서 명확히 구분해야 한다.
