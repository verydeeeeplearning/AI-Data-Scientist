# Plan 14: Thread-Aware Session Isolation

**Status**: Proposed  
**Created**: 2026-04-13  
**Scope**: Separate Telegram topics or threads into distinct runtime sessions and persistent state boundaries

---

## 1. Objective

`PLAN_12` preserved Telegram thread context in inbound and outbound delivery
paths. It did not make runtime identity or persisted state thread-aware.

This plan exists for the case where one Telegram chat uses multiple topics for
different projects or operational lanes and needs:

- isolated runs
- isolated approvals
- isolated checkpoints
- isolated goals and memory
- isolated recovery and resume behavior

This is the highest-risk Telegram follow-up because it changes identity and
persistence semantics, not just UX.

Implementation note:

- Current code already carries `thread_id` through message delivery where Telegram
  provides it.
- But live session ids, approval defaults, persisted session ids, and run lookup
  still collapse to `telegram:{chat}`.
- Alert delivery also remembers only the last-seen thread target per chat, which
  is not the same thing as true per-topic runtime isolation.
- This plan should only promise isolation where Telegram provides a real
  `message_thread_id`; direct chats and non-topic groups remain chat-scoped
  unless a separate identity contract explicitly broadens support.

---

## 2. Why This Plan Exists

Current Telegram state is still effectively keyed by `chat`, not `chat + topic`.

That means:

- multiple topics in the same chat can share one agent session accidentally
- checkpoint and goal state may blur across topics
- approval queues can look correct but still represent mixed conversational context
- recovery can revive the wrong operational lane

If Telegram is used heavily in topic-enabled groups, this becomes a correctness
problem, not just a UX inconvenience.

---

## 3. Phase Order

1. Phase 00: Identity Model and Compatibility Contract
2. Phase 01: Thread-Keyed Session and Run Isolation
3. Phase 02: Persistent State Namespace Migration
4. Phase 03: Recovery, Approval, and Coordinator Isolation
5. Phase 04: Surface Parity, Migration Rollout, and Hardening

---

## 4. Milestones

### Milestone A: Safe Identity Contract

- Phase 00 complete
- there is one canonical Telegram thread-aware session identity model

### Milestone B: Isolated Foreground Execution

- Phase 01 complete
- runs and live session behavior are isolated by topic

### Milestone C: Isolated Persistent Memory

- Phase 02 complete
- checkpoint, transcript, goal, working memory, and approvals no longer bleed across topics

### Milestone D: Isolated Autonomous Recovery

- Phase 03 complete
- resume, recovery, and approval routing are thread-correct

### Milestone E: Safe Rollout

- Phase 04 complete
- migration and observability are good enough for production enablement

---

## 5. Verification Baseline

Every phase should pass:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_api.py -q -p no:cacheprovider
python -m pytest tests/integration/test_runtime_wiring.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/gateway/telegram_runner.py \
  src/ds_agent/gateway/session_manager.py \
  src/ds_agent/runtime
```

If migration logic is introduced, also run:

```bash
python -m pytest tests/e2e/test_ws_e2e.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_runtime_persistence.py -q -p no:cacheprovider
```

---

## 6. Phase Summary

| Phase | Goal | Priority | Status |
|------|------|----------|--------|
| 00 | define canonical Telegram thread identity and compatibility rules | P0 | proposed |
| 01 | isolate session and run behavior by chat plus thread | P0 | proposed |
| 02 | migrate persisted stores to thread-aware namespaces safely | P0 | proposed |
| 03 | isolate recovery, approvals, and autonomous coordination logic | P1 | proposed |
| 04 | expose thread-aware state across surfaces and roll out safely | P1 | proposed |

---

## 7. Notes

- This plan should start only if Telegram topics are becoming a real operational boundary.
- If the need is mostly notification quality, `PLAN_13` and `PLAN_15` should come first.
- Rollout should likely use compatibility flags or dual-read logic before hard cutover.

---

## 8. Detailed Documents

- [PHASE_00_identity_model_compatibility_contract.md](./PHASE_00_identity_model_compatibility_contract.md)
- [PHASE_01_thread_keyed_session_run_isolation.md](./PHASE_01_thread_keyed_session_run_isolation.md)
- [PHASE_02_persistent_state_namespace_migration.md](./PHASE_02_persistent_state_namespace_migration.md)
- [PHASE_03_recovery_approval_coordinator_isolation.md](./PHASE_03_recovery_approval_coordinator_isolation.md)
- [PHASE_04_surface_parity_migration_hardening.md](./PHASE_04_surface_parity_migration_hardening.md)

---

## 9. Review: 실현 가능성 점검 코멘트 (2026-04-13)

### 9.1 Telegram Forum Topics의 실제 동작 조건

`message_thread_id`가 존재하는 경우는 **슈퍼그룹에서 포럼 모드를 활성화한 경우에 한정**된다.

| 채팅 유형 | `message_thread_id` | 포럼 토픽 지원 |
|----------|---------------------|---------------|
| 1:1 DM (가장 흔한 봇 사용 패턴) | **항상 null** | **미지원** |
| 일반 그룹 | **항상 null** | **미지원** |
| 슈퍼그룹 (포럼 비활성화) | **항상 null** | **미지원** |
| **슈퍼그룹 + 포럼 활성화** | ✅ 존재 | ✅ 지원 |

**의미**: 이 계획의 ROI는 Telegram 포럼 그룹을 **실제 운영 채널로 사용하는 경우에만** 정당화된다.
1:1 DM 중심 운영이라면 이 계획의 우선순위를 낮추고 PLAN_13, PLAN_15를 먼저 진행해야 한다.

Phase 00의 compatibility contract에서 이 분기를 명확히 정의해야 하며,
DM/비포럼 그룹에서는 기존 chat-scoped 동작을 **그대로 유지**하는 것이 정답이다.

### 9.2 Session ID 하드코딩 — 변경 범위가 광범위

현재 `telegram_runner.py`에서 `f"telegram:{conversation_id}"`가 **15곳 이상**에서 inline으로 사용된다:

```
_handle_message()        — pending approval lookup
_execute_agent_turn()    — session ensure, run create
_format_status()         — session_id 생성
_format_runs()           — session scoping
_format_approvals()      — session scoping
_format_approval_detail() — approval resolution
_format_session()        — checkpoint/goal/memory lookup
_format_history()        — transcript lookup
_handle_resume_command() — checkpoint restore
_handle_stop_command()   — run lookup (간접)
_handle_approval_command() — pending approval lookup
_format_run_detail()     — run lookup (간접)
```

**권장**: Phase 00에서 `_session_id(conversation_id, thread_id)` 헬퍼를 먼저 추출하고,
모든 하드코딩을 이 헬퍼로 교체한 후에 Phase 01을 진행해야 한다.
이 헬퍼 추출은 이 계획의 **가장 중요한 첫 번째 작업**이다.

`SessionManager.get_or_create()` (session_manager.py:43)도 현재:
```python
key = f"{channel_id}:{conversation_id}"  # thread_id 미포함
```
이것도 함께 변경해야 한다.

### 9.3 마이그레이션 전략 — dual-read 필수

5개 JSON 스토어의 키가 모두 영향받는다:
- `JsonTranscriptStore` — 세션별 JSONL 파일명
- `JsonCheckpointStore` — 세션별 JSON 파일명
- `JsonApprovalStore` — `session_id` 필드 기반 조회
- `JsonGoalStore` — `session_id` 기반 조회
- `JsonWorkingMemoryStore` — `session_id` 기반 조회

기존 `telegram:12345` 데이터를 새 형식 `telegram:12345:67890`으로 마이그레이션할 때,
**dual-read** (새 키 먼저 조회 → 없으면 legacy 키 fallback)가 가장 안전하다.

eager migration(일괄 변환)은 **실행 중인 세션과 충돌**할 위험이 있으므로 피하는 것이 좋다.

### 9.4 이 계획 착수 시점에 대한 의견

계획서 Notes에도 적혀 있지만 강조한다:

> **1:1 DM 중심 운영이라면 이 계획은 불필요하다.**
> 포럼 그룹을 운영에 실제로 쓰기 시작하는 시점에 착수하는 것이 맞다.
> 그 전에는 PLAN_13(UX 개선)과 PLAN_15(알림 지능화)가 체감 효과가 훨씬 크다.
