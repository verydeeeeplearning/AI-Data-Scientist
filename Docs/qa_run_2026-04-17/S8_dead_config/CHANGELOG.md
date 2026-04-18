# S8 Dead Config Cleanup — CHANGELOG

**실행일**: 2026-04-18
**스코프**: PyInstaller spec의 dead hidden import 정리 (C15-O6 포함)

## 변경

### spec 파일
- `ds-agent-api.spec:105` `'ds_agent.memory.session_db'` 제거. 해당 모듈은 소스에 존재하지 않는 dead entry였음 (C15 Post-QA 단계에서 백그라운드 PyInstaller 빌드 로그가 `ERROR: Hidden import 'ds_agent.memory.session_db' not found`로 검출).

### 신규 `__init__.py` 2건 (hiddenimports 연관된 것만, scope-adjacent bug fix)
- `src/ds_agent/infrastructure/artifact/__init__.py` (신규, 7 모듈 regular package 화)
- `src/ds_agent/infrastructure/external/__init__.py` (신규, 6 connector regular package 화)

**근거**: 두 디렉토리 모두 `ds-agent-api.spec`에 hiddenimport로 등록되어 있었으나 `__init__.py`가 없어 PyInstaller가 regular package로 인식하지 못해 dead entry로 분류됨. 해당 디렉토리 하위 모듈(`dashboard_engine`, `notebook_engine`, `slack_connector` 등)은 실제로 사용 중이므로 regular package 전환이 올바른 해소.

## 검증

- [x] `python .tmp/qa_S8/check_hiddenimports.py` → `Dead hidden imports: 0`
- [x] spec 전체 re-scan: dead entry 0
- [x] import-linter 계약 2건 유지 (`python scripts/check_import_contracts.py` 통과)
- [x] ruff 0 error on new `__init__.py` (docstring만 포함)
- [ ] PyInstaller 재빌드 smoke 5/5 → **S8 외부 실행 의존**. 재빌드 15~20분 소요로 본 Sprint 내부 생략. 다음 smoke 재빌드 시 검증.

## 별도 스프린트로 이월 — "S20 __init__.py hygiene"

`__pycache__` 제외 **42 디렉토리가 `__init__.py` 없이 PEP 420 namespace package**로 운영 중. runtime 동작은 정상이나 PyInstaller/mypy/import-linter 안정성 저하 가능.

대표 누락 위치:
- `src/ds_agent/application/usecases/`
- `src/ds_agent/evaluation/{application,infrastructure,presentation}/` 서브 트리 전체
- `src/ds_agent/skills/{builtin,custom,domain,missions,shared}/`

**권고**: 별도 소규모 스프린트 S20으로 일괄 추가. Scope 크지만 위험 Low (빈 파일 추가).

본 S8은 Decision Log §24.2-4 "Sprint 당 scope-adjacent bug 최대 2건" 원칙 준수 위해 2건만 병합 (artifact + external — hiddenimports 직접 관련).

## Rollback

세 변경 모두 독립 revert 가능:
1. spec line 105 복원
2. `__init__.py` 2건 삭제

## 의존성 / 후속

- Epic-A `ws_handler.py` 분할 시점에 spec 전반 재정렬 권장.
- S20 신규 제안: `__init__.py` hygiene 42건 일괄 추가. (Task 추가됨)
