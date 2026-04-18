# A01 - Architecture Auditor

**Tier**: 1
**Duration**: 269.593 sec
**Status**: fail
**Code SHA**: git-unavailable (workspace is not a Git checkout)
**Dependencies**: Tier 0 preflight artifacts were not present in-repo; `uv sync --extra dev` was executed during this run only to make `import-linter` available.

## 1. Scope

A01 계획서 기준으로 아래 범위를 검증했다.

- `.importlinter`와 `scripts/check_import_contracts.py` 기반 Clean Architecture 계약
- `tests/unit/architecture/` 단위 테스트
- `src/ds_agent/domain/` 전수 AST 스캔
- `src/ds_agent/application/` 전수 AST 스캔
- 구조 핫스팟 3개 파일 책임 분산 상태 요약

## 2. Methodology

실행 순서는 계획서 4.1 A01 절차를 따랐다.

1. `START.json` 기록
2. `python scripts/check_import_contracts.py`
3. `lint-imports`
4. `pytest tests/unit/architecture/ -v --junitxml=Docs/qa_run_2026-04-17/A01_architecture/junit.xml`
5. AST 직접 감사
   - `domain/`: stdlib, `pydantic`, `ds_agent.domain.*`, relative import만 허용
   - `application/`: `ds_agent.infrastructure.*` 직접 import 금지
6. 핫스팟 파일 3개 구조 검토

추가 메모:

- 초기 환경에서는 `lint-imports`가 PATH/.venv에 없어 실행 불가였다.
- 코드 변경은 하지 않았고, dev 의존성 동기화만 수행한 뒤 외부 import-linter 결과를 확보했다.

## 3. Results Matrix

| Check | Result | Evidence |
|---|---|---|
| `python scripts/check_import_contracts.py` | pass | `.tmp/qa_A01/check_import_contracts.log` |
| `lint-imports` | pass after `uv sync --extra dev` | `.tmp/qa_A01/uv_sync_dev.log`, `.tmp/qa_A01/lint_imports_post_sync.log` |
| `pytest tests/unit/architecture/ -v` | pass, 3/3 | `junit.xml`, `.tmp/qa_A01/pytest_architecture.log` |
| Domain AST scan | pass, 97 files / 0 violations | `A01_domain_imports.json` |
| Application AST scan | fail, 64 files / 3 violations | `A01_domain_imports.json` |
| Hotspot responsibility review | advisory only | `A01_hotspot_summary.md` |

## 4. Failures and Anomalies

### 4.1 Hard-fail findings

Application layer에서 infrastructure를 직접 import하는 사례 3건이 확인됐다.

1. `src/ds_agent/application/services/lineage_capture_service.py:11`
   `from ds_agent.infrastructure.persistence.lineage_store import SqliteLineageStore`
2. `src/ds_agent/application/services/reproducibility_exporter.py:9`
   `from ds_agent.infrastructure.artifact.notebook_engine import NotebookEngine`
3. `src/ds_agent/application/services/scheduler_service.py:11`
   `from ds_agent.infrastructure.cron_runner import CronRunner`

이로 인해 A01 계획서 pass 기준인 "application layer direct infrastructure import 0건"을 만족하지 못했다.

### 4.2 Coverage gap

자동화된 기존 검증과 A01 계획서 범위 사이에 간극이 있었다.

- `.importlinter`는 현재 `ds_agent.domain` 독립성만 강제한다.
- `scripts/check_import_contracts.py`도 `domain_independence`만 검사한다.
- `tests/unit/architecture/test_semantic_layer_deps.py`는 전역 `application/`이 아니라 `ds_agent.memory.semantic` 하위 레이어만 검사한다.

즉, 이번에 발견된 3건은 현재 CI 녹색 상태를 통과하면서도 남아 있을 수 있는 구조 위반이다.

### 4.3 Environment anomaly

- 첫 `lint-imports` 실행은 command not found로 실패했다.
- `pyproject.toml`에는 `import-linter>=2.0`가 dev extra로 선언돼 있으나 현재 `.venv`에는 설치돼 있지 않았다.
- `uv sync --extra dev` 이후 `lint-imports`는 정상 실행되어 계약 1건 kept, 0 broken을 반환했다.

## 5. Evidence Index

- `Docs/qa_run_2026-04-17/A01_architecture/START.json`
- `Docs/qa_run_2026-04-17/A01_architecture/junit.xml`
- `Docs/qa_run_2026-04-17/A01_architecture/A01_domain_imports.json`
- `Docs/qa_run_2026-04-17/A01_architecture/A01_hotspot_summary.md`
- `.tmp/qa_A01/check_import_contracts.log`
- `.tmp/qa_A01/lint_imports.log`
- `.tmp/qa_A01/lint_imports_post_sync.log`
- `.tmp/qa_A01/lint_imports_uv.log`
- `.tmp/qa_A01/pytest_architecture.log`
- `.tmp/qa_A01/uv_sync_dev.log`

## 6. Recommendations

1. `application -> infrastructure` 직접 의존 3건을 Protocol/port로 역전하고 조립은 composition root로 이동시킬 것.
2. `.importlinter`와 `scripts/check_import_contracts.py`에 `application_no_infrastructure` 계약을 추가할 것.
3. `tests/unit/architecture/`에 전역 `src/ds_agent/application/` 경계 테스트를 추가할 것.
4. `ws_handler.py`, `ipc.ts`, `MissionBriefPanel.tsx`는 기능 추가 전에 분리 계획을 선행할 것. 현재도 동작은 가능하지만 책임 집중도가 높다.
