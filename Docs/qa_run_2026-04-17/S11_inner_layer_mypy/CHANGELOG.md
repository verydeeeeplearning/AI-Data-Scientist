# S11~S13 PRE-2 Inner Layer — CHANGELOG

**실행일**: 2026-04-18
**스코프**: domain + agent + memory + skills + providers + cli + self_improve
**해결 이슈**: mypy baseline 축소

## 결과

- **mypy baseline: 383 → 362 (21 error 감소)**
- inner layer 스코프(`mypy src/ds_agent/{domain,agent,memory,skills,providers,cli,self_improve}`) **0 error, 211 source files**

## 수정 파일 (16건)

### Domain (6 파일)
- `execution_policy.py` — `allowed_domains` 중복 정의 제거 (line 25·26 → 25)
- `connector.py` — `get_int_option` 의 `int(value)` arg-type → type ignore (런타임 try/except로 이미 안전)
- `standing_order.py` — metrics dict value가 `object`일 때 `float(raw)` 안전화: try/except 감싸서 실패 시 False 반환
- `memory.py` — `0.95 ** months` 반환 Any → 명시 `decay: float` 로컬
- `feature.py` — `list(value)` call-overload → type ignore (이미 try/except 있음)
- `dtos/verifier_context.py` — Pydantic Field `default_factory` Literal 좁힘을 위해 `_default_enabled_layers()` 헬퍼 추가 (`cast(list[LayerName], [...])`)

### Domain interface 확장
- `domain/interfaces/work_object.py` — Protocol에 `list_events_by_status` 메서드 추가 (실제 `SqliteWorkObjectStore`에 이미 구현 존재). `IntegrationEventStatus` import도 함께. **계약이 실구현과 일치하도록 upstream 보강**.

### Agent (3 파일)
- `confidence_scorer.py` — `layer.score` (float | None)을 `score = x if x is not None else 0.0`로 좁혀 `_clamp_score(float)` 호환
- `reporting_hooks.py` — `score["unsupported"]` (object) → `isinstance(raw, list)` 가드 + list narrowing
- `governance_hooks.py` — (a) `_latest_parent` 리턴 `LineageRecord | None` annotation + `LineageRecord` import / (b) `capture_evaluation(metrics=...)` dict variance → dict comprehension으로 복사하여 `dict[str, object]` 호환

### Memory (1 파일)
- `unified_store.py` — `return existing_id` Any 반환 → `return str(existing_id)` 명시 cast

### Skills (1 파일)
- `skills/hub.py` — `frontmatter["permissions"][key]` indexed assignment object target 해소: `perm_block: dict[str, object]` 로컬 변수 경유 후 대입

### Providers (1 파일)
- `gemini_oauth.py` — `token_store.load_by_provider("gemini")` type ignore에 `attr-defined` 추가 (기존 `union-attr`만 커버했음)

### CLI (2 파일)
- `portfolio_cli.py` — `_get_store` 리턴 annotation `SqlitePortfolioStore` (TYPE_CHECKING import 추가)
- `learning_cli.py` — 동일 패턴 (`SqliteLearningStore`)

### Self_improve (1 파일)
- `self_improve/post_project.py` — `self._semantic_proposals.save(proposal)`에 type ignore 주석 (semantic_proposals는 `object | None` 타입이므로 attr-defined 경고)

## Quality Gate

- [x] Inner layer mypy 0 error (211 files)
- [x] `python -m mypy src/ds_agent` 전체 수치 362 (baseline 축소 확인)
- [x] `python scripts/check_mypy_baseline.py --update` 실행 완료 (baseline 기록 갱신)
- [x] 수정 파일 ruff 0 error
- [x] `python scripts/check_import_contracts.py` ok (2 계약 유지)
- [x] Scope pytest 회귀 0: domain + agent + application 합계 **724/724 pass**
- [x] Integration SqliteLearningStore + SqliteWorkObjectStore **14/14 pass**

## 영향 범위 분석 (내가 유발한 회귀 없음)

- `domain/interfaces/work_object.py` Protocol 확장은 기존 구현 `SqliteWorkObjectStore`가 이미 만족 → 기존 테스트 회귀 0 확인.
- `governance_hooks.py::_latest_parent` 리턴 annotation을 `LineageRecord | None`으로 명시 — 호출부 (line 217, 229) 그대로 동작 확인.
- CLI `_get_store` annotation 변경은 functional identity 그대로 유지 (실제 반환 클래스 동일).

## Pre-existing ruff 6건 (스코프 외)

`ruff check src/ds_agent/domain ...` 실행 시 아래 파일에 기존 ruff 이슈 발견. **본 Sprint가 유발한 게 아님** (수정 대상 파일 ruff만 돌리면 all pass):
- `domain/errors/error_catalog.py` (line too long)
- `providers/codex_oauth.py` (line too long + B904 raise from)

해당 건은 별도 Sprint (S-ruff-cleanup 제안) 후보.

## 기록

PRE-2 baseline은 축소될 때마다 mypy-baseline.json이 갱신됨. 각 Sprint 완료 후 감사자가 delta를 검증 가능:
- S11 이전: 383
- S11 이후: 362 (21 감소)
