# S12 PRE-2 Application Layer — CHANGELOG

**실행일**: 2026-04-18
**스코프**: `src/ds_agent/application/` mypy 해소
**해결 이슈**: PRE-2 baseline 17건 축소

## 결과

- **mypy baseline: 362 → 345 (17 error 감소)**
- application layer scope(`mypy src/ds_agent/application`) **0 error, 69 source files**
- 누적 baseline 축소: 383(초기) → 345 = **38 error 해소 (9.9%)**

## 수정 파일 (8건)

### Service 계층
- `artifact_generator.py` — `_as_list(object) -> list[object]` 헬퍼 추가 + `_memo`, `_slide_spec`에서 `data.get(...)` object 값을 `_as_list`로 narrow. 6건 해소 (4 iter + 1 var-annotated + 1 enumerate).
- `lineage_capture_service.py` — (a) `content: dict[str, object]` 명시 annotation으로 invariance 회피. (b) `os.sys.version` → `import sys` + `sys.version`으로 정상 접근.
- `usage_summary.py` — (a) `summary["costUsd"]` / `summary["runCount"]` dict[str, object] 값 접근 4건 → type ignore. (b) `recent_runs`: list[dict[str, float|str|None]] → list[dict[str, object]] `[dict(r) for r in ...]`로 복사. (c) `sorted(key=lambda item: ...)` type ignore.
- `ab_test_analyzer.py` — `from scipy import stats`에 `# type: ignore[import-untyped]` (scipy-stubs 미설치 정책 유지).
- `feature_registry_usecases.py` — `_build_warnings(feature)` 파라미터 annotation 누락 → `Feature` 타입 명시 + `from ds_agent.domain.entities.feature import Feature` import 추가.
- `reproducibility_exporter.py` — `content` 로컬 변수가 `str | dict[str, object]` 두 분기 결과 → 상단에 annotation 선언.

### Learning use case
- `submit_learning_proposal.py` — `scope: str = "project"` → `scope: Literal["project", "domain", "global"] = "project"`. `from typing import Literal` 추가.

### Run diff
- `run_diff_usecases.py` — `_delta_direction(...) -> str` → `Literal["better", "worse", "neutral"]`. `from typing import Literal` 추가. 세 분기 모두 Literal 집합 원소이므로 narrowing 자연스러움.

## Quality Gate

- [x] Application layer mypy 0 error (69 files)
- [x] `mypy src/ds_agent` 전체 345 (baseline 축소 확인)
- [x] `check_mypy_baseline --update` 실행 완료
- [x] 수정 파일 ruff 0 error (feature_registry_usecases.py import order는 --fix로 자동 정리)
- [x] `check_import_contracts` ok
- [x] Scope pytest 회귀 0: `tests/unit/application/` **507/507 pass**

## 설계 노트

- `_as_list` 헬퍼를 `ArtifactGenerator` 클래스 내 staticmethod로 두어 여러 artifact 타입에서 재사용 가능. Public API 변경 없음.
- `LearningItem.scope` 타입 강화는 Literal narrowing이 **호출부 영향 있음** — `submit_learning_proposal(scope="foo")` 같은 잘못된 값 호출이 mypy 시점에 잡히게 됨. 바람직한 방향.
- `scipy`, `google.generativeai`는 optional 의존성이라 stub 설치 정책 보류 (S18에서 재평가).
- `os.sys` 접근 제거는 Python linting 관점에서 일반 권고 — private module navigation 회피.

## 누적 진행 로드맵

| 단계 | 완료 | 누적 baseline |
|:----:|:----:|:------------:|
| Post-QA Phase 1b | baseline freeze | 383 |
| S11~S13 inner | -21 | 362 |
| **S12 application** | **-17** | **345** |

다음 타겟 후보:
- S18 tools (18건)
- S17 infrastructure (36건)
- S19 evaluation (38건)
- Epic-A runtime+api+gateway (345 중 대부분)

## 재감사

본 Sprint는 PRE-2 축소만 수행 — 원자성/계약 변경 없음. 별도 재감사 스폰 불요. 단 차기 QA cycle에서 `mypy src/ds_agent` 전수 수치 345가 `mypy-baseline.json`과 일치하는지 자동 검증.
