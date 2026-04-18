# DS Agent — 시스템 아키텍처 & 주요 기능 분석 보고서

**문서 버전**: 1.0
**작성일**: 2026-04-18
**문서 범위**: 시스템 설계, 아키텍처 레이어, 주요 기능, LLM/도구/샌드박스/패키징
**관련 문서**: UI/UX 및 디자인 세부 사항은 [`UI_UX_DESIGN_ANALYSIS.md`](./UI_UX_DESIGN_ANALYSIS.md) 참조

---

## 0. 문서 구성 안내 (Cross-Reference Guide)

본 프로젝트는 두 개의 분리된 분석 문서로 관리됩니다. 각 문서는 독립적으로 읽을 수 있지만, 서로 참조 지점이 명시되어 있어 함께 볼 때 완전한 이해가 가능합니다.

| 문서 | 범위 | 주요 독자 |
|------|------|----------|
| **본 문서** (`SYSTEM_ARCHITECTURE_AND_FEATURES.md`) | 기능, 아키텍처 레이어, LLM/도구/샌드박스, 패키징, 보안 모델 | 백엔드/플랫폼 엔지니어, 시스템 설계자 |
| [`UI_UX_DESIGN_ANALYSIS.md`](./UI_UX_DESIGN_ANALYSIS.md) | Electron/CLI/Telegram UX, 디자인 시스템, 컬러·타이포, 접근성, UX 플로우 | 디자이너, 프론트엔드 엔지니어, PM |

**교차 참조 표기**: 본 문서 내에서 UI/UX 측면의 내용이 필요한 부분은 `→ [UI/UX §N.N]` 형태로 표기합니다. 반대로 UI/UX 문서에서는 `→ [ARCH §N.N]`로 본 문서를 가리킵니다.

### 빠른 네비게이션 (본 문서 ↔ UI/UX 문서 매핑)

| 주제 | 본 문서 섹션 | UI/UX 문서 섹션 |
|------|--------------|----------------|
| 3-Tier 인터페이스 개요 | [§4. Interface Surface](#4-interface-surface-3-tier) | [UX §1. Interface Inventory](./UI_UX_DESIGN_ANALYSIS.md#1-interface-inventory) |
| LLM Provider (OAuth/LOCAL/API) | [§5. LLM Provider Architecture](#5-llm-provider-architecture-3-way-model) | [UX §8.2 모델 선택 UX](./UI_UX_DESIGN_ANALYSIS.md#82-모델-선택-ux) |
| 도구 호출 실행 | [§6. Tool System](#6-tool-system) | [UX §2.4 Tool Activity 시각화](./UI_UX_DESIGN_ANALYSIS.md#24-tool-activity-시각화) |
| 샌드박스 실행 | [§7. Sandbox & Code Execution](#7-sandbox--code-execution) | [UX §2.9 오류 처리 & 오버레이](./UI_UX_DESIGN_ANALYSIS.md#29-오류-처리--오버레이) |
| 세션/워크스페이스 | [§9. Session & Workspace](#9-session--workspace-management) | [UX §8.3 채팅 플로우](./UI_UX_DESIGN_ANALYSIS.md#83-채팅-플로우) |
| 보안 / OAuth | [§10. Security Model](#10-security-model) | [UX §8.1 온보딩 플로우](./UI_UX_DESIGN_ANALYSIS.md#81-온보딩-플로우) |

---

## 1. 시스템 개요

### 1.1 제품 정체성

**DS Agent**는 데이터 과학 엔드-투-엔드 워크플로우를 자율적으로 수행하는 **Hermes-스타일 AI 에이전트**입니다. 경직된 파이프라인/상태머신/페이즈 게이트 없이, **단일 while-loop**가 `LLM → tool_calls → execute → observe → repeat`을 무한 반복하며, LLM 자체가 모든 오케스트레이션을 담당합니다.

### 1.2 핵심 설계 원칙

| 원칙 | 내용 |
|------|------|
| **LLM = Orchestrator** | 워크플로우 자동화가 아닌 자율 에이전트 — 고정 파서/상태머신 금지 |
| **Clean Architecture 엄수** | `import-linter`로 도메인 독립성 강제 (4 계층: Domain → Application → Infrastructure → Presentation) |
| **3-Tier Interface** | CLI (터미널) + Telegram (모바일/원격) + Electron (데스크탑) |
| **3-Way LLM Connection** | OAuth (Codex/Gemini CLI) + LOCAL (Ollama/vLLM/SGLang) + API (Anthropic/OpenAI/LiteLLM) |
| **통합 ML 스택** | numpy, scipy, pandas, scikit-learn, xgboost, lightgbm, matplotlib, seaborn, optuna를 PyInstaller 번들로 포함 |

### 1.3 현재 상태 (2026-04-18 기준)

- **Python**: 3.11+
- **테스트**: 762/762 pass, 커버리지 목표 78%
- **릴리즈 게이트**: CONDITIONAL_GO (내부 준비 완료, 외부 blocker 5건 — 코드 서명/Sentry DSN/keyring 검증 등 procurement 범위)
- **주요 Epic 완료**: LLM OAuth (Codex + Gemini CLI 2/2), Sandbox frozen symmetry (source ↔ PyInstaller), ML 스택 번들링

---

## 2. 전체 시스템 토폴로지

```
┌────────────────────────────────────────────────────────────────────────┐
│                          USER INTERFACES                                │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────┐    │
│  │  CLI (TUI)   │  │ Telegram Bot │  │  Electron Desktop (React)  │    │
│  │ Typer+Rich   │  │ (python-tg)  │  │  Vite + Tailwind + Zustand │    │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬───────────────┘    │
│         │                 │                       │ WebSocket (auth)   │
│         └────────┬────────┴───────────────────────┘                    │
│                  ▼                                                      │
│         ┌─────────────────────────────────────────┐                    │
│         │      FastAPI Gateway (api/app.py)       │                    │
│         │  • WS handler (ws_handler.py, ~7K LOC)  │                    │
│         │  • REST routes (admin/config/files/…)   │                    │
│         │  • SEC-01 one-time token auth           │                    │
│         └────────────────────┬────────────────────┘                    │
└──────────────────────────────┼──────────────────────────────────────────┘
                               ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  AGENT CORE (autonomous while-loop)                     │
│   DSAgent (agent/core.py)                                               │
│   • LLM Provider (router → codex/gemini_cli/anthropic/…)                │
│   • ToolRegistry (40+ tools)                                            │
│   • Budget Tracker (token/cost/iteration/wall-time caps)                │
│   • 5-layer Memory (immediate / session / KB / code / project)          │
└──┬──────────────────┬─────────────────┬──────────────────────┬──────────┘
   ▼                  ▼                 ▼                      ▼
┌────────┐  ┌──────────────┐  ┌──────────────────┐  ┌─────────────────┐
│Domain  │  │ Application  │  │ Infrastructure   │  │  Presentation   │
│ (pure) │  │  (use cases) │  │ (adapters/ports) │  │  (formatting)   │
└────────┘  └──────────────┘  └──────────────────┘  └─────────────────┘
   │              │                    │
   │              │                    ├── providers/ (LLM)
   │              │                    ├── persistence/ (SQLite/FTS5)
   │              │                    ├── sandbox/ (ProcessSandbox)
   │              │                    ├── secrets/ (keyring)
   │              │                    ├── auth/ (OAuth)
   │              │                    ├── exporters/ (ipynb/md/pdf/pptx)
   │              │                    └── observability/ (Sentry)
```

---

## 3. 아키텍처 레이어 (Clean Architecture)

의존성 규칙은 **내측 단방향**이며, `.importlinter` 파일로 `import-linter` 툴에 의해 CI에서 자동 검증됩니다.

### 3.1 Domain Layer (`src/ds_agent/domain/`) — 최내측

**특성**: 프레임워크/I/O 무의존. 순수 Python dataclass 및 Protocol.

| 하위 | 주요 모듈 | 역할 |
|------|----------|------|
| `entities/` | `messages.py` (ChatMessage, LLMResponse, ToolCall, Role, Usage), `goal.py`, `session_checkpoint.py`, `sandbox.py` (SandboxPolicy, SandboxViolation), `experiment.py`, `model.py`, `feature.py`, `task_contract.py`, `delivery_pack.py`, `review_verdict.py`, `mission_pack.py`, `work_object.py`, `standing_order.py`, `certification.py` | 비즈니스 엔티티 |
| `value_objects/` | `budget.py` (BudgetPolicy — immutable cap 값) | 불변 값 타입 |
| `interfaces/` (ports) | `llm_provider.py`, `tool_registry.py`, `session_state.py` (TranscriptStore/CheckpointStore/GoalStore/WorkingMemoryStore), `delivery.py`, `learning.py`, `verifier_ports.py`, `portfolio.py`, `feature_registry.py`, `model_registry.py`, `task_contract.py`, `work_object.py` | 추상 포트 (의존성 역전) |

### 3.2 Application Layer (`src/ds_agent/application/`)

**특성**: 도메인만 참조. Infrastructure import 금지 (lint 강제).

| 하위 | 주요 모듈 | 역할 |
|------|----------|------|
| `usecases/` | `task_contract_usecases.py` (~500 LOC), `promotion_gate_usecases.py` (~450), `run_diff_usecases.py` (~300), `drift_analyzer.py` (~400), `work_object_usecases.py`, `post_deploy_usecases.py` | 애플리케이션 비즈니스 규칙 |
| `services/` | `audience_renderer.py` (~600 LOC — DS/임원/ML엔지니어 대상별 렌더링), `verifier_orchestrator.py` (~250), `policy_evaluator.py` (~250), `lineage_capture_service.py`, `artifact_generator.py`, `certification_usecases.py` | 오케스트레이션 서비스 |
| `dtos/` | Request/Response DTO (FastAPI 경계 전달용) | 계층 간 데이터 전송 |
| `ports/` | Application-level 인터페이스 (팩토리, 쿼리) | 입출력 포트 |

### 3.3 Infrastructure Layer (`src/ds_agent/infrastructure/`)

**특성**: Domain의 ports를 구현(adapter). 외부 세계와의 실제 I/O.

| 하위 | 주요 모듈 | 역할 |
|------|----------|------|
| `secrets/` | `secret_storage.py` (KeyringSecretStorage, InMemorySecretStorage), `config_secret_manager.py`, `api_key_manager.py`, `connector_secret_manager.py` | OS keyring 추상화. **P0-02 Windows 청크화**: 1024자 초과 시 `key__part0/1/…` 분할, `__ds_chunked__:N` 헤더 |
| `sandbox/` | `preamble.py` (~370 LOC — AST+regex 기반 30+ 금지 패턴), `sandbox_factory.py` | 프로세스 샌드박스 + 보안 프리앰블 |
| `persistence/` | `certification_store.py` (~350), `portfolio_store.py` (~450), `task_contract_store.py` (~600), `work_object_store.py` (~450), `learning_store.py` (~650), `postgres_adapter.py`, `snowflake_adapter.py`, `bigquery_adapter.py` | SQLite+FTS5 및 외부 DB 어댑터 |
| `observability/` | Sentry SDK (백엔드+Electron), DSA-* 오류 카탈로그, structlog | 관측성 |
| `exporters/` | `ipynb_exporter.py`, `markdown_exporter.py`, `pdf_exporter.py`, `pptx_exporter.py`, `template_registry.py`, `theme_loader.py` | 결과물 내보내기 (**P1-12 Artifact Export** 48 tests, 한국어 파일명/내용 round-trip) |
| `auth/` | Codex ChatGPT OAuth, Gemini Google OAuth 플로우 | OAuth 어댑터 |
| `verifiers/` | Statistical/Policy/Data/Narrative 검증 포트 구현 | 검증 어댑터 |

### 3.4 Presentation Layer (`src/ds_agent/presentation/`)

오디언스별 출력 렌더링 (데이터 과학자 / 임원 / ML 엔지니어). 차트 렌더링, 내러티브 생성. UI 자체는 별도 Electron 앱에 구현 → [UX §2](./UI_UX_DESIGN_ANALYSIS.md#2-electron-desktop-app-design-primary-focus) 참조.

### 3.5 Import-Linter 강제 계약

`.importlinter`에 2개 contract:
1. **Domain 독립성**: `domain/`이 `api/application/channels/cli/config/evaluation/gateway/infrastructure/memory/providers/runtime/self_improve/tools`로부터 import 금지
2. **Application/Infrastructure 경계**: `application/`이 `infrastructure/` import 금지

CI에서 `lint-imports` 실행 시 위반 시 빌드 fail.

---

## 4. Interface Surface (3-Tier)

> **UI/UX 세부**: 각 인터페이스의 시각 디자인/레이아웃/상호작용은 [UX §1–§4](./UI_UX_DESIGN_ANALYSIS.md#1-interface-inventory)를 참조.

### 4.1 CLI (TUI) — `src/ds_agent/cli/`

- **엔트리**: `main.py` (~450 LOC, Typer + Rich)
- **서브커맨드**: `semantic_cli`, `learning_cli`, `portfolio_cli`, `work_cli`, `task_contract_cli`, `verdict_cli`, `certification_cli`, `delivery_cli`, `integration_cli`, `mode_cli`
- **Wizard** (`cli/wizard/`): P1-08 온보딩 마법사 완성

### 4.2 Telegram Bot — `src/ds_agent/gateway/telegram_runner.py`

- **규모**: ~3800 LOC 단일 러너
- **기능**: 스레드 기반 세션 격리 (topic-aware), 구독/ack/mute/digest, 인라인 콜백, `/menu`, 오퍼레이터 감사로그
- **Delivery Policy**: quiet hours, digest cadence, timezone 자동화

### 4.3 Electron Desktop App — `electron/`

- **스택**: Electron 31 + React 18 + Vite + Tailwind + Zustand
- **테스트**: Playwright E2E + contract tests (delivery-preview, mission-brief, policy-studio, work-objects, verifier 등)
- **API 연결**: WebSocket (localhost:18790) — SEC-01 일회용 토큰 인증

### 4.4 API Gateway — `src/ds_agent/api/`

- **FastAPI `app.py`** (~150 LOC): Lifespan startup에서 READY 이벤트 발행 (Electron health check)
- **WebSocket handler `ws_handler.py`** (~7000 LOC): JSON-RPC 스타일 디스패치, AppState가 백그라운드 에이전트 세션 관리
- **CORS**: `localhost:5173` (Vite), `localhost:18790` (self), `127.0.0.1:5173`만 허용
- **Routes**: `admin`, `certification`, `config`, `files`, `integrations`, `status`, `support`, `task_contracts`, `usage`, `work_objects`

### 4.5 Provider Router — `src/ds_agent/providers/router.py`

- **모델 문자열 파싱**: `anthropic/claude-*`, `openai/gpt-*`, `gemini/`, `codex/`, `ollama/`, `litellm/*`
- **폴백 체인**: 1차 실패 시 자동 전환 → [UX §8.4 오류 복구](./UI_UX_DESIGN_ANALYSIS.md#84-오류-복구)

---

## 5. LLM Provider Architecture (3-Way Model)

OpenClaw의 3-way LLM connection 모델을 채택:

### 5.1 OAuth Mode (구독자 경로)

| Provider | 파일 | 인증 방식 |
|----------|------|----------|
| **Codex (ChatGPT Plus)** | `providers/codex_oauth.py` (~350 LOC) | `~/.codex/auth.json` JWT access_token + account_id |
| **Gemini (Google)** | `providers/gemini_cli.py` (~350), `providers/gemini_oauth.py` (~150) | `~/.gemini/oauth_creds.json` (Google OAuth2), subprocess 경유 `gemini -p PROMPT -o json` |

**Gemini CLI 구현 상세**:
- `_build_clean_env()`: IDE companion 환경변수(`GEMINI_CLI_IDE_*`, `TERM_PROGRAM`, `CURSOR_`, `ANTIGRAVITY_`) 제거 — workspace scan EPERM 방지
- Windows `cmd.exe /c` 래퍼로 `.CMD` shim argparse 안정화
- Single-line prompt 직렬화 (role marker inline) — multiline 시 CLI가 interactive input으로 해석하여 timeout 방지
- 직접 HTTP (`cloudcode-pa.googleapis.com`) 회피 — OpenClaw issue #14203 계정 차단 위험

### 5.2 LOCAL Mode

| Provider | 파일 | 비고 |
|----------|------|------|
| Ollama | `providers/ollama.py` (~150 LOC) | 로컬 추론 |
| vLLM / SGLang | local_discovery에서 auto-detect | 엔드포인트 `local_discovery.py` (~60 LOC) |

### 5.3 API Mode

| Provider | 파일 |
|----------|------|
| Anthropic | `providers/anthropic.py` (~350) |
| OpenAI | `providers/openai_provider.py` (~200) |
| LiteLLM (100+ models) | `providers/litellm_provider.py` (~150) |

### 5.4 공통 Base

- `providers/base.py` (~300 LOC): `LLMProvider` 추상 인터페이스, `messages_to_openai_format`, `openai_response_to_llm_response`, 도구 스키마 변환기
- `providers/pricing.py` (~150): 제공자별 토큰 비용 계산

### 5.5 Parity Harness (Fixture 기반 재생)

- `scripts/parity_harness/record_codex_fixture.py`, `record_gemini_cli_fixture.py`: subprocess.run 캡처, JWT/account_id/refresh_token/email 샌티타이즈
- 테스트: `tests/integration/providers/test_codex_fixture_replay.py`, `test_gemini_cli_fixture_replay.py` — byte-identical 재생 + sanitize guard
- `scripts/check_cassette_secrets.py`: 12 cassette에서 0 leak 검증 (JWT regex, Codex account_id UUID 패턴 포함)

---

## 6. Tool System

### 6.1 Tool Registry — `src/ds_agent/tools/registry.py`

- `@tool` 데코레이터 패턴 (Hermes 스타일)
- `ToolEntry`: `name`, `description`, `handler`, `category`, `parameters` (JSON schema), `timeout`, `prompt`, `safety_level`
- Async 디스패치, Unicode-safe 오류 로깅
- 40+ 등록된 도구 → [UX §5.3 Tool Call 시각화](./UI_UX_DESIGN_ANALYSIS.md#53-tool-call-시각화)

### 6.2 도구 카테고리

| 카테고리 | 주요 도구 | 역할 |
|---------|----------|------|
| **Core DS** | `data_loader`, `data_profiler`, `eda`, `feature_eng`, `modeling`, `evaluation`, `reporting`, `deployment`, `sampling_utils` | 엔드-투-엔드 워크플로우 |
| **Advanced** | `ab_test_tools`, `drift_tools`, `drift_analyzer`, `schema_tools`, `sql_tools`, `sql_result_summarizer` | 분석/검증 |
| **Integration** | `integration_tools` (Postgres/BQ/Snowflake), `governance_tools`, `distributed_tools` | 외부 데이터 + 오케스트레이션 |
| **Artifact & Learning** | `artifact_tools`, `learning_tools`, `decision_os_tools`, `task_contract_tools`, `standing_order_tools` | 자산 관리/스케줄링/학습 |
| **Memory** | `memory_tools` (semantic search, FTS5), `skill_tools`, `lookup_term`, `load_semantic_pack` | 지식 검색 |
| **Sandbox** | `sandbox` (ProcessSandbox + 프리앰블), `network_sandbox`, `code_execution`, `file_ops`, `code_security` | 격리 실행 |
| **Domain-Specific** | `ds_error_translator`, `portfolio_tools`, `feature_registry_tools`, `verifier_tool`, `web_search` | 특화 기능 |

### 6.3 Code Security — `src/ds_agent/tools/code_security.py` (~250 LOC)

- AST + regex 스캐너
- 30+ 차단 패턴: subprocess 실행, pickle/eval, 파일 경로 탈출, 네트워크 접근, 권한 상승
- 위반 시 프리앰블이 이벤트 발행 → UI 승인 모달 트리거 → [UX §2.9](./UI_UX_DESIGN_ANALYSIS.md#29-오류-처리--오버레이)

### 6.4 Network Sandbox — `src/ds_agent/tools/network_sandbox.py`

- LLM 작성 코드의 egress allowlist
- 허용 호스트: PyPI, huggingface, kaggle, pandas docs 등 데이터 과학 공식 소스

---

## 7. Sandbox & Code Execution

### 7.1 ProcessSandbox — `src/ds_agent/tools/sandbox.py` (~350 LOC)

- Subprocess 격리, per-call timeout
- **PyInstaller self-reexec** (`RFC_2026-04_sandbox_frozen_exec.md`):
  - Frozen 번들에서 외부 Python 인터프리터 불필요
  - `--mode exec SCRIPT` 서브커맨드로 자기 자신을 재실행
  - `_build_exec_command()`가 `sys.frozen` 감지
- `SandboxResult`: success, stdout/stderr, return_code, files_created, violations, execution_time_ms

### 7.2 Preamble Injection — `infrastructure/sandbox/preamble.py` (~370 LOC)

- 사용자 코드 **이전** 실행되는 보안 프리앰블
- 위반 이벤트 `sandbox.violation` 발행 → Electron UI 토스트/모달 노출
- Workspace 경계 검증 (`is_relative_to`)

### 7.3 Frozen/Source Parity

- `tests/integration/sandbox/test_ml_execution_parity.py`: IRIS 분류 8 tests, source vs frozen 동일 결과 검증
- `_hash_deterministic_fields()`: sklearn version + accuracy만 추출해 비교 (타임스탬프 등 non-deterministic 제외)
- `scripts/smoke_packaged_ml.py`: iris_accuracy=0.9737 + "SMOKE_OK"

---

## 8. Packaging

### 8.1 PyInstaller Spec — `ds-agent-api.spec` (~400 LOC)

**ML 스택 번들링** (`RFC_2026-04_ml_deps_policy.md`):

```python
# pure-Python
numpy, scipy, pandas, scikit-learn, matplotlib, seaborn, optuna, joblib

# native binaries (명시적 수집)
collect_submodules("xgboost", skip_substrings=("testing","dask","spark","federated"))
explicit: (f"{VENV_SITE}/xgboost/lib/xgboost.dll", "xgboost/lib")
lightgbm: collect_dynamic_libs
```

**제외**: torch, tensorflow (DL 프레임워크) — 초기 범위 제외, 추후 `[dl]` extra로 예약.

### 8.2 Electron Packaging — `electron/electron-builder.yml`

- NSIS (Windows), DMG (macOS), AppImage (Linux)
- Main process가 PyInstaller 바이너리 spawn
- Auto-update: `electron-updater` (P1-14 — 코드 서명 인증서 procurement 블로킹)

### 8.3 Dependency Summary — `pyproject.toml`

핵심 의존성: `keyring`, `pydantic>=2.0`, `structlog`, `PyYAML`, `python-dotenv`
ML/Data: `numpy>=1.26`, `scipy>=1.11`, `pandas>=2.2`, `scikit-learn>=1.5`, `xgboost>=2.0`, `lightgbm>=4.3`, `matplotlib>=3.8`, `seaborn>=0.13`, `optuna>=3.5`
Export: `markdown`, `python-docx`, `openpyxl`, `nbformat`, `python-pptx`
Providers: `anthropic>=0.30`, `openai>=1.30`, `litellm>=1.40`
Gateway: `fastapi>=0.115`, `uvicorn`, `websockets>=13`
Observability: `sentry-sdk==2.58.0`
CLI: `typer>=0.12`, `rich>=13`, `questionary`

---

## 9. Session & Workspace Management

### 9.1 Session State Ports — `domain/interfaces/session_state.py`

- `TranscriptStore`: 메시지 이력
- `CheckpointStore`: 목표/대화 상태 스냅샷
- `GoalStore`: 목표 추적
- `WorkingMemoryStore`: 즉시 컨텍스트

### 9.2 5-Layer Memory

| Layer | 구현 | 역할 |
|-------|------|------|
| 1. Immediate context | 작업 메모리 내 `ChatMessage` 리스트 | 실행 중 컨텍스트 |
| 2. Session DB | `memory/unified_store.py` (~350 LOC, SQLite+FTS5) | transcript, checkpoint, goal |
| 3. Domain KB | `memory/domain_kb.py`, `semantic/` 서브디렉토리 (임베딩) | 지식 베이스 |
| 4. Code Registry | 이전 실행에서 학습된 패턴 | 재사용 코드 |
| 5. Project Store | `experiment_log.py` (~450 LOC), `certification_store`, `portfolio_store`, `learning_store` | 실험 메타데이터/리니지 |

### 9.3 Workspace Isolation — `src/ds_agent/tools/path_utils.py`

- `is_relative_to` 상대 경로 검증 → workspace 탈출 방지
- File ops는 workspace 루트에 샌드박스됨

### 9.4 Experiment & Lineage

- `memory/experiment_log.py`: 실험 메타, 모델 성능, feature importance
- `infrastructure/persistence/lineage_store.py`: 데이터 프로비넌스, feature lineage, 모델 의존성 (RFC `lineage_spec.md`)
- `memory/experiment_compare.py`: cross-run 분석

---

## 10. Security Model

### 10.1 Credential Handling — `infrastructure/secrets/secret_storage.py`

- **Keyring backend** (OS 네이티브):
  - macOS Keychain
  - Windows Credential Manager
  - Linux Secret Service
- **In-memory fallback**: keyring 불가 시 volatile mode (CLI 배너로 경고 → [UX §3.1](./UI_UX_DESIGN_ANALYSIS.md#31-엔트리--시각적-계층))
- **P0-02 Windows fix**: 1024자 초과 값을 `key__part0/1/2/…`로 분할, `__ds_chunked__:N` 헤더로 원자적 기록
- `describe_secret_storage()`: CLI/UI 배너 생성

### 10.2 OAuth Flows

- **Codex**: 브라우저 OAuth, JWT + account_id keyring 저장
- **Gemini**: Google OAuth2, `~/.gemini/oauth_creds.json`
- 온보딩 플로우 UI → [UX §8.1](./UI_UX_DESIGN_ANALYSIS.md#81-온보딩-플로우)

### 10.3 WebSocket Authentication (SEC-01)

- FastAPI startup 시 일회용 토큰 생성
- stdout으로 Electron에 전달: `READY:<port>:<token>`
- Electron이 WS handshake Authorization 헤더에 포함
- `app.py`가 upgrade 전 검증

### 10.4 CORS Policy (SEC-04)

- Allowlist: `localhost:5173`, `localhost:18790`, `127.0.0.1:5173`
- 외부 오리진 전면 차단

### 10.5 Code Execution Security

- AST + regex 스캐너 30+ 패턴
- Network egress allowlist
- Workspace 경계 체크
- 위반 시 UI 승인 모달 / 토스트 → [UX §2.9](./UI_UX_DESIGN_ANALYSIS.md#29-오류-처리--오버레이)

### 10.6 Cassette Secret Leak 방지

- `scripts/check_cassette_secrets.py`:
  - `**/*.json`, `**/*.yaml` 스코프
  - Patterns: JWT 3-segment regex, `codex_chatgpt_account_id` UUID, `Bearer <placeholder>` 제외
  - 12 cassette 검증, 0 leak 확인

---

## 11. Testing

### 11.1 테스트 구조 (338 파일)

| 구분 | 위치 | 범위 |
|------|------|------|
| Unit | `tests/unit/{agent,application,domain,infrastructure,presentation,runtime,skills,tools,evaluation}` | 레이어별 단위 |
| Integration | `tests/integration/{api,application,evaluation,infrastructure,providers,runtime,sandbox,semantic,skills,tools}` | 컴포넌트 경계 |
| Smoke (Electron) | `electron/tests/smoke/*.spec.ts` | diagnostic-window, happy-path, autonomy-control-plane, task-contract-*, decision-os-review, workflow-integration |
| Contract (Electron) | `electron/tests/contract/*.spec.ts` | delivery-preview, mission-brief, policy-studio, work-objects, verifier, regression-board, semantic-metric-panel, project-control-tower, learning-inbox |

### 11.2 현재 상태

- **762/762** 테스트 통과
- **Import-linter**: 2개 contract KEPT
- **Cassette**: 12개 0 secret leak
- **Coverage 목표**: 78% (pyproject.toml `fail_under = 78`)

### 11.3 Cassette 시스템

- `tests/fixtures/llm_cassettes/`: VCR.py + 커스텀 subprocess fixture
- Providers: `codex`, `gemini_cli`, `manifest.json`
- Deterministic 시나리오: P01, P02, P03

---

## 12. Tech Stack Summary

| 영역 | 기술 | 버전 |
|------|------|------|
| Language | Python | 3.11+ |
| Backend | FastAPI | 0.115+ |
| WebSocket | websockets | 13.0+ |
| DB | SQLite + FTS5 | 내장 |
| Logging | structlog | 23.0+ |
| Validation | Pydantic | 2.0+ |
| Type Check | mypy | 1.10+ |
| Linter | ruff | 0.6.0+ |
| Test | pytest | 8.0+ |
| Observability | Sentry | 2.58.0 |
| **Frontend** | **React** | **18.3.1** |
| Desktop | Electron | 31.7.5 |
| Build | Vite | 5.4+ |
| CSS | TailwindCSS | 3.4.17 |
| State | Zustand | 4.5.5 |
| Desktop Builder | electron-builder | 24.13.3 |
| CLI | Typer + Rich | 0.12 / 13 |
| ML | scikit-learn / xgboost / lightgbm / pandas / numpy / matplotlib / seaborn | 1.5 / 2.0 / 4.3 / 2.2 / 1.26 / 3.8 / 0.13 |
| Tuning | Optuna | 3.5+ |
| Telegram | python-telegram-bot | 21.0+ |
| Keyring | keyring | 24.0+ |
| Arch Lint | import-linter | 2.0+ |

---

## 13. 관련 문서 (Related Documents)

### 13.1 내부 참조 (Docs/ 하위)

- [UI/UX & 디자인 분석](./UI_UX_DESIGN_ANALYSIS.md) — **본 문서와 쌍으로 작성된 파트너 문서**
- [DS Agent 종합 보고서](./DS_AGENT_COMPREHENSIVE_REPORT_2026-04-16.md)
- [2026-04-17 Addendum](./DS_AGENT_COMPREHENSIVE_REPORT_2026-04-17_ADDENDUM.md)
- [QA Run — 2026-04-17](./qa_run_2026-04-17/) (RELEASE_GATE_DECISION, POST_RELEASE_FALLBACK_ANALYSIS, HANDOFF_NEXT_AGENT)
- [Enhancement Roadmap](./ds-agent-enhancement-roadmap.md)

### 13.2 RFC 문서 (`Docs/rfc/`)

- `RFC_2026-04_sandbox_frozen_exec.md` — Self-reexec 서브커맨드 설계
- `RFC_2026-04_ml_deps_policy.md` — ML 의존성 정책 (core vs optional, DL 제외)
- `RFC_2026-04_lineage_spec.md` — 데이터/모델 리니지 스펙

### 13.3 Plan 문서 (`Docs/plans/`)

- `PLAN_llm_oauth_and_ml_execution_2026-04-18.md` — 8-Phase Epic (OAuth + ML 실행 경로 복구)
- `PLAN_17` — 제품화 capability 로드맵

---

## 14. 변경 이력

| 일자 | 주요 변경 | 참조 |
|------|----------|------|
| 2026-04-18 | 초판 작성. 시스템 아키텍처 전면 스냅샷. | 본 문서 |
| 2026-04-17 | Phase 5 (Codex OAuth), Phase 6 (ML parity), Phase 4 (Gemini CLI) 완료 → 3-way LLM 2/2 OAuth, sandbox 2/2 parity | `qa_run_2026-04-17/` |
| 2026-04-16 | PLAN_17 로드맵 P0/P1 마일스톤 | `DS_AGENT_COMPREHENSIVE_REPORT_2026-04-16.md` |

---

*본 문서는 `UI_UX_DESIGN_ANALYSIS.md`와 상호 참조되어 작성되었습니다. UI/UX 측면의 상세한 내용은 해당 문서를 참조하십시오.*
