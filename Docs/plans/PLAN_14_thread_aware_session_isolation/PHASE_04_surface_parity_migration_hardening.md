# Phase 04: Surface Parity, Migration Rollout, and Hardening

**Priority**: P1  
**Status**: Proposed  
**Depends On**: Phase 00-03

---

## 1. Goal

Expose thread-aware state cleanly across operator surfaces and roll out the new
model without hidden regressions.

---

## 2. Current Gap

Even after backend correctness work, operators still need visibility and safe
rollout controls.

Missing pieces include:

- explicit thread labels in summaries and timelines
- migration observability
- rollback strategy
- documented operational procedure

---

## 3. Planned Implementation

Primary files:

- `src/ds_agent/api/ws_handler.py`
- `electron/src/renderer/`
- `src/ds_agent/gateway/telegram_runner.py`

Potentially needed:

- migration metrics or status reporting in `src/ds_agent/runtime/`

Implementation items:

- expose thread labels in runtime session and run summaries
- update Electron runtime surfaces if they display Telegram state
- add migration status or counters if rollout uses dual-read or backfill
- document enablement sequence and rollback conditions

---

## 4. Rollout Rules

- rollout should be staged, not instant
- observability must land before hard cutover
- if rollback is supported, it must be documented before migration starts
- operator-visible labels must reduce confusion, not expose implementation noise

---

## 5. Verification

Required:

```bash
python -m pytest tests/unit/infrastructure/test_api.py -q -p no:cacheprovider
python -m pytest tests/e2e/test_ws_e2e.py -q -p no:cacheprovider
cd electron && npm run typecheck
```

Manual checks:

1. Inspect session and run summaries and confirm thread identity is visible
2. Verify migration status is observable before enabling the new mode broadly

---

## 6. Exit Criteria

- thread-aware Telegram state is visible and understandable across surfaces
- rollout risk is bounded by documented migration and rollback procedures
- the new identity model is operable, not just technically correct

---

## Review: 실현 가능성 점검 코멘트 (2026-04-13)

### R1. Electron 측 영향 — 최소

Electron의 runtime 패널(SessionsPanel, RunsPanel 등)은 이미 session_id를 문자열로 표시한다.
`telegram:12345:67890` 형식이 되면 자동으로 표시되지만,
`_display_session()` 포맷터가 thread 부분을 사람이 읽기 좋게 보여줘야 한다.
예: `chat 12345 / topic 67890`

### R2. 롤백 전략

dual-read 전략(Phase 02)을 쓰면 롤백은 비교적 간단하다:
- identity 헬퍼의 `thread_id` 파라미터를 항상 `None`으로 고정하면
  기존 chat-scoped 동작으로 즉시 복원된다.
- 새 형식으로 저장된 데이터는 남지만, 해당 포럼 그룹을 다시 사용할 때까지 무해하다.

### R3. feature flag 권장

이 계획 전체를 config flag 하나로 켜고 끌 수 있어야 한다:
```yaml
gateway:
  telegram_thread_isolation_enabled: false  # true로 전환 시 활성화
```
false일 때는 PLAN_12의 기존 동작을 유지하고,
true일 때만 thread-aware identity와 namespace를 사용한다.
