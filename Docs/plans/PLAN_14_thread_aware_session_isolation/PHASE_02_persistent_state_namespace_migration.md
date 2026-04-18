# Phase 02: Persistent State Namespace Migration

**Priority**: P0  
**Status**: Proposed  
**Depends On**: Phase 00-01

---

## 1. Goal

Move persisted Telegram state from chat-scoped keys to thread-aware namespaces
without losing resumability.

---

## 2. Current Gap

Even if live sessions become thread-aware, persisted stores would still contain
legacy chat-scoped data until explicitly migrated.

Affected surfaces include:

- transcript store
- checkpoint store
- approval store
- goal store
- working memory store

Without a migration plan, recovery becomes ambiguous.

---

## 3. Planned Implementation

Primary files:

- `src/ds_agent/runtime/transcript_store.py`
- `src/ds_agent/runtime/checkpoint_store.py`
- `src/ds_agent/runtime/approval_store.py`
- `src/ds_agent/runtime/goal_store.py`
- `src/ds_agent/runtime/working_memory.py`

Likely new migration helpers:

- `src/ds_agent/runtime/migrations/telegram_thread_namespace.py`

Implementation items:

- define whether migration is:
  - eager
  - lazy dual-read
  - dual-write then cutover
- migrate persisted keys to thread-aware namespaces
- preserve compatibility with legacy sessions during the transition window
- make store-level helpers consistent so each persistence layer does not reinvent migration logic

---

## 4. Runtime Rules

- migration must be deterministic and idempotent
- no store should choose its own Telegram key format
- legacy state must not silently shadow new thread-aware state
- recovery semantics during mixed-state windows must be documented

---

## 5. Verification

Required:

```bash
python -m pytest tests/unit/infrastructure/test_runtime_persistence.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/runtime
```

Manual checks:

1. Seed legacy chat-only state and verify the thread-aware path can read or migrate it
2. Confirm new topic activity does not overwrite legacy state unexpectedly

---

## 6. Exit Criteria

- persisted Telegram state can be safely addressed by topic
- migration behavior is deterministic and test-covered
- resumability survives the namespace transition

---

## Review: 실현 가능성 점검 코멘트 (2026-04-13)

### R1. dual-read 전략 권장 — eager migration은 위험

| 전략 | 장점 | 단점 |
|------|------|------|
| eager migration (일괄 변환) | 깔끔한 상태 | 실행 중인 세션과 충돌 가능; 롤백 어려움 |
| lazy dual-read | 안전; 점진적 | 코드 복잡성 증가; 레거시 코드 잔존 |
| dual-write + cutover | 새 데이터 안전 | 기존 데이터 접근에 추가 로직 필요 |

**권장: lazy dual-read**.

```python
# 스토어 조회 로직 예시
def load(self, session_id: str):
    data = self._read(session_id)          # 새 형식 먼저
    if data is None and ":" in session_id:
        # "telegram:12345:67890" → "telegram:12345" 로 fallback
        legacy_id = session_id.rsplit(":", maxsplit=1)[0]
        data = self._read(legacy_id)
    return data
```

Phase 00의 `parse_telegram_session_id()` 헬퍼를 사용하면 fallback 키 생성이 일관적이다.

### R2. 스토어별 영향도

| 스토어 | 키 유형 | 마이그레이션 난이도 |
|--------|---------|-----------------|
| `JsonTranscriptStore` | 파일명에 session_id 포함 | 중 — 파일 I/O 경로 변경 |
| `JsonCheckpointStore` | 파일명에 session_id 포함 | 중 — 동일 |
| `JsonApprovalStore` | JSON 필드 `session_id` | 하 — 조회 로직만 변경 |
| `JsonGoalStore` | JSON 필드 `session_id` | 하 — 동일 |
| `JsonWorkingMemoryStore` | 파일명에 session_id 포함 | 중 — 파일 I/O 경로 변경 |

파일명 기반 스토어는 session_id에 `:`가 포함되므로 **파일명으로 쓸 수 없다**.
현재 파일명 생성 로직이 `:` 를 어떻게 처리하는지 확인해야 한다.
일반적으로 `session_id.replace(":", "_")` 같은 sanitization이 필요하다.

### R3. 쓰기는 새 형식만

dual-read로 레거시를 읽되, **새로운 쓰기는 항상 thread-aware 형식**으로 해야 한다.
그래야 시간이 지나면서 자연스럽게 레거시 데이터가 소멸하고 cutover가 가능해진다.
