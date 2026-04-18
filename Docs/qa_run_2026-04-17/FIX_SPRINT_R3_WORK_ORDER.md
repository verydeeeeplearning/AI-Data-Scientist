# Fix Sprint Round 3 — Work Order

**작성일**: 2026-04-17
**트리거**: Tier 2 Gate 판정 후 이월된 이슈 처리
**원칙 출처**: `Docs/qa_run_2026-04-17/FIX_SPRINT_WORK_ORDER.md` (R1/R2 당시 정립된 원칙을 그대로 상속)
**참조**: `Docs/qa_run_2026-04-17/TIER2_GATE_DECISION.md` §6 이월 이슈 표

---

## 1. 원칙 재확인 (R1/R2 공용)

1. **감사자 ≠ 수정자**: Fix Sprint agent는 수정만 하고, 재감사는 원래 감사 agent (B11 등)가 동일 프롬프트 + delta 검증으로 수행.
2. **스코프 밖 파일 금지**: 각 스트림은 지정된 파일 집합 이외에 손대지 않음.
3. **TDD**: RED(실패 재현 테스트) → GREEN(최소 수정) → REFACTOR.
4. **Clean Architecture 유지**: domain/application/infrastructure 경계 준수. 신규 의존성은 Port 경유.
5. **전체 회귀 pytest 대신 스코프 격리**: Windows `.tmp/pytest` flake 대응.
6. **LLM=오케스트레이터 원칙 훼손 금지**: 수정 중 하드코딩 flow 추가 금지.

---

## 2. 스트림 분배

| 스트림 | 우선순위 | 대상 이슈 | 스코프 | 산출물 폴더 |
|:------:|:--------:|----------|--------|------------|
| **S6** | **HIGH** | FAIL-B11-8 Rollback atomicity | `src/ds_agent/application/learning/rollback_promotion.py`, `src/ds_agent/infrastructure/persistence/learning_store.py`, 신규 테스트 1개 | `Docs/qa_run_2026-04-17/S6_rollback_atomicity/` |
| S7 | MED | NOTE-B08-1 / D5-1 / B11 D1~D2 / B09-F2 문서 정렬 | `Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md` 해당 단락만 수정 (코드는 건드리지 않음) | `Docs/qa_run_2026-04-17/S7_doc_alignment/` |
| S8 | MED | RC-5 in-adapter kill-switch 검토 | `src/ds_agent/infrastructure/integrations/*` 중 slack/jira/confluence/notion/git 5개 adapter의 `_is_configured` 가드 추가 여부 **설계 결정 + RFC 문서만** (코드 변경은 결정 후 별도) | `Docs/qa_run_2026-04-17/S8_adapter_killswitch_rfc/` |
| S9 | LOW | ENV-2 pandas/numpy 누락 | `pyproject.toml` dev extras 점검, 실제 누락이면 추가. 테스트 구동 검증. | `Docs/qa_run_2026-04-17/S9_test_env/` |

**S6은 Tier 3과 병렬 실행. S7~S9는 S6 완료 후 순차 또는 다음 사이클에 수행.**

---

## 3. S6 상세 스펙 (이번 사이클 유일한 실코드 수정 스트림)

### 3.1 문제 재현

B11 증거: `Docs/qa_run_2026-04-17/B11_portfolio_learning/B11_rollback_atomicity_sqlite_probe.json`

```
RollbackPromotionUseCase.execute(item_id) 내부:
  1) store.save_item(updated)   → commit
  2) store.save_deprecation_record(dep)  → commit (별도 트랜잭션)

중간 실패 시:
  - item.status == "deprecated" (persisted)
  - DeprecationRecord 없음
  → audit trail split
```

### 3.2 수정 방향 (두 가지 옵션 중 선택)

**Option A — Use-case-level transaction (권장)**:
- `LearningStorePort`에 `save_item_and_deprecation(item, dep_record) -> None` 또는 `begin_txn() -> ContextManager` 추가.
- `SqliteLearningStore`가 단일 connection에서 `BEGIN...COMMIT`으로 감쌈.
- `RollbackPromotionUseCase`가 이 메서드를 사용.

**Option B — Compensating revert**:
- 현 2-step 유지. `save_deprecation_record` 실패 시 item을 이전 status로 되돌리는 catch 블록.
- Option A보다 단순하나 race 조건 노출 가능 (동시성 상황에서 중간 상태가 관측될 수 있음).

→ **Option A 권장**. Clean Architecture상 Port 확장은 Domain/Application 규약 강화.

### 3.3 TDD 절차

**RED**:
- 신규 테스트 `tests/unit/application/test_rollback_atomicity.py`:
  - 모킹된 store에 `save_deprecation_record` 실패 주입.
  - use case 실행 후 `store.save_item`이 persist되지 않았음을 검증 (또는 revert됨).
  - 현재 코드에서는 FAIL이어야 함.

**GREEN**:
- Port에 신규 메서드 추가 (interface).
- `SqliteLearningStore` 구현.
- `RollbackPromotionUseCase` 수정.
- 테스트 pass 확인.

**REFACTOR**:
- Port 계약 문서화.
- 다른 use case (PromoteLearningItem 등) 중 유사한 이중 write 패턴 있는지 1회 스캔 (수정은 scope 밖 — 기록만).

### 3.4 Pass 기준

- 신규 테스트 GREEN.
- 기존 테스트 (`tests/unit/application/test_rollback_promotion.py`, `tests/integration/infrastructure/test_sqlite_learning_store.py`) 전수 GREEN.
- `import-linter` 0 violation.
- `ruff check src/ds_agent/application/learning/rollback_promotion.py src/ds_agent/infrastructure/persistence/learning_store.py` 0 error.
- B11이 `B11_rollback_atomicity_sqlite_probe.json`과 동일 프로브 재실행 시 `atomicity_kind="atomic"` 반환.

### 3.5 산출물 요구사항

S6 agent는 `Docs/qa_run_2026-04-17/S6_rollback_atomicity/` 아래에:
- `START.json` / `FINAL.json`
- `DIFF_SUMMARY.md` — 변경된 파일/라인/이유
- `TEST_RESULTS.md` — pytest junit 결과 + 신규 테스트 증거
- `CHANGELOG.md` — 변경 요약 (외부 재감사자용)
- `RECOMMENDATIONS.md` — S7~S9로 위임할 부수 발견

### 3.6 제약

- **스코프 밖 파일 수정 금지** — 위에 명시한 파일 + 신규 테스트 1개만.
- **import-linter 계약 유지** — `application_independence_from_infrastructure` 깨지 않도록 Port 경유.
- **domain 계층 수정 금지** — 이번 이슈는 application/infrastructure 경계에서 해결.
- **LLM=오케스트레이터 원칙 유지** — Port 메서드는 정보/동작 제공이지 LLM 실행 순서 강제 아님.

---

## 4. 재감사 절차

S6 완료 후:
1. 오케스트레이터는 `S6/FINAL.json`의 status와 증거 확인.
2. B11 재감사 agent 스폰 — 원래 B11과 **동일한 프롬프트**에 "이번에는 `B11_rollback_atomicity_sqlite_probe.json`의 atomicity_kind 확인에 집중" 추가.
3. Round 2 결과를 `Docs/qa_run_2026-04-17/B11_portfolio_learning_reaudit/` 에 저장.
4. Round 2에서 Path 8 PASS 확인 시 Tier 2 Gate 보완 완료.

---

## 5. 이력

| 날짜 | 이벤트 |
|------|--------|
| 2026-04-17 | Work Order 작성 (Tier 2 완료 직후) |
