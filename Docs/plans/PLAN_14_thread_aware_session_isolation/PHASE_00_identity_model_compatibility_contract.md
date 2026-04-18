# Phase 00: Identity Model and Compatibility Contract

**Priority**: P0  
**Status**: Proposed  
**Depends On**: `PLAN_12` complete

---

## 1. Goal

Define one canonical thread-aware Telegram identity model before touching
runtime behavior or persistence.

---

## 2. Current Gap

Today the codebase uses chat-scoped identity in multiple places.

Risks:

- ad hoc thread handling added in only some paths
- inconsistent key composition between runs, approvals, and memory
- no migration contract for pre-existing `telegram:{chat}` data

If this phase is skipped, later phases are likely to create subtle data drift.

---

## 3. Planned Implementation

Primary files:

- `src/ds_agent/gateway/telegram_runner.py`
- `src/ds_agent/gateway/session_manager.py`

Likely new shared helpers:

- `src/ds_agent/runtime/channel_identity.py`

Implementation items:

- define canonical identity components:
  - channel id
  - conversation id
  - optional thread id
- define canonical string format for persisted session ids
- define compatibility rules for:
  - direct chats
  - non-topic group chats
  - topic-enabled group chats
- state explicitly whether initial support is limited to Telegram
  `message_thread_id`-backed contexts
- document dual-read or migration policy from legacy `telegram:{chat}` keys

---

## 4. Runtime Rules

- there must be exactly one canonical formatter and parser
- no caller should manually concatenate thread ids into session ids
- no hidden fallback should silently merge thread-scoped state back into chat-scoped state
- compatibility behavior must be explicit and testable
- callers must not invent synthetic topic ids where Telegram did not actually
  provide a thread identity

---

## 5. Verification

Required:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/gateway/telegram_runner.py src/ds_agent/gateway/session_manager.py
```

Manual checks:

1. Verify one direct chat and one topic-enabled chat map to the intended identity format
2. Verify legacy chat-only identifiers have a documented compatibility path

---

## 6. Exit Criteria

- Telegram thread identity is defined once and reused everywhere
- compatibility behavior for old session ids is explicit
- later phases can build on a stable contract

---

## Review: 실현 가능성 점검 코멘트 (2026-04-13)

### R1. 권장 identity 포맷과 호환성 규칙

```python
# src/ds_agent/runtime/channel_identity.py

def telegram_session_id(conversation_id: str, thread_id: str | None) -> str:
    """Canonical Telegram session identity.

    Rules:
    - DM (thread_id=None):          "telegram:{chat_id}"
    - 비포럼 그룹 (thread_id=None): "telegram:{chat_id}"
    - 포럼 그룹 (thread_id 존재):   "telegram:{chat_id}:{thread_id}"

    Legacy 호환: thread_id가 None이면 기존 형식 그대로.
    포럼 토픽이 있을 때만 확장 형식 사용.
    """
    if thread_id is None:
        return f"telegram:{conversation_id}"
    return f"telegram:{conversation_id}:{thread_id}"


def parse_telegram_session_id(session_id: str) -> tuple[str, str | None]:
    """Parse canonical id back to (conversation_id, thread_id | None)."""
    parts = session_id.removeprefix("telegram:").split(":", maxsplit=1)
    conversation_id = parts[0]
    thread_id = parts[1] if len(parts) > 1 else None
    return conversation_id, thread_id
```

이 형식이면:
- DM/비포럼: `telegram:12345` — **기존 데이터와 100% 호환**
- 포럼 토픽: `telegram:12345:67890` — 새 네임스페이스
- Legacy dual-read: 새 형식 조회 실패 시 `telegram:{chat_id}`로 fallback

### R2. 포럼 토픽 감지

Telegram Bot API에서 포럼 그룹 여부를 확인하는 방법:
- `update.message.is_topic_message` — True면 포럼 토픽 메시지
- `update.message.message_thread_id` — 토픽 ID (General 토픽도 ID 가짐)
- `chat.is_forum` — `getChat()` 응답에 포함

현재 `poll_updates()`에서 `message_thread_id`를 이미 추출하고 있으므로(plugin.py:241),
identity 헬퍼만 추가하면 별도 감지 로직은 불필요하다.

### R3. 이 Phase의 실제 작업 범위

1. `channel_identity.py` 생성 (위 헬퍼 2개)
2. `telegram_runner.py`의 15곳+ `f"telegram:{conversation_id}"` → 헬퍼 호출로 교체
3. `session_manager.py`의 키 생성 로직에 thread_id 반영
4. 테스트: DM(thread_id=None), 포럼(thread_id 존재), legacy 파싱 각각 검증
5. 마이그레이션 정책 문서화: 기존 데이터는 건드리지 않고, 새 포럼 세션만 확장 형식 사용
