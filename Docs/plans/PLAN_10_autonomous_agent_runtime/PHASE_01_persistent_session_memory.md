# Phase 01: Persistent Session/Memory Substrate

**Priority**: P0  
**Estimated**: 1주  
**Milestone**: B

---

## 0. 구현 상태

**Status**: Completed  
**Last Updated**: 2026-04-12

이번 구현 패스에서 완료된 항목:

- [x] `TranscriptStore` port 및 `JsonTranscriptStore` 구현
- [x] `CheckpointStore` port 및 `JsonCheckpointStore` 구현
- [x] `DSAgent`가 transcript/checkpoint를 통해 history를 load/save 하도록 변경
- [x] `chat.history`가 transcript/checkpoint store를 읽도록 변경
- [x] `memory_search`, `memory_store`를 실제 backing store 기반 구현으로 교체
- [x] `MemoryQueryService`를 통해 `ExperimentLog`, `CodeRegistry`, `DomainKB`, `ProjectStore`를 검색 대상으로 연결
- [x] WebSocket/E2E 경로에서 persisted history 조회 검증
- [x] transcript/checkpoint/memory tool targeted tests 추가 및 통과

검증 결과:

- `pytest` targeted: `100 passed`
- `ruff check`: passed
- `ruff format --check`: passed
- `mypy`: 현재 이 세션에서는 명령/모듈이 없어 미검증

구현 메모:

- 실제 코드베이스에는 `session_db.py` 소스가 없어서, 계획 대비 `transcript_store + checkpoint_store` 조합으로 Phase 01 substrate를 대체했다.
- `chat.history`는 더 이상 active agent의 `_history`만 직접 보지 않고 persisted state를 우선 조회한다.
- checkpoint는 in-progress run을 위해 저장되고, final response 시 transcript로 승격된 뒤 정리된다.

---

## 1. 목표

인메모리 중심 대화/진행 상태를 영속 저장 기반으로 전환한다.

자율형 agent처럼 보이려면 단순히 루프가 길어지는 것이 아니라, 프로세스 재시작 후에도 세션 맥락과 작업 맥락을 이어갈 수 있어야 한다.

---

## 2. 해결할 문제

현재 상태:

- `agent._history`가 사실상 대화의 단일 저장소 역할을 한다.
- `memory_search`, `memory_store`는 실질적으로 스텁에 가깝다.
- 세션 복원성과 checkpoint continuity가 약하다.

이 상태에서는 Telegram이나 daemon 관점에서 장기 실행 agent를 운영할 수 없다.

---

## 3. 범위

포함:

- transcript store 도입
- checkpoint store 도입
- memory tool 실구현
- 기존 메모리 계층과 runtime memory query 연결

제외:

- goal layer 도입
- autonomous sensor 판단 로직
- 고급 ranking/retrieval optimization

---

## 4. 구현 작업

1. `runtime/transcript_store.py`를 추가해 session transcript를 append/read 가능하게 만든다.
2. `runtime/checkpoint_store.py`를 추가해 active work snapshot을 저장한다.
3. `memory_query_service.py`를 추가해 `DomainKB`, `ExperimentLog`, `CodeRegistry`, `ProjectStore`를 공통 검색 대상으로 묶는다.
4. `memory_search`, `memory_store`를 실제 구현으로 교체한다.
5. `chat.history` 및 관련 history 조회 경로가 `_history` 대신 transcript store를 읽도록 변경한다.
6. restart 후 history reload integration test를 추가한다.

---

## 5. 예상 수정 파일

신규:

- `src/ds_agent/runtime/transcript_store.py`
- `src/ds_agent/runtime/checkpoint_store.py`
- `src/ds_agent/runtime/memory_query_service.py`

수정:

- `src/ds_agent/tools/memory_tools.py`
- `src/ds_agent/agent/core.py`
- `src/ds_agent/api/ws_handler.py`
- 필요 시 `src/ds_agent/memory/*`

---

## 6. 테스트 계획

- transcript persistence unit tests
- restart/reload history integration tests
- memory_search 결과 스키마 테스트
- checkpoint save/load 테스트
- tool error format 회귀 테스트

핵심 시나리오:

- 프로세스를 재시작한 뒤 동일 세션 transcript를 다시 읽을 수 있다.
- `memory_search`가 실제 검색 결과와 출처 메타데이터를 반환한다.
- `memory_store`가 no-op가 아니라 저장 결과를 남긴다.

---

## 7. 완료 기준

- 프로세스 재시작 후에도 최근 세션 history 조회가 가능하다.
- `memory_search`가 실제 결과를 반환한다.
- `memory_store`가 no-op가 아니다.
- checkpoint 저장/복구가 동작한다.

---

## 8. 구현 메모

- 초기 구현은 file-backed JSON/JSONL로 시작해도 된다.
- 다만 interface는 나중에 SQLite로 바꿔도 상위 계층이 흔들리지 않게 분리해야 한다.
- 이후 goal/run/task 계층은 모두 이 영속 substrate 위에 쌓아야 한다.
