# DS Agent Pre-Release QA — 인계 문서 (HANDOFF)

**작성일**: 2026-04-17 (Post-QA Risk Mitigation 완료 시점)
**현재 지점**: **CONDITIONAL_GO (Internal readiness 강화)** — KAG-1 해소, C13 process-level 업그레이드, PRE-1 cleared, PRE-2 baseline freeze. 외부 자격증명 5건만 남음
**인계 대상**: 외부 자격증명 조달 후 GO 전환 담당자
**남은 작업량**: 외부 조달(P0-05/06/07/P1-14/P0-02) → 서명 빌드 재smoke → `GO` 전환

---

## 0. 이 문서 사용법

인계 agent는 **이 문서부터 읽으세요**. 다른 문서들은 이 문서의 §3 "문서 지도"에서 가리키는 순서대로 필요할 때 열어보면 됩니다. 이 문서가 나머지 전부의 인덱스·요약·결정 이력·현재 상태 스냅샷입니다.

---

## 1. 프로젝트 한 줄 요약

DS Agent는 Hermes-style 자율형 AI 데이터 사이언티스트(Python 백엔드 + Electron/CLI/Telegram 3-Tier 인터페이스). 상용 배포 직전 단계로, **사람 개입 없이 AI Agent 팀이 정적 감사 → 기능 테스트 → E2E → 카오스/회귀 → Go/No-Go 서명**까지 책임진다.

## 2. 현재 상태 (2026-04-17 기준)

### 2.1 완료된 단계

- ✅ **테스트 계획 수립**: `Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md` (18 agent × 4-Tier 구조)
- ✅ **Tier 1 Round 1 감사**: A01~A04 4개 agent 전원 fail (9개 블로킹 이슈 발견)
- ✅ **Fix Sprint Round 1**: S1~S4 병렬 수정 (S1은 API 500으로 중단 후 Resume agent 마무리)
- ✅ **Fix Sprint Round 2**: S5가 S1 Resume이 노출한 R1/R3 해소
- ✅ **Tier 1 Round 2 재감사**: A01~A04 전원 pass, 새 회귀 0건, 스코프 준수

### 2.2 게이트 판정 (최종)

**Tier 1 Hard Gate: PASS** (Round 2)
**Tier 2 Hard Gate: PASS → FAIL-B11-8 cleared** (S6 + B11 Round 2)
**Tier 3 Hard Gate: PASS** — `TIER3_GATE_DECISION.md`
**Tier 4 Hard Gate: PASS** — D16 8/8 복구, D17 no-change delta=0.0 (<1e-9)
**D18 최종 판정: CONDITIONAL_GO** — `D18_release/RELEASE_GATE_DECISION.md`

### 2.3 다음에 할 일

상용 배포 GO 전환을 위해 **외부 자격증명 조달**:
- P0-05 Windows EV 코드 서명 + Apple Developer ID
- P0-06 서명 바이너리 E2E (P0-05 의존)
- P0-07 Sentry DSN 활성화
- P1-14 서명된 auto-updater (latest.yml)
- P0-02 멀티플랫폼 keyring 실측

조달 완료 후 C15 smoke 5/5 + auto-updater live drill만 서명 빌드 기준으로 재실행하면 **GO 전환 가능** (A01~D17 재실행 불필요, 소스 변경 없는 한).

### 2.3-legacy 이전 Tier 2 스폰 가이드 (이력 보존용)

**Tier 2 — Feature Behavior Test** 병렬 스폰:
- B05 Agent Core & Hook Chain
- B06 Tools Registry Fuzz (76 tool × 5 입력)
- B07 Memory & Semantic
- B08 Task Contract / Verifier / Decision OS
- B09 Autonomy Control Plane
- B10 Comms / Workflow / Export
- B11 Portfolio / Learning Governance
- B12 Provider Router & Cost

각 agent의 **책임·절차·Pass 기준**은 계획서 §5에, **자체 기동 프롬프트 템플릿**은 §12에 있다. §12 A01 프롬프트 예시를 그대로 복제·치환해서 쓰면 된다. 단 §4.5 참고: 8개 동시 스폰은 API rate limit 리스크 — 사용자 지시에 따라 2~3 배치로 나누는 방안도 검토.

---

## 3. 문서 지도 (읽어야 할 순서)

새 agent는 이 순서대로 필요한 만큼 열어보면 상태를 완전히 재구성할 수 있다.

### 3.1 반드시 먼저 읽기

| # | 파일 | 역할 | 분량 |
|:-:|------|------|:----:|
| 1 | **본 문서 (HANDOFF_NEXT_AGENT.md)** | 현재 상태·결정·인덱스 | 작음 |
| 2 | `Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md` | 18 agent × 4-Tier 계획서 전체. Tier 2 책임·Pass 기준·프롬프트 템플릿은 여기. | 중간 |
| 3 | `Docs/DS_AGENT_COMPREHENSIVE_REPORT_2026-04-16.md` | 시스템 전반 종합 보고서 (18 기능 / 76 tool / 30 hook / 80 WS RPC / 3-Tier 인터페이스 설명) | 큼 |

### 3.2 Tier 1 실적 (원인 분석·스코프 판단 시)

| 파일 | 역할 |
|------|------|
| `Docs/qa_run_2026-04-17/A01_architecture/FINAL.json` | Round 1 A01 감사 결과 (fail) |
| `Docs/qa_run_2026-04-17/A01_architecture/A01_arch_report.md` | A01 Round 1 상세 보고서 |
| `Docs/qa_run_2026-04-17/A02_security/FINAL.json` | Round 1 A02 (fail) |
| `Docs/qa_run_2026-04-17/A02_security/A02_security_report.md` | A02 Round 1 상세 |
| `Docs/qa_run_2026-04-17/A03_contract_schema/FINAL.json` | Round 1 A03 (fail) |
| `Docs/qa_run_2026-04-17/A03_contract_schema/A03_report.md` | A03 Round 1 상세 |
| `Docs/qa_run_2026-04-17/A04_migration/FINAL.json` | Round 1 A04 (fail) |
| `Docs/qa_run_2026-04-17/A04_migration/A04_report.md` | A04 Round 1 상세 |

### 3.3 Fix Sprint 실적

| 파일 | 역할 |
|------|------|
| `Docs/qa_run_2026-04-17/FIX_SPRINT_WORK_ORDER.md` | 5개 Fix Sprint 스트림 정식 작업 지시서 (S1~S4 + S5 설계 원칙) |
| `Docs/qa_run_2026-04-17/S1_clean_arch/FINAL.json` | S1 내부 결과 (API 500 interrupt → Resume agent가 증거 완성) |
| `Docs/qa_run_2026-04-17/S2_pii_redaction/FINAL.json` | S2 내부 결과 (pass) |
| `Docs/qa_run_2026-04-17/S3_drift_cleanup/FINAL.json` | S3 내부 결과 (pass) |
| `Docs/qa_run_2026-04-17/S4_v13_migration/FINAL.json` | S4 내부 결과 (pass, v13=learning_store) |
| `Docs/qa_run_2026-04-17/S5_sandbox_port/FINAL.json` | S5 내부 결과 (SandboxPort 역전 + R3 conftest fixture) |

각 스트림 폴더 내부에 `DIFF_SUMMARY.md`, `TEST_RESULTS.md`, `CHANGELOG.md`, `RECOMMENDATIONS.md`가 함께 있음.

### 3.4 Tier 1 재감사 (Round 2)

| 파일 | 역할 |
|------|------|
| `Docs/qa_run_2026-04-17/A01_architecture_reaudit/FINAL.json` | Round 2 pass, V1/V2/V3 + R1/R3 resolved |
| `Docs/qa_run_2026-04-17/A02_security_reaudit/FINAL.json` | Round 2 pass, PII 7/7 + UUID/SHA false positive guard |
| `Docs/qa_run_2026-04-17/A03_contract_schema_reaudit/FINAL.json` | Round 2 pass, 86/86 tool + 273/273 contract |
| `Docs/qa_run_2026-04-17/A04_migration_reaudit/FINAL.json` | Round 2 pass, aggregate_max=13 |

---

## 4. 핵심 결정 이력 (중요 — 같은 논의 반복하지 말 것)

### 4.1 원칙: 감사자 ≠ 수정자

- 감사 agent는 수정하지 않는다. 실패를 있는 그대로 기록.
- 수정은 별도 스트림 agent가 수행.
- 수정 후 원래 감사자가 **동일 프롬프트 + delta 검증**으로 재감사.
- 근거: 자기 확증 편향 + 신호 오염 방지. FIX_SPRINT_WORK_ORDER §1.1.

### 4.2 LLM = 오케스트레이터 원칙 보존 (프로젝트 철학)

메모리 `feedback_preserve_autonomy` 기반:
- Workflow automation으로 역행 금지.
- Scheduler/Governance는 **정보 제공자·품질 게이트**이지 controller가 아님.
- Hard constraint(SLA 상한, `max_active_slots`, 자동 폐기)만 코드가 강제.
- 테스트에서 "이 테스트를 통과시켜달라" 같은 LLM 힌트 주입 금지 — 원칙 위반.

### 4.3 v13 결정 (A04-F3)

사용자 명시 확정: **v13이 정답, 코드에 누락**.
→ S4가 `learning_store`에 v13 마이그레이션을 실코드로 추가 (schema_migrations에 `description TEXT` 감사 컬럼) + 중앙 러너(`infrastructure/migration/sqlite_migrations.py`) 신설. A04 재감사가 `observed_max_schema_version=13` 확인.

### 4.4 Hermes-style vs Clean Architecture 해석 (R1 판정 근거)

- **Hermes-style**: 앱 컨셉 — LLM이 runtime에 tool registry를 orchestrate.
- **Clean Architecture**: 개발 철학 — 소스 레벨 의존성 방향 제약.
- **두 축은 직교**. Hermes는 Clean Arch 위반을 정당화하지 않는다.
- `tools/`는 `.importlinter`에서 domain에게 forbidden 모듈로 지정된 **outer/adapter 레이어**. 따라서 `application → tools` 직접 import도 Clean Arch 위반.
- 그래서 S5가 `SandboxPort`를 신설해 `execution_router`를 Port 의존으로 전환.

### 4.5 Windows `.tmp/pytest` 테스트 플레이크

- 전체 회귀 pytest에서 18~42건 실패가 반복됐으나, **S2/S3/S4/S5가 각각 독립적으로 격리 재실행 시 전원 pass 확인**.
- 원인: Windows 파일 핸들 누적 + ToolRegistry singleton cross-test 간섭 + 이전 세션의 `data/` 오염.
- 결론: **Fix Sprint 회귀 신호 아님**. 환경 이슈로 분리.
- **Tier 2 이후 agent 프롬프트에도 이 원칙 명시 필수** (계획서 §10.1 soft-fail 취급): 전체 회귀 대신 **스코프 격리 실행**을 pass/fail 신호로 채택.

### 4.6 pre-existing 이슈 (무시하되 기록)

- `tests/unit/application/test_semantic_ports.py::test_semantic_ports_are_runtime_checkable` — `ds_agent.memory.semantic` 영역 pre-existing fail. S1/S5/A01 모두 "스코프 외 pre-existing"으로 분류.
- mypy **실측 383 error / 85 파일** (Post-QA Phase 0 2026-04-17 재확인). 원래 기록 "3건"은 과소 추정. 해소 전략: baseline freeze 채택 (`Docs/plans/PLAN_post_qa_risk_mitigation_2026-04-17.md` Phase 1b). 레이어별 domain 9건·runtime 137건·api 129건. Addendum §1.2 갱신됨. 참고: `.tmp/qa_phase0/mypy_baseline_summary.md`.
- 향후 **Tier 4 또는 별도 유지보수 스프린트**로 이관.

---

## 5. Fix Sprint에서 변경된 파일 전체 목록 (Tier 2 agent가 알아야 할 스펙)

Tier 2 agent들은 아래 파일을 읽게 될 가능성이 큼. 원래 계획서보다 **최신 상태 기준**으로 테스트할 것.

### 5.1 신규 생성

```
src/ds_agent/application/ports/lineage_store_port.py        # S1
src/ds_agent/application/ports/notebook_engine_port.py      # S1
src/ds_agent/application/ports/cron_runner_port.py          # S1
src/ds_agent/application/ports/sandbox_port.py              # S5
src/ds_agent/infrastructure/sandbox/sandbox_factory.py      # S5 (ProcessSandboxFactory adapter)
src/ds_agent/infrastructure/migration/sqlite_migrations.py  # S4 (중앙 러너)
tests/unit/architecture/test_application_infrastructure_boundary.py  # S1
tests/unit/application/conftest.py                          # S5 (autouse LineageCaptureService fixture)
tests/integration/infrastructure/test_central_migration_runner.py    # S4
```

### 5.2 수정

```
src/ds_agent/application/services/lineage_capture_service.py      # S1 (Port 의존 전환)
src/ds_agent/application/services/reproducibility_exporter.py     # S1
src/ds_agent/application/services/scheduler_service.py            # S1
src/ds_agent/application/services/execution_router.py             # S5 (SandboxPort 의존)
src/ds_agent/infrastructure/observability/sentry_backend.py       # S2 (PII regex + 필드 토큰 + deep redact + Luhn)
src/ds_agent/infrastructure/persistence/learning_store.py         # S4 (v13 마이그레이션 추가)
src/ds_agent/infrastructure/migration/__init__.py                 # S4 (re-export)
src/ds_agent/tools/learning_tools.py                              # S3 (6 @tool 명명 인자화)
src/ds_agent/tools/portfolio_tools.py                             # S3 (5 @tool 명명 인자화)
src/ds_agent/agent/factory.py                                     # S1 (Port 배선)
scripts/check_import_contracts.py                                 # S1 (application_no_infrastructure 검사 추가)
.importlinter                                                     # S1 (application_independence_from_infrastructure 계약 추가)
tests/e2e/test_ws_e2e.py                                          # S3 (monkeypatch authority_mode 수용)
tests/integration/infrastructure/test_sqlite_work_object_store.py # S3 (v12 assertion)
tests/integration/semantic/test_migration_v6.py                   # S3 (v7 assertion)
tests/unit/infrastructure/test_observability.py                   # S2 (PII 테스트 10건 추가)
tests/unit/application/test_execution_router.py                   # S5 (Port 기반 DI 테스트)
```

### 5.3 확정된 계약 수치 (원래 계획서 수치와 변경됨)

| 항목 | 계획서 | 현재 | 비고 |
|------|:------:|:----:|------|
| `@tool` 등록 | 76 | 86 | S3 명명 인자화 후 learning(6)+portfolio(5) 완전 등록 |
| Hook | 30 | 30 | 변동 없음 |
| WS RPC | 80 | 80 | 변동 없음 |
| Pydantic entities | 156 | 156 | 변동 없음 |
| import-linter 계약 | 1 | 2 | `application_independence_from_infrastructure` 추가 |
| SQLite schema 최대 버전 | 12 | 13 | learning_store v13 + 중앙 러너 |

→ **Tier 2 A03류 재현 시 86 tool / 2 계약이 기준**.

---

## 6. Tier 2 진입 가이드 (다음 agent 액션)

### 6.1 스폰 전 체크

1. 본 문서 §4 결정 이력 숙지 — 같은 논의 반복 금지.
2. 계획서 §5 전수 정독 (B05~B12 책임·Pass 기준).
3. 계획서 §12 자체 기동 프롬프트 템플릿 확인.
4. §5.1~5.8을 §12 템플릿에 치환해서 각 agent 프롬프트 생성.

### 6.2 권장 스폰 전략

8개 동시 스폰 시 API rate limit / 500 에러 리스크 (S1 때 실제 발생). 사용자 확인 후 다음 중 선택:

**Option A (공격적 병렬)**: 8개 동시 스폰. 빠르지만 일부 실패 재스폰 필요 가능성.
**Option B (배치)**: 3-3-2 또는 4-4 배치로 순차 스폰. 안전하지만 시간 증가.
**Option C (선행 의존 기반)**:
- 1차: B05 (Agent Core) + B06 (Tools Fuzz) + B07 (Memory) — 기초 4개
- 2차: B08~B12 — 기초 위에서 동작하는 상위 기능

**기본 추천**: Option B (4-4 배치). 이전 경험(S1~S5) 기준 세이프.

### 6.3 각 agent 공통 제약 재강조

- **실패 시 소스 수정 금지** — 기록만. Fix Sprint Round 3를 이 문서에 추가.
- **real external adapter 호출 금지** — 전부 simulated / mocked.
- **스코프 밖 파일 금지** — 다른 agent 영역 건드리지 않음.
- **자기 pass 판정 금지** — 다음 Tier의 판정자가 결정.
- **전체 회귀 pytest 대신 스코프 격리 실행**을 pass/fail 신호로 (§4.5 참조).
- `data/` 실제 사용자 데이터 건드리지 말 것.

### 6.4 Tier 2 Hard Gate 기준 (계획서 §10.1)

- 30 hook 전부 fire 확인.
- 86 tool 전부 호출 가능 (계약 스키마 통과).
- 4-layer verifier 전부 경로 실행.
- 개별 도구 오류율 <5% (soft-fail 한도).

Tier 2 전부 pass 시 Tier 3 (C13 Parity, C14 Gold Tasks, C15 Packaging) 진입.

---

## 7. 잔존 추적 이슈 (Tier 2~4 중 해결 또는 post-beta로 이관)

| ID | 출처 | 설명 | 권장 이관 |
|----|------|------|----------|
| RC-1 | S5 | `tools/sandbox.py` lazy import chain (outer→outer, 계약 위반 아님) | post-beta |
| RC-2 | S5 | `ExecutionRouter` factory.py single-source wiring 통합 가능 | 여력 시 |
| RC-3 | S5 | `build_hook_registry`가 process-global state 의존 — 완전 DI 리팩터 가능 | post-beta |
| RC-4 | S5 | Windows `data/` directory 오염으로 테스트 flake | Tier 4 D16 Chaos |
| PRE-1 | S1/S5/A01 | `test_semantic_ports_are_runtime_checkable` pre-existing fail (memory/semantic) | 별도 스프린트 |
| PRE-2 | S1/A01 | mypy 3건 pre-existing 에러 | 유지보수 스프린트 |
| ENV-1 | 전 스트림 | Windows `.tmp/pytest` teardown PermissionError flake | Tier 4 D16 또는 환경 개선 |

---

## 8. 환경 및 명령어 참조

### 8.1 Python 도구

```bash
# 의존성 동기화 (dev extra 필수 — import-linter 포함)
uv sync --extra dev

# 정적 분석
ruff check src tests
ruff format --check src tests
mypy src/ds_agent
python -m compileall src
python scripts/check_import_contracts.py
lint-imports

# 테스트
pytest -x --tb=short                                 # 빠른 실패
pytest tests/unit/architecture/ -v                   # 아키텍처
pytest tests/unit/ tests/integration/ -v             # 유닛+통합 (전체 회귀는 Windows flake)
pytest -k "test_keyword" -v                          # 필터
```

### 8.2 에이전트 CLI

```bash
ds-agent --help
ds-agent task list
ds-agent eval board show
ds-agent learning inbox
```

### 8.3 패키징

```bash
python scripts/build_backend.py              # PyInstaller 단일 파일
cd electron && npm run build                 # Electron 빌드
cd electron && npm run test:contract         # 9 contract suites
cd electron && npm run test:e2e              # Playwright E2E
```

### 8.4 플랫폼 주의

- OS: Windows 11
- Shell: bash (Unix syntax — `/dev/null`, forward slashes)
- 리포지토리 `is a git repository: false` → `git log`·worktree isolation 불가, `code_sha`는 `git-unavailable`로 기록됨
- Python ≥ 3.11, uv 기반 env

---

## 9. 인계 시 묶어서 전달할 파일 (체크리스트)

인계 agent에게 다음을 **모두** 참조 가능하도록 전달:

- [x] **`Docs/qa_run_2026-04-17/HANDOFF_NEXT_AGENT.md`** (본 문서 — 먼저 읽기)
- [x] `Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md` (원본 계획서)
- [x] `Docs/DS_AGENT_COMPREHENSIVE_REPORT_2026-04-16.md` (시스템 종합)
- [x] `Docs/qa_run_2026-04-17/FIX_SPRINT_WORK_ORDER.md` (Fix Sprint 원칙 — 추후 재사용)
- [x] `Docs/qa_run_2026-04-17/` 폴더 **전체** (Tier 1 Round 1 + Fix Sprint S1~S5 + Round 2 재감사 전수)
- [x] 루트의 `pyproject.toml`, `.importlinter`, `uv.lock` (환경 재현용)
- [x] 메모리 항목 (있는 경우):
  - `feedback_preserve_autonomy`: LLM=orchestrator 원칙
  - `feedback_arch_pivot`: v2 autonomous agent 채택 이력
  - `feedback_ux_design`: LLM as renderer 원칙
  - `project_overview`: 189 tests passing 기준선

> 간단한 전달은 "`Docs/qa_run_2026-04-17/HANDOFF_NEXT_AGENT.md` 이 문서부터 읽고, 그 안의 §3 문서 지도를 따라가라"고 지시하면 충분하다.

---

## 10. Tier 2 결과 (2026-04-17 추가)

### 10.1 실행 전략
Option B (4-4 배치) 채택. 1차 batch (B05+B06+B07+B08) 동시 스폰 → 2차 batch (B09+B10+B11+B12) 동시 스폰.

- 1차 batch: 4/4 완료. 평균 7~15분 내외, API limit 이슈 없음.
- 2차 batch: B09/B12 완료, **B10/B11 Claude 구독 rate limit 도달** (resets 9am Asia/Seoul). 양 agent 모두 증거·리포트는 limit 도달 전 저장됨. B10은 FINAL.json까지, B11은 FINAL.json만 orchestrator가 증거 기반 재구성.

### 10.2 Gate 판정

**Tier 2 Gate: PASS (with FAIL-B11-8 → Fix Sprint Round 3)**

상세 판정 근거: `Docs/qa_run_2026-04-17/TIER2_GATE_DECISION.md` 참조.

- Hard Gate 4/4 통과 (30 hook fire / 86 tool / 4-layer verifier / <5% 오류).
- No-Go Trigger 0건.
- 주요 발견:
  - **FAIL-B11-8** (HIGH): `RollbackPromotionUseCase` 비원자성 — save_item + save_deprecation_record 트랜잭션 미감쌈. 감사 trail split 위험.
  - NOTE-B08-1: Promotion Gate staging도 3-of-3 (계획서 2-of-3과 불일치, 코드가 더 엄격).
  - RC-5: Slack/Jira/Confluence/Notion/Git connector 내부 kill-switch 부재 (hub policy에 의존).
  - D5-1: 계획서 `<ds:review_artifacts>` ≠ 코드 `<!-- DS_REVIEW_ARTIFACTS -->`.
  - B09-F2: FREEZE 모드 diagnostic read 일부 허용 (writes는 9/9 block).
  - ENV-2: B08 pandas/numpy 미설치 4 fail (환경).

### 10.3 Fix Sprint Round 3 권고 범위
1. **FAIL-B11-8 우선 해결** — `RollbackPromotionUseCase` 원자성 (single txn 또는 compensating revert).
2. 계획서 문서 정렬: NOTE-B08-1, D5-1, B11 D1~D4.
3. 아키텍처 검토: RC-5 adapter-level kill-switch 추가 여부.
4. 테스트 env 보정: ENV-2 dev extras.
5. Tier 3 진입은 Fix Sprint Round 3와 병렬 가능 (Tier 3 시나리오가 rollback atomicity를 직접 검증하지 않음).

### 10.4 Tier 2 산출물 경로
- 각 agent 출력 폴더: `Docs/qa_run_2026-04-17/B{05..12}_*/`
- 종합 판정: `Docs/qa_run_2026-04-17/TIER2_GATE_DECISION.md`

---

## 11. Tier 3 결과 (2026-04-17 추가)

### 11.1 실행 전략
Option 기반 3-agent 병렬 + 단독 조합. S6 Fix Sprint와 C13/C14를 동시 스폰 → C15 단독 → B11 Round 2 단독.

- S6 + C13 + C14 3개 병렬: 전원 완료 (rate limit 이슈 없음).
- C15 단독: PyInstaller+Electron 포트 경합 회피.
- B11 Round 2: S6 수정 후 독립 재감사.

### 11.2 Gate 판정

**Tier 3 Gate: PASS** — `Docs/qa_run_2026-04-17/TIER3_GATE_DECISION.md`.

- Hard Gate 3/3: C13 parity / C14 regression / C15 smoke 전부 통과.
- FAIL-B11-8 cleared (B11 Round 2 자체 독립 probe).
- 주요 발견:
  - **C13**: fallback(code-level factory equivalence) 명시. R4: factory time 75 vs runtime 86 tool count gap — 채널 간 parity는 유지되나 runtime-time 재검증 권고 (post-beta).
  - **C14**: baseline 없어 freeze candidate 기록. 이후 D17가 이 baseline 사용.
  - **C15**: build_success=true, smoke 5/5, READY race 10/10. C15-O1~O5 비차단. **C15-O6 (Main orchestrator 발견, 백그라운드 monitor)**: `ds-agent-api.spec:105` `ds_agent.memory.session_db` dead hidden import.
  - **S6**: atomicity 해결. **R-1/R-2/R-3 신규**: Promote/Deprecate/Review use case에 동형 이중-write 패턴 존재 — Fix Sprint R3 추가 스트림 후보.

### 11.3 Tier 4 진입 권고
- D16 단독 → 시스템 재정돈 → D17 단독 → D18 집계.
- D17 no-change delta 검사 전 환경 정비 필수.

### 11.4 Tier 3 산출물 경로
- 각 agent: `Docs/qa_run_2026-04-17/C{13,14,15}_*/`, `S6_rollback_atomicity/`, `B11_portfolio_learning_reaudit/`
- 종합 판정: `Docs/qa_run_2026-04-17/TIER3_GATE_DECISION.md`
- Fix Sprint 작업지시서: `Docs/qa_run_2026-04-17/FIX_SPRINT_R3_WORK_ORDER.md`

---

## 12. Tier 4 + 최종 판정 결과 (2026-04-17 추가)

### 12.1 실행 현황
- **D16 Chaos**: 단독 실행. 8/8 시나리오 복구, silent failure 0, cleanup 완료 (D16-spawned orphan 0). C15 잔류 orphan(`ds-agent-api.exe pid=193632`)은 주의 flag만.
- **orphan 정리**: 오케스트레이터가 D17 전에 pid=193632 종료 (Stop-Process, 깨끗한 상태 확보).
- **D17 Regression**: 5/5 경로 pass. **no-change delta = 0.0 (<1e-9) — §10.3 No-Go trigger 통과**. Synthetic 주입·alert dispatch·rollback byte-restore·daemon schedule 전부 확인.
- **D18 Release Readiness**: 17/17 agent FINAL.json 집계 완료.

### 12.2 최종 판정: **CONDITIONAL_GO**

`Docs/qa_run_2026-04-17/D18_release/RELEASE_GATE_DECISION.md`

- Hard Gate 전 Tier 통과.
- No-Go Trigger 0건 발동.
- Internal Blocker 0건 (FAIL-B11-8 등 이전 cluster 모두 Fix Sprint R1/R2/R3로 해결·재감사 확인).
- **External Blocker 5건** (조달 대기):
  - P0-05 Windows EV / Apple Dev ID 서명
  - P0-06 서명 바이너리 E2E
  - P0-07 Sentry DSN
  - P1-14 서명 auto-updater
  - P0-02 멀티플랫폼 keyring 실측
- KAG-1 (Python coverage ≥78% 수치 측정 불가): HANDOFF §4.5 원칙 근거 fallback 수용 (2200+ scope-isolated pass).

### 12.3 R4 후보 (post-release)
- **R-1/R-2/R-3**: Promote/Deprecate/Review use case에 FAIL-B11-8과 동형 이중-write 패턴. S6 RECOMMENDATIONS에서 이관. 주입된 중간 실패 시나리오에서만 노출되므로 이번 릴리스 non-blocking.
- 그 외 이월 표는 TIER2/TIER3 Gate Decision 문서의 §7/§6에 집계됨.

### 12.4 GO 전환 경로
외부 자격증명 조달 → 서명 빌드로 C15 smoke 5/5 + auto-updater live drill 재확인 → `GO` 전환. A01~D17 재실행 불필요(소스 변경 없는 한).

### 12.5 Tier 4 산출물 경로
- `Docs/qa_run_2026-04-17/D16_chaos/`
- `Docs/qa_run_2026-04-17/D17_regression/`
- `Docs/qa_run_2026-04-17/D18_release/RELEASE_GATE_DECISION.md`
- `Docs/qa_run_2026-04-17/D18_release/QA_RUN_SUMMARY.csv`

---

## 13. Post-QA Risk Mitigation 결과 (2026-04-17)

계획서: `Docs/plans/PLAN_post_qa_risk_mitigation_2026-04-17.md`. Addendum §9에 상세.

### 13.1 결과 요약

| 옵션 | 상태 | 핵심 메트릭 |
|:----:|:----:|-------------|
| C (PRE-1) | cleared | test_semantic_ports PASS — mock에 `fetch_glossary_terms` 추가 |
| C (PRE-2) | baseline freeze | **실측 383 error**를 `mypy-baseline.json`에 고정, `scripts/check_mypy_baseline.py`로 신규 error만 fail. HANDOFF §4.6 "3건" 표기 정정 |
| A (Coverage) | **81.53%** 실측 | `scripts/measure_coverage.py`, 리포트 `.tmp/qa_phase2/html|coverage_terminal.txt`. KAG-1 해소 |
| B (C13 process-level) | **9/9 run**, parity hash 일치 | `scripts/parity_harness/` 신설. C15 dist 재사용. Electron+CLI live 통과. Telegram은 `python-telegram-bot` 미설치로 factory wiring parity 수준까지만 — Round 1 gap 일부 유지 |

### 13.2 잔존 gap (post-release)
- Telegram process-level 실경로 (Updater polling)
- LLM record-replay fixture (mocked provider의 error-body를 parity signal로 사용 중)
- PRE-2 점진 해소 (레이어별 domain→api 순서)
- R-1/R-2/R-3 원자성 patterns
- RC-5 / C15-O6 / D5-1 / NOTE-B08-1

### 13.3 Internal Readiness 개선 요약

이번 사이클 이전: §10.1 GO 조건 중 3건이 fallback(coverage Clean 주장, C13 code-level parity, mypy Clean 주장).
이번 사이클 이후: 3건 모두 실측 또는 baseline 기반으로 업그레이드. **외부 자격증명 5건만 남은 순수 Conditional 상태**.

---

## 14. Post-Release Follow-ups 결과 (2026-04-18 추가)

계획서: `Docs/plans/PLAN_post_release_followups_2026-04-17.md`. **12 Sprint 완료** (S7/S8/S9/S10/S11~S13/S12/S14/S15/S16/S17~S19/S20).

### 14.1 핵심 성과
- **mypy baseline: 383 → 257 (126건 해소, -32.9%)**
- **Port atomic 메서드 3개 확립** (S6 + S9 + S10) → R-4 Epic-B RFC 트리거 충족
- **RC-5 in-adapter egress kill-switch 도입** — 5 connector 전수 `DS_AGENT_NETWORK_EGRESS_ENABLED` fail-safe default
- **3-Tier parity 최강도 증명**: S15 Telegram live (fake bot harness) + S16 LLM record-replay → 9 run byte-identical (실 LLM 성공 응답 hash 기준). 이전 mocked error hash 대비 업그레이드
- **문서 5건 drift 정정** + dead config 청소 + 37 `__init__.py` 정비
- **Clean Architecture 강화**: `WorkObjectStore` Protocol 확장 (3개 메서드 추가) — 계약-실구현 동기화

### 14.2 이월 (Epic / Post-Release)
- Epic-A `ws_handler.py` 분할 + 257건 잔여 mypy (runtime/api/gateway 중심)
- Epic-B R-4 일반화 `begin_transaction()` port RFC
- ~~**S-packaging-numpy**~~ → **closed 2026-04-18** (`Docs/qa_run_2026-04-17/S-packaging-numpy_spec_fix/`). 다만 이 sprint는 backend의 단순 import failure만 고침, ML 실행 경로는 여전히 비어있었음 — S-ml-stack-packaging으로 보완
- ~~**S-ml-stack-packaging**~~ → **closed 2026-04-18** (`Docs/qa_run_2026-04-17/S-ml-stack-packaging/`). sklearn/xgboost/lightgbm/matplotlib/seaborn/optuna/joblib core 의존성 + frozen-mode `--mode exec` 서브커맨드 + 번들 218MB→458MB. Packaged exe iris 97.4% accuracy 실증
- S-ruff-cleanup pre-existing ruff 정리
- evaluation scorer Protocol 추상화 (file-level pragma 13건)
- domain-pack-enterprise 이름 정책 RFC
- **3-way LLM 커버리지 gap** (POST_RELEASE_FALLBACK_ANALYSIS.md §5): Gemini OAuth(S21', paused — 사용자 구독 확보됨), Codex OAuth subprocess(S22, paused — `codex login` 필요), LOCAL MODEL chaos(S23), Router failover(S24). Gemini+Codex 2건이 완료되면 3-way 중 2개 OAuth 경로 live parity 확보. API matrix(S21 원안)는 제품 컨셉상 불필요로 강등 (3-channel parity는 provider-agnostic)

### 14.3 산출물 위치
- 각 Sprint CHANGELOG: `Docs/qa_run_2026-04-17/S{7,8,9,10,11,12,14,17,20}_*/CHANGELOG.md`
- RFC: `Docs/rfc/RFC_2026-04_adapter_killswitch.md`
- 스크립트: `scripts/check_mypy_baseline.py`, `scripts/measure_coverage.py`
- baseline: `mypy-baseline.json` (257 error frozen)

---

## 15. 변경 이력

| 날짜 | 변경 | 작성자 |
|------|------|--------|
| 2026-04-17 | 최초 작성 — Tier 1 완료 시점 인계 | Main orchestrator |
| 2026-04-17 | Tier 2 완료 업데이트 — Gate PASS, FAIL-B11-8 Fix Sprint Round 3 이관 | Main orchestrator |
| 2026-04-17 | Tier 3 완료 + S6 Fix + B11 Round 2 cleared — Tier 4 진입 가능 | Main orchestrator |
| 2026-04-17 | Tier 4 완료 + D18 CONDITIONAL_GO 판정 — QA 파이프라인 종료, 외부 조달 대기 | Main orchestrator |
| 2026-04-17 | Post-QA Risk Mitigation 완료 — A(coverage 81.53%) / B(9/9 parity) / C(PRE-1 cleared + PRE-2 baseline freeze). Internal readiness 강화 | Main orchestrator |
| 2026-04-18 | Post-Release Follow-ups 10 Sprint 완료 — baseline -33%, R-1~R-3 원자성, RC-5 egress kill-switch, doc drift 정정, `__init__.py` hygiene | Main orchestrator |
| 2026-04-18 | S15 Telegram live parity + S16 LLM record-replay 완료 — 3-Tier parity byte-identical on real LLM responses, $0.00013 | Main orchestrator |
| 2026-04-18 | S-packaging-numpy 완료 — numpy/scipy/pandas PyInstaller 번들 포함, packaged backend smoke 통과(`/health` 200, 18 skill load, READY). S16-FB2 closed. 이제 "진짜 실패" 0건 | Main orchestrator |
| 2026-04-18 | 이전 S-packaging-numpy의 "진짜 실패 0건" 주장이 실은 부분적이었음을 사용자 지적으로 발견 — sklearn 등 ML libs가 `.venv`에 없고 sandbox의 `sys.executable` 패턴이 frozen 모드에서 작동 안 함. 릴리스 판정 전 필수 복원 | Main orchestrator |
| 2026-04-18 | S-ml-stack-packaging 완료 — 8 Phase plan: RFC 2건, ML libs core deps(sklearn/xgboost/lightgbm/matplotlib/seaborn/optuna/joblib), sandbox frozen-mode 감지 + `ds-agent-api.exe --mode exec SCRIPT` 서브커맨드, PyInstaller collect_all 우회로 xgboost.dll 143MB 명시 번들링. Packaged exe에서 iris 97.4% accuracy 실증. 번들 218→458MB. Phase 4(Gemini OAuth)/Phase 5(Codex OAuth)는 사용자 구독 자격 승인 대기 | Main orchestrator |
| 2026-04-18 | S22 (Phase 5) 완료 — Codex OAuth subprocess fixture 3 scenarios 녹화, byte-identical replay 5/5 pass, secret leak 0. ChatGPT Plus 3턴 소모. OpenClaw-style 3-way LLM 커버리지 1/2 OAuth (Codex) 확보. Phase 4 Gemini CLI는 provider 재설계 필요로 보류 중 | Main orchestrator |
| 2026-04-18 | Phase 6 (S-ml-execution-parity) 완료 — source vs frozen sandbox 8/8 byte-identical on deterministic fields (iris 0.973684, sklearn 1.8.0). ML 실행 경로의 환경 대칭성 확보 | Main orchestrator |
| 2026-04-18 | S21 (Phase 4) 완료 — Gemini CLI OAuth subprocess provider 신규 작성(`gemini_cli.py`) + `gemini_oauth.py` auto-detect transport + 3 scenarios fixture 녹화 + byte-identical replay 6/6 pass. OpenClaw 직접 HTTP 방식 대신 안전한 `gemini -p` subprocess 채택. OAuth 2/2 CLEAR — 3-way LLM 커버리지 완성 | Main orchestrator |

---

*본 문서는 Tier 진행에 따라 업데이트된다. Tier 3 종료 시 "Tier 3 결과" 섹션을 추가하고, 최종 Go/No-Go 판정 후 `RELEASE_GATE_DECISION.md`로 이관한다.*
