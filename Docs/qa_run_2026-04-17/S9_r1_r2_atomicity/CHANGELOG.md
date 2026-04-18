# S9 R-1 + R-2 Atomicity — CHANGELOG

**실행일**: 2026-04-18
**스코프**: Promote + Deprecate-Immediate 경로에 S6 atomic 패턴 확장
**해결 이슈**: R-1 (phantom-promotion audit split) / R-2 (immediate deprecation audit split)

## 코드 변경

### 신규 Port 메서드
- `src/ds_agent/application/ports/learning_store_port.py`: `LearningStoreAtomicPort.save_promotion_and_item(*, promotion, item)` 추가 + docstring에 S6/S9 history 명시.

### 신규 SQLite 구현
- `src/ds_agent/infrastructure/persistence/learning_store.py::SqliteLearningStore.save_promotion_and_item`: S6 `save_item_and_deprecation`와 동일한 `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK-on-error` 패턴. `promotion_records` INSERT + `learning_items` INSERT.

### Use case 수정 (R-1)
- `src/ds_agent/application/learning/promote_learning_item.py`:
  - `LearningStoreAtomicPort` import 추가
  - 2개 독립 write (`save_promotion_record` + `save_item`) → 1개 atomic call (`save_promotion_and_item`)

### Use case 수정 (R-2)
- `src/ds_agent/application/learning/deprecate_learning_item.py`:
  - `LearningStoreAtomicPort` import 추가
  - IMMEDIATE 경로: `save_item(updated) + save_deprecation_record(record)` → `save_item_and_deprecation(item=updated, deprecation=record)` (S6 port 재사용)
  - GRACE 경로: 단일 `save_deprecation_record` 유지 (atomic 불필요)

### 테스트
**신규**:
- `tests/unit/application/test_promote_atomicity.py` (5 테스트): use case 레벨 2건 + Sqlite 레벨 3건 (happy + failure rollback + runtime_checkable)
- `tests/unit/application/test_deprecate_atomicity.py` (3 테스트): IMMEDIATE atomic + IMMEDIATE 실패 + GRACE 단일 write 보존

**기존 테스트 업데이트** (S6 R-5 패턴 따라 call-pattern assertion만 갱신):
- `tests/unit/application/test_promote_learning_item.py::test_promote_kb_entry_passes`: `save_promotion_record/save_item` assertion → `save_promotion_and_item` assertion
- `tests/unit/application/test_deprecate_learning_item.py::test_immediate_transitions`: 동일 패턴

## Quality Gate

- [x] 신규 테스트 28/28 pass (RED→GREEN 증거 명시)
- [x] 기존 테스트 회귀 0 (application layer 515/515 pass + integration SqliteLearningStore 9/9)
- [x] `ruff check` 0 error (수정 파일 + 신규 테스트)
- [x] `python scripts/check_import_contracts.py` ok (2 계약 유지)
- [x] `python scripts/check_mypy_baseline.py` baseline 383 동일, new=0

## Clean Architecture 준수

- 신규 Port는 application 레이어에 위치 — `application_independence_from_infrastructure` 계약 유지.
- Use case는 Port Protocol에만 의존 (`# type: ignore[assignment]` cast로 `LearningStore` → `LearningStoreAtomicPort` 런타임 duck typing, S6 패턴 복제).
- Clean Architecture 의존성 방향 불변.

## Rollback 전략

3개 layer 독립 revert 가능:
1. Port 메서드 제거 → use case의 atomic call 제거 → 기존 2-step write 복원
2. SqliteLearningStore 구현 제거
3. 테스트 4개 파일 revert (신규 2 + 기존 2)

## 잔존 관찰

- **R-3** (`ReviewLearningItemUseCase`): 미해결, S10 스코프.
- **R-4** (일반화된 `begin_transaction()` port): atomic 메서드 누적 3건(save_item_and_deprecation / save_promotion_and_item / 향후 save_review_event_and_item) → Epic-B RFC 트리거 조건 충족.
- **`auto_deprecate_on_failure`**: `DeprecateLearningItemUseCase.execute(IMMEDIATE)`를 호출하므로 atomic 혜택 자동 상속 — 별도 수정 불요.

## 재감사 요구사항

B11 Round 3 재감사 스폰 권고 — **Path 6 (promotion threshold)** + **Path 7 (auto-deprecation)** 기존 기능 + **R-1/R-2 atomicity probe 신규 추가**. 본 스프린트의 테스트는 agent self-assert이므로 독립 감사자가 재확인.
