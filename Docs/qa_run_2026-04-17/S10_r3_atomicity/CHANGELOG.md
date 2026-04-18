# S10 R-3 Atomicity — CHANGELOG

**실행일**: 2026-04-18
**스코프**: ReviewLearningItemUseCase 원자성 전환
**해결 이슈**: R-3 (review-event vs item-state audit split)

## 코드 변경

### Port 확장
- `src/ds_agent/application/ports/learning_store_port.py`: `LearningStoreAtomicPort.save_review_event_and_item(*, event, item)` 추가. `ReviewEvent` import도 함께.

### SQLite 구현
- `src/ds_agent/infrastructure/persistence/learning_store.py::SqliteLearningStore.save_review_event_and_item`: `BEGIN IMMEDIATE` + `INSERT review_events` + `INSERT OR REPLACE learning_items` + `COMMIT` / `ROLLBACK-on-error`. `review_events`는 append-only semantic(event_id PK)이므로 `INSERT OR REPLACE`가 아닌 순수 `INSERT` 사용.

### Use case 수정
- `src/ds_agent/application/learning/review_learning_item.py`:
  - `LearningStoreAtomicPort` import 추가
  - 2개 독립 write (`save_review_event` + `save_item`) → 1개 atomic call (`save_review_event_and_item`)

### 테스트
**신규**:
- `tests/unit/application/test_review_atomicity.py` (7 테스트): use case 레벨 2건 + Sqlite 레벨 3건 (happy + failure rollback + runtime_checkable)
- 기존 테스트 회귀 0 (`test_review_learning_item.py` 8/8 유지)

## Quality Gate

- [x] 신규 테스트 7/7 pass
- [x] 기존 테스트 회귀 0: application 전체 520/520 pass (515 Sprint 이전 + 5 신규 atomicity)
- [x] `ruff check` 0 error
- [x] `check_import_contracts` ok (2 계약 유지)
- [x] `check_mypy_baseline` baseline 383 동일, new=0

## Clean Architecture

R-1/R-2/R-3 통해 `LearningStoreAtomicPort`에 atomic 메서드 3개 누적:
1. `save_item_and_deprecation` (S6)
2. `save_promotion_and_item` (S9)
3. `save_review_event_and_item` (S10)

→ **R-4 Epic-B 트리거 충족**. 일반화된 `LearningStoreTxnPort.begin_transaction() -> ContextManager` RFC 착수 조건이 S9+S10 완료 시점에 맞추어 확립. 본 Epic-B RFC는 별도 사이클로 이월 (현 Sprint 플로우에서는 RFC 파일 stub만 남기는 경량 작업 가능).

## Rollback 전략

3개 layer 독립 revert 가능 (S9 패턴과 동일).

## 재감사 요구사항

B11 Round 3에 R-3 atomicity probe도 함께 포함 (S9/S10 통합 재감사).
