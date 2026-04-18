# DS Agent 종합 시스템 보고서 — 2026-04-17 변동 부록 (ADDENDUM)

**작성일**: 2026-04-17
**원본 문서**: `Docs/DS_AGENT_COMPREHENSIVE_REPORT_2026-04-16.md` (2026-04-16 기준)
**목적**: 2026-04-17 Pre-Release QA 파이프라인(18 agent × 4 Tier + Fix Sprint R1~R3) 수행 중 발생한 **코드·계약·수치·구조 변동**을 원본 보고서에 증분(incremental)으로 반영
**원본 유지 원칙**: 2026-04-16 스냅샷 문서는 감사 추적 보존을 위해 수정하지 않음. 본 Addendum이 **현재 시스템의 실측 상태**를 정정한다
**최종 판정**: **CONDITIONAL_GO** (`Docs/qa_run_2026-04-17/D18_release/RELEASE_GATE_DECISION.md`)

---

## 0. 읽는 법

원본 § → Addendum § 연결:

| 원본 섹션 | Addendum 조치 |
|-----------|---------------|
| §2.2 Clean Architecture | §2 Addendum "Import-linter 계약 2개로 확장" |
| §3.3 데이터 저장소 | §4 Addendum "중앙 Migration Runner" |
| §5.2 "100+ Tools" 제목 + §7.2 수치 | §1 Addendum "Tool 수 76 → 86" |
| §5.4 "25+ Hook" | §1 Addendum "Hook 정확 수치 30" |
| §5.15 Learning Governance "rollback atomic" 주장 | §3 Addendum "Rollback Atomicity 실제 구현 이력" |
| §7.2 주요 동적 인터페이스 수치 | §1 Addendum 수치 정정 |
| §9.2 검증 기준선 | §5 Addendum "2026-04-17 검증 기준선 재집계" |
| 부록 핵심 수치 요약 | §1 Addendum |

**원본 수치와 Addendum이 충돌하면 Addendum이 우선.**

---

## 1. 정량 수치 정정

### 1.1 도구·Hook·Migration (§7.2 / 부록 대체)

| 지표 | 원본 (2026-04-16) | 실측 (2026-04-17) | 출처 · 사유 |
|------|:------------------:|:------------------:|-----|
| `@tool(...)` 등록형 도구 | **76** | **86** | Fix Sprint R1 S3가 `learning_tools.py` 6개 + `portfolio_tools.py` 5개를 명명 인자화하여 완전 등록. A03 R2 / B06 Round 2 감사에서 86/86 AST ↔ `ToolRegistry.list_tools()` 일치 확인 |
| §5.2 제목 "100+ Tools" | 러프 표현 | **86 (정확)** | 과거 1차 설계 기준 수치의 잔재. 현재 집계는 86 |
| Hook 수 | §5.4 "**25+**" (불특정), §7.2 "30" | **30 (확정)** | B05가 `build_hook_registry` 전수 fire trace로 30/30 실행 확인 |
| WebSocket RPC 메서드 | 80 | 80 | 변동 없음 |
| Pydantic 엔티티 | 156 (HANDOFF §5.3) | 156 | 변동 없음 |
| import-linter 계약 | 1 | **2** | S1이 `application_independence_from_infrastructure` 계약 추가 (§2 Addendum 참조) |
| SQLite Migration 최대 버전 | v13 (learning_store) / v12 (portfolio_store) | 동일 | 부록 §1213에 이미 v13 반영됨. portfolio.db는 여전히 v12 — **원본 §3.3:167~168 표기 유지 타당** |

### 1.2 Python 테스트 (§9.2 / 부록 대체)

| 지표 | 원본 | 실측 (2026-04-17) | 사유 |
|------|:------:|:------------------:|-----|
| Python Unit + Smoke Tests | **1,382+ passed** | **2,200+ passed (scope-isolated)** | 2026-04-16 이후 Fix Sprint R1~R3에서 신규 테스트 다수 추가. Tier 2/3/4 agent들이 스코프 격리 실행으로 2,200+ scope 테스트 pass 집계. **전체 회귀 1-shot 수치는 Windows `.tmp/pytest` 환경 flake(ENV-1)로 측정 불가** (HANDOFF §4.5) |
| `mypy` | **Clean** | **실측 383 error / 85 파일** (Post-QA Phase 0 확인) | HANDOFF §4.6 "3건" 표기는 **과소 추정**이었음. 2026-04-17 Post-QA Phase 0 전수 재실행으로 정정. 카테고리: attr-defined 127 · arg-type 89 · no-untyped-def 45 · no-any-return 36 · call-overload 30 · assignment 20 · import-untyped 8 · union-attr 6 · 기타 22. 레이어: runtime 137 · api 129 (`ws_handler.py` 핫스팟) · gateway 79 · evaluation 38 · infrastructure 36 · application 23 · 기타. **domain 레이어는 9건으로 가장 깨끗** (Clean Architecture 내부 준수). 원본 §9.2 "mypy Clean" 주장은 부정확. 상세: `.tmp/qa_phase0/mypy_baseline_summary.md`, `mypy_baseline_raw.txt`. 해소 전략은 `Docs/plans/PLAN_post_qa_risk_mitigation_2026-04-17.md` Phase 1b 참조 (baseline freeze 채택) |
| Coverage `>= 78%` | **Clean** (주장) | **81.53% 측정 완료 (Post-QA Phase 2, 2026-04-17)** | KAG-1 해소. `scripts/measure_coverage.py` 재현, HTML/terminal 리포트 `.tmp/qa_phase2/` 저장. 2108 passed + 18 ENV-1 flake (file_ops·integration_tools 등, HANDOFF §4.5 기존 flake와 동일 범위) |
| `ruff check` / `compileall` | Clean | **Clean (유지)** | A01 Round 2 + S6 수정 범위에서 재확인 |
| Electron E2E 6 suites | pass | pass (C15 재확인) | 변동 없음 |
| Electron Contract 9 suites | pass | pass | 변동 없음 |
| Enhancement Spec 12/12 phases | 100% complete | 100% (변동 없음) | 기능 추가 아닌 신뢰성 개선 중심 사이클이었기 때문 |

---

## 2. Clean Architecture 변동 (§2.2 보강)

### 2.1 Import-linter 계약: 1개 → **2개**

2026-04-16 기준 `scripts/check_import_contracts.py` + `.importlinter`는 단일 `domain_independence_from_outer` 계약만 검사했다. S1 Fix Sprint R1이 다음을 추가:

- **신규 계약**: `application_independence_from_infrastructure` — `src/ds_agent/application/**`이 `src/ds_agent/infrastructure/**`를 직접 import하지 않음을 강제 (composition root `agent/factory.py`만 예외).
- `tools/`는 `.importlinter`에서 domain에게 forbidden 모듈로 지정된 **outer/adapter 레이어**로 확정 분류 → `application → tools` 직접 import도 위반.
- `scripts/check_import_contracts.py`가 새 계약 자동 검사.

검증: A01 Round 2에서 2개 계약 0 violation, B11 Round 2에서 S6 변경 후에도 유지 확인.

### 2.2 신규 Application Port 5개 추가

Clean Architecture **Port 패턴 확장**. 모두 `src/ds_agent/application/ports/` 하위:

| Port | 신설 스트림 | 역할 | 구현체 |
|------|:----------:|------|--------|
| `LineageStorePort` | S1 (R1) | Data lineage 기록 계약 추상화 | `lineage_capture_service.py`가 의존 |
| `NotebookEnginePort` | S1 (R1) | Notebook 실행 엔진 추상화 | `reproducibility_exporter.py`가 의존 |
| `CronRunnerPort` | S1 (R1) | Cron 스케줄러 추상화 | `scheduler_service.py`가 의존 |
| `SandboxPort` | S5 (R2) | Sandbox 코드 실행 추상화 | `execution_router`가 의존 · 구현 `infrastructure/sandbox/sandbox_factory.py` (`ProcessSandboxFactory` adapter) |
| `LearningStoreAtomicPort` | S6 (R3) | **Rollback/Deprecate 이중 write 원자화 계약** | `SqliteLearningStore.save_item_and_deprecation` (`BEGIN IMMEDIATE ... COMMIT / ROLLBACK`) |

모든 Port는 Application 계층에 정의되고, Infrastructure가 구현한다 — **의존성 역전 원칙** 엄격 준수.

### 2.3 `.importlinter` 계약 갱신
신규 Port 5개 경로(`application/ports/*`)는 application 계층에 속하므로 기존 layering rule 준수.

---

## 3. Rollback Atomicity 이력 정정 (§5.15:679)

### 3.1 원본 주장 vs 실제

**원본 문구 (line 679)**:
> `RollbackPromotionUseCase`로 PromotionRecord.rollback_ref 기반 atomic 복원

**실제 2026-04-16 시점 상태**: **비원자적**. `RollbackPromotionUseCase.execute`가 `store.save_item(updated)` + `store.save_deprecation_record(dep)`를 **독립된 두 commit**으로 실행. 중간 실패 시 item은 `deprecated`로 persist, DeprecationRecord는 누락 → audit trail split.

### 3.2 발견 및 해결 이력

- **2026-04-17 B11 Round 1**: Path 8 probe (`B11_rollback_atomicity_sqlite_probe.json`)가 `NON_ATOMIC_PARTIAL` 판정 → **FAIL-B11-8**
- **S6 Fix Sprint R3**:
  - `LearningStoreAtomicPort.save_item_and_deprecation(item, dep_record)` 신설
  - `SqliteLearningStore`가 단일 connection에서 `BEGIN IMMEDIATE ... COMMIT` 트랜잭션으로 구현 (실패 시 `ROLLBACK`)
  - `RollbackPromotionUseCase` 수정 → 신규 원자 메서드 호출로 전환
  - 신규 테스트 `tests/unit/application/test_rollback_atomicity.py` (5건) 추가
- **B11 Round 2 재감사**: 자체 독립 probe 3 시나리오로 `ATOMIC_REVERT` 확인 (2026-04-17 cleared)

### 3.3 현재 문구의 정합성

S6 이후 시점에는 원본 line 679 문구 **"atomic 복원"이 실측과 일치**. 다만 2026-04-16 스냅샷 기준으로는 **낙관적 주장**이었음을 기록. 이는 향후 comprehensive report 개정 시 "설계 의도 vs 실측"을 구분해 표기할 것을 권장.

### 3.4 잔존 유사 패턴 (Fix Sprint R4 후보)

S6 RECOMMENDATIONS.md가 동형(double-write, no-use-case-txn) 패턴을 3건 추가 식별:

| ID | Use Case | 위험 |
|----|----------|------|
| R-1 | `PromoteLearningItemUseCase` | Promotion 중간 실패 시 item만 promoted 기록 + PromotionRecord 누락 가능 |
| R-2 | `DeprecateLearningItemUseCase` | Deprecation 중간 실패 시 item 상태 변경 + DeprecationRecord 분리 |
| R-3 | `ReviewLearningItemUseCase` | Review 완료 중간 실패 시 상태 split 가능 |

**현재 릴리스 non-blocking** (주입된 중간 실패 시나리오에서만 노출). 동일 Port 확장(같은 단일 트랜잭션 방식)으로 Fix Sprint R4에서 해결 권장.

---

## 4. Persistence 변동 (§3.3 보강)

### 4.1 중앙 Migration Runner 신설

S4 Fix Sprint R1이 **중앙 migration runner**를 도입:

- **위치**: `src/ds_agent/infrastructure/migration/sqlite_migrations.py`
- **역할**: 기존에 각 store가 자체 migration 로직을 들고 있던 것을 중앙집중화. `schema_migrations` 테이블에 `description TEXT` 감사 컬럼 추가.
- **재익스포트**: `src/ds_agent/infrastructure/migration/__init__.py`
- **Learning Store v13**: S4가 이 러너 위에 `learning_store` v13 마이그레이션을 정식 등록.

### 4.2 SQLite 스키마 버전 현황

| 데이터베이스 | 버전 | 관리 |
|------------|:----:|------|
| session.db | (원본 유지) | store 자체 |
| experiment_log.db | (원본 유지) | store 자체 |
| portfolio.db | **v12** | store 자체 (중앙 러너 이관 후보) |
| learning.db | **v13** | **중앙 러너** (`sqlite_migrations.py`) 관리 — 2026-04-17 신규 |
| decision_os.db | (원본 유지) | store 자체 |

**멱등성**: A04 Round 2가 v13 적용 후 `run_migrations()` 재호출에서 변경 0건 확인.

### 4.3 `learning_store.py` 변경 요약

- S4: v13 마이그레이션 등록 (중앙 러너 경유)
- S6: 신규 메서드 `save_item_and_deprecation(item, dep_record)` 추가 — `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK-on-error` semantics

기존 `save_item` / `save_deprecation_record` 독립 메서드는 유지 (다른 호출부 파급 최소화).

---

## 5. 2026-04-17 검증 기준선 재집계 (§9.2 대체)

| 검증 항목 | 원본 (2026-04-16) | 실측 (2026-04-17) |
|----------|:------------------:|:------------------:|
| Python scope-isolated tests | 1,382+ | **2,200+** (Tier 2/3/4 + Fix Sprint R3 신규 포함) |
| 전체 회귀 1-shot 수치 | (측정 주장) | **ENV-1 flake로 측정 불가** — 스코프 격리로 대체 |
| 패키지 바이너리 smoke | 5/5 | **5/5** (C15 재확인 + READY race 10/10 unique) |
| Electron E2E | 6 suites pass | **pass** (diagnostic/happy-path C15 live 재확인) |
| Electron Contract | 9 suites pass | **pass** (변동 없음) |
| Electron TypeScript typecheck | Clean | Clean |
| Electron build | Clean | Clean |
| `ruff check` | Clean | **Clean** (A01 R2 + S1/S5/S6 수정 범위) |
| `mypy` | **Clean** (주장) | **3건 pre-existing fail 유지** (PRE-2) |
| `python -m compileall` | Clean | Clean |
| Coverage threshold ≥78% | Clean (주장) | **KAG-1 미측정 · fallback 수용** |
| Clean Architecture import-linter | 단일 계약 통과 | **2개 계약 전수 0 violation** |
| Enhancement Spec 12/12 phases | 100% | 100% (변동 없음) |

---

## 6. 제품화 현황 변동 (§8 보강)

원본 §8.1 Milestone A의 상태 중 QA 파이프라인이 영향을 준 항목:

| # | 항목 | 원본 상태 | 현재 상태 | 비고 |
|---|------|----------|----------|------|
| P0-01 | 코드 실행 샌드박싱 | Complete | Complete | B06이 10/10 샌드박스 페이로드 block + SQL 주입 무력화 실측 재확인 |
| P0-02 | 자격증명 보안 저장 | Complete (코드) | Complete (코드) | A02 R2에서 keyring chunking round-trip + PII 7/7 재검증. **멀티플랫폼 실측은 여전히 외부 대기** |
| P0-03 | 시작 진단 및 복구 | Complete | Complete | D16 Mid-session kill / SQLite lock / Incident 재시작 3 시나리오로 복구 실측 확인 |
| P0-05 | 코드 서명 및 배포 | Blocked | Blocked (외부 대기 유지) | Conditional Go blocker |
| P0-06 | 패키지 QA & 스모크 | In Progress | **Complete (unsigned 기준)** — C15 smoke 5/5 + READY race 10/10 | 서명 바이너리 E2E는 P0-05 의존 — 서명 후 재smoke 필요 |
| P0-07 | 관찰 가능성 & 크래시 리포팅 | Complete (코드) | Complete (코드) | A02 R2가 Sentry PII redaction 10건 테스트로 재확인 |

**P1-14 자동 업데이트**: C15 정적 검증 8/8 통과 (실제 live feed 주입은 P0-05 이후).

---

## 7. Fix Sprint 결과 누적 (원본에 없는 신규 섹션)

| Round | Stream | 해결 이슈 | 주요 산출물 |
|:-----:|:------:|-----------|-------------|
| R1 | S1 Clean Arch | V1/V2/V3 import-linter 계약 | 신규 Port 3 + import-linter 계약 추가 |
| R1 | S2 PII Redaction | PII-1~7 | `sentry_backend.py` regex + 필드 토큰 + deep redact + Luhn |
| R1 | S3 Drift Cleanup | F1/F2 schema drift | `learning_tools.py` / `portfolio_tools.py` 명명 인자화 (86 tool 확정) |
| R1 | S4 v13 Migration | F3 migration 누락 | `learning_store` v13 + 중앙 migration runner |
| R2 | S5 Sandbox Port | R1/R3 (S1 Resume) | `SandboxPort` 신설 + `execution_router` Port 의존 전환 + conftest fixture |
| R3 | S6 Rollback Atomicity | **FAIL-B11-8** | `LearningStoreAtomicPort` + 단일 트랜잭션 원자 메서드 + Use case 수정 |

### 7.1 R4 후보 (post-release)

- R-1 / R-2 / R-3: Promote/Deprecate/Review use case의 동형 이중-write 패턴
- C15-O6: PyInstaller spec dead hidden import `ds_agent.memory.session_db` 정리
- PRE-1 / PRE-2: `test_semantic_ports_are_runtime_checkable` + mypy 3건
- D5-1 / NOTE-B08-1 / B11-D1~D4: 계획서 문구와 코드 정렬
- RC-5: Slack/Jira/Confluence/Notion/Git connector에 in-adapter kill-switch 추가 RFC

---

## 8. 전체 차이 요약 (TL;DR)

**정량 정정 (6)**: 76→86 tool / "25+"→30 hook / 1,382+→2,200+ test / mypy Clean→pre-existing 3건 / coverage Clean→KAG-1 미측정 / "100+ Tools" 표현 정확화(86).

**구조 신규 (5)**: import-linter 계약 +1 / Application Port +5 (lineage/notebook/cron/sandbox/learning_store_atomic) / 중앙 migration runner / S6 원자 트랜잭션 / Sandbox adapter 분리.

**이력 정정 (1)**: "rollback atomic" 주장은 2026-04-16 시점엔 비원자적, S6 이후에만 사실.

**신규 섹션 (1)**: Fix Sprint R1~R3 누적 결과.

---

## 9. Post-QA Risk Mitigation 결과 (2026-04-17 추가)

계획서: `Docs/plans/PLAN_post_qa_risk_mitigation_2026-04-17.md`

### 9.1 Phase 1 — PRE-1 + PRE-2 (C 옵션)
- **PRE-1 cleared**: `tests/unit/application/test_semantic_ports.py::test_semantic_ports_are_runtime_checkable` PASS. 원인은 `_ExternalSource` mock의 `fetch_glossary_terms` 메서드 누락 (Protocol은 4개 요구, mock은 3개). 한 줄 추가로 해결. Protocol 설계는 그대로.
- **PRE-2 baseline freeze**: `scripts/check_mypy_baseline.py` + `mypy-baseline.json` 신설. 실측 383 error를 baseline으로 고정. 이후 실행 시 신규 error 발생만 fail. 점진 해소는 별도 레이어 스프린트 (권고 순서: domain(9)→application(23)→agent(9)→infrastructure(36)→evaluation(38)→tools(18)→runtime(137)→api(129, `ws_handler.py` 분할 후)→gateway(79)).

### 9.2 Phase 2 — Coverage 실측 (A 옵션)
- **Coverage: 81.53%** (1-shot `pytest tests/unit/ --cov=src/ds_agent` 성공). 임계값 78% 달성.
- 재현: `python scripts/measure_coverage.py`
- 리포트: `.tmp/qa_phase2/html/index.html`, `.tmp/qa_phase2/coverage_terminal.txt`
- 18 flake (ENV-1) — HANDOFF §4.5가 이미 분리 관리. 측정에 영향 없음.

### 9.3 Phase 3 — 3-Tier Process-Level Parity (B 옵션)
- **9/9 run 완료**, `delivery_pack_body_hash` 3채널 전수 일치 (sha256 `51de5976...`)
- 산출물: `Docs/qa_run_2026-04-17/C13_parity_process_level/` (Round 2 supplement)
- Harness: `scripts/parity_harness/` (`backend_control.py`, `harness_cli.py`, `harness_telegram.py`, `harness_electron.js`, `run_all.py`, `scenarios.py`, `extract.py`)
- Electron: C15 dist 재사용 (source hash 불변 확인, 재빌드 없음)
- **Telegram 잔존 gap**: `python-telegram-bot`이 host venv/dist에 없어 실제 Updater polling 경로는 미검증. Telegram-shaped session id + `surface=telegram`으로 factory wiring parity까지만 실측. 실제 Telegram API 경로는 **Round 1 fallback 상태 그대로 이월**.
- **LLM record-replay**: mocked provider가 deterministic error를 반환하여 parity signal로 사용. 실제 LLM 성공 경로의 live parity는 record-replay fixture가 별도 필요 (Round 1 gap 유지).
- 추가 의존성: `websockets==16.0` (stdlib에 WS 클라이언트 없음). production source 변경 없음.
- 0 real external calls, cleanup confirmed (orphan process 0).

### 9.4 남은 Gap (post-release 후속)
- Telegram process-level 실경로 (python-telegram-bot Updater polling)
- LLM 성공 응답의 byte-identical live parity (record-replay fixture 필요)
- PRE-2 layer별 점진 해소 (baseline freeze로 새 error 차단은 가능)
- R-1/R-2/R-3 (Promote/Deprecate/Review 이중-write 원자성)
- C15-O6 (PyInstaller spec dead hidden import)
- RC-5, D5-1, B11 D1~D4, NOTE-B08-1 등 문서/아키텍처 후속

### 9.5 최종 Go 조건 재판정

| §10.1 조건 | 2026-04-17 Post-QA 시점 | 비고 |
|-----------|:----------------------:|------|
| Tier 1 4/4 pass | ✅ | 유지 |
| Tier 2 8/8 pass (B11 Round 2 cleared) | ✅ | 유지 |
| Tier 3 3/3 (C13 + **process-level Round 2**) | ✅ | **fallback→live 업그레이드 완료** |
| Tier 4 D16/D17 | ✅ | 유지 |
| ruff / compileall | ✅ Clean | 유지 |
| mypy | ⚠️ baseline freeze (383 error 고정, 신규 0) | "Clean"에서 "baseline 관리"로 정책 전환 |
| Coverage >= 78% | ✅ **81.53% 실측** | **KAG-1 해소** |
| 하드코딩 시크릿 0 | ✅ | 유지 |
| 3-Tier 등가성 | ✅ **process-level 9/9** (Telegram 일부 gap 제외) | Round 2로 격상 |

### 9.6 External Blocker (변동 없음)
P0-05 / P0-06 / P0-07 / P1-14 / P0-02 — 이 5건은 내부 기술로 해결 불가. `CONDITIONAL_GO` 상태 유지.

---

## 10. Post-Release Follow-ups 결과 (2026-04-18 추가)

계획서: `Docs/plans/PLAN_post_release_followups_2026-04-17.md`. 10 Sprint 실행.

### 10.1 Sprint 완료 현황

| Sprint | 결과 | Baseline 변화 |
|:------:|:----:|:-------------:|
| S7 Doc alignment | 5건 drift 정정 | — |
| S8 Dead config | spec session_db 제거 + 2 `__init__.py` | — |
| S9 R-1 + R-2 원자성 | Promote/Deprecate IMMEDIATE atomic 전환 | — |
| S10 R-3 원자성 | Review atomic 전환, Port atomic method 3개 누적 (→ Epic-B 트리거 충족) | — |
| S11~S13 inner layer | domain+agent+memory+skills+providers+cli+self_improve | 383 → 362 (-21) |
| S12 application | artifact_generator/usage_summary/run_diff 등 | 362 → 345 (-17) |
| S14 RC-5 kill-switch | 5 connector in-adapter guard + RFC + 27 테스트 | — |
| S17 infrastructure | 14 파일 (sentry/pandas/verifier Literal 등) | 345 → 311 (-34) |
| S18+S19 tools+evaluation | 22 파일 (일부는 Epic-A 후보 file-level pragma) | 311 → 255 (-56) |
| S20 `__init__.py` hygiene | 37 regular package 전환 (5 하이픈 제외) | 255 → 257 (+2 visible 조정) |
| **S15** Telegram live polling | `python-telegram-bot` fake bot harness 3 run, real API 0건, hash 일치 | — |
| **S16** LLM record-replay | VCR.py cassette 3 녹화 + 9 replay run, byte-identical per scenario, secret leak 0, $0.00013 | — |

**누적 baseline 축소: 383 → 257 (126 해소, -32.9%)**
**3-Tier parity 증명 수준**: 이전 "mocked error body hash" → **실 LLM 성공 응답 byte-identical hash** (S16으로 upgrade).

### 10.2 누적 코드/테스트 산출물

- **신규 Port atomic 메서드**: `LearningStoreAtomicPort`에 3개 (save_item_and_deprecation, save_promotion_and_item, save_review_event_and_item). R-4 일반화 txn port RFC 트리거 충족.
- **신규 보안 유틸**: `infrastructure/external/egress_guard.py` (`is_egress_enabled`, `make_disabled_result`). 5 connector 전수 in-adapter kill-switch 삽입.
- **신규 스크립트**: `scripts/check_mypy_baseline.py` (baseline freeze + delta 검증), `scripts/measure_coverage.py`.
- **신규 RFC**: `Docs/rfc/RFC_2026-04_adapter_killswitch.md`.
- **신규 테스트**: atomicity 5+3+7=15건, egress kill-switch 27건, coverage harness 간접 — 총 50+건.
- **Domain interface 확장**: `WorkObjectStore` Protocol에 `list_events_by_status`, `get_event`, `update_event_status` 추가 (실구현과 계약 동기화).
- **파일 레벨 mypy pragma 13건**: evaluation 구조 리팩터 후보로 Epic-A에 연계.

### 10.3 제품 컨셉 정합성

- LLM=오케스트레이터 원칙 **유지**. 모든 hard constraint (atomicity, egress kill-switch) 만 코드가 강제.
- fail-safe 원칙 전면 도입: `DS_AGENT_NETWORK_EGRESS_ENABLED` default false, atomic 메서드 실패 시 rollback.
- Clean Architecture: domain/application port 확장, infrastructure 구현. import-linter 2 계약 무중단 유지.

### 10.4 이월 (Epic 후보)
- **Epic-A**: `ws_handler.py` 분할 + runtime/api/gateway 257건 mypy 잔여 구조 리팩터
- **Epic-B**: `LearningStoreTxnPort.begin_transaction()` 일반화 RFC (R-4)
- ~~**S-packaging-numpy**~~ → **closed 2026-04-18**. `ds-agent-api.spec`에서 numpy/scipy/pandas를 excludes에서 hiddenimports로 이동. 번들 40→218 MB. 단, 이 sprint는 backend **import-time** 실패만 고침 — ML 실행 경로 자체는 여전히 빈 상태였음. 세부: `Docs/qa_run_2026-04-17/S-packaging-numpy_spec_fix/CHANGELOG.md`.
- ~~**S-ml-stack-packaging**~~ → **closed 2026-04-18**. S-packaging-numpy 이후 드러난 **execution-time gap** 해소: (1) `.venv`에 sklearn/xgboost/lightgbm/matplotlib/seaborn/optuna/joblib core deps 추가, (2) `tools/sandbox.py`에 `sys.frozen` 감지 + `ds-agent-api.exe --mode exec SCRIPT` 서브커맨드 분기(RFC_2026-04_sandbox_frozen_exec.md), (3) xgboost.dll 143 MB native 번들 명시 수집. Packaged exe에서 iris 분류 97.4% accuracy로 실 ML 실행 실증. 번들 218→458 MB. 세부: `Docs/qa_run_2026-04-17/S-ml-stack-packaging/CHANGELOG.md`.
- **S-ruff-cleanup**: pre-existing ruff E501 / B904 정리 (S17~S19에서 관찰된 6건)
- **domain-pack-enterprise 이름 정책 RFC** (하이픈 vs underscore)
- **evaluation scorer Protocol 추상화** (S19 file-level pragma 13건)

---

## 11. 변경 이력

| 날짜 | 변경 | 작성자 |
|------|------|--------|
| 2026-04-17 | 최초 작성 — 2026-04-16 원본 대비 QA 파이프라인(R1~R3) 변동사항 반영 | Main orchestrator |
| 2026-04-17 | Post-QA Risk Mitigation Phase 1~3 결과 통합 (KAG-1 해소, C13 process-level 업그레이드, PRE-1 cleared, PRE-2 baseline freeze) | Main orchestrator |
| 2026-04-18 | Post-Release Follow-ups S7~S20 10 Sprint 결과 통합 (baseline -33%, R-1~R-3 원자성, RC-5 kill-switch, __init__.py hygiene) | Main orchestrator |
| 2026-04-18 | S15 Telegram live + S16 LLM record-replay 완료 — 3-Tier parity byte-identical on real LLM, 총 12 Sprint. S-packaging-numpy 신규 이월 이슈 기록 | Main orchestrator |
| 2026-04-18 | S-packaging-numpy closed — PyInstaller spec numpy/scipy/pandas 복원, packaged backend smoke 통과(`/health` 200, 18 skill load, READY, import error 0). POST_RELEASE_FALLBACK_ANALYSIS의 유일한 "진짜 실패" 해소 → 0건 | Main orchestrator |
| 2026-04-18 | 사용자 지적으로 S-packaging-numpy가 부분 해소에 그쳤음을 발견: (a) .venv에 sklearn/xgboost 등 미설치, (b) frozen-mode sandbox `sys.executable script_path` 패턴이 bootloader argparse로 전면 불능. 릴리스 선언 전 재검증 필수 | Main orchestrator |
| 2026-04-18 | S-ml-stack-packaging closed — 8 Phase: RFC 2건, ML libs core deps, sandbox frozen detect + `--mode exec` 서브커맨드, xgboost.dll 포함 native DLL 명시 번들링. Packaged exe iris 97.4% accuracy 실증. 번들 218→458MB. Phase 4/5(Gemini/Codex OAuth)는 사용자 자격증명 대기 | Main orchestrator |
| 2026-04-18 | Phase 5 (S22) closed — Codex OAuth subprocess fixture 3건 + byte-identical replay 5/5. ChatGPT Plus 3턴 소모. OAuth 1/2 | Main orchestrator |
| 2026-04-18 | Phase 6 (S-ml-execution-parity) closed — sandbox source/frozen 8/8 byte-identical (iris 0.973684 고정). 3-채널 공유 backend 구조상 이는 3채널 parity의 최종 보증 | Main orchestrator |
| 2026-04-18 | Phase 4 (S21) closed — `GeminiCliProvider` 신규 `gemini_cli.py`, `gemini_oauth.py` auto-detect transport. Gemini CLI subprocess(`gemini -p -o json`) 3건 녹화 + replay 6/6 pass. OpenClaw 직접 HTTP 방식(정책 risk) 대신 안전한 CLI 경로 채택. **3-way LLM OAuth 2/2 완성**. LLM OAuth + ML Execution Epic 전체 완결 | Main orchestrator |

---

*본 Addendum은 2026-04-17 QA 파이프라인 완료 시점의 **실측 상태 스냅샷**. 차기 comprehensive report 개정(예: 2026-MM-DD) 시 본 Addendum 내용을 본문에 통합하고, 그 이전 스냅샷(2026-04-16 + 본 Addendum)은 함께 archive한다.*
