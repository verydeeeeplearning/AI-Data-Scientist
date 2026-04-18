# Implementation Plan: Post-Release Follow-ups (잔존 gap 해소 로드맵)

**Status**: **Approved (user delegation, 2026-04-18)** — Decision Log §24 기반 실행 착수
**Started**: 2026-04-17
**Last Updated**: 2026-04-18 (Decision Log 추가, S7 착수)
**상위 문서**:
- `Docs/DS_AGENT_COMPREHENSIVE_REPORT_2026-04-17_ADDENDUM.md` (Addendum, 특히 §9.4)
- `Docs/qa_run_2026-04-17/HANDOFF_NEXT_AGENT.md` §13
- `Docs/qa_run_2026-04-17/D18_release/RELEASE_GATE_DECISION.md`
- `Docs/plans/PLAN_post_qa_risk_mitigation_2026-04-17.md` (직전 사이클)

**CRITICAL INSTRUCTIONS** (이전 계획서 동일):
1. 각 Sprint 완료 후 체크박스 갱신, Quality Gate 전수 재실행, "Last Updated" 갱신, Notes 섹션에 학습 기록.
2. Quality Gate 실패 상태에서 다음 Sprint로 진행 금지.
3. 수정 agent와 재감사 agent는 **별도 역할**. 동일 agent가 작성·판정 금지.

---

## 1. Overview

### 1.1 해결 대상 잔존 gap 5가지 (Addendum §9.4 기준)

| ID | 이름 | 현재 상태 | 소스 |
|:--:|------|----------|------|
| G1 | **PRE-2 레이어별 mypy 해소** | baseline freeze (383 error) — 신규 error 차단만 | Post-QA Phase 1b |
| G2 | **R-1/R-2/R-3 원자성** | 동형 이중-write 패턴 3건 | S6 RECOMMENDATIONS §R-1~R-3 |
| G3 | **Telegram live polling parity** | `python-telegram-bot` 미설치로 factory wiring 수준만 검증 | Phase 3 riport |
| G4 | **LLM record-replay fixture** | mocked provider가 deterministic error를 parity signal로 사용 | Phase 3 noted gap |
| G5 | **문서·설정 정합화** | RC-5, C15-O6, D5-1, NOTE-B08-1, B11 D1~D4 등 누적 | Tier 2/3 agent 보고서 |

### 1.2 Sprint 분할 원칙

- **작게 자르고 자주 릴리스**: 각 Sprint 1~4시간. 큰 구조 리팩터(예: ws_handler.py 분할)는 **더 큰 범위의 Epic**으로 분리.
- **TDD 엄수**: 모든 Sprint RED → GREEN → REFACTOR. 수정 전에 실패 재현 테스트부터.
- **Clean Architecture 유지**: 내부 계층 의존성 방향 불변. 새 port 필요 시 기존 S6 패턴 복제.
- **baseline 축소 원칙**: PRE-2 Sprint는 완료 후 반드시 `python scripts/check_mypy_baseline.py --update`로 baseline 축소.

### 1.3 전체 Sprint 지도

| Sprint | 이름 | gap | 예상 시간 | 선행 | 위험도 |
|:------:|------|:---:|:---------:|:----:|:-----:|
| **S7** | Doc alignment (5건 일괄) | G5 | 1~2h | 없음 | Low |
| **S8** | Dead config cleanup (C15-O6 등) | G5 | 30m | 없음 | Low |
| **S9** | R-1 + R-2 원자성 | G2 | 2~3h | 없음 (S6 port 재사용) | Low |
| **S10** | R-3 원자성 (신규 atomic 메서드) | G2 | 2~3h | S9 권장 | Low-Med |
| **S11** | PRE-2 domain + agent + memory (19건) | G1 | 2~3h | 없음 | Low |
| **S12** | PRE-2 application (23건) | G1 | 3~4h | S11 권장 | Low-Med |
| **S13** | PRE-2 skills/providers/cli/self_improve (9건) | G1 | 1~2h | 없음 | Low |
| **S14** | RC-5 in-adapter kill-switch (RFC + 구현) | G5 | 3~4h | S7 (문구) | Med |
| **S15** | Telegram live polling parity | G3 | 2~3h | 없음 | Med |
| **S16** | LLM record-replay fixture | G4 | 4~6h | 없음 | Med-High |
| **S17** | PRE-2 infrastructure (36건) | G1 | 3~4h | S11-S13 | Med |
| **S18** | PRE-2 tools (18건) | G1 | 2~3h | 없음 | Low-Med |
| **S19** | PRE-2 evaluation (38건) | G1 | 3~4h | S11-S13 | Med |
| **Epic-A** | PRE-2 runtime + api + gateway (345건) + `ws_handler.py` 분할 | G1 | 1~2주+ | 이전 S | **High** |
| **Epic-B** | R-4 일반화된 txn port RFC | G2 | 1주 (RFC+prototype) | S9/S10 | Med |

**단일 Sprint 실행 후 Hard Gate 전수 통과 시에만 다음 Sprint 진입.** Epic은 별도 릴리스 사이클.

---

## 2. Sprint S7 — Documentation Alignment (일괄)

### 2.1 스코프 (5건)
| ID | 파일 | 수정 내용 |
|----|------|----------|
| D5-1 | `Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md:249` | `<ds:review_artifacts>...</ds:review_artifacts>` → `<!-- DS_REVIEW_ARTIFACTS {...} -->` |
| NOTE-B08-1 | 계획서 §5.4 Promotion Gate 조항 | "3-role 중 2명 승인 → staging" → "3-of-3 승인 (staging + production)" + 근거 코드 경로 링크 |
| B11-D1 | 계획서 §5.7.1 / §6.1 | portfolio terminal states `{completed, failed, cancelled}` → `{completed, cancelled, archived}` |
| B11-D2 | 계획서 §5.7.3 | PriorityCalculator coefficients `0.5/1.0/0.2` → `2.0/3.0/0.5` + "ordering intent는 동일 (P0≫P3, overdue 지배)" 주석 |
| B11-D3 | 계획서 §5.7.4 | WaitCondition 문구에 "Timer만 fully functional; Approval/DataFreshness/External는 adapter 대기 (v2 maturity gap)" 추가 |

추가 연관 문구:
- `Docs/qa_run_2026-04-17/HANDOFF_NEXT_AGENT.md` §4.6 이미 정정됨 (Phase 0에서). 재확인만.
- Addendum §5 "2026-04-17 검증 기준선"은 실측 반영됨.

### 2.2 절차
- [ ] 7.1 각 문서 해당 라인 Edit.
- [ ] 7.2 각 수정에 "(updated 2026-04-17, source: S7)" 주석.
- [ ] 7.3 문서 전반 reflow (다른 문구와 상충 없는지 self-check).
- [ ] 7.4 `Docs/qa_run_2026-04-17/S7_doc_alignment/CHANGELOG.md` 작성.

### 2.3 Quality Gate
- [ ] 5건 전수 수정 완료, diff 전수 기록
- [ ] 문서 markdown lint 통과 (`python -m markdown` 또는 mdl 없음 시 눈으로 확인)
- [ ] 변경 이력 테이블 업데이트

### 2.4 Risk
**Low** — 문서 수정만. 코드 무관.

---

## 3. Sprint S8 — Dead Config Cleanup

### 3.1 스코프
- **C15-O6**: `ds-agent-api.spec:105` `'ds_agent.memory.session_db'` 제거. (해당 모듈 없음 확인됨: `src/ds_agent/memory/` contents = `code_registry, domain_kb, experiment_compare, experiment_log, project_store, semantic/, unified_store`)
- 잠재 추가 스캔: spec의 hiddenimports 전체를 `src/ds_agent/` 실제 파일 존재 여부와 대조.

### 3.2 절차
- [ ] 8.1 RED: PyInstaller를 재빌드하면 WARNING 로그 재현.
- [ ] 8.2 spec의 hiddenimports 전수와 `src/ds_agent/**/*.py` 비교 스크립트 `.tmp/qa_S8/check_hiddenimports.py` 작성.
- [ ] 8.3 존재하지 않는 import 전부 제거.
- [ ] 8.4 GREEN: `python scripts/build_backend.py` 재실행, WARNING 0 확인.
- [ ] 8.5 smoke 5/5 재확인 (C15 harness 재사용).

### 3.3 Quality Gate
- [ ] hidden-import WARNING 0
- [ ] binary 크기 차이 ±1MB 이내 (다른 변화 없음 증명)
- [ ] C15 smoke 5/5 유지

### 3.4 Risk
**Low** — spec 수정. 실수로 실제 필요한 import 제거 시 런타임 실패 가능하나, smoke가 catches.

---

## 4. Sprint S9 — R-1 + R-2 원자성 (S6 port 재사용)

### 4.1 스코프
| R | 파일 | 문제 라인 |
|:-:|------|----------|
| R-1 | `src/ds_agent/application/learning/promote_learning_item.py:94-95` | `save_promotion_record(record)` + `save_item(updated)` 별도 commit |
| R-2 | `src/ds_agent/application/learning/deprecate_learning_item.py:81-83` | `save_item(updated)` + `save_deprecation_record(record)` 별도 commit |

### 4.2 수정 전략
**R-2는 S6의 `LearningStoreAtomicPort.save_item_and_deprecation`을 그대로 사용** (시그니처 일치 — S6 RECOMMENDATIONS §R-2 명시).
**R-1은 신규 메서드 필요**: `save_promotion_and_item(promotion: PromotionRecord, item: LearningItem)`.

### 4.3 절차 (TDD)
#### RED
- [ ] 9.1 `tests/unit/application/test_promote_atomicity.py` — `save_item` 실패 주입 → `save_promotion_record`만 persist된 상태 재현 (현 코드 fail 확인).
- [ ] 9.2 `tests/unit/application/test_deprecate_atomicity.py` — 동일 패턴.

#### GREEN
- [ ] 9.3 `LearningStoreAtomicPort`에 `save_promotion_and_item` 추가 (Port `src/ds_agent/application/ports/learning_store_port.py`).
- [ ] 9.4 `SqliteLearningStore`에 구현 (S6 `save_item_and_deprecation`와 동일 패턴: `BEGIN IMMEDIATE/COMMIT/ROLLBACK`).
- [ ] 9.5 `PromoteLearningItemUseCase.execute` 수정 — 신규 atomic 메서드 호출.
- [ ] 9.6 `DeprecateLearningItemUseCase.execute` IMMEDIATE 경로 수정 — 기존 `save_item_and_deprecation` 호출.
- [ ] 9.7 테스트 GREEN 확인.

#### REFACTOR
- [ ] 9.8 R-4 대비 준비: atomic 메서드가 3개가 됐으므로 `R-4 RFC` 이슈에 note.
- [ ] 9.9 docstring 정리.

### 4.4 정적 검증
- [ ] `ruff check` 0 error
- [ ] `python scripts/check_import_contracts.py` ok
- [ ] `lint-imports` 0 violation
- [ ] `python scripts/check_mypy_baseline.py` 0 new

### 4.5 재감사 절차
B11 Round 3 (scope: Path 6 promotion + Path 7 auto-deprecation + R-1/R-2 atomicity probe 자체). B11 Round 2와 동일 프롬프트에 "R-1/R-2 atomicity probe 추가" 지시.

### 4.6 Quality Gate
- [ ] 2 신규 테스트 RED→GREEN
- [ ] 기존 `test_rollback_atomicity.py` + `test_promote_learning_item.py` + `test_deprecate_learning_item.py` 회귀 0
- [ ] 정적 검증 4종 clean
- [ ] B11 Round 3 재감사 pass

### 4.7 Risk
**Low**. S6 패턴 복제라 새로운 구조 변경 없음.

---

## 5. Sprint S10 — R-3 원자성 (신규 atomic 메서드)

### 5.1 스코프
`src/ds_agent/application/learning/review_learning_item.py:73-74`:
```python
self._store.save_review_event(event)
self._store.save_item(updated)
```

### 5.2 수정 전략
신규 atomic 메서드: `save_review_event_and_item(event: ReviewEvent, item: LearningItem)`.
**Alternative**: R-4 시점을 앞당겨 `begin_txn() -> ContextManager` 일반 port 채택 — 단, 이 경우 S10이 Epic-B로 승격되므로 별도 판단 필요.

### 5.3 절차 (TDD)
#### RED
- [ ] 10.1 `tests/unit/application/test_review_atomicity.py` — `save_item` 실패 주입 → `save_review_event`만 persist.

#### GREEN
- [ ] 10.2 `LearningStoreAtomicPort`에 `save_review_event_and_item` 추가.
- [ ] 10.3 `SqliteLearningStore` 구현.
- [ ] 10.4 `ReviewLearningItemUseCase.execute` 수정.
- [ ] 10.5 테스트 GREEN.

#### REFACTOR
- [ ] 10.6 S9 + S10 완료 후 atomic 메서드가 총 3개 → Epic-B R-4 RFC 트리거.

### 5.4 Quality Gate
S9와 동일 구조.

### 5.5 Risk
**Low-Med**. ReviewEvent invariant 유지 중요 (append-only semantics).

### 5.6 재감사
B11 Round 3에 포함 (S9 재감사와 함께).

---

## 6. Sprint S11 — PRE-2 Domain + Agent + Memory 레이어 해소 (19건)

### 6.1 스코프 (전수 목록)

#### Domain (9건)
| 파일:라인 | 코드 | 요약 |
|-----------|------|------|
| `domain/value_objects/execution_policy.py:26` | no-redef | `allowed_domains` 중복 정의 |
| `domain/value_objects/connector.py:133` | arg-type | `int(...)` 호출 시 None 허용 필요 — narrowing |
| `domain/entities/standing_order.py:90` | arg-type | `float(object)` — 타입 확정 |
| `domain/entities/memory.py:45` | no-any-return | 반환 Any → float 명시 |
| `domain/entities/feature.py:20` | call-overload | `list(object)` — Iterable 타입 확정 |
| `domain/dtos/verifier_context.py:32` | arg-type | Pydantic Field default_factory 타입 Literal 정합 |

#### Agent (9건)
| 파일:라인 | 코드 | 요약 |
|-----------|------|------|
| `agent/confidence_scorer.py:88-89` | operator / arg-type | `float \| None` 곱셈 + `_clamp_score` 호출 |
| `agent/reporting_hooks.py:40, 47` | index | `object` indexable 확정 |
| `agent/governance_hooks.py:253` | arg-type | `LineageCaptureService.capture_evaluation` metrics `dict[str, float]` vs `dict[str, object]` — Mapping 변수형 고려 |
| `agent/governance_hooks.py:273` | no-untyped-def | 리턴 annotation 추가 |

#### Memory (1건)
| 파일:라인 | 코드 | 요약 |
|-----------|------|------|
| `memory/unified_store.py:134` | no-any-return | 반환 Any → str 명시 |

### 6.2 절차
- [ ] 11.1 baseline snapshot 저장 (`python scripts/check_mypy_baseline.py` 현 상태 기록).
- [ ] 11.2 각 error를 개별 커밋 단위로 수정 — 한 파일씩 또는 관련 그룹씩.
  - confidence_scorer.py: `score | None` 경로 early-return 또는 `score = 0.0 if score is None else score` 명시.
  - reporting_hooks: `cast(dict, payload)` 또는 TypedDict 도입.
  - governance_hooks: `Mapping[str, object]` 로 시그니처 변경 (호환성 체크).
  - feature.py: `list(cast(Iterable[Any], raw))` 또는 `raw: Iterable[...]` annotate.
  - verifier_context.py: default_factory 타입 명시 `default_factory=lambda: [cast(Literal[...], ...)]`.
- [ ] 11.3 각 수정 후 해당 파일만 `mypy`로 확인 (fast feedback).
- [ ] 11.4 전체 완료 후 `python -m mypy src/ds_agent` → 19 error 감소 확인.
- [ ] 11.5 baseline update: `python scripts/check_mypy_baseline.py --update`.

### 6.3 Quality Gate
- [ ] 해당 19 error 전수 해소 (mypy 보고 기준).
- [ ] 기존 테스트 scope-isolated 회귀 0 (`tests/unit/domain/`, `tests/unit/agent/`, `tests/unit/memory/`).
- [ ] `ruff check` + `check_import_contracts` + `lint-imports` clean.
- [ ] `check_mypy_baseline --update` 후 검증 모드 `exit 0`.

### 6.4 Risk
**Low**. domain은 pure type annotation + narrowing. agent/memory는 Protocol/TypedDict 도입 가능성 있으나 계층 경계 보존.

### 6.5 주의
`governance_hooks.py:253`에서 `LineageCaptureService` 시그니처를 `Mapping[str, object]`로 바꾸면 **모든 호출부 영향** — scope 외 파일도 영향. 이 경우 "시그니처 변경 없이 캐스팅"을 우선 (`cast(dict[str, object], metrics)`).

---

## 7. Sprint S12 — PRE-2 Application 레이어 해소 (23건)

### 7.1 스코프 주요 파일

| 파일 | error 수 | 핵심 이슈 |
|------|:--------:|----------|
| `artifact_generator.py` | 6 | `section: object` iterable/indexable — TypedDict 또는 Pydantic 도입 |
| `lineage_capture_service.py` | 2 | dict 변수성 + `os.sys` 접근 |
| `usage_summary.py` | 4 | `float(object)`, `int(object)`, dict 변수성 |
| `ab_test_analyzer.py` | 1 | `scipy-stubs` 설치 또는 `# type: ignore[import-untyped]` |
| `feature_registry_usecases.py` | 1 | 파라미터 annotation 누락 |
| `submit_learning_proposal.py` | 1 | Literal scope narrowing |
| `reproducibility_exporter.py` | 1 | 변수 타입 충돌 |
| `run_diff_usecases.py` | 1 | Literal direction narrowing |

### 7.2 절차
- [ ] 12.1 `ab_test_analyzer.py`: `scipy-stubs` dev extras 추가 (pyproject.toml). 또는 파일 상단 `# type: ignore[import-untyped]`.
- [ ] 12.2 `artifact_generator.py`: `section` 변수에 TypedDict 도입 — scope 내 변경만.
- [ ] 12.3 `usage_summary.py`: dict 값에 Union 명시 + `float(value if isinstance(value, (int, float)) else 0.0)` 패턴.
- [ ] 12.4 `submit_learning_proposal.py`, `run_diff_usecases.py`: Literal 검증 로직 추가 (value가 Literal 집합에 속하는지 validate).
- [ ] 12.5 `lineage_capture_service.py`: `os.sys` 접근을 `import sys` + `sys.X`로 교체.
- [ ] 12.6 `feature_registry_usecases.py:62`: 파라미터 annotation 추가.
- [ ] 12.7 `reproducibility_exporter.py:37`: 변수 재정의 분리.
- [ ] 12.8 전체 `mypy` → 23 error 감소 확인.
- [ ] 12.9 baseline update.

### 7.3 Quality Gate
S11과 동일.

### 7.4 Risk
**Low-Med**. `artifact_generator.py` TypedDict 도입 시 호출부 영향 최소화 검증 필요.

---

## 8. Sprint S13 — PRE-2 skills/providers/cli/self_improve (9건)

### 8.1 스코프
| 파일:라인 | 코드 | 요약 |
|-----------|------|------|
| `skills/hub.py:352, 354` | index | indexed assignment target 타입 확정 |
| `providers/gemini_oauth.py:82` | attr-defined | `load_by_provider` 접근 — 적절한 타입 캐스팅 |
| `self_improve/post_project.py:205` | attr-defined | `save` 메서드 접근 |
| `cli/portfolio_cli.py:45`, `learning_cli.py:63` | no-untyped-def | 리턴 annotation 추가 |
| `cli/integration_cli.py:79, 82` | attr-defined | `WorkObjectStore.list_events_by_status` 존재 여부 확인 — 메서드 실제로 없으면 코드 버그 가능성 |

### 8.2 절차
- [ ] 13.1 `cli/integration_cli.py`: `list_events_by_status` 메서드 실존 여부 확인. 없으면 해당 CLI 기능이 **실제로 동작하지 않음** → 버그 fix 또는 CLI 기능 제거.
- [ ] 13.2 나머지 annotation 추가 / 타입 narrowing.
- [ ] 13.3 mypy baseline update.

### 8.3 Quality Gate
- [ ] 9 error 해소
- [ ] `integration_cli` 실동작 확인 (subprocess 호출) — 특히 13.1에서 bug 발견 시 fix 포함
- [ ] 기존 CLI test 회귀 0

### 8.4 Risk
**Low-Med**. `integration_cli` attr-defined 2건은 **runtime AttributeError 가능성**이므로 잠재 bug일 수도 있음. 발견 시 scope 확장 (fix 포함).

---

## 9. Sprint S14 — RC-5 In-Adapter Kill-Switch (RFC + 구현)

### 9.1 배경
B10 agent가 발견: Slack/Jira/Confluence/Notion/Git connector들이 **adapter 내부에 `_is_configured()` 가드가 없음**. Real mode egress는 hub policy layer에서만 gating. 만약 hub policy가 우회되면 adapter가 real egress 가능.

### 9.2 스코프
| 파일 | 현재 | 개선 |
|------|------|------|
| `src/ds_agent/infrastructure/external/slack_connector.py` | no `_is_configured` | 모든 send 경로 시작부에 guard |
| `src/ds_agent/infrastructure/external/jira_connector.py` | 동 | 동 |
| `src/ds_agent/infrastructure/external/confluence_connector.py` | 동 | 동 |
| `src/ds_agent/infrastructure/external/notion_connector.py` | 동 | 동 |
| Git connector (위치 확인 필요) | 동 | 동 |

Email/Calendar는 B10 리포트상 이미 kill-switch 보유 — scope 외.

### 9.3 RFC (S14-Prelude)
- [ ] 14.1 `Docs/rfc/RFC_2026-04-adapter_killswitch.md` 작성:
  - 현재 계층별 가드 비교
  - 제안 방식 (전역 `DS_AGENT_NETWORK_EGRESS_ENABLED=false` 환경변수 + adapter guard + integration test)
  - 대안 비교 (hub 단일 게이트 vs defense-in-depth)
  - 대안별 pros/cons
  - 승인 후 구현 단계

### 9.4 구현 (RFC 승인 후)
#### RED
- [ ] 14.2 각 connector에 대해 `dispatch` 계열 메서드 호출 시 `_is_configured()==False`면 `ConnectorDisabledError` 발생 — 테스트.

#### GREEN
- [ ] 14.3 각 connector에 `_is_configured() -> bool` 구현. 환경변수 + 설정 조합 판정.
- [ ] 14.4 `send`/`publish`/`post` 등 egress 함수 시작부에 guard.
- [ ] 14.5 기존 테스트 회귀 없음 (simulated mode 유지).

### 9.5 Quality Gate
- [ ] RFC 사용자 승인
- [ ] 5 connector 각각 guard 작동 (테스트 5건)
- [ ] `DS_AGENT_NETWORK_EGRESS_ENABLED=false` 시 모든 connector dispatch 거부
- [ ] B10 재감사 pass (Round 2 spec)

### 9.6 Risk
**Medium**. RFC 승인 필요. 구현 중 real mode 호환성 깨뜨리지 않게 주의.

---

## 10. Sprint S15 — Telegram Live Polling Parity

### 10.1 배경
Post-QA Phase 3 결과: `python-telegram-bot`이 host venv/dist에 없어 C13 process-level parity에서 Telegram은 factory wiring 수준만 검증. Updater polling 실경로 미검증.

### 10.2 스코프
- [ ] 15.1 `uv sync --extra channels` — `python-telegram-bot>=21.0` 설치.
- [ ] 15.2 또는 `pyproject.toml`의 `dev` extras에 `python-telegram-bot` 추가 여부 논의 (dev 환경 표준화).

### 10.3 Harness 확장
- [ ] 15.3 `scripts/parity_harness/harness_telegram.py` 개선:
  - 현재: subprocess + Telegram-shaped session id
  - 개선: `python-telegram-bot` test harness 사용하여 fake `Update` 객체 주입 → `TelegramSensor`가 receive → 실제 polling 경로 탐 → backend 경유
  - real bot token 사용 금지: `TestApplicationBuilder`의 fake bot 사용
- [ ] 15.4 3 시나리오 (P-01/P-02/P-03) 각각 실행.

### 10.4 절차
- [ ] 15.5 RED: 현 harness_telegram 그대로 실행하여 "factory wiring only" 기록.
- [ ] 15.6 GREEN: `python-telegram-bot` `TestUpdater` 또는 `ApplicationBuilder.bot(fake_bot)` 도입. fake Update 주입 → message handler 경로 → backend WS 호출 추적.
- [ ] 15.7 3 시나리오 × 1 채널 = 3 추가 run. C13 process-level과 동등한 parity 매트릭스.

### 10.5 Quality Gate
- [ ] 3 Telegram run complete
- [ ] 비인프라 필드 (기존 CLI+Electron과 동일 parity signal)
- [ ] real Telegram API 호출 0건 (fake bot 검증)
- [ ] `Docs/qa_run_2026-04-17/C13_parity_process_level/` Round 3 supplement 작성

### 10.6 Risk
**Medium**. `python-telegram-bot` test harness 사용법 학습 + fake Update 객체 구조 파악 필요.

---

## 11. Sprint S16 — LLM Record-Replay Fixture

### 11.1 배경
Post-QA Phase 3에서 parity signal로 **mocked provider의 deterministic error body**(`DSA-LLM-001`) hash를 사용. "같은 error로 수렴"은 증명되지만 "같은 성공 응답으로 수렴"은 증명되지 않음.

### 11.2 목표
LLM provider의 실제 성공 응답(cassette)을 녹화 → 재생하여 3채널 모두 동일 LLM 응답을 받았을 때 최종 DeliveryPack이 byte-identical임을 증명.

### 11.3 기술 선택지

| 방식 | 장점 | 단점 | 권장 |
|------|------|------|-----|
| **VCR.py** | HTTP 레벨 자동 캡처, 널리 사용 | HTTP 기반 provider(Anthropic, OpenAI) 한정, streaming 지원 제한 | 1순위 (HTTP provider에 한정) |
| **pytest-recording** | VCR.py 기반 pytest 플러그인 | 동 | VCR.py 채택 시 함께 |
| **직접 fixture** (JSONL dump) | streaming/SDK 어떤 것도 대응 | 녹화 인프라 수동 | 3순위 |
| **respx** (httpx mock) | 현대적, async 지원 | cassette 파일 수동 관리 | 2순위 |

**권장**: VCR.py + pytest-recording (Anthropic/OpenAI provider 커버), Codex 같은 subprocess 기반은 직접 fixture.

### 11.4 절차
#### RFC (S16-Prelude)
- [ ] 16.1 `Docs/rfc/RFC_2026-04-llm_record_replay.md`:
  - cassette 파일 저장 위치 (`tests/fixtures/llm_cassettes/`)
  - secret sanitization 정책 (API key는 기록 금지)
  - cassette 갱신 정책 (provider API 변경 시 re-record)
  - CI에서 record mode 금지 (replay only)

#### 구현
- [ ] 16.2 `VCR.py` + `pytest-recording` dev extras 추가.
- [ ] 16.3 기존 `tests/integration/providers/` 테스트 중 1건을 pilot으로 cassette 녹화 (로컬 real API 1회 사용 — key 기록 금지).
- [ ] 16.4 `scripts/parity_harness/` 확장: replay mode로 3 시나리오 × 3 채널 run.
- [ ] 16.5 9 run의 DeliveryPack body byte-identical 확인.

### 11.5 Quality Gate
- [ ] RFC 승인
- [ ] Pilot cassette 1건 replay 성공
- [ ] 9 run byte-identical DeliveryPack body
- [ ] CI에서 record mode 금지 자동 검증 (env var `VCR_RECORD_MODE=none` 강제)
- [ ] cassette 파일에 secret 누출 0 (git-secrets 또는 grep 자동 검사)

### 11.6 Risk
**Medium-High**.
- 녹화 당시 real API call 1회 필요 (비용 발생, 소액).
- cassette 무효화 주기 관리 (provider API 변경 시 CI fail).
- streaming 응답 녹화는 VCR.py가 완벽 지원 안 함 — fallback 필요.

### 11.7 의존성
S15 완료 후 권장 (Telegram 포함 전수 9 run).

---

## 12. Sprint S17 — PRE-2 Infrastructure 레이어 (36건)

### 12.1 스코프
`src/ds_agent/infrastructure/` 전수 36 error. 저장소 adapter, persistence, exporters 등.

### 12.2 특이점
- `pii_detector.py:142` no-redef — 중복 정의 해소 (S11과 동일 패턴)
- `sqlite_*.py` 계열: DB row → dataclass 변환 타입 캐스팅
- `exporters/`: 포맷별 cell type narrowing

### 12.3 절차
- [ ] 17.1 파일 그룹별 분할 해소 (persistence / exporters / external / secrets / observability).
- [ ] 17.2 각 그룹 후 mypy baseline update.

### 12.4 Quality Gate & Risk
S11/S12와 동일 구조. Medium risk (가장 많은 adapter 코드).

---

## 13. Sprint S18 — PRE-2 Tools 레이어 (18건)

### 13.1 스코프
`src/ds_agent/tools/` 18 error — 주로 `sql_result_summarizer.py` type-var (4건) 포함.

### 13.2 특이점
`sampling_utils.py:5` pandas-stubs — `pandas-stubs` dev extras 추가 결정 필요 (pandas는 optional이지만 여러 tool이 사용).

### 13.3 Quality Gate
S11과 동일.

### 13.4 Risk
**Low-Med**.

---

## 14. Sprint S19 — PRE-2 Evaluation 레이어 (38건)

### 14.1 스코프
`src/ds_agent/evaluation/`의 평가 하네스, 스코어러 관련 38건.

### 14.2 특이점
- Scoring 로직의 Any 반환 다수 (no-any-return) — Literal/TypedDict 도입 지연되어 누적
- JSON payload → dataclass 변환에서 타입 narrowing

### 14.3 Quality Gate & Risk
S11과 동일. Medium risk.

---

## 15. Epic-A — PRE-2 Runtime + API + Gateway (345건, `ws_handler.py` 포함)

### 15.1 규모
- runtime 137건
- api 129건 (대부분 `ws_handler.py` 4,434줄)
- gateway 79건

### 15.2 분리 이유
1. `ws_handler.py` 자체가 유지보수 hotspot (§7.4). 타입 annotation만 추가해도 **구조 변경이 수반**될 가능성이 매우 높음.
2. 단일 Sprint로 처리 불가 — 2~3주 규모.
3. 위험도 높음.

### 15.3 권장 접근
단일 Sprint 금지. 다음 Epic 단위로 분할:
- **Epic-A1**: `ws_handler.py` **수직 분할** (RPC 계층 + dispatch + state 관리 등). mypy 해소는 분할 후.
- **Epic-A2**: runtime autonomy/sensor/policy 타입 강화.
- **Epic-A3**: gateway telegram/channel 라우팅 타입 강화.

각 Epic은 **별도 PLAN_ 파일**로 분리 권장.

### 15.4 선행 조건
S11~S19 전부 완료 (쉬운 레이어부터) + R-4 RFC (Epic-B) 승인.

---

## 16. Epic-B — R-4 일반화된 Transaction Port RFC

### 16.1 배경
S6 → S9 → S10으로 3개 원자 메서드 누적. R-4 RECOMMENDATIONS에서 일반화된 `begin_transaction()` port 필요성 제기.

### 16.2 스코프
- [ ] B.1 `Docs/rfc/RFC_2026-04-learning_store_txn_port.md`:
  - 현재 4개 원자 메서드 (S6 `save_item_and_deprecation`, S9 `save_promotion_and_item`, S10 `save_review_event_and_item`)
  - 제안 `LearningStoreTxnPort.begin_transaction() -> ContextManager[LearningStoreBatch]`
  - batch interface 설계
  - Protocol + ContextManager 타입 정합성 분석
  - migration 경로
- [ ] B.2 RFC 승인 후 prototype
- [ ] B.3 기존 원자 메서드 deprecation 전략

### 16.3 선행
S9 + S10 완료 후 시작.

### 16.4 Risk
**Medium**. Port 설계가 깨지면 구조 전체에 영향.

---

## 17. 전체 로드맵 & 예상 시간

### 17.1 직렬 실행 (권장)

| 우선순위 | Sprint | 예상 시간 | 누적 |
|:--------:|:------:|:---------:|:-----:|
| 1 | S7 Doc alignment | 1.5h | 1.5h |
| 2 | S8 Dead config | 0.5h | 2h |
| 3 | S9 R-1+R-2 | 2.5h | 4.5h |
| 4 | S10 R-3 | 2.5h | 7h |
| 5 | S11 domain+agent+memory | 2.5h | 9.5h |
| 6 | S13 skills+providers+cli | 1.5h | 11h |
| 7 | S12 application | 3.5h | 14.5h |
| 8 | S18 tools | 2.5h | 17h |
| 9 | S17 infrastructure | 3.5h | 20.5h |
| 10 | S19 evaluation | 3.5h | 24h |
| 11 | S14 RC-5 kill-switch | 3.5h | 27.5h |
| 12 | S15 Telegram polling | 2.5h | 30h |
| 13 | S16 LLM record-replay | 5h | 35h |
| 14 | Epic-B R-4 RFC | 1주+ | 별도 |
| 15 | Epic-A runtime/api/gateway | 2~3주 | 별도 |

**Sprint S7~S19 누적: ~35시간 (5~7 영업일)**
**Epic-A/B 별도 릴리스 사이클.**

### 17.2 병렬 실행 옵션 (rate limit 주의)
- S7 + S8 동시
- S9 + S11 동시 (코드 영역 겹침 없음)
- S13 + S18 동시
- S14 RFC + S15 준비 동시

### 17.3 Dependency 그래프
```
S7 → S8
S9 → S10 → (Epic-B)
S11 → S12 → S17 → S19
      S13 → S18
S14 (RFC) → S14 (impl) → B10 재감사
S15 → (선택) S16
S16 → process-level Round 3 supplement
Epic-B ← S9, S10
Epic-A ← S11~S19
```

---

## 18. 성공 기준 (전체 로드맵)

- [ ] mypy baseline 0 (또는 최소 50 이하로 축소)
- [ ] 4개 원자 Use Case 전원 atomic (S6 + S9 + S10)
- [ ] R-4 일반화 port RFC 채택 여부 결정
- [ ] process-level parity 9/9 모든 채널 (Telegram real polling 포함)
- [ ] LLM record-replay로 byte-identical DeliveryPack 증명
- [ ] 5 connector 전수 in-adapter kill-switch 구현
- [ ] 5건 문서 정합 + dead config 청소
- [ ] 모든 변경이 `import-linter` 2 계약 유지
- [ ] 기존 테스트 회귀 0

---

## 19. Risk Register (요약)

| Sprint | 최대 위험 | 확률 | 영향 | 완화책 |
|:------:|----------|:----:|:----:|--------|
| S7 | 문서 reflow로 인한 상호참조 깨짐 | L | L | 수정 후 grep 검증 |
| S8 | 실제 필요한 hidden import를 제거 | L | M | smoke 5/5 재확인 |
| S9 | Port 변경이 다른 use case 영향 | L | M | 기존 메서드 유지, 신규만 추가 |
| S10 | ReviewEvent invariant 위반 | L-M | M | append-only semantics 보존 검증 |
| S11-S19 | annotation 변경이 runtime 동작 변경 | L | H | 각 파일별 scope-isolated 회귀 + logic 동등성 수동 확인 |
| S14 | RC-5 구현이 real mode 호환성 깨뜨림 | M | M | RFC 후 feature flag 보호 |
| S15 | fake bot API가 real 환경과 diverge | M | L | 3채널 diff로 발견 |
| S16 | cassette 무효화로 CI flake | M | M | pinned cassette 버전 + record mode 금지 |
| Epic-A | `ws_handler.py` 분할 중 기능 회귀 | H | H | Epic-A1 분할 자체를 별도 대형 PR로 |
| Epic-B | Port 재설계가 보일러플레이트 증가 | M | M | prototype 후 채택 |

---

## 20. Rollback Strategy

### 20.1 Sprint 단위
각 Sprint 완료 시 독립 commit. 문제 발견 시 해당 commit만 revert.

### 20.2 baseline 관리
모든 PRE-2 Sprint는 `mypy-baseline.json`을 **축소**. 만약 revert 발생하면 baseline도 revert하여 기준 불일치 방지.

### 20.3 긴급 중단 조건
- 어떤 Sprint 중이라도 **기존 기능 회귀가 회귀 Sprint 범위 밖에서 발견**되면 즉시 중단.
- D17 no-change delta ≠ 0 재발현 시 release decision 재심사.

---

## 21. Progress Tracking

- S7: 0%
- S8: 0%
- S9: 0%
- S10: 0%
- S11: 0%
- S12: 0%
- S13: 0%
- S14: 0%
- S15: 0%
- S16: 0%
- S17: 0%
- S18: 0%
- S19: 0%
- Epic-A: 0%
- Epic-B: 0%

**Overall: 0%**

---

## 22. Notes & Learnings

### 2026-04-17 (계획 수립)
- S6 RECOMMENDATIONS.md가 R-1~R-5를 매우 상세히 기술해둠. S9/S10의 파일/라인 파악에 재작업 불필요.
- `python-telegram-bot`이 `channels` extras에 위치 — 현재 dev 환경에 미설치. S15에서 `uv sync --extra channels` 필요.
- PRE-2 baseline이 383건 — domain(9)+agent(9)+memory(1) = 19건만 S11에서 해소해도 symbolic 의미 큼 (가장 내부 계층이 가장 먼저 깨끗해짐).
- `cli/integration_cli.py`의 `list_events_by_status` attr-defined는 잠재 runtime bug — S13에서 실존 여부 먼저 확인 후 처리.

---

## 23. 사용자 승인 요청 사항 (해소됨, §24 참조)

(원문 섹션은 §24 Decision Log로 이관.)

---

## 24. Decision Log (2026-04-18, 자율 판단 위임 기준)

### 24.1 판단 기준 (제품 컨셉)

메모리 `feedback_preserve_autonomy` 및 CLAUDE.md 재확인:
- **LLM = 유일한 오케스트레이터**. 코드는 도구·정보·hard constraint 제공.
- **Workflow automation으로 역행 금지** — Sprint 설계도 "자동화 파이프라인 깊이" 아닌 "LLM이 touch할 지점의 정보 정확성 + 안전 가드"로 맞춤.
- **Hard constraint만 코드가 강제**: 데이터 무결성(원자성), 보안(kill-switch), 타입 안전성(baseline freeze로 신규 regression 차단).

### 24.2 Decision

| # | 결정 | 근거 |
|:-:|------|------|
| 1 | **Sprint 순서 채택**: S7 → S8 → S9 → S10 → S11 → S13 → S12 → S14(RFC+impl) → S15 → S16 → S18 → S17 → S19 | 순서 logic: (a) 먼저 문서/설정(S7/S8): LLM이 참조하는 정보 정확성 확보. (b) 데이터 원자성(S9/S10): hard constraint. (c) inner layer mypy(S11/S13/S12): LLM 프롬프트에 노출되는 Pydantic/Protocol 타입 신뢰도. (d) 보안(S14): 외부 egress 가드. (e) parity 실측(S15/S16): 3-Tier 등가성 증거 강화. (f) outer layer mypy(S18/S17/S19): 기술부채 상환. |
| 2 | **Epic-A + Epic-B는 별도 릴리스 사이클** | Epic-A (`ws_handler.py` 분할) 2~3주 구조 리팩터. 현 릴리스 GO 전환 경로 밖 (baseline freeze로 regression은 차단). Epic-B (R-4 일반화 port)는 S9+S10 완료 후 자연스럽게 필요성 평가 — 지금은 RFC 파일만 stub 생성. |
| 3 | **S9/S10 agent-driven 직접 구현 승인** | S6(FAIL-B11-8)가 이미 agent 주도 성공. S9는 패턴 복제, S10은 신규 메서드 1개 추가. 복잡도 동일. 단 **B11 Round 3 재감사 필수** (agent ≠ auditor 원칙). |
| 4 | **Sprint 당 scope-adjacent bug 최대 2건 병합 허용** (3건 이상이면 별도 Sprint 열고 본 Sprint는 annotation만) | PRE-2 해소 중 `integration_cli::list_events_by_status` 같은 잠재 runtime bug 발견 시 현명한 수선. 무제한 확장은 Sprint 무한화 유발하므로 상한. |
| 5 | **S16 real API 1회 호출 허용 (엄격한 가드 하)** | cassette 녹화 위해 불가피. 조건: (a) 3 시나리오만 녹화, (b) API key sanitization 의무, (c) CI에서 record mode 금지 (`VCR_RECORD_MODE=none` 강제), (d) 녹화 후 `git-secrets`/grep으로 secret leak 자동 검사. |
| 6 | **S14 + S16만 RFC 선행, 나머지는 본 계획서가 RFC 대체** | RFC 필요 기준 = "정책 결정이 코드 외 영역에 영향". S14 (외부 egress 가드 정책) + S16 (cassette/secret 정책) 두 건만 해당. S9/S10은 S6 패턴 승계라 RFC 불필요. |

### 24.3 Non-Decision (명시적으로 보류)

- `pandas-stubs` 설치 여부 (S18/S12 시점에 재평가)
- `scipy-stubs` 설치 여부 (S12 시점에 재평가)
- `python-telegram-bot` dev extras 표준화 (S15 시점에 결정)

### 24.4 Execution Protocol

1. Sprint 1개 완료 → Quality Gate 4~6 항목 전수 통과 → 간결 보고 → 다음 Sprint 착수.
2. Quality Gate 실패 → 해당 Sprint roll back, 원인 분석, 재시도 또는 scope 재분할.
3. 매 Sprint 완료마다 이 계획서 §21 Progress Tracking + §22 Notes & Learnings 갱신.
4. 모든 Sprint 완료 후 Addendum §9 + HANDOFF §13 + RELEASE_GATE_DECISION 최종 갱신.

### 24.5 실행 착수

S7 Documentation Alignment로 시작. 착수 시각: 2026-04-18.

### 24.6 추가 결정 — S-packaging-numpy (2026-04-18, S16 이후)

| # | 결정 | 근거 |
|:-:|------|------|
| 7 | **S-packaging-numpy 직접 착수 (P0-05 조달 대기 불필요)** | `POST_RELEASE_FALLBACK_ANALYSIS.md`에서 유일한 "진짜 실패"로 식별된 S16-FB2(packaged backend import failure)의 원인은 spec 설정이므로 external blocker와 무관. 조달 전에도 fix + rebuild + smoke까지 가능. 서명 smoke 자체는 여전히 P0-05 대기. |
| 8 | **numpy/scipy/pandas만 excludes에서 제거, sklearn/matplotlib는 유지** | 코드 실측: sklearn/matplotlib는 LLM 프롬프트 문자열에만 등장, 실행은 sandbox subprocess(`sys.executable`)에서 시스템 Python이 담당. backend 번들에 포함시키면 크기만 증가. |
| 9 | **번들 크기 증가(+178 MB) 수용** | numpy/scipy/pandas가 실 요구사항. "작은 번들"보다 "real LLM 경로 동작"이 우선. GO 전환 시점에 Electron installer 다운로드 크기 영향은 별도 분석. |

### 24.7 잔존 gap (3-way LLM parity, POST_RELEASE_FALLBACK_ANALYSIS 기반)

GO 전환 시 아래 중 **S21 + S22**는 제품 컨셉(3-way first-class) 충족을 위해 포함 권장.

| Sprint | 범위 | 우선 | 착수 조건 |
|:------:|------|:---:|----------|
| S21 | API provider matrix cassette (Anthropic + LiteLLM via Groq/Mistral) | P1 | 해당 provider API key 확보 (Anthropic ≥1, 선택 1) |
| S22 | Codex OAuth subprocess record-replay (stdout JSON dump fixture) | P1 | ChatGPT Plus 세션 1회 |
| S23 | Local model chaos (Ollama 서버 부재·포트 점유·타임아웃) | P2 | — |
| S24 | Router failover cassette (primary 503 → secondary 200) | P2 | S21 cassette 재사용 |
| S25 | Real Telegram wire (실 bot token) | P2 | 실 bot token |

