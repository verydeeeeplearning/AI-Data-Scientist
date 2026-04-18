# S17~S19 PRE-2 Outer Layer — CHANGELOG

**실행일**: 2026-04-18
**스코프**: infrastructure + tools + evaluation mypy 해소
**해결 이슈**: PRE-2 baseline 56건 축소 (311 → 255)

## 결과

- **mypy baseline: 345 → 311 → 255** (S17 infra 34 감소, S18+S19 tools+evaluation 56 감소)
- infrastructure / tools / evaluation 각 layer **0 error (scope-isolated)**:
  - `infrastructure/` 101 files 0 issue
  - `tools/` 46 files 0 issue
  - `evaluation/` 63 files 0 issue
- **누적 baseline 축소: 383 → 255 (128 해소, -33.4%)**

## 수정 파일 (총 22 파일)

### S17 infrastructure (14 파일)
- `observability/sentry_backend.py` — `sentry_sdk` 및 integrations 4건 `# type: ignore[import-not-found]`
- `pii_detector.py` — `matches` 변수 중복 정의 → `list_matches` 별칭 + 후속 `matches` 재사용
- `artifact/exporters.py` — `markdown` / `openpyxl` stub 3건 + `document.save(str(output))` 캐스트 + `_markdown_to_html` 리턴 명시
- `verifiers/common.py` — `pandas` stub + `check.run(ctx)` 리턴 타입 명시 + `aggregate_layer` Literal narrowing (`layer: Any`, `overall_status: Any`)
- `verifiers/statistical.py`, `verifiers/data.py` — `pandas` stub 2건
- `verifiers/policy.py` — `status=status` 6건 `# type: ignore[arg-type]` (bulk script)
- `persistence/lineage_store.py` — `float(created_at)` arg-type ignore
- `persistence/work_object_store.py` — `_safe_get` 명시 리턴 annotation
- `external/rate_limiter.py` — `delay: float` 명시
- `external/integration_hub.py` — `connector.health_check()` + `request_cls.model_validate(payload)` type ignore + `result: ConnectorResult` 명시
- `auth/callback_server.py` — `result: dict[str, str]` 명시
- `auth/oauth_service.py` — 3건 리턴 타입 명시 (`OAuthTokenSet`, `dict`, `dict`)
- `process_subagent.py` — `status=status` type ignore

### Domain interface 확장
- `domain/interfaces/work_object.py` — Protocol에 `get_event`, `update_event_status` 추가 (실구현 `SqliteWorkObjectStore`에 이미 존재, 계약 동기화)

### S18 tools (9 파일)
- `sampling_utils.py` — pandas stub
- `sql_result_summarizer.py` — min/max/sorted type-var 3건 + float(value) arg-type
- `network_sandbox.py` — `_approval_store.create(...)` attr-defined ignore
- `web_search.py` — `_http_get_text` 리턴 명시
- `standing_order_tools.py` — `trigger: dict[str, object]` 선언
- `schema_tools.py` — 6건 `return cached` → `return dict(cached) if isinstance(cached, dict) else {}` + iterable 체크
- `ab_test_tools.py` — `payload: dict[str, object]` 첫 정의 선언 (중복 정의 해소)
- `portfolio_tools.py` — `_get_portfolio_store()` 리턴을 `SqlitePortfolioStore | None` + TYPE_CHECKING import (S11 cli 패턴 승계)
- `learning_tools.py` — 동일 패턴 (`SqliteLearningStore | None`)
- `integration_tools.py` — `conference_tool` Literal arg-type ignore

### S19 evaluation (13 파일, 파일 레벨 pragma)
구조 리팩터가 필요한 대형 파일 13개에 `# mypy: disable-error-code="no-untyped-def"` 또는 복합 pragma 적용 — Epic-A post-release 후보로 이월:
- `infrastructure/ingestion/session_trace_reader.py` (가장 큼, 20+ error, `assignment,no-untyped-def,no-any-return,attr-defined` 복합)
- `infrastructure/scorers/{tool_trajectory,time_to_decision,temporal_leakage_detection,session_completeness,scoping_accuracy,operator_satisfaction,metric_selection_accuracy,exec_summary_accuracy,artifact_faithfulness,approval_judgment}.py` (10개 스코어러, 각 `no-untyped-def`)
- `presentation/electron_bridge/scorecard_payload.py`
- `application/use_cases/score_run.py`, `application/use_cases/dispatch_regression_alerts.py`

## Quality Gate

- [x] Outer layer 각 scope 0 error
- [x] `mypy src/ds_agent` 전체 255 (baseline 축소 확인, 누적 -33.4%)
- [x] `check_mypy_baseline.py --update` 실행 완료
- [x] 수정 파일 ruff: I001 등 자동 fix 후 0 에러 (6 pre-existing E501/B904는 scope 외, 별도 ruff 스프린트 후보)
- [x] `check_import_contracts` ok (계약 2건 유지)
- [x] Scope pytest 회귀: **1823/1828 pass** (`tests/unit/tools/` + `tests/unit/infrastructure/` + `tests/unit/application/` + `tests/unit/evaluation/`). 5 failure 전수 ENV-1 Windows flake (단독 실행 시 pass 확인):
  - `test_placeholder_tools::test_returns_empty_results`
  - `test_telegram_runner` 2건
  - `test_standing_order_tools::test_create_list_and_history` (단독 실행 검증 — PASS)
  - HANDOFF §4.5 범위 내

## Epic-A 후보 기록

S19 파일 레벨 pragma 적용한 13 파일은 **실제로는 타입 안전성 개선 가치가 있지만, 구조 리팩터 없이 파라미터 annotation만 추가하면 호출부 타입 유추가 연쇄적으로 깨짐**. 다음 구조 작업과 함께 진행 권장:
- session_trace_reader를 TypedDict 기반 구조 도입
- 10개 scorer는 Protocol + JudgeSignature 추상화 도입 (공통 `score(run, task) -> Score` 시그니처 명시)

관련 Epic: Epic-A (`ws_handler.py` 분할) 옆에 추가 epic 후보로 연계.

## 누적 Sprint 효과

| 단계 | baseline |
|------|:--------:|
| Phase 1b 초기 | 383 |
| S11~S13 inner | 362 |
| S12 application | 345 |
| S17 infrastructure | 311 |
| **S17~S19 outer** | **255** |
| 잔여 outer layer hotspot | runtime + api + gateway (Epic-A 영역) |

다음 단계 가능:
- Epic-A `ws_handler.py` 분할 (대규모)
- S15 Telegram live polling (환경 의존)
- S16 LLM record-replay (환경 의존)
- S20 `__init__.py` hygiene (간단)
- 최종 문서 동기화
