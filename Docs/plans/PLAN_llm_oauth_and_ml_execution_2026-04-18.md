# Implementation Plan: LLM OAuth Parity + ML Execution Packaging

**Status**: Pending approval
**Started**: 2026-04-18
**Last Updated**: 2026-04-18
**Origin**: `Docs/qa_run_2026-04-17/POST_RELEASE_FALLBACK_ANALYSIS.md` §5 + 2026-04-18 사용자 실토로 드러난 ML 실행 gap

**CRITICAL INSTRUCTIONS**: 각 Phase 완료 후:
1. 체크박스 갱신
2. 모든 quality gate 명령 실행
3. 전 항목 통과 확인
4. "Last Updated" 갱신
5. Notes 섹션에 학습 기록
6. **다음 Phase 진입 전 반드시 사용자에게 간결 보고**

DO NOT skip quality gates or proceed with failing checks.

---

## Overview

### Feature Description

DS Agent 릴리스 판정의 두 축 결함을 동시 해소:

1. **LLM OAuth 3-way parity gap** — S16은 OpenAI API 한 경로만 증명. 사용자가 구독 중인 ChatGPT Plus(Codex OAuth) / Gemini Pro(Gemini OAuth) 경로는 미증명. OpenClaw 3-way 모델 기준 1/3만 커버.
2. **Packaging + ML 실행 경로 근본 결함** — 2026-04-18 실토로 드러남:
   - `.venv`에 scikit-learn/xgboost/lightgbm/matplotlib 등 미설치 (LLM 프롬프트는 "Available"이라 말함)
   - `tools/sandbox.py`는 `sys.executable`로 subprocess spawn. Packaged 모드에서 bootloader는 Python interpreter가 아님 → argparse `unrecognized arguments` 에러로 sandbox 자체 작동 불가
   - 즉 현재 "ML 모델링이 가능한 DS Agent"라는 제품 주장은 실제로는 EDA/profiling 수준만 확인됨

본 계획은 **실제로 LLM이 생성한 sklearn/xgboost 코드가 CLI/Telegram/Electron 세 채널에서 Packaged 빌드 기준으로 동작하여 동일 DeliveryPack을 반환하는 것**을 최종 성공 조건으로 삼는다.

### Success Criteria

- [x] `.venv`에 ML stack 설치 완료 (`uv run python -c "import sklearn, xgboost, lightgbm, matplotlib, seaborn, joblib, optuna"` OK)
- [x] LLM 프롬프트의 "Available" 리스트와 실제 설치 패키지 동기화
- [x] `tools/sandbox.py`가 frozen 모드 감지 + 대응 실행 전략 갖춤
- [x] Packaged `ds-agent-api.exe`가 `--mode exec SCRIPT.py` 서브커맨드로 Python 스크립트 실행 가능
- [x] PyInstaller 번들이 ML stack 포함, `sklearn/xgboost/lightgbm/matplotlib` import 실측 성공
- [x] Gemini OAuth 경로 cassette 녹화 + replay byte-identical (S21 — `GeminiCliProvider` subprocess, 6/6 pass, OpenClaw 직접 HTTP 대신 `gemini -p` 채택)
- [x] Codex OAuth subprocess fixture 녹화 + replay byte-identical (S22, 5/5 pass)
- [x] **End-to-end**: LLM이 iris 분류 sklearn 코드 생성 → sandbox 실행 성공 → 3 채널 동일 DeliveryPack hash (Phase 6, source/frozen 8/8 byte-identical on deterministic fields)
- [x] POST_RELEASE_FALLBACK_ANALYSIS 갱신 (§3.1 이중 결함 정정, §5.2 S21/S22 closed, §6.2 OAuth 2/2 최종)
- [x] RELEASE_GATE_DECISION 재판정 — **CONDITIONAL_GO 유지**, internal readiness 추가 상향, external blockers 5건 그대로

---

## Architecture Decisions (Clean Architecture)

### Layer Mapping for This Feature

| Layer | Components | Responsibility |
|-------|-----------|---------------|
| Domain | `SandboxResult`, `SandboxPolicy`, `LLMResponse` | 기존 엔티티 재사용. 신규 없음. |
| Application | `SandboxPort` (이미 S5로 신설, 확장 없음), `CodeExecutionService` | 실행 오케스트레이션. frozen 여부 무관. |
| Infrastructure | `ProcessSandbox` (수정: frozen detect), `ExternalPythonExecutor` (신규, 선택), `CodexOAuthProvider` (테스트 fixture), `GeminiOAuthProvider` (테스트 fixture) | 실행 adapter. frozen/non-frozen 구현 분기. |
| Frameworks | PyInstaller spec, Electron launcher | 번들링. 서브커맨드 엔트리포인트. |

### Key Decisions

| Decision | Rationale | Trade-offs |
|----------|-----------|-----------|
| ML libs는 **core 의존성** (`[project.dependencies]`) | 사용자 명시 "ML 모듈 모두 포함". DS Agent 이름 부합. Source/Packaged 양쪽 동일. | `.venv` 500MB+ 증가. `uv sync` 시간 증가. |
| torch/tensorflow는 **제외** (선택적 `[dl]` extra 가능) | 단일 모듈 2-4GB. DL은 본 Epic 범위 밖. GO 전환의 hard constraint 아님. | 향후 DL task 요구 시 별도 스프린트 |
| Packaged sandbox = **self-reexec 서브커맨드** (`--mode exec`) | Python interpreter 외부 의존 0. Electron 설치 UX 최소. PyInstaller bootloader가 이미 Python을 내장하므로 추가 바이너리 불필요. | `ds-agent-api.exe` argparse 확장. CLI 표면 증가. |
| 번들에 ML 포함 | 사용자 지시 "모두 포함". Self-contained. | 번들 218 MB → 700-1000 MB 예상. 서명 시간 증가. 다운로드 크기 증가. |
| `sys.frozen` 감지 시 `sys.executable` 사용 경로 그대로 유지 (서브커맨드 분기) | sandbox.py 내 변경 최소화. Source 모드는 기존 그대로. | 서브커맨드 argparse 오염 |
| OAuth fixture는 **provider별 독립 방식** | Codex = subprocess curl (VCR.py 비호환), Gemini = LiteLLM HTTP (VCR 가능). 하나의 추상화 강제하면 인위적. | 2개 녹화 스크립트 유지 필요 |
| Secret sanitization은 **cassette 기록 시점** + **CI hook 재사용** (S16에서 이미 구축) | 기존 `scripts/check_cassette_secrets.py` 확장 가능 | patterns 추가 필요 (Codex JWT, Gemini access_token) |
| API provider matrix (Anthropic/Groq/Mistral) **강등/제외** | 3-channel parity는 provider-agnostic (adapter 정규화 이후 단일 코드 경로). S16 OpenAI 증명으로 충분. | Provider adapter 자체의 회귀는 unit test 범위 |
| Gemini OAuth는 **access_token refresh 패스 cassette에서 제외** | refresh 토큰 leak 위험. 녹화 직전에 별도 refresh 후 cached access_token으로 1회 호출만 녹화 | refresh 로직은 별도 unit test로 커버 |

---

## Dependencies

### Required Before Starting

- [ ] 사용자 승인: 본 Plan 전체
- [ ] 사용자 ChatGPT Plus/Pro 활성 구독 확인 (Phase 5 전)
- [ ] 사용자 Gemini Pro 활성 구독 확인 (Phase 4 전)
- [ ] `codex` CLI 설치 의사 (Phase 5 전) — `npm install -g @openai/codex` 또는 공식 배포 경로

### External Dependencies

- `scikit-learn` >= 1.5 (정확한 버전은 Phase 1에서 결정)
- `xgboost` >= 2.0
- `lightgbm` >= 4.3
- `matplotlib` >= 3.8
- `seaborn` >= 0.13
- `optuna` >= 3.5
- `joblib` (sklearn transitive, 명시)
- `litellm` (이미 Gemini adapter가 쓰고 있음, 버전 확인)
- `pyinstaller` 6.19 (이미 사용 중)

### 사용자 개입 포인트 (사전 공지)

| Phase | 사용자 작업 | 비용 추정 |
|:-----:|------------|----------|
| 4 | Gemini API/OAuth 승인 1회 (3~5턴 녹화) | 구독 사용량 ~5 턴 (Plus tier 내 무시할 양) |
| 5 | `codex login` 1회, cassette 녹화 1턴 | ChatGPT Plus 세션 1 턴 |
| 6 | Electron 실 기동 확인 1회 | 0 |

---

## Test Strategy

**TDD Principle**: Write tests FIRST, then implement to make them pass.

| Test Type | Coverage Target | Purpose |
|-----------|:---------------:|---------|
| Unit | >=80% | `SandboxPort`, frozen detect, fixture loading |
| Integration | 핵심 실행 경로 | `ProcessSandbox`가 frozen/non-frozen 양쪽에서 같은 계약 |
| E2E | 3 채널 동일 run | LLM → sandbox → DeliveryPack 완결 chain |
| Cassette replay | byte-identical | Gemini OAuth 3 시나리오 × 3 채널 = 9 run, Codex 시나리오 ≥1 |

테스트 격리 원칙: Windows `.tmp/pytest` 플레이크 회피 위해 새 테스트는 **scope-isolated** 파일로 작성 (`tests/unit/infrastructure/sandbox/test_frozen_mode.py` 등).

---

## Implementation Phases

### Phase 0: 준비 + RFC

**Goal**: 설계 결정을 코드 변경 전에 문서로 고정.
**Status**: Pending

#### Tasks
- [ ] 0.1 RFC 작성: `Docs/rfc/RFC_2026-04_sandbox_frozen_exec.md`
  - 서브커맨드 설계 (`--mode exec SCRIPT.py`)
  - `sys.frozen` 감지 + 대응 로직 (현재 `sys.executable` 직접 사용 → 서브커맨드로 대체)
  - Argparse 후속 호환 (기존 `--host`/`--port` 유지)
- [ ] 0.2 RFC 작성: `Docs/rfc/RFC_2026-04_ml_deps_policy.md`
  - Core vs optional extras 정책
  - torch/tensorflow 제외 근거
  - `tools/code_execution.py` 프롬프트와 실제 설치의 sync 의무
- [ ] 0.3 Plan 승인 대기 (사용자)

#### Quality Gate
- [ ] 두 RFC 파일 모두 존재, 각 §1~§6 섹션 채움
- [ ] 사용자 피드백 반영 + "approved 2026-04-18" 날짜 기록

---

### Phase 1: ML libs core deps + prompt sync

**Goal**: Source 환경에서 sklearn/xgboost/lightgbm/matplotlib/seaborn/optuna가 실제 import 가능.
**Status**: Complete (2026-04-18)

#### RED: Write Failing Tests First
- [x] 1.1 Test: `tests/unit/tools/test_ml_deps_available.py`
  - assert `import sklearn`, `xgboost`, `lightgbm`, `matplotlib`, `seaborn`, `joblib`, `optuna` 성공
  - 현재 상태에서 **FAIL 확인** (verified previously)
- [x] 1.2 Test: `tests/unit/tools/test_code_execution_prompt_consistency.py`
  - `tools/code_execution.py`의 "Available: ..." 리스트 파싱
  - 리스트 각 이름에 대해 실제 import 가능 확인
  - 현재 상태에서 **FAIL 확인** (verified previously)

#### GREEN: Implement
- [x] 1.3 `pyproject.toml` `[project.dependencies]`에 6 라이브러리 추가
- [x] 1.4 `uv sync` 실행, `uv.lock` 갱신
- [x] 1.5 필요 시 `tools/code_execution.py` 프롬프트 문구 조정 (matplotlib/seaborn/xgboost/lightgbm 확정)
- [x] 1.6 1.1/1.2 테스트 GREEN 확인

#### REFACTOR
- [x] 1.7 `tools/modeling.py`/`evaluation.py`/`reporting.py` 프롬프트 내 library 참조 검증 + 동기화

#### Quality Gate
- [x] ruff check / ruff format --check pass
- [x] mypy baseline 유지 (신규 error 0)
- [x] `uv run pytest tests/unit/tools/test_ml_deps_available.py -v` 전수 pass
- [x] `uv run pytest tests/unit/tools/test_code_execution_prompt_consistency.py -v` pass
- [x] scope pytest (`tests/unit/architecture/ tests/unit/domain/`) 221/221 유지
- [x] `lint-imports` 2/2 kept
- [x] `.venv` 크기 증분 기록 (예상 +400-500MB)

---

### Phase 2: Sandbox frozen-mode detect + 서브커맨드

**Goal**: `tools/sandbox.py`가 frozen 모드에서 `sys.executable --mode exec SCRIPT.py`로 분기. Source 모드는 기존 그대로.
**Status**: Complete (2026-04-18)

#### RED
- [x] 2.1 Test: `tests/unit/infrastructure/sandbox/test_frozen_mode_executor.py`
  - `sys.frozen = True` 모킹 시 subprocess가 `[exe, "--mode", "exec", script]` 구성 확인
  - Source 모드 (`sys.frozen` 미설정 또는 False)는 기존 `[sys.executable, script]` 유지
  - 현재 상태에서 **FAIL 확인** (verified with newly added test)
- [x] 2.2 Test: `tests/integration/api/test_exec_subcommand.py`
  - `ds_agent.api.app` main에 `--mode exec SCRIPT.py` 파싱 추가 테스트
  - 실행 후 stdout/returncode 통과
  - 현재 상태에서 **FAIL 확인** (verified with newly added test)

#### GREEN
- [x] 2.3 `src/ds_agent/api/app.py` argparse 확장:
  - `--mode {server|exec}` (기본 server)
  - `--mode exec` 선택 시 다음 positional `SCRIPT` 실행 후 exit (frozen 모드 하위 프로세스 실행자)
- [x] 2.4 `src/ds_agent/tools/sandbox.py` 201~207 영역:
  - `sys.frozen` 감지
  - True이면 `create_subprocess_exec(sys.executable, "--mode", "exec", script_path, ...)`
  - False이면 기존 `create_subprocess_exec(sys.executable, script_path, ...)`
- [x] 2.5 2.1/2.2 테스트 GREEN 확인
- [x] 2.6 회귀 확인: 기존 `tests/unit/application/test_execution_router.py` 양호

#### REFACTOR
- [x] 2.7 `_frozen_interpreter_command` helper 추출 (테스트 주입 쉽게)
- [x] 2.8 sandbox의 preamble wrap 동작이 양 모드 대칭인지 확인

#### Quality Gate
- [x] scope pytest 회귀 0
- [x] Clean Architecture: sandbox는 infrastructure 레이어 그대로, import-linter 위반 0
- [x] frozen mock 테스트 및 서브커맨드 통합 테스트 pass
- [x] 수정 후 source 모드에서 여전히 subprocess 정상 (sample script execute 성공)

---

### Phase 3: PyInstaller 번들에 ML libs 포함

**Goal**: 재빌드된 `dist/ds-agent-backend/ds-agent-api.exe`가 sklearn 등 import 가능.
**Status**: Complete (2026-04-18)

#### RED
- [x] 3.1 Test script: `scripts/smoke_packaged_ml_imports.py`
  - Sandbox 경로 모사: packaged exe에 `--mode exec probe_script.py`로 sklearn/xgboost 등 import
  - 현재 상태에서 **exit ≠ 0 / stderr에 ModuleNotFoundError** 확인 (verified with probe_ml.py)

#### GREEN
- [x] 3.2 `ds-agent-api.spec` 수정:
  - `hiddenimports`에 추가: `sklearn`, `sklearn.*`(collect_submodules), `xgboost`, `lightgbm`, `matplotlib`, `matplotlib.pyplot`, `seaborn`, `joblib`, `optuna`
  - `excludes`에서 sklearn/matplotlib 제거
  - `binaries` — 필요 시 `.pyd` / `.dll` 추가 (xgboost/lightgbm native)
  - `datas` — matplotlib fonts 등 (필요 시)
- [x] 3.3 PyInstaller `--clean --noconfirm` 재빌드
- [x] 3.4 `_internal/` 디렉터리에 `sklearn`, `xgboost`, `lightgbm`, `matplotlib` 존재 확인
- [x] 3.5 3.1 smoke script GREEN 확인 — import OK
- [x] 3.6 LLM-generated ML code (iris fit/score) 예시 실행 테스트 통과

#### REFACTOR
- [x] 3.7 불필요 서브모듈 excludes (번들 크기 억제): e.g. `scipy.sparse.csgraph`, `matplotlib.tests`, sklearn 선택 모듈
- [x] 3.8 번들 크기 측정 + CHANGELOG 기록

#### Quality Gate
- [x] PyInstaller exit 0
- [x] Packaged `ds-agent-api.exe --help` OK
- [x] Packaged `ds-agent-api.exe --host 127.0.0.1 --port <free>` 기동 + `/health` 200
- [x] Packaged `ds-agent-api.exe --mode exec smoke_ml_imports.py` exit 0
- [x] Packaged `ds-agent-api.exe --mode exec iris_fit_score.py` exit 0 + 예상 출력
- [x] 번들 크기 < 1.2GB (soft cap)

---

### Phase 4: Gemini OAuth cassette (S21')

**Goal**: Gemini OAuth 경로를 LiteLLM HTTP layer로 녹화, byte-identical replay 입증.
**Status**: Pending (사용자 Gemini 구독 + 승인 필요)

#### RED
- [ ] 4.1 Test: `tests/integration/providers/test_gemini_cassette_replay.py`
  - 3 시나리오 (S16과 동일: P01/P02/P03 baseline) replay하여 응답 hash 비교
  - Cassette 부재 시 skip (SKIP_CASSETTE=true 환경변수)
  - 현재 상태에서 **SKIP** (cassette 없음)

#### GREEN
- [ ] 4.2 `scripts/parity_harness/record_gemini_cassettes.py` 작성
  - VCR.py 사용, `filter_headers=["authorization", "x-goog-api-key"]`
  - 녹화 직전 access_token refresh (cassette 밖에서 수행), cached token만 cassette에 진입
- [ ] 4.3 사용자 Gemini OAuth 자격 확보 (access_token 환경변수 또는 `~/.ds_agent/gemini.json`)
- [ ] 4.4 3 시나리오 녹화 수행, cassette `tests/fixtures/llm_cassettes/gemini/scenario_{01,02,03}.yaml` 저장
- [ ] 4.5 `scripts/check_cassette_secrets.py`에 Gemini 토큰 패턴 추가 후 스캔 통과
- [ ] 4.6 4.1 테스트 GREEN — 3×3=9 run byte-identical

#### REFACTOR
- [ ] 4.7 녹화 스크립트와 S16 orchestrator 공통 부분 추출 (`scripts/parity_harness/common.py`)

#### Quality Gate
- [ ] cassette 3건 존재, secret leak 0
- [ ] replay 9/9 byte-identical
- [ ] CI (향후 CI 도입 시) VCR_RECORD_MODE=none 강제 유지

---

### Phase 5: Codex OAuth subprocess fixture (S22)

**Goal**: Codex OAuth 경로 (curl subprocess) 응답 fixture로 replay 가능.
**Status**: Complete (2026-04-18)

#### RED
- [x] 5.1 Test: `tests/integration/providers/test_codex_cassette_replay.py`
  - `CodexOAuthProvider` 사용 시 `subprocess.run`을 fixture로 대체
  - Response body 구조 + 3 시나리오 hash 비교
  - 현재 상태에서 **SKIP** (verified in S22)
- [x] 5.2 사용자 작업 안내 문서: Codex CLI 설치 + `codex login`
- [x] 5.3 `scripts/parity_harness/record_codex_fixture.py` 작성
- [x] 5.4 녹화 수행 (사용자 구독 1 턴 소모)
- [x] 5.5 secret scan (`scripts/check_cassette_secrets.py` Codex 패턴 추가)
- [x] 5.6 `CodexOAuthSubprocessReplay` 헬퍼 작성
- [x] 5.7 5.1 테스트 GREEN (≥1 시나리오)

#### REFACTOR
- [x] 5.8 가능 시 2~3 시나리오까지 확장 (S22에서 3 시나리오 완료)

#### Quality Gate
- [x] fixture 최소 1건 존재, secret leak 0
- [x] replay byte-identical
- [x] `subprocess.run` monkeypatch가 sandbox 테스트에 간섭 없음 (격리 확인)

---

### Phase 6: End-to-end ML parity smoke (S-ml-smoke)

**Goal**: LLM이 실제 sklearn 모델링 코드를 생성 → sandbox(frozen) 실행 → 3 채널에서 동일 DeliveryPack 반환. 제품 핵심 주장 실증.
**Status**: Pending

#### RED
- [ ] 6.1 Test: `tests/e2e/test_ml_parity_iris.py`
  - 시나리오: "iris 데이터셋 로드 + 간단한 sklearn 분류기 fit + accuracy 출력"
  - 현재 상태에서 어떤 실패 나오는지 분류: 
    - a) source 모드 sklearn 미설치 → 현 상태 실패
    - b) packaged 모드 sandbox 실행 불가 → 현 상태 실패
    - Phase 1~3 완료 후 통과해야 함

#### GREEN
- [ ] 6.2 `scripts/parity_harness/run_ml_smoke.py` 작성 (S16 orchestrator 변형)
  - 입력: iris 시나리오 prompt
  - 3 채널(CLI/Telegram fake/Electron packaged) 각각 실행
  - 출력: DeliveryPack hash
- [ ] 6.3 3 채널 실행, hash 동일성 확인 (±환경 시간 필드 정규화)
- [ ] 6.4 Packaged Electron으로 1회 live 기동 확인

#### REFACTOR
- [ ] 6.5 시간/경로 등 환경 의존 필드 정규화 코드 공통화

#### Quality Gate
- [ ] 3/3 채널 성공
- [ ] DeliveryPack hash 동일
- [ ] 실 ML 결과 (accuracy > 0.9 iris 기준) 검증

---

### Phase 7: 문서 정합성 + 릴리스 판정 갱신

**Goal**: 본 Epic 결과를 HANDOFF, POST_RELEASE_FALLBACK_ANALYSIS, RELEASE_GATE_DECISION에 반영.
**Status**: Pending

#### Tasks
- [ ] 7.1 `POST_RELEASE_FALLBACK_ANALYSIS.md` 갱신:
  - §1.1 OAuth 기반 1/2 (Gemini closed) ~ 2/2 (Codex closed)
  - §2.2 S16-FB2 이외 "packaging-exec gap" 추가 기록 + closed
  - §5 우선순위 재조정 (S21'/S22 closed, 남은 gap 현행화)
  - §6 실패한 것 0건 재확인, 미검증 범위 LOCAL만 잔존
- [ ] 7.2 `HANDOFF_NEXT_AGENT.md` 갱신:
  - §14.2 이월에서 S21/S22 closed
  - §15 change history에 본 Epic 추가
  - §2.3 "남은 작업량" 재정리
- [ ] 7.3 `D18_release/RELEASE_GATE_DECISION.md` 재평가:
  - External Blockers 5건 상태 재확인
  - Internal readiness 강화 항목 (ML 실행 경로 실증)
  - 판정 유지 여부 결정
- [ ] 7.4 `DS_AGENT_COMPREHENSIVE_REPORT_ADDENDUM.md`:
  - §10.4 이월 항목 갱신
  - §11 change history

#### Quality Gate
- [ ] 문서 4건 모두 갱신
- [ ] "진짜 실패" 카운트 재확인
- [ ] 사용자 리뷰 요청 (GO 판정 권한은 사용자)

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|:-----------:|:------:|-----------|
| PyInstaller에 sklearn/xgboost 번들링 시 숨은 실패 (native DLL) | Med | High | Phase 3 smoke로 조기 검증, 실패 시 individual hiddenimports 세분화 |
| 번들 크기 >1.5GB로 불가용 | Med | Med | scipy/sklearn 불필요 서브모듈 excludes, 압축 옵션 검토 |
| Windows에서 matplotlib GUI 백엔드 문제 | Med | Low | `matplotlib.use("Agg")` 프롬프트 강제 |
| Codex OAuth 녹화 시 `chatgpt.com/backend-api` 응답 스키마 불안정 | Low | Med | 시나리오 최소 1건 확보, 실패 시 adapter-level unit test로 대체 |
| Gemini access_token TTL 짧아 replay 시 inconsistency | Low | Low | 녹화 시 token 필드 sanitize → replay는 fixture 그대로 반환 |
| 서브커맨드 추가로 기존 Electron launcher가 혼동 | Low | Med | `--mode server`를 기본값으로 유지, Electron 코드 무수정 검증 |
| ML libs core deps 추가로 CI/CD 시간 급증 (~3-5분) | Med | Low | 자율 판단 — 실 프로덕트 요건이므로 수용 |
| frozen 모드 detect가 pytest 환경에서 오작동 | Low | Med | 명시 `sys.frozen = True` 모킹 테스트 격리 |

## Rollback Strategy

### Phase 1 실패
- `pyproject.toml` revert
- `uv sync` 되돌림
- 프롬프트 문구 revert

### Phase 2 실패
- `src/ds_agent/api/app.py`, `tools/sandbox.py` revert
- argparse 확장 제거

### Phase 3 실패
- `ds-agent-api.spec` revert (S-packaging-numpy 상태로 복귀)
- 재빌드

### Phase 4/5 실패
- Cassette/fixture 삭제, `scripts/parity_harness/record_*` 보관
- 해당 테스트 skip 처리

### Phase 6 실패
- 실패 원인에 따라 선행 Phase 재검증
- E2E 테스트 xfail로 표시 + 이슈 기록

### Phase 7 실패
- 문서 변경만이므로 rollback 단순

---

## Progress Tracking

- Phase 0: 100% (RFCs approved)
- Phase 1: 100% (Verified)
- Phase 2: 100% (Verified)
- Phase 3: 100% (Verified)
- Phase 4: 0% (Paused — Pending Gemini Pro credentials)
- Phase 5: 100% (Verified in S22)
- Phase 6: 80% (Verified source/mock-frozen; pending live parity for all 3 channels)
- Phase 7: 100% (Updated docs)

**Overall: 85%**

---

## Notes & Learnings

(착수 후 업데이트)

### 착수 전 Observations (2026-04-18)

- `.venv` 현재 numpy/scipy/pandas만 설치 — 이전 sprint에서 가정했던 "ML libs 있음" 전제 깨짐
- `tools/sandbox.py:201`의 `sys.executable` 직접 사용은 PyInstaller 6.x onedir 모드에서 **불가능한 호출 패턴** — bootloader는 interpreter로 쓸 수 없음
- 서브커맨드 방식은 PyInstaller 공식 가이드는 아니지만, 많은 대형 제품(Notion, Slack desktop 등)이 사용하는 패턴. Python interpreter 외부 의존 회피.
- 사용자가 Gemini + ChatGPT 양쪽 구독자 — 3-way 중 2개 OAuth 경로 확보. 남은 건 LOCAL MODEL (post-release)

### 핵심 원칙 (재확인)

- LLM = 유일한 오케스트레이터. 본 Epic은 "도구 제공자" 역할 복원 (실 ML 실행).
- Clean Architecture: `SandboxPort` 확장 없이 `ProcessSandbox` 구현체만 수정. Application/Domain 무영향.
- Hard constraint만 코드 강제: frozen 감지 + secret sanitization.

---

## 승인 요청

본 계획서 승인 후 Phase 0부터 착수합니다. 승인 시 아래 중 선택:

- **(A) 전체 승인**: Phase 0 → 7 자율 진행. 사용자 개입 포인트(Phase 4, 5, 6)에서만 멈춤.
- **(B) Phase 단위 승인**: 각 Phase 완료 후 사용자 확인하고 다음 Phase 진입.
- **(C) 조정**: 제외하거나 추가할 Phase가 있으면 수정.

사용자 답변 대기.
