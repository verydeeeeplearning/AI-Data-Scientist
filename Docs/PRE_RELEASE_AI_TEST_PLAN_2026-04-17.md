# DS Agent — 상용 배포 전 자율 AI 검증 계획 (Pre-Release AI QA Plan)

**작성일**: 2026-04-17
**대상 시스템**: `AI_Data_Scientist_Demo` (DS Agent v0.1.0)
**기준 보고서**: `Docs/DS_AGENT_COMPREHENSIVE_REPORT_2026-04-16.md`
**검증 범위**: 18개 핵심 기능 / 76개 `@tool` / 30개 Hook / 80개 WebSocket RPC / 3-Tier 인터페이스 / 10개 Enhancement Spec
**검증 방식**: **사람 개입 없이** 복수의 AI Agent가 역할을 나눠 **정적 감사 → 기능 테스트 → 엔드투엔드 시나리오 → 회귀·복원력** 순으로 검증하고 Go/No-Go 판정을 내린다.

> **원칙**: 본 계획은 "LLM을 테스터로 쓰는 것"이 아니라, **자율 AI Agent 팀에게 검증 책임을 위임하여 결정론적 증거(로그·diff·커버리지·아티팩트)를 수집**하는 것이다. AI가 "괜찮아 보인다"고 말하는 것만으로는 통과할 수 없고, 모든 판정은 관측 가능한 신호로 뒷받침되어야 한다.

---

## 목차

1. [검증 철학과 원칙](#1-검증-철학과-원칙)
2. [AI Agent 팀 구성 및 역할 분담](#2-ai-agent-팀-구성-및-역할-분담)
3. [3-Tier 테스트 방법론 개요](#3-3-tier-테스트-방법론-개요)
4. [Tier 1 — 정적 코드베이스 감사](#4-tier-1--정적-코드베이스-감사-static-audit)
5. [Tier 2 — 기능별 행동 테스트](#5-tier-2--기능별-행동-테스트-feature-behavior-test)
6. [Tier 3 — 엔드투엔드 및 시나리오 검증](#6-tier-3--엔드투엔드-및-시나리오-검증)
7. [Tier 4 — 카오스·회복력·회귀 검증](#7-tier-4--카오스회복력회귀-검증)
8. [실행 오케스트레이션 및 의존성](#8-실행-오케스트레이션-및-의존성)
9. [테스트 아티팩트 및 보고 규약](#9-테스트-아티팩트-및-보고-규약)
10. [Go/No-Go 품질 게이트](#10-gono-go-품질-게이트)
11. [안티패턴 및 주의사항](#11-안티패턴-및-주의사항)
12. [부록: 에이전트 즉시 기동 프롬프트](#12-부록-에이전트-즉시-기동-프롬프트)

---

## 1. 검증 철학과 원칙

### 1.1 자율 검증의 핵심 공리

| # | 공리 | 구체적 의미 |
|---|------|------------|
| A1 | **LLM 판단은 증거가 아니다** | AI 에이전트가 "통과" 선언을 하더라도, 반드시 `pytest` 결과, 로그 라인, diff, 스크린샷, 메트릭 수치 같은 **기계가 재현 가능한 산출물**을 남겨야 한다. 판정은 산출물에 의거해서만 인정된다. |
| A2 | **정적 분석 → 동적 테스트 순서 엄수** | import 계약·타입·스키마·아키텍처 의존성 같은 정적 신호가 실패하는 채로 동적 테스트에 진입하지 않는다. 정적 단계에서 걸러낼 수 있는 문제를 E2E에서 발견하는 것은 비용·노이즈 낭비다. |
| A3 | **하나의 사실을 여러 관측으로 교차 검증** | 같은 동작을 코드 읽기 + 단위 테스트 + 통합 테스트 + E2E 로그 + 아티팩트 파일 검증 등 최소 2개 이상의 독립 관측점으로 확인한다. |
| A4 | **인간 없이 끝낸다** | 승인이 필요한 경로(autonomy Supervised/Incident, Promotion Gate 3-role)도 **테스트용 가짜 승인 경로**를 통해 자동으로 통과/거절 시나리오를 수행한다. 단, 실제 외부 서비스 전송(Email/Slack/Jira/Calendar)은 simulated adapter로만 테스트한다 (real-adapter kill switch 강제). |
| A5 | **각 Agent는 단일 책임** | 한 AI Agent가 모든 것을 보지 않는다. 코드베이스 핫스팟(`ws_handler.py` 4,434줄 등)과 기능 경계선 기준으로 책임을 분할해, 각자가 자신의 도메인에서 전문가 수준 증거를 수집한다. |
| A6 | **LLM=오케스트레이터 원칙 보존** | 테스트 중에도 에이전트의 자율성을 훼손하지 않는다. "원하는 결과가 나오도록 프롬프트 힌트를 추가"하는 식의 튜닝은 금지. 실패하면 실패로 기록한다. |
| A7 | **상용 배포 차단 조건은 외부 의존과 명확히 분리** | P0-05 (코드 서명), P0-07 (Sentry DSN) 같이 인증서/자격 조달이 차단 요인인 항목은 **"코드 레벨 Ready + 자격 조달 대기"**로 분리 판정한다. 테스트는 코드 레벨 Ready 여부까지만 확인한다. |

### 1.2 "rigorous"의 정의

본 계획에서 말하는 rigorous 점검은 다음을 모두 만족한다:

1. **전수 검증**: 76개 모든 `@tool`, 30개 모든 hook, 80개 모든 WebSocket RPC 메서드가 **최소 1개 자동 테스트에 커버**되어야 한다 (기능적 통과가 아닌, 호출 가능성 자체를 확인).
2. **경계값·악성 입력**: 각 도구와 hook에 대해 정상 입력, 경계값, 스키마 위반, timeout 초과, 샌드박스 위반 입력을 모두 시도한다.
3. **3-Tier 등가성**: 동일한 유스케이스가 CLI / Telegram / Electron에서 **동일한 결과를 낸다**는 것을 동일 시나리오의 3채널 실행으로 증명한다 (`create_agent()` 팩토리 보장의 관측 증명).
4. **결정론적 재현성**: 모든 테스트는 `pytest -x --tb=short` 단일 명령으로 재실행 가능해야 하고, random seed가 고정되어야 하며, 외부 네트워크 의존이 mocked 돼야 한다.
5. **격리 환경**: 각 테스트는 `tmp_path` / 임시 SQLite / workspace 샌드박스에서 실행되어 서로 오염되지 않는다. `tmp_path_retention_policy = "none"` 이미 설정됨.

---

## 2. AI Agent 팀 구성 및 역할 분담

### 2.1 팀 구성 원칙

- **15명의 특화 에이전트**를 4개 Tier에 걸쳐 배치한다.
- 동일 Tier 내 에이전트들은 **병렬 실행**된다 (단일 메시지에서 다중 Agent 툴콜).
- 다음 Tier는 **이전 Tier의 Quality Gate 통과 후**에만 진입한다.
- 모든 에이전트는 **자기 영역의 보고서 MD 1개 + 증거 파일들**을 `Docs/qa_run_<YYYY-MM-DD>/<agent-id>/` 아래에 남긴다.

### 2.2 전체 에이전트 매트릭스

| Tier | Agent ID | 이름 | 대상 도메인 | 핵심 책임 | 주요 증거물 |
|:----:|:--------:|------|-------------|----------|-------------|
| 1 | A01 | **Architecture Auditor** | Clean Architecture 경계, import 계약 | `scripts/check_import_contracts.py`, `.importlinter`, `tests/unit/architecture/*` 실행 + `domain/`이 외부 라이브러리를 import 하는지 AST 스캔 | `A01_arch_report.md`, import 위반 JSON |
| 1 | A02 | **Static Security Auditor** | 샌드박스·시크릿·PII | `tools/code_security.py` 테스트, `infrastructure/secrets/` keyring chunking 검사, Sentry redaction filter 검증, 하드코딩된 비밀 스캔 | `A02_security_report.md`, secret-scan 로그 |
| 1 | A03 | **Contract & Schema Auditor** | 76 tool 스키마, 30 hook 시그니처, 80 WS RPC 메서드, Pydantic 엔티티 | 각 `@tool` 데코레이터 파라미터 JSON Schema 유효성, `_METHOD_MAP` 전수 점검, Pydantic v2 model validate 테스트 | `A03_contract_matrix.csv` (n=186+), `A03_report.md` |
| 1 | A04 | **Migration & Config Auditor** | SQLite v1~v13 마이그레이션, Pydantic config v4, `pyproject.toml` 의존성 | 빈 DB → v13까지 순차 적용, 역방향 호환, YAML config 파싱 실패 케이스 | `A04_migration_log.txt`, config fixtures |
| 2 | B05 | **Agent Core & Hook Chain Tester** | `DSAgent.run()` 루프, `PromptBuilder`, 30 hook pre/post 체인 | 각 hook에 대해 ALLOW/DENY/MODIFY 3 경로 테스트, budget 소진 시 정확 종료, 토큰 예산 초과 시 섹션 드롭 검증 | `B05_hook_matrix.md` (hook × outcome 그리드) |
| 2 | B06 | **Tools Registry Fuzz Tester** | 76 tools (40 모듈) | 각 도구: 정상/경계/스키마 위반/timeout/샌드박스 위반 5 입력, `run_python`·`run_sql`·`run_bash`는 악성 페이로드 분리 | `B06_tools_fuzz.csv`, 실패 샘플 repro |
| 2 | B07 | **Memory & Semantic Tester** | 5계층 메모리, FTS5, semantic metric/glossary/trust, VQ store | SQLite FTS5 쿼리 정확성, `unified_store` 크로스레이어 조회, semantic-first + domain_kb fallback, dual-write 일관성 | `B07_memory_report.md` |
| 2 | B08 | **Task Contract / Verifier / Decision OS Tester** | Spec 01, 03, 06 | 계약 `draft→closed` 전체 수명주기, 4-layer verifier, 10-dim scorer, Promotion Gate 3-role 승인, RunDiff determinism | `B08_lifecycle_traces.json` |
| 2 | B09 | **Autonomy Control Plane Tester** | Spec 04 — Authority/Audience/Mission 3축, ActionMatrix, approval | 6개 Authority 모드 × 위험 도구 매트릭스, Incident 24h 오버라이드 자동 만료, Freeze 시 모든 도구 DENY 검증 | `B09_authority_matrix.csv` (6×N) |
| 2 | B10 | **Comms / Workflow / Export Tester** | Spec 07, 08 — DeliveryRouter, 6 export 포맷, 7 connector | 청중 5종 × 포맷 6종 = 30개 DeliveryPack 생성 + 한국어 round-trip, 7 connector simulated mode, DLQ 재시도 | `B10_delivery_matrix/`, export 파일들 |
| 2 | B11 | **Portfolio / Learning Governance Tester** | Spec 09, 10 (feature flag on/off 양쪽) | 4분면 전이 + `max_active_slots` hard constraint, 8-state learning machine, 2회 연속 eval 실패 → auto-deprecate, rollback 원자성 | `B11_state_traces.md` |
| 2 | B12 | **Provider Router & Cost Tester** | 10+ LLM providers, 가격 테이블, OAuth flows | 각 provider mocked endpoint, 비용 계산 정확성(토큰×가격=기대값), OAuth PKCE callback loopback, fail-over | `B12_provider_matrix.csv` |
| 3 | C13 | **Interface Parity Tester** | CLI + Telegram + Electron 등가성 | 동일 시나리오(예: 계약 생성 → EDA → 보고서) 3채널 실행, 최종 DeliveryPack 해시/내용 동등성 | `C13_parity_diff.md` |
| 3 | C14 | **Scenario Runner (Gold Tasks)** | Evaluation Harness Offline 모드 | 6개 도메인(finance/healthcare/marketing/ops/retail/saas) Gold Task 실행, 10-dim scorer + 베이스라인 diff | `C14_eval_board_snapshot.json` |
| 3 | C15 | **Packaging & Diagnostic Tester** | PyInstaller 바이너리, Electron NSIS, Diagnostic Panel | 패키지 바이너리 `/health`, READY:port:token race, backend crash → diagnostic window 전환, auto-updater mocked | `C15_package_smoke.log` |
| 4 | D16 | **Chaos / Recovery Engineer** | Startup recovery, 크래시, 동시성, degraded mode | kill -9, DB lock, keyring 비활성, 네트워크 drop, 세션 중 재시작 후 체크포인트 복원 | `D16_chaos_report.md` |
| 4 | D17 | **Regression Board Operator** | Eval baseline freeze, shadow compare, 회귀 알림 | 코드 미변경 상태 재실행 시 10-dim delta = 0 확인, 일부러 회귀 유발 → Slack/Teams mock 알림 수신 | `D17_regression_diff.json` |
| 4 | D18 | **Release Readiness Auditor** | 모든 Tier 결과 취합, Go/No-Go 판정 | A01~D17 보고서 합산, 차단 요인 분리(내부/외부), 최종 판정 서명 | `RELEASE_GATE_DECISION.md` |

> 총 **18개 에이전트**이지만 검증 Tier별 병렬성 덕분에 실제 실행 벽시계 시간은 **Tier 1(≈병렬 30분) + Tier 2(≈병렬 90분) + Tier 3(≈부분 병렬 120분) + Tier 4(≈60분)** ≈ **5시간 내 완주 가능**하게 설계.

### 2.3 에이전트 공통 규약

모든 에이전트는 다음 계약을 준수해야 한다:

1. **작업 시작 시**: `Docs/qa_run_<YYYY-MM-DD>/<agent-id>/START.json`에 `{agent_id, tier, started_at, inputs_hash}` 기록.
2. **작업 종료 시**: 동일 폴더에 `FINAL.json`에 `{status: "pass"|"fail"|"blocked", evidence: [파일 목록], metrics: {...}, duration_sec}` 기록.
3. **실패 시 처리 방침**: 즉시 fix 시도 금지. 실패를 **있는 그대로 기록하고** 다음 에이전트에 전파한다. 수정은 Release Readiness Auditor가 블로킹 이슈로 마크하면 **별도 fix sprint**에서 수행한다. (= 테스트 중 셀프 수정은 신호를 오염시킨다)
4. **테스트 데이터 격리**: 모든 임시 파일은 `.tmp/qa_<agent-id>/` 아래에 둔다. 실제 `data/` 디렉토리의 사용자 데이터를 변경·삭제하지 않는다.

---

## 3. 3-Tier 테스트 방법론 개요

```
┌───────────────────────────────────────────────────────────────────┐
│ Tier 0: Pre-flight (공통 준비)                                     │
│   - 깨끗한 git 체크아웃, uv sync, 의존성 설치, PyInstaller 바이너리 빌드  │
│   - `.tmp/qa_run_<date>/` 출력 폴더 생성                            │
│   - READY artifact 스냅샷 (코드 SHA, pyproject lock 해시)            │
└───────────────────────────────────────────────────────────────────┘
                              ↓
┌───────────────────────────────────────────────────────────────────┐
│ Tier 1: Static Audit (병렬 4 agents ≈ 30분)                        │
│   A01 Architecture | A02 Security | A03 Contracts | A04 Migration │
│   └ Gate: 모든 항목 pass 아니면 Tier 2 진입 금지 (hard gate)         │
└───────────────────────────────────────────────────────────────────┘
                              ↓
┌───────────────────────────────────────────────────────────────────┐
│ Tier 2: Feature Behavior (병렬 8 agents ≈ 90분)                    │
│   B05 AgentCore | B06 Tools | B07 Memory | B08 TaskContract       │
│   B09 Autonomy | B10 Comms | B11 Portfolio | B12 Provider         │
│   └ Gate: 각 feature 대상 >=80% 테스트 통과 + 0 critical            │
└───────────────────────────────────────────────────────────────────┘
                              ↓
┌───────────────────────────────────────────────────────────────────┐
│ Tier 3: End-to-End (부분 병렬 3 agents ≈ 120분)                    │
│   C13 Parity (CLI+TG+Electron) | C14 Gold Tasks | C15 Packaging   │
│   └ Gate: Parity diff 허용치 이내 + Gold Task baseline regression 無 │
└───────────────────────────────────────────────────────────────────┘
                              ↓
┌───────────────────────────────────────────────────────────────────┐
│ Tier 4: Chaos & Release Decision (≈ 60분)                         │
│   D16 Chaos | D17 Regression | D18 Release Readiness               │
│   └ Output: RELEASE_GATE_DECISION.md (Go / No-Go + 차단요인 목록)   │
└───────────────────────────────────────────────────────────────────┘
```

### 3.1 Tier별 Quality Gate 요약

| Tier | Hard Gate (실패 시 전체 중단) | Soft Gate (경고만) |
|------|-----------------------------|--------------------|
| 1 | Import 계약 0 위반 / ruff 0 error / mypy 0 error / 마이그레이션 v1→v13 성공 / 하드코딩 시크릿 0건 | typecheck warning, 테스트 커버리지 <78% |
| 2 | 30 hook 전부 fire 확인 / 76 tool 전부 호출 가능 / 4-layer verifier 전부 경로 실행 | 개별 도구 오류율 <5% |
| 3 | CLI↔Electron↔Telegram 동일 입력 → DeliveryPack 핵심 필드(goal, metric, verdict) 일치 / Gold Task 10-dim 회귀 0건 | E2E 실행 시간 p95 <180s |
| 4 | 재시작 후 체크포인트 복원 성공 / regression baseline delta = 0 (코드 무변경 상태) | chaos 경로 복구 시간 |

---

## 4. Tier 1 — 정적 코드베이스 감사 (Static Audit)

**목표**: 코드를 실행하기 전에, 구조·계약·경계·설정 수준에서 **시스템이 자기 자신이 주장하는 모습과 일치**하는지를 검증한다.

### 4.1 A01 Architecture Auditor

**책임**: Clean Architecture 4계층 의존성 규칙이 코드에 실제로 강제되는지 검증.

**입력**: 전체 리포지토리 + `.importlinter` + `scripts/check_import_contracts.py`.

**수행 절차**:

1. `python scripts/check_import_contracts.py` 실행 → exit code 0 확인.
2. `lint-imports` (import-linter) 실행 → 계약 위반 0건.
3. `pytest tests/unit/architecture/ -v` 실행.
4. **AST 직접 스캔**: `src/ds_agent/domain/**/*.py`의 `import` 구문을 파싱해 stdlib + `pydantic` + 프로젝트 내부 `ds_agent.domain.*` 외 어떤 import도 없음을 확인. 위반 시 파일:라인 기록.
5. `src/ds_agent/application/` 역시 `ds_agent.infrastructure.*`를 직접 import 하지 않음을 확인 (composition root `agent/factory.py` 예외).
6. **핫스팟 파일 검토**: `ws_handler.py` (≈4,434줄), `ipc.ts` (≈1,509줄), `MissionBriefPanel.tsx` (≈863줄)의 책임 분산 여부를 섹션 주석 기반으로 요약.

**Pass 기준**:
- import-linter 0 violations
- `tests/unit/architecture/` all pass
- Domain layer AST 스캔 외부 의존 0건

**산출물**: `A01_arch_report.md`, `A01_domain_imports.json`, `A01_hotspot_summary.md`.

### 4.2 A02 Static Security Auditor

**책임**: 실행 전 코드에서 발견 가능한 보안 위반을 검사.

**수행 절차**:

1. **시크릿 스캔**: `ripgrep` 기반 패턴 매칭으로 `sk-...`, `xoxb-...`, `AIza...`, `ghp_...` 등 하드코딩된 API key/token 검사. (테스트 픽스처 제외)
2. **코드 보안 스캐너 자체 검증**: `tools/code_security.py`에 대해 다음 악성 페이로드가 모두 차단되는지 단위 테스트:
   - `os.system("rm -rf /")`, `subprocess.Popen` 탈출 시도
   - `socket.socket(...)` 네트워크 직접 연결
   - `../../etc/passwd` 경로 탈출
   - `eval(...)`, `exec(...)`, `__import__("os")`
   - `urllib.request.urlopen("http://attacker...")`
3. **샌드박스 preamble 검증**: `infrastructure/sandbox/preamble_generator.py`가 주입하는 가드가 코드 상단에 포함되고 주석으로 비활성화되지 않음.
4. **Keyring 청크 분할**: `secret_storage.py`에서 1024+ char 시크릿이 `2560` byte Windows 한도 우회를 위해 청크 저장/복원 round-trip 테스트.
5. **Sentry redaction filter**: `sentry_backend.py`가 PII 패턴(이메일, 전화번호, 신용카드)을 이벤트 payload에서 제거하는지 샘플 이벤트 입력으로 검증.

**Pass 기준**: 하드코딩 시크릿 0건 + 악성 페이로드 전부 block + keyring round-trip 성공 + redaction 100%.

**산출물**: `A02_security_report.md`, `A02_secret_scan.txt`, `A02_sandbox_blocklist.csv`.

### 4.3 A03 Contract & Schema Auditor

**책임**: LLM/운영자가 접하는 모든 외부 표면(tool/hook/WS RPC/엔티티)의 스키마 일관성 검증.

**수행 절차**:

1. **도구 스키마 전수**: `src/ds_agent/tools/` 40 모듈을 파싱해 각 `@tool(...)` 호출의 `parameters` 인자에서 JSON Schema를 뽑아 `jsonschema.Draft202012Validator.check_schema(...)` 통과 여부 확인.
2. **도구 ID 유일성**: 76 tool의 `name`이 전역 유일.
3. **Hook 시그니처**: 30 hook이 `HookBase` 프로토콜 (또는 동등 Protocol)의 `on_pre_tool` / `on_post_tool` / `on_final_response` 중 최소 1개를 구현.
4. **WebSocket RPC 매트릭스**: `api/ws_handler.py::_METHOD_MAP`에 등록된 80 메서드명 추출 → 각 메서드의 request/response Pydantic 모델이 존재하고 validate 가능.
5. **Pydantic 엔티티**: `domain/entities/*.py` 30+ 엔티티에 대해 `model_json_schema()`가 throw 없이 생성되는지 확인.
6. **3-Tier 인터페이스 일관성**: CLI 서브커맨드 (`ds-agent task ...`) ↔ Telegram 명령어 (`/task`) ↔ Electron WS RPC (`taskContract.*`) 사이에 **같은 동사가 같은 효과**를 내는지 메서드 매핑 테이블 작성.

**Pass 기준**: 186+ 계약(76 tool + 30 hook + 80 WS) 100% 검증 + 엔티티 schema 생성 100%.

**산출물**: `A03_contract_matrix.csv` (컬럼: layer, id, schema_valid, cli_verb, tg_verb, ws_method), `A03_report.md`.

### 4.4 A04 Migration & Config Auditor

**책임**: DB 스키마 v1~v13 마이그레이션 + Pydantic config v4 + 의존성 정합성 검증.

**수행 절차**:

1. **빈 DB → v13 순차 적용**: 빈 SQLite 파일에 `infrastructure/migration/` 러너를 호출해 v1→v13 순차 실행 → 최종 스키마 dump → 기대 스키마와 byte-level diff.
2. **멱등성**: v13 적용 후 다시 `run_migrations()` 호출 → 변경 0건.
3. **역방향 로드 호환**: v10에서 멈춘 DB 파일을 로드해 v13까지 이어서 적용 성공.
4. **설정 스키마 v4**: `config/ds_agent.yaml` 샘플 + 고의로 invalid 필드 몇 개 → Pydantic ValidationError 명확한 error message.
5. **의존성 lock**: `uv.lock`과 `pyproject.toml`의 `[project.optional-dependencies]` 간 버전 constraint 충돌 없음.
6. **feature flag defaults**: `DS_AGENT_PORTFOLIO_ENABLED`, `DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1` 등 기본 off 확인.

**Pass 기준**: 13 마이그레이션 전부 성공 + 멱등 + config invalid 시 sharp error.

**산출물**: `A04_migration_log.txt`, `A04_config_fixtures/`, `A04_report.md`.

---

## 5. Tier 2 — 기능별 행동 테스트 (Feature Behavior Test)

**목표**: 각 Enhancement Spec / 핵심 기능이 문서가 주장하는 대로 **실제로 동작**함을 증명. 외부 서비스는 모두 mock/simulated adapter 사용.

### 5.1 B05 Agent Core & Hook Chain Tester

**대상**: `DSAgent.run()` 메인 루프 + `PromptBuilder` + 30 hook.

**테스트 시나리오**:

1. **Hook 전수 fire 검증**: dummy tool + mocked provider 환경에서 세션을 한 번 돌리고, 30 hook 중 **실제로 호출된 hook 목록**을 수집해 factory 등록 목록과 diff. 미호출 hook 발견 시 "dead hook"으로 플래그.
2. **Hook outcome 매트릭스**: 각 hook에 대해
   - ALLOW 경로: 정상 도구 호출 → 실행 성공
   - DENY 경로: 위험 파라미터 → 도구 실행 차단 + 메시지 반환
   - MODIFY 경로: 인자 수정 후 실행 (`LeakageDetectionHook`이 대표)
3. **BudgetGuardHook**: max_iter=3 설정 → 4번째 반복 시 정확히 중단, budget_exhausted flag 세팅.
4. **PromptBuilder 토큰 예산**: 예산이 매우 작을 때 필수 섹션(Identity, Authority, Safety)은 유지되고 선택 섹션(Portfolio, Learning hints)은 드롭되는지.
5. **Session Init Hook**: 세션 첫 턴에서 DS 방법론 규칙이 system prompt에 정확히 1회 주입.
6. **ReviewArtifactCaptureHook**: LLM 응답에 `<!-- DS_REVIEW_ARTIFACTS {...} -->` 블록 포함된 fixture → 아티팩트 저장소에 파싱된 결과 기록. (updated 2026-04-18, source: S7 D5-1 — 이전 문구 `<ds:review_artifacts>...</ds:review_artifacts>`는 계획서 drift였음; 코드 실제 contract는 HTML 주석 sentinel)

**Pass 기준**: 30 hook 전부 최소 1회 fire, 각 hook의 3 경로 중 적용 가능한 경로 전부 테스트.

**산출물**: `B05_hook_matrix.md`, `B05_fire_trace.jsonl`.

### 5.2 B06 Tools Registry Fuzz Tester

**대상**: 40 모듈 76 tool.

**테스트 절차**:

1. **목록 대조**: `tool_registry.list()` 출력이 소스에서 발견된 `@tool` 선언과 일대일 일치.
2. **정상 호출**: 각 도구에 fixture 입력으로 1회 호출 → JSON-serializable 문자열 결과.
3. **스키마 위반**: required 필드 누락, 타입 불일치 시 `ToolValidationError` 발생 (RuntimeError 아님).
4. **Timeout 강제**: 도구별 `timeout=N` 선언에 대해 그보다 오래 걸리는 mock 함수 주입 → TimeoutError 정확히 발생.
5. **샌드박스 위반**: `run_python`에 `import socket`, `open("/etc/passwd")`, 네트워크 요청 등 5종 악성 페이로드 → 전부 block.
6. **Workspace 경로 바운드**: `load_csv("../../../etc/shadow")` → `Path.is_relative_to()` 검증에서 거절.
7. **SQL 주입**: `run_sql`에 `; DROP TABLE users; --` → 파라미터 바인딩으로 무력화.
8. **멱등성(idempotent) 도구 분류 검증**: 같은 입력으로 2회 호출 시 결과 동일 (프로파일링, 쿼리류). `write` 계열 도구는 idempotent 대상 제외.

**Pass 기준**: 76 tool × 5 입력 = 380 cell 중 **0 critical failure** (정상 결과 없어도 되지만 정확한 에러 반환).

**산출물**: `B06_tools_fuzz.csv`, 실패 재현 스니펫 `B06_failures/`.

### 5.3 B07 Memory & Semantic Tester

**대상**: 5계층 메모리 + semantic memory + semantic proposal + dual-write.

**테스트 절차**:

1. **FTS5 전문 검색**: 세션 트랜스크립트 100건 삽입 → 한국어·영어 쿼리 검색 정확도(precision @10).
2. **Unified Store**: `query_domain_kb + query_session + query_project`를 한 번에 aggregate 하는 path가 각 하위 store 호출 순서·merge 규칙을 지키는지.
3. **Semantic-first + domain_kb fallback**: semantic에 "customer_ltv" 메트릭 있을 때/없을 때 `memory_query_service.get_metric()` 반환 소스 확인.
4. **Dual-write**: `store("domain_knowledge", ...)` 호출 시 domain_kb에 즉시 기록 + semantic proposal 큐에 하나 추가됨.
5. **Semantic proposal 승인/거부**: `/semantic_proposal approve <id>` path가 metric catalog에 실제 반영.
6. **DataTrustRegistry**: untrusted 소스에서 온 메트릭을 `SemanticReadGuardHook`이 경고.
7. **VerifiedQueryStore**: 동일 쿼리의 verified 버전이 있을 때 LLM에 제안 형태로 주입.

**Pass 기준**: 7 path 전부 기대 동작, FTS5 precision @10 ≥ 0.8 on 고정 쿼리 fixture.

**산출물**: `B07_memory_report.md`, `B07_semantic_proposal_trace.jsonl`.

### 5.4 B08 Task Contract / Verifier / Decision OS Tester

**대상**: Spec 01, 03, 06.

**테스트 절차**:

1. **Task Contract 수명주기**: `draft → agreed → in_progress → review → closed` 전이 + invalid 역전이(예: closed → in_progress) 차단.
2. **AssumptionLog verify**: 가정 2개 생성 → 1개 verify → ReviewVerdict 신뢰도 변동 확인.
3. **4-Layer Verifier**: L1 통계 실패, L2 데이터 결측 과다, L3 PII 포함, L4 LLM judge 논리 불일치 각각 독립 테스트 + 전체 통과 happy path.
4. **10-Dim Scorer**: 각 차원 최저/최고 fixture → 점수 차이 ≥ 0.5.
5. **Shadow Evaluation**: 같은 입력을 model A/B로 실행한 결과 비교 → diff 테이블 생성.
6. **Decision OS Promotion Gate**: 3-role(DS/Lead/MLOps) **전수 승인(3-of-3)** 이 staging 및 production 양쪽 모두 요구. 2명 이하 승인 상태는 전이 거부. (updated 2026-04-18, source: S7 NOTE-B08-1 — 이전 "2명만 승인 → staging 머무름 / 3명 승인 → production 이동" 문구는 spec drift였음. 실제 코드는 양쪽 단계 모두 3-of-3 강제. B08 Round 1 agent가 `PromotionGate`를 더 엄격한 정책으로 관찰하여 deviation NOTE-B08-1 보고함.)
7. **RunDiffEngine determinism**: 동일 입력 2회 실행 → byte-level 동일 diff.
8. **`DS_REVIEW_ARTIFACTS` 자동 캡처**: LLM 응답에 hidden block 포함 fixture → 실험 실행에 artifact 링크됨.

**Pass 기준**: 8 경로 전부 기대 동작 + Promotion Gate 역할 경계 정확히 enforcement.

**산출물**: `B08_lifecycle_traces.json`, `B08_verdict_samples/`.

### 5.5 B09 Autonomy Control Plane Tester

**대상**: Spec 04 — Authority / Audience / Mission / ActionMatrix.

**테스트 절차**:

1. **Authority 6 모드 × 위험 도구 매트릭스**: Shadow(전부 제안만), Supervised(매 도구 승인), Delegate(CAUTION만 승인), Autopilot(예산 내 자율), Incident(24h 오버라이드), Freeze(전부 DENY) 각 모드에서 SAFE/CAUTION/CRITICAL 도구 호출 → 기대 결과 매트릭스와 일치.
2. **Audience 5 페르소나**: 동일 입력 → Junior/Peer/Senior/Executive/Auditor 각각 다른 DeliveryPack 톤·깊이 생성.
3. **Mission Pack**: YAML mission 주입 → system prompt에 goal/constraint 섹션 포함됨.
4. **ActionClassifier**: SQL/deployment/governance/python/tool-map 5 전략별 분류 정확성.
5. **Incident 오버라이드 자동 만료**: 23h 59min 시점 여전히 활성, 24h 01min 시점 비활성.
6. **Freeze 강제**: Freeze 모드에서 SAFE 도구조차 DENY.
7. **Certification 영속화**: 인증 상태가 재시작 후 복원.
8. **PolicyStudio 프리뷰/적용**: 4 프리셋(delegated peer / executive review / audit guard / mentor walkthrough)이 ActionMatrix 정확히 반영.

**Pass 기준**: 6 × N 매트릭스 전 셀 기대치와 일치 + 오버라이드 경계값 정확.

**산출물**: `B09_authority_matrix.csv`, `B09_audience_diffs/`.

### 5.6 B10 Comms / Workflow / Export Tester

**대상**: Spec 07, 08.

**테스트 절차**:

1. **Export 포맷 × 청중 매트릭스**: 5 청중 × 6 포맷 = 30 DeliveryPack 생성 → 파일 존재 + 포맷별 구조 검증(PPTX 슬라이드 수, DOCX 헤딩 계층, PDF 페이지, IPYNB 셀 수).
2. **한국어 round-trip**: 한국어 텍스트 → export → parse back → string equality.
3. **DeliveryRouter 정책**: quiet_hours(22:00-08:00) 설정 → 23:00 트리거 시 digest 큐에 적재, 익일 08:00 일괄 발송.
4. **Rate limiter**: 분당 10건 초과 요청 → TokenBucket 거부 + backoff.
5. **7 Connector simulated mode**: Email/Slack/Notion/Confluence/Jira/Calendar/Git 각각 simulated 플래그에서 작동, real mode는 kill-switch로 강제 차단.
6. **DLQ 재시도**: 실패 payload → DLQ 기록 → `_REPLAY_REQUEST_TYPES` 매핑으로 정확히 복원 후 재시도.
7. **ML Handoff Spec**: Confluence/Jira handoff 템플릿이 필요 필드(Model version, owner, rollback plan)를 모두 채움.
8. **WorkObject 수명주기**: Intake → Executing → Review → Closed 전이 + 역전이 차단.

**Pass 기준**: 30 cell 매트릭스 100% + 한국어 round-trip string equality + real adapter 0건 호출.

**산출물**: `B10_delivery_matrix/`, 모든 export 파일들, `B10_report.md`.

### 5.7 B11 Portfolio / Learning Governance Tester

**대상**: Spec 09, 10 (feature flag on/off 양쪽).

**테스트 절차**:

1. **포트폴리오 4분면 전이**: Active ↔ Waiting ↔ Monitoring ↔ Candidates + 3 terminal(**completed / cancelled / archived**). 불법 전이(Candidates → Monitoring 직접)는 validator가 reject. (updated 2026-04-18, source: S7 B11-D1 — 이전 문구 `completed/failed/cancelled`는 spec drift; 실제 domain/portfolio 코드는 `archived`를 terminal로 사용하며 별도 `failed` 상태는 없음. 의미 동등(archived가 monitoring 이후 terminal absorb)이지만 문구 실측 기준 정정.)
2. **`max_active_slots` hard constraint**: slots=2로 설정, 3번째 `resume_task` 호출 → 거부 응답 + "현재 활성 작업 수"를 LLM에 정보 제공.
3. **PriorityCalculator**: 실제 계수는 `business_weight=2.0, sla_urgency=3.0, age_factor=0.5` 조합 → 공식에 따른 점수 일치. 우선순위 ordering intent(P0≫P3, overdue SLA 지배)는 동일. **LLM 실행 순서 강제 금지** 원칙 재확인 — 정보 제공만. (updated 2026-04-18, source: S7 B11-D2 — 이전 문구 `0.5/1.0/0.2`는 계획 단계 잠정 계수였으며 code truth는 `2.0/3.0/0.5`. B11 Round 1 agent가 `priority_calculator.py` 실측으로 drift 보고.)
4. **WaitCondition 4종**: Timer/Approval/Data Freshness/External 각 조건의 satisfied 판정 로직. **현재 Timer만 완전 기능, Approval/Data Freshness/External은 adapter 대기 상태이므로 `satisfied=False` + "requires adapter" 사유 반환** (v2 maturity gap으로 기록). (updated 2026-04-18, source: S7 B11-D3 — B11 Round 1 path 4 probe에서 확인. safe default는 `false-pending` — 절대 false-positive `satisfied=True`를 반환하지 않음.)
5. **학습 8-state machine**: `proposed → under_review → approved → promoted → monitored → deprecated → archived` 전체 경로 + invalid 역전이.
6. **Promotion threshold**: pattern=1.00, kb_entry=1.00, custom_skill=1.02 — threshold 미만이면 promoted 상태 불가.
7. **Auto-deprecation hard constraint**: 2회 연속 eval 실패 fixture → 자동으로 deprecated 상태 전이.
8. **Rollback 원자성**: PromotionRecord 롤백 중 중간 실패 주입 → DB 롤백되어 일관성 유지.
9. **Feature flag off**: `DS_AGENT_PORTFOLIO_ENABLED=false` 상태에서 관련 도구가 프롬프트에 노출되지 않음.

**Pass 기준**: 9 경로 전부 기대 동작 + hard constraint 2건 절대 우회 불가.

**산출물**: `B11_state_traces.md`, `B11_flag_on_off_diff.md`.

### 5.8 B12 Provider Router & Cost Tester

**대상**: 10+ LLM providers, 가격 테이블, OAuth flows.

**테스트 절차**:

1. **각 provider mocked endpoint**: Anthropic/OpenAI/Codex/Gemini/Groq/Mistral/Ollama/vLLM/LiteLLM 모두 mocked response로 `provider.chat(...)` 왕복.
2. **비용 계산**: 토큰 수 × 가격 테이블 = 예상 비용 (오차 없음).
3. **Streaming delta**: streaming mode 응답 → partial delta assembly가 final 문자열과 동일.
4. **OAuth PKCE flow**: ChatGPT/Gemini OAuth 2.0 PKCE 플로우 → localhost callback 서버에서 code 수신 → token 교환 mocked → 저장.
5. **Fail-over**: primary provider 503 → secondary로 전환 (만약 구현되어 있다면, 없다면 문서 예상 동작과 실제 차이 기록).
6. **Timeout 120s 강제**: mock이 130s 지연 → TimeoutError.

**Pass 기준**: 10 provider 전부 round-trip 성공 + 비용 오차 0 + OAuth 2 provider 전부 callback 성공.

**산출물**: `B12_provider_matrix.csv`, OAuth trace.

---

## 6. Tier 3 — 엔드투엔드 및 시나리오 검증

### 6.1 C13 Interface Parity Tester (CLI / Telegram / Electron)

**목표**: `create_agent()` 팩토리의 약속 — **3-Tier 인터페이스가 동일한 에이전트를 공유** — 를 관측 가능한 증거로 증명.

**시나리오 스크립트 (3채널 공통)**:

```
시나리오 P-01: 기본 분석 → 보고서
  1. 계약 생성: goal="tips.csv의 total_bill 예측", audience=Peer
  2. 데이터 로드 + 프로파일
  3. baseline 선형 회귀
  4. 평가 + DeliveryPack(PDF)

시나리오 P-02: 자율 모드 전환
  1. Authority 모드를 Supervised → Delegate
  2. CAUTION 도구 호출 (실험 기록 삭제 시도 — 가상)
  3. Approval 경로가 각 채널에서 기대대로 작동

시나리오 P-03: 학습 거버넌스
  1. 세션에서 패턴 추출 → LearningInbox
  2. review approve
  3. 프로모션 + 2회 eval 실패 → auto-deprecate
```

**채널별 자동화**:
- **CLI**: `subprocess.Popen(["ds-agent", ...])` + `pexpect` 또는 stdin 스크립트 주입
- **Telegram**: `python-telegram-bot` test harness + `TelegramSensor` fake updates
- **Electron**: Playwright E2E + `DS_AGENT_E2E_USE_BUILT_RENDERER=1` + `DS_AGENT_BACKEND_COMMAND` 주입

**동등성 판정**:
- 각 시나리오 종료 후 session DB에서 `task_contract.final_verdict`, `delivery_pack.content_hash`, `experiment.run_id`를 추출.
- 3채널 간 "비인프라 필드" 비교: goal, metric_spec, verdict confidence, DeliveryPack body (markdown 정규화 후).
- **허용되는 차이**: channel origin field, timestamps, session_id.
- **허용되지 않는 차이**: verdict 결과, goal content, DeliveryPack 본문.

**Pass 기준**: 3 시나리오 × 3 채널 = 9 실행 모두 성공 + 동등성 필드 100% 일치.

**산출물**: `C13_parity_diff.md`, 9 run 로그.

### 6.2 C14 Scenario Runner — Gold Tasks

**대상**: Evaluation Harness Offline 모드.

**수행 절차**:

1. `gold_tasks/` 아래 finance/healthcare/marketing/ops/retail/saas 6 도메인 Gold Task 전수 실행.
2. 각 Task에 대해 10-dim scorer 점수 수집.
3. 베이스라인(이전 커밋 스냅샷)과 dimension별 delta 계산.
4. delta ≤ 0.05 for all dimensions = 회귀 없음 판정. 초과 시 회귀로 플래그.
5. `ds-agent eval board show` 출력 스냅샷 저장.
6. `ds-agent eval board freeze-baseline` 실행 후 `ds-agent eval board send-alerts` mock 수신 확인.

**Pass 기준**: 6 도메인 전부 실행 완료 + 회귀 delta 0 + alert dispatch 정상.

**산출물**: `C14_eval_board_snapshot.json`, per-task traces, `C14_regression_report.md`.

### 6.3 C15 Packaging & Diagnostic Tester

**목표**: PyInstaller 바이너리 + Electron NSIS가 실제로 기동하고 복구 경로가 살아있는지.

**수행 절차**:

1. **바이너리 빌드**: `python scripts/build_backend.py` → `dist/ds-agent-api` single-file binary (≈43.5MB).
2. **Backend smoke**: 바이너리 실행 → `READY:port:token` stdout 수신 → `/health`, `/api/status`, WS `ping` 왕복 (P0-06 5/5 smoke).
3. **READY race**: 동시에 10 프로세스 실행 → 각각 서로 다른 포트 선택 + 토큰 유출 없음.
4. **Electron happy-path** (Playwright): onboarding → provider 선택 → 간단 chat → 세션 종료.
5. **Electron diagnostic path**: `DS_AGENT_BACKEND_COMMAND="false"` → backend 즉시 실패 → 진단 윈도우 전환.
6. **Auto-updater mock**: electron-updater에 fake feed 주입 → 업데이트 알림 UI 노출 (서명 대기이므로 실제 설치는 하지 않음).

**Pass 기준**: 6 경로 전부 성공 + READY race에서 충돌 0건.

**산출물**: `C15_package_smoke.log`, Playwright 비디오/스크린샷, `C15_diagnostic_trace.md`.

---

## 7. Tier 4 — 카오스·회복력·회귀 검증

### 7.1 D16 Chaos / Recovery Engineer

**시나리오**:

1. **Mid-session kill**: 분석 중간에 backend `SIGKILL` → Electron이 자동 재기동 → `startup_recovery.py` 체크포인트 로드 → 세션이 마지막 저장 지점부터 이어짐.
2. **SQLite lock**: 두 프로세스가 동시 write 시도 → 한쪽은 backoff 재시도, 최종 일관성 유지.
3. **Keyring 비활성 (degraded mode)**: OS keyring 접근 실패 → `describe_secret_storage()`가 in-memory fallback 경고를 CLI/UI에 표시, 세션은 진행 가능.
4. **네트워크 drop**: LLM provider 호출 중 네트워크 끊김 → timeout + retry with backoff → 3회 실패 후 사용자 알림.
5. **Disk full**: 임시 workspace가 가득 찬 상태에서 `run_python` → 샌드박스가 명확한 에러, 시스템 크래시 없음.
6. **Clock drift**: 시스템 시간이 역행(또는 +1일) → SLA 계산이 wrap-around 없이 처리.
7. **동시 세션**: 동일 사용자 5 세션 병렬 → 세션 격리(채널 identity + thread-aware) 유지.
8. **Incident 모드 강제 종료**: Incident 활성 중 앱 재시작 → 남은 시간 정확히 복원.

**Pass 기준**: 8 시나리오 전부 **복구 성공** 또는 **명확한 에러 + 사용자 알림**. silent failure 0건.

**산출물**: `D16_chaos_report.md`, 각 시나리오 로그 + 복구 trace.

### 7.2 D17 Regression Board Operator

**수행 절차**:

1. **No-change delta**: 코드 1 byte도 수정하지 않은 상태에서 regression board 재실행 → 10-dim delta 정확히 0.
2. **Synthetic regression**: `scoring.py` 임의 값 ±1% 주입 → delta가 해당 차원에만 정확히 반영됨.
3. **Alert dispatch**: 임계 초과 시 Slack/Teams mock webhook 수신.
4. **Daemon schedule**: `ds-agent-daemon` 에 cron-like schedule 등록 → 지정 시각에 자동 실행.
5. **Baseline freeze rollback**: freeze → 후보 평가 → rollback → baseline 원복.

**Pass 기준**: 5 경로 전부 정확 동작 + alert 100% 수신.

**산출물**: `D17_regression_diff.json`, alert payload 샘플.

### 7.3 D18 Release Readiness Auditor (최종 판정자)

**책임**: A01~D17의 모든 산출물을 수집해 **단 하나의 Go/No-Go 결정**을 내린다.

**수행 절차**:

1. 각 에이전트의 `FINAL.json` 수집 → status 집계 (pass/fail/blocked).
2. **내부 차단 요인**: Tier 1~2 어디든 hard gate 실패가 있으면 **No-Go**.
3. **외부 차단 요인**: 코드는 Ready지만 인증서·DSN 조달 대기인 항목(P0-05, P0-07, P1-14, P0-02 일부)은 **"Conditional Go"**로 분리.
4. **회귀 차단**: D17에서 non-zero baseline delta 발견 시 **No-Go**.
5. **결정 서명**: `RELEASE_GATE_DECISION.md`에 다음 필수 섹션 포함:
   - Decision: GO / CONDITIONAL_GO / NO_GO
   - Summary table (17 agents × pass/fail)
   - Internal blockers (있으면 해결 계획)
   - External blockers (조달 대기 항목)
   - Evidence links (모든 FINAL.json 경로)
   - Next action owner

**Pass 기준**: 자체적으로 통과/실패 없음 — 이 에이전트의 Pass는 **결정 문서를 생성했다는 사실**.

**산출물**: `RELEASE_GATE_DECISION.md`, `QA_RUN_SUMMARY.csv`.

---

## 8. 실행 오케스트레이션 및 의존성

### 8.1 의존성 그래프

```
Tier 0 (Preflight)
  │
  ├─→ A01 ─┐
  ├─→ A02 ─┤  (Tier 1 병렬, gate)
  ├─→ A03 ─┤
  └─→ A04 ─┘
           │
           ▼
  ┌─────────────┐
  │  Gate 1     │  All Tier 1 pass?
  └─────────────┘
           │ (yes)
  ┌────────┴────────────────────────┐
  ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼
  B05  B06  B07  B08  B09  B10  B11  B12   (Tier 2 병렬)
  │    │    │    │    │    │    │    │
  └────┴────┴────┴────┴────┴────┴────┴──► Gate 2
                                             │ (yes)
                                             ▼
                                    ┌──────┬──────┬──────┐
                                    ▼      ▼      ▼
                                    C13    C14    C15    (Tier 3 부분 병렬)
                                    │      │      │
                                    └──────┴──────┴──► Gate 3
                                                         │ (yes)
                                                         ▼
                                                   ┌─────┬─────┐
                                                   ▼     ▼
                                                   D16   D17   (Tier 4)
                                                   │     │
                                                   └──┬──┘
                                                      ▼
                                                      D18 (최종)
```

### 8.2 오케스트레이터 에이전트 프로토콜

하나의 **Orchestrator Agent**가 전체 흐름을 관리한다 (선택적이지만 권장). 역할:
- Tier별 gate 확인
- 병렬 에이전트의 `FINAL.json` 수집
- Tier 실패 시 다음 Tier 진입 차단 + D18에 블로킹 사유 전달
- 각 에이전트에 기본 컨텍스트 전달(working dir, output dir, code SHA)

권장 구현:
- `scripts/run_qa_pipeline.py` (없다면 신규 작성 대상이지만 테스트 계획 자체 범위에서 제외).
- 또는 AI 오케스트레이터가 Task 툴로 각 에이전트를 순차/병렬 스폰하여 진행.

### 8.3 병렬성 제약

- Tier 1: CPU-bound 정적 분석이므로 4 agents 완전 병렬 OK.
- Tier 2: B06 (tools fuzz)은 샌드박스 프로세스를 많이 생성하므로 동시 실행 시 다른 agents와 workspace 충돌 가능 → **작업 디렉토리 격리** 필수.
- Tier 3: C15 (패키징)은 빌드 캐시/포트 경합으로 C13/C14와 같은 머신에서 동시 실행 금지. C13+C14는 병렬 OK.
- Tier 4: D16 (chaos)은 process-kill을 수반하므로 **단독 실행**.

---

## 9. 테스트 아티팩트 및 보고 규약

### 9.1 디렉토리 구조

```
Docs/qa_run_2026-04-17/
├── SUMMARY.md                        # Release Readiness Auditor가 링크 집계
├── RELEASE_GATE_DECISION.md          # 최종 판정
├── QA_RUN_SUMMARY.csv                # agent × status 매트릭스
├── A01_architecture/
│   ├── START.json
│   ├── FINAL.json
│   ├── A01_arch_report.md
│   ├── A01_domain_imports.json
│   └── A01_hotspot_summary.md
├── A02_security/ ...
├── ...
├── D18_release/
│   └── RELEASE_GATE_DECISION.md
└── .tmp/                             # 재현용 raw 로그 (선택)
```

### 9.2 보고서 MD 공통 섹션

각 에이전트 보고서는 다음 섹션을 포함해야 한다:

```markdown
# <Agent ID> — <Agent Name>

**Tier**: 1|2|3|4
**Duration**: N min
**Status**: pass | fail | blocked
**Code SHA**: <git sha / code snapshot id>
**Dependencies**: (선행 에이전트 결과)

## 1. Scope
(이 에이전트가 검증한 범위 — 대상 모듈/기능/spec)

## 2. Methodology
(사용한 테스트 기법, mock 전략, fixture 출처)

## 3. Results Matrix
(표 — 항목별 pass/fail + 증거 파일 링크)

## 4. Failures and Anomalies
(발견된 이슈 + 재현 명령 + 원인 가설)

## 5. Evidence Index
- /path/to/evidence1
- /path/to/evidence2

## 6. Recommendations
(다음 tier 또는 수정 sprint에 넘길 이슈 리스트)
```

### 9.3 증거 요구사항

| 증거 유형 | 필수 조건 |
|----------|----------|
| `pytest` 결과 | JUnit XML + stdout 전문 저장 |
| 로그 | UTC timestamp + structlog JSON 포맷 |
| 스크린샷 (Playwright) | `electron/tests/smoke/out/` 아래 .png 저장 |
| 파일 해시 비교 | SHA-256 계산값 명기 |
| 커버리지 | `pytest-cov` HTML + terminal 요약 |

---

## 10. Go/No-Go 품질 게이트

### 10.1 최종 Go 조건 (ALL)

- [ ] Tier 1: 4개 에이전트 전부 `pass`.
- [ ] Tier 2: 8개 에이전트 전부 `pass`. 개별 feature의 optional 경로 실패는 soft-fail로 허용하되 보고서에 명시.
- [ ] Tier 3: C13 parity diff 허용치 이내 + C14 Gold Task 회귀 0 + C15 패키지 smoke 5/5.
- [ ] Tier 4: D16 chaos 8 시나리오 복구 + D17 baseline delta = 0.
- [ ] `ruff check`, `mypy`, `python -m compileall` 전부 clean.
- [ ] Python coverage ≥ 78%.
- [ ] 하드코딩 시크릿 0건.
- [ ] 3-Tier 인터페이스 등가성 9/9 성공.

### 10.2 Conditional Go (내부 Ready + 외부 대기)

다음은 **코드 레벨 pass이면 Conditional Go**로 분류하고, 운영 배포 직전에 외부 자원 조달 후 재검증 필요:

- P0-05 코드 서명 (Windows EV + Apple Developer ID)
- P0-06 서명 바이너리 E2E (P0-05 의존)
- P0-07 Sentry DSN 활성화
- P1-14 서명된 auto-updater
- P0-02 멀티플랫폼 keyring 실측

### 10.3 No-Go 트리거

다음 중 하나라도 해당되면 No-Go:

- Tier 1 hard gate 실패.
- Tier 2에서 security/auth 관련 critical 실패 (샌드박스 탈출, 시크릿 노출, PII 누설).
- D17에서 no-change regression delta ≠ 0 (= 시스템이 비결정적).
- 3-Tier 인터페이스 결과 불일치 (같은 입력인데 다른 verdict).
- 30 hook 중 등록되었으나 한 번도 fire 안 된 것이 있음 ("dead hook" = 아키텍처 주장 모순).

---

## 11. 안티패턴 및 주의사항

### 11.1 테스트 중 하지 말 것

| ❌ 안티패턴 | 이유 |
|------------|------|
| 실제 Slack/Email/Jira 전송 | 운영 데이터 오염 + 외부 수신자에게 noise. 반드시 simulated adapter + kill-switch. |
| 에이전트가 실패 발견 시 즉시 소스 수정 | 신호 오염. 기록만 하고 Release Auditor가 fix sprint로 넘김. |
| 프롬프트에 "이 테스트를 통과시켜줘" 힌트 주입 | LLM=오케스트레이터 원칙 위반. 실제 운영 환경과 괴리된 green을 만듦. |
| 동일 LLM이 테스트 작성 + 테스트 판정 동시 수행 | 자기 확증 편향. 판정은 **결정론적 메트릭**이 해야 한다. |
| 커버리지 숫자만 보고 pass 선언 | 78% 커버리지가 100% 경로 정확성을 보장하지 않음. 경계값·에러 경로를 별도 매트릭스로 확인. |
| E2E 실패를 "flaky"로 재시도 마스킹 | flakiness는 버그 신호. 재시도 없이 1-shot 성공을 원칙으로. 불가피하면 명시적으로 기록. |
| real-adapter feature flag on + 테스트 실행 | 글로벌 kill-switch 강제. 실수 방지. |
| `data/` 실제 프로젝트 데이터에 write | 격리된 tmp workspace만 사용. |

### 11.2 에이전트 간 정보 오염 방지

- 에이전트는 다른 에이전트의 **결론**을 읽지 않는다 (단, 선행 Tier의 fail 여부만 gate 확인용으로 본다).
- 같은 기능을 중복 검증하는 것은 OK — 오히려 교차 검증으로 신뢰도↑.
- Release Readiness Auditor만 **전체를 본다**.

### 11.3 LLM=오케스트레이터 원칙 보존 (사용자 repeat 강조 사항)

메모리 기록상 이 프로젝트는:
- **Workflow automation으로 역행 금지**.
- Scheduler/Governance는 정보 제공자·품질 게이트이지 controller가 아님.
- Hard constraint(SLA 상한, max_active_slots, 자동 폐기)만 코드가 강제.

테스트 설계가 이 원칙을 어기지 않는지 매 단계 자문:
> "이 테스트는 LLM의 판단을 대체하는 hardcoded path를 만들고 있지 않은가?"

만약 그렇다면 테스트 기준을 "정보가 정확히 전달되는가"로 재구성.

---

## 12. 부록: 에이전트 즉시 기동 프롬프트

오케스트레이터가 Task 툴로 각 에이전트를 스폰할 때 사용할 수 있는 **self-contained** 프롬프트 템플릿. 실제 사용 시 `{PLACEHOLDER}` 치환.

### 12.1 템플릿 (공통 헤더)

```
당신은 DS Agent Pre-Release QA 팀의 {AGENT_ID} {AGENT_NAME} 입니다.

## 컨텍스트
프로젝트 루트: C:\Users\aquap\Desktop\AI_Data_Scientist_Demo
전체 계획: Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md (이 문서)
종합 보고서: Docs/DS_AGENT_COMPREHENSIVE_REPORT_2026-04-16.md
출력 폴더: Docs/qa_run_2026-04-17/{AGENT_ID}/

## 책임
{AGENT_RESPONSIBILITY}

## 절차
{NUMBERED_STEPS}

## Pass 기준
{PASS_CRITERIA}

## 산출물
- START.json (작업 시작 시)
- FINAL.json (작업 종료 시 — status, evidence list, metrics)
- {AGENT_ID}_report.md (공통 섹션 준수)
- 기타 raw 증거 파일

## 제약
- 실패 발견 시 소스 수정 금지 (기록만)
- 외부 서비스 real 전송 금지 (simulated only)
- 테스트 데이터 격리 (.tmp/qa_{AGENT_ID}/)
- LLM 힌트로 green 만들기 금지
- 보고서 공통 섹션 템플릿 준수

시작해주세요. 완료 시 FINAL.json 경로와 상위 결과 요약만 반환하세요.
```

### 12.2 예시 — A01 Architecture Auditor 프롬프트

```
당신은 DS Agent Pre-Release QA 팀의 A01 Architecture Auditor 입니다.

## 컨텍스트
프로젝트 루트: C:\Users\aquap\Desktop\AI_Data_Scientist_Demo
출력 폴더: Docs/qa_run_2026-04-17/A01_architecture/

## 책임
Clean Architecture 4계층 의존성 규칙이 코드 수준에서 강제되는지 검증.
- domain/ → 외부 라이브러리 import 0건
- application/ → infrastructure 직접 import 0건 (composition root 제외)
- import-linter 계약 100% 통과
- tests/unit/architecture/ 전부 pass

## 절차
1. START.json 생성 (agent_id, tier=1, started_at=ISO8601, code_sha)
2. `python scripts/check_import_contracts.py` 실행 → exit code + stdout 저장
3. `lint-imports` 실행 (또는 `import-linter` CLI) → 위반 보고서 저장
4. `pytest tests/unit/architecture/ -v --junitxml=Docs/qa_run_2026-04-17/A01_architecture/junit.xml`
5. AST 직접 스캔: `src/ds_agent/domain/` 모든 .py 파일의 top-level import 수집 → 허용 목록 외 발견 시 파일:라인 기록
6. 대형 핫스팟 파일 3개의 섹션 구조 요약 (ws_handler.py, ipc.ts, MissionBriefPanel.tsx)
7. A01_arch_report.md 작성 (공통 섹션 준수)
8. FINAL.json 생성 (status, evidence, metrics)

## Pass 기준
- import-linter violations == 0
- tests/unit/architecture/ all pass
- Domain layer AST 외부 import == 0
- 모든 증거 파일 출력 폴더에 존재

## 제약
- 실패 발견 시 소스 수정 금지, 기록만
- 보고서 공통 섹션 템플릿 준수 (Scope, Methodology, Results Matrix, Failures, Evidence, Recommendations)

시작하세요.
```

### 12.3 다른 에이전트 프롬프트

A02~D18 각각에 대해 12.1 템플릿에 섹션 4~7(책임/절차/Pass 기준/산출물)을 이 문서의 해당 절(§4~§7)에서 복붙하여 생성. 각 에이전트는 공통 제약을 동일하게 상속한다.

---

## 부록 B — 참고 명령어 모음

### Python 테스트
```bash
pytest -x --tb=short -q                                  # 빠른 실패 피드백
pytest tests/unit/ -v --cov=src --cov-report=html       # 유닛 + 커버리지
pytest tests/integration/ -v -m integration             # 통합 (실제 외부 가능)
pytest tests/smoke/ -v                                   # 백엔드 스모크
pytest -k "test_portfolio" -v                            # 키워드 필터
```

### 정적 분석
```bash
ruff check .                                             # 린트
ruff format --check .                                    # 포매팅
mypy src/ds_agent                                        # 타입
python -m compileall src                                 # 파싱 검증
python scripts/check_import_contracts.py                # 의존성 계약
lint-imports                                             # import-linter
```

### 빌드/E2E
```bash
python scripts/build_backend.py                          # PyInstaller
cd electron && npm run build                             # Electron 빌드
cd electron && npm run test:contract                     # 9 contract suites
cd electron && npm run test:e2e                          # Playwright E2E
```

### 에이전트 CLI 실측
```bash
ds-agent --help
ds-agent task list
ds-agent eval board show
ds-agent learning inbox
```

---

## 부록 C — 변경 추적

| 날짜 | 변경 | 작성자 |
|------|------|--------|
| 2026-04-17 | 최초 작성 — 18개 에이전트 4-Tier 계획 정립 | AI QA Plan |

---

*이 계획은 상용 배포 직전 실행되며, D18 Release Readiness Auditor의 `RELEASE_GATE_DECISION.md`가 생성되기 전까지 배포는 보류된다. 계획은 라이브 문서이며, Tier 실행 중 발견되는 새로운 검증 포인트는 즉시 이 문서의 해당 절에 반영되어야 한다.*
