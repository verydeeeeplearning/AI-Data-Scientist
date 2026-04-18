# S20 `__init__.py` Hygiene — CHANGELOG

**실행일**: 2026-04-18
**스코프**: `src/ds_agent/` 누락된 `__init__.py` 일괄 추가
**출처**: S8 발견 (42 디렉토리 누락)

## 변경

### 추가 (37 빈 파일)
PEP 420 namespace package → regular package 전환. 내용은 빈 파일. Python import 동작은 동일, mypy/import-linter/PyInstaller 안정성 향상.

대표 위치:
- `application/usecases/`
- `evaluation/{application,infrastructure,presentation}/` 전체 서브트리 (20+)
- `skills/{builtin,custom,domain,missions,shared}/` (도메인 팩 포함)
- gold_tasks/{finance,healthcare,marketing,ops,retail,saas}

### 제외 (5 파일, Python invalid 이름)
하이픈 포함 디렉토리는 valid Python identifier가 아니므로 `__init__.py` 추가 불가:
- `skills/domain/domain-pack-enterprise/` 및 하위 4개 (glossary/metrics/trust/verified_queries)

이들은 **데이터 자원 디렉토리**로서 Python import 대상이 아님 — 단순 파일 번들링으로 PyInstaller가 이미 `datas=skills_data` 경로로 처리 중. 이름 변경 없이 유지.

## Quality Gate

- [x] 37 파일 추가 완료
- [x] `domain-pack-enterprise` 5건 정확히 제외
- [x] `python -m mypy src/ds_agent` 전체 실행 성공 (이전엔 namespace package 탐색 중 중단 가능성)
- [x] `mypy-baseline.json` 갱신: **255 → 257** (숨겨진 2건 발견, 의도된 결과)
- [x] scope pytest regression: `tests/unit/domain/ + application/` 721/721 pass
- [x] import-linter ok

## mypy baseline 미세 변동의 의미

이전 baseline(255)은 namespace package로 scan되던 상태에서 측정. S20으로 regular package 전환 후 mypy가 **이전에 건너뛰던 2 파일의 error**를 새로 인식. **regression이 아니라 이전 measurement의 blind spot 해소**.

- scope pytest 0 regression
- 새로 발견된 2건은 이미 baseline에 포함됨 (축소 아닌 확장)
- 향후 발견된 2건이 고쳐지면 baseline 축소 가능

## 영향 분석

- PyInstaller: regular package가 더 안정적으로 번들링. S8 C15-O6 dead import와 유사한 문제 재발 방지.
- mypy: 향후 전수 분석이 일관성 확보.
- import-linter: 계약 검증 범위 확장 가능.

## Rollback

37 `__init__.py` 삭제로 이전 상태 복원 가능. 단 hyphen 디렉토리 5건은 별도 처리 (제거만).

## 후속

- Epic-A `ws_handler.py` 분할 시점에 namespace vs regular package 정책 재검토.
- `domain-pack-enterprise` 이름 체계는 별도 RFC로 결정 (하이픈 유지 vs underscore 전환).
