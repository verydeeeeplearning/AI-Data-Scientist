# As-Is 시스템 분석: DS Agent (AI Data Scientist)

**작성일**: 2026-04-15
**대상 저장소**: `C:\Users\aquap\Desktop\AI_Data_Scientist_Demo`
**분석 범위**: 현재 메인 트리 기준의 아키텍처, 모듈, 인터페이스, 빌드/테스트 파이프라인, 운영 속성, 한계점

---

## 1. 요약 (Executive Summary)

DS Agent는 **LLM을 오케스트레이터로 사용하는 자율형 데이터 사이언스 에이전트**다. 고정된 워크플로/단계 게이트 없이 `LLM → tool_calls → execute → repeat` 단일 루프만을 돌며, 데이터 로딩·프로파일링·EDA·피처 엔지니어링·모델링·평가·리포팅을 수행한다.

- **상위 원칙**: LLM이 유일한 플래너. 하드코드된 상태 머신 없음.
- **배포 형태**: ① CLI(TUI) ② Telegram 봇 ③ Electron 데스크톱 앱 — 세 인터페이스가 동일한 에이전트 코어를 공유.
- **아키텍처 스타일**: Clean Architecture 4계층(Domain / Application / Infrastructure / Presentation).
- **현재 상태(2026-04-15)**: PLAN_10~15 완료, PLAN_17 캐파빌리티 로드맵 진행 중, 베타 출시(Productization) **P0 대부분 완료 / P0-05(코드서명)·P1-14(자동업데이트)는 인증서 조달 블록**.
- **검증 베이스라인**: `pytest tests/unit tests/smoke` → **1,382 통과**, Electron E2E 2/2 통과, 패키지 바이너리 스모크 5/5 통과.

---

## 2. 아키텍처 전경

### 2.1 고수준 구성도

```
┌─────────────────────────────────────────────────────┐
│  Interface Layer                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ CLI (TUI)│  │ Telegram │  │ Electron Desktop │  │
│  └─────┬────┘  └────┬─────┘  └────────┬─────────┘  │
│        └────────────┼─────────────────┘              │
│                     ▼                                │
│  ┌─────────────────────────────────────────────┐    │
│  │  Agent Core (single while loop)              │    │
│  │  LLM → tool_calls → execute → loop          │    │
│  ├─────────────────────────────────────────────┤    │
│  │  Tool Registry (@tool 자기등록)              │    │
│  │  Skills: builtin 8 + shared 6 (Markdown)    │    │
│  │  Memory: Session + Experiment + Domain KB + │    │
│  │           Code Registry + Project Store      │    │
│  │  Runtime: approvals, digest, policy, sensor, │    │
│  │           recovery, delivery policy          │    │
│  │  Self-Improvement: pattern/skill learning    │    │
│  ├─────────────────────────────────────────────┤    │
│  │  Provider Router                             │    │
│  │  Anthropic │ OpenAI │ Codex │ Gemini │ Groq  │    │
│  │  Ollama │ vLLM │ SGLang │ LiteLLM(100+)     │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

### 2.2 Clean Architecture 매핑

| 계층 | 위치 | 책임 |
|------|------|------|
| **Domain** | `src/ds_agent/domain/` | 엔티티, 값 객체, 도메인 인터페이스(포트). 외부 의존성 0. |
| **Application** | `src/ds_agent/application/` | 유즈케이스, DTO, 애플리케이션 포트. Domain에만 의존. |
| **Infrastructure** | `src/ds_agent/infrastructure/` | 영속성, 인증(OAuth/PKCE), 시크릿, 샌드박스, 관측, 마이그레이션 등 포트 구현체. |
| **Presentation** | `src/ds_agent/cli/`, `src/ds_agent/api/`, `electron/src/renderer/` | 입출력 번역 계층 (TUI, FastAPI, React). |

의존성 규칙은 `CLAUDE.md`에 정의되어 있으며, 릴리스된 모든 기능은 "Domain은 외부 패키지를 import하지 않는다", "Use case는 Port 인터페이스에만 의존한다"를 강제하는 퀄리티 게이트를 통과한 상태다.

---

## 3. 소스 트리 (중심 모듈)

```
src/ds_agent/
├── agent/              # 코어 루프, 훅, 퍼미션, 프롬프트 빌더, 버짓 트래커
│   ├── core.py                         # 에이전트 메인 루프
│   ├── hooks.py / builtin_hooks.py     # Pre/Post-tool 훅 인프라
│   ├── ds_workflow_hooks.py            # DS 특화 훅
│   ├── governance_hooks.py             # 퍼미션/거버넌스 훅
│   ├── self_debug_hook.py              # 에이전트 자기디버깅
│   ├── query_cost_guard_hook.py        # SQL 비용 가드
│   ├── temporal_join_guard_hook.py     # 시간 조인 누출 가드
│   ├── backtrack_hook.py               # 재시도/백트랙
│   ├── budget_tracker.py               # 반복/토큰/비용/벽시간 버짓
│   ├── permissions.py
│   ├── prompt_builder.py / prompt_sections.py
│   └── context_manager.py
│
├── domain/             # Clean Architecture 최내층 — 비즈니스 규칙만
├── application/        # 유즈케이스 + DTO + 포트
│
├── infrastructure/
│   ├── auth/           # OAuth 서비스, PKCE, 콜백 서버, 토큰 저장소
│   ├── secrets/        # KeyringSecretStorage (2560B 초과 시 chunk), 커넥터 시크릿
│   ├── sandbox/        # LLM이 작성한 코드 실행을 위한 preamble 생성기
│   ├── observability/  # Sentry 백엔드 브릿지, PII 리덕션 필터
│   ├── persistence/    # 세션/프로젝트/레지스트리 저장소
│   ├── migration/      # 스키마 마이그레이션 러너 + 레지스트리 (v4)
│   └── ...             # artifact, distributed, external, support
│
├── providers/          # 멀티-프로바이더 LLM 라우터
│   ├── anthropic.py / openai_provider.py
│   ├── codex_oauth.py / gemini_oauth.py   # OAuth 기반
│   ├── litellm_provider.py                # 100+ 프록시
│   ├── ollama.py / local_discovery.py
│   ├── pricing.py                         # 토큰 가격표
│   ├── router.py                          # provider/model 네이밍 파싱
│   └── base.py
│
├── tools/              # 35+ 자기등록 도구 (@tool 데코레이터)
│   ├── code_execution.py                  # LLM이 작성한 Python 실행 + 샌드박스
│   ├── data_loader.py / data_profiler.py / eda.py
│   ├── feature_eng.py / modeling.py / evaluation.py / reporting.py
│   ├── deployment.py / ab_test_tools.py / drift_tools.py
│   ├── schema_tools.py / sql_tools.py / warehouse_sandbox.py
│   ├── integration_tools.py               # 외부 커넥터 (Postgres 등)
│   ├── network_sandbox.py                 # 네트워크 I/O 샌드박스
│   ├── file_ops.py / artifact_tools.py
│   ├── governance_tools.py                # 승인 큐, 정책 도구
│   ├── distributed_tools.py / sampling_utils.py
│   ├── memory_tools.py / skill_tools.py
│   ├── ds_error_translator.py             # DSA-* 에러 카탈로그 매핑
│   ├── sql_result_summarizer.py
│   ├── standing_order_tools.py            # 반복 목표
│   ├── user_interaction.py
│   ├── web_search.py
│   ├── sandbox.py / sandbox_context.py / code_security.py
│   └── registry.py                         # 도구 자동 발견 & 등록
│
├── skills/             # Markdown 기반 기술지식(skills)
│   ├── builtin/        # 8종: scoping, data-profiling, eda, feature-engineering,
│   │                   #       modeling, evaluation, reporting, deployment
│   ├── shared/         # 6종: backtesting, causal-assumption-check, hypothesis-ranking,
│   │                   #       resource-aware-planning, retrain-vs-rollback,
│   │                   #       uncertainty-quantification
│   ├── domain/         # 도메인 팩(optional)
│   ├── custom/         # 사용자 작성
│   ├── hub.py          # 스킬 허브 (검색/로드)
│   ├── parser.py       # frontmatter+body 파싱
│   └── domain_pack_loader.py
│
├── memory/             # 5계층 메모리 시스템
│   ├── session_db (SQLite + FTS5)
│   ├── experiment_log / experiment_compare
│   ├── code_registry   # 학습된 패턴/스니펫
│   ├── domain_kb       # 도메인 지식베이스
│   ├── project_store   # 프로젝트 단위 맥락
│   └── unified_store   # 조회 진입점
│
├── runtime/            # 30+ 오케스트레이션 모듈 (런타임 운영 레이어)
│   ├── coordinator.py / policy_engine.py / policy_store.py
│   ├── approval_store.py / action_token.py
│   ├── sensor_hub.py / sensors/                # 사건 감지
│   ├── event_classifier.py / runtime_event_log.py
│   ├── digest_builder.py / delivery_policy_store.py
│   │                       / delivery_rate_limiter.py / delivery_settings.py
│   │                       / outcome_delivery.py       # 알림 전달 정책
│   ├── operator_alert_state_store.py / operator_preferences_store.py
│   ├── session_registry.py / run_registry.py / task_ledger.py
│   ├── checkpoint_store.py / startup_recovery.py       # 크래시 복구
│   ├── channel_identity.py                             # Telegram 스레드 인식
│   ├── background_task_manager.py
│   ├── goal_store.py / memory_query_service.py
│   ├── organization_store.py / transcript_store.py
│   ├── working_memory.py
│   ├── tool_runtime_context.py / provider_factory.py
│
├── self_improve/       # 프로젝트 완료 후 학습
│   ├── 패턴 추출 / 도메인 KB 추출 / 스킬 생성
│   └── 독립 평가자 (다른 모델로 교차검증)
│
├── config/             # Pydantic 스키마 v4, YAML/환경변수 로더
├── cli/                # Rich 기반 인터랙티브 TUI, 슬래시 명령, 온보딩 위저드
├── api/                # FastAPI 앱 (lifespan READY emit), WebSocket RPC
│   └── routes/         # admin, config, files, status, support, usage
├── channels/           # 채널 플러그인 시스템 (Telegram ...)
└── gateway/            # 세션 매니저, Telegram 러너

electron/
├── src/main/           # 메인 프로세스 (백엔드 spawn, 진단 창, IPC)
├── src/preload/        # 보안 IPC 브릿지 (secret vault, 정책, updater 노출)
├── src/renderer/       # React 18 + TypeScript + Tailwind + Zustand
│   ├── components/
│   │   ├── chat/       # ChatPanel, ChatMessage, ChatInput, ToolActivity
│   │   ├── sidebar/    # FileExplorer, FileUpload, PlotGallery, ModelSelector
│   │   ├── layout/     # MainPanel, StatusBar, SplashScreen, DisconnectOverlay
│   │   ├── runtime/    # SessionsPanel, RunsPanel, RunDetailDrawer, approvals
│   │   ├── sandbox/    # SandboxApprovalModal, SandboxViolationToast
│   │   ├── settings/   # SettingsPanel, OnboardingWizard, ConnectorWizard
│   │   ├── diagnostic/ # DiagnosticPanel
│   │   └── workflow/   # WorkflowProgress, AlertBanner, QualityPanel, BudgetBar
│   └── stores/         # chatStore, agentStore, filesStore, configStore,
│                       # i18nStore, workflowStore
└── tests/smoke/        # Playwright _electron 스펙

scripts/
├── build_backend.py    # PyInstaller → build/ds-agent-backend/
├── build_all.py        # 전체 파이프라인 (테스트 → PyInstaller → Electron → 인스톨러)
├── sign_backend.py     # Windows signtool / macOS codesign
├── check_av_clean.py   # VirusTotal 자동 스캔
└── clean_workspace.ps1 # 캐시/빌드 산출물 정리
```

---

## 4. 인터페이스 계층 상세

### 4.1 CLI (TUI)
- 구현: `src/ds_agent/cli/` — Rich 기반 대화형 TUI.
- 특징: 슬래시 명령, 온보딩 위저드, one-shot 실행(`ds-agent "Analyze data.csv, target is churn"`).
- 의존: 에이전트 코어에 직접 호출.

### 4.2 FastAPI 백엔드 (`src/ds_agent/api/`)
- `app.py`에 FastAPI 앱, `lifespan` 훅에서 `READY:port:token` 스탠다드아웃 emit — Electron의 `/health` 레이스 방지.
- WebSocket `/ws` 엔드포인트는 **OpenClaw 패턴**의 토큰 인증 JSON-RPC.
- 라우트: `routes/{admin,config,files,status,support,usage}.py`.

#### WebSocket 프로토콜 요약
```jsonc
// 요청
{ "type": "req", "id": "r1", "method": "chat.send", "params": { "message": "..." } }
// 응답
{ "type": "res", "id": "r1", "ok": true, "payload": { "sessionId": "abc" } }
// 서버 이벤트
{ "type": "event", "event": "stream.delta",      "payload": { "token": "Hello" } }
{ "type": "event", "event": "tool.start",         "payload": { "name": "data_loader" } }
{ "type": "event", "event": "tool.end",           "payload": { "name": "data_loader", "success": true } }
{ "type": "event", "event": "stream.done",        "payload": { "content": "...", "cost": 0.05 } }
{ "type": "event", "event": "sandbox.violation",  "payload": { "kind": "filesystem", "blocked": true } }
```

#### 토큰 인증 (SEC-01)
백엔드가 기동 시 일회용 `DS_AGENT_WS_TOKEN`을 발급, Electron 메인 프로세스가 렌더러에 `token` 쿼리 파라미터로 전달. 토큰 불일치/부재 시 `1008`로 close.

#### 대표 RPC 메서드 (35+)
`chat.send / chat.abort / chat.history`, `run.start / run.wait / run.list`, `session.list`, `task.list`, `runtime.events.list`, `approval.list / approval.resolve`, `policy.get / policy.upsertRecurringGoal`, `config.get / config.set`, `files.list / files.upload`, `provider.list / provider.models`, `project.list / project.create`, `connector.create / connector.test / connector.list`, `secret.set / secret.delete`, `support.exportBundle`.

### 4.3 Electron 데스크톱 앱
- 스택: Electron + React 18 + TypeScript + Vite + Tailwind + Zustand.
- 기능: 채팅(마크다운/코드하이라이트/표), 툴 액티비티 스트림, 사이드바(파일 탐색/플롯 갤러리/모델·모드 선택), 런타임 콘솔(세션/런/승인, 스레드 라벨), 샌드박스 승인 모달·위반 토스트, 온보딩 위저드, 진단 패널, 자동 업데이트 배너, 다크/라이트 + ko/en i18n.
- 접근성: `role=dialog`, `aria-modal`, `aria-live` 7개 모달/오버레이에 적용.
- 배포: Windows NSIS(179MB), macOS DMG, Linux AppImage. PyInstaller로 묶인 백엔드 바이너리(43.5MB `ds-agent-api.exe`)를 메인 프로세스가 `spawn()`.

### 4.4 Telegram 봇 (`src/ds_agent/gateway/`, `channels/`)
- PLAN_12~14에서 오퍼레이터 페어리티 + 스레드 인식 세션 격리 완료.
- 기능: 구독, ack/mute/digest, 인라인 콜백 액션, `/menu`, 봇 커맨드 등록, 오퍼레이터 감사 로그.
- 토픽 인식 아이덴티티: `runtime/channel_identity.py`가 Telegram thread_id를 세션에 매핑.

---

## 5. 에이전트 코어

### 5.1 단일 루프
`src/ds_agent/agent/core.py`: LLM 호출 → 응답에 `tool_calls`가 있으면 실행 → 결과를 대화에 추가 → 다시 LLM 호출. 종료 조건은 LLM의 자연 종료 또는 버짓 고갈.

### 5.2 Hook 시스템
- Pre/Post-tool 훅, `DS_workflow_hooks`, `governance_hooks`, `reporting_hooks`, `self_debug_hook`, `query_cost_guard_hook`, `temporal_join_guard_hook`, `backtrack_hook`.
- 훅 수: 현재 26개 (참고: `tests/integration/test_runtime_wiring.py::test_all_25_hooks_registered`는 25를 기대하는 사전 드리프트 존재).

### 5.3 버짓 제어
- 반복/토큰/비용/벽시간 한도, 경고 임계값. 구현: `agent/budget_tracker.py`.

### 5.4 운영 모드
`auto`, `supervised`, `step-by-step` 3종.

---

## 6. 도구(Tool) 생태계

- 자기등록 패턴: `@tool` 데코레이터가 `tools/registry.py`에 등록.
- 도구 카테고리:
  - **데이터/ML**: data_loader, data_profiler, eda, feature_eng, modeling, evaluation, reporting, ab_test, drift, schema, sql, sampling_utils
  - **실행/샌드박스**: code_execution(Python 코드 실행), sandbox, sandbox_context, code_security, network_sandbox, warehouse_sandbox, `_ds_sandbox_runner`
  - **운영/거버넌스**: governance_tools, standing_order_tools, user_interaction, ds_error_translator, sql_result_summarizer
  - **통합**: integration_tools(Postgres 등), deployment, distributed_tools
  - **아티팩트/파일**: artifact_tools, file_ops, path_utils, web_search
  - **메모리/스킬**: memory_tools, skill_tools

---

## 7. 스킬(Skills) 시스템

- Markdown frontmatter+body 기반. 파서: `skills/parser.py`, 허브: `skills/hub.py`.
- **Builtin (8)**: scoping, data-profiling, eda, feature-engineering, modeling, evaluation, reporting, deployment.
- **Shared (6)**: backtesting, causal-assumption-check, hypothesis-ranking, resource-aware-planning, retrain-vs-rollback, uncertainty-quantification.
- Domain pack / Custom 스킬은 로드 가능한 확장 포인트.

---

## 8. 메모리 계층

| 계층 | 파일 | 역할 |
|------|------|------|
| Immediate context | in-memory (agent core) | 현재 턴 맥락 |
| Session DB | `memory/session_db` (SQLite + FTS5) | 세션/대화/실행 기록, FTS 검색 |
| Experiment Log / Compare | `memory/experiment_log.py`, `experiment_compare.py` | 실험 이력 & 비교 |
| Domain KB | `memory/domain_kb.py` + `domain_kb.json` | 도메인 지식 |
| Code Registry | `memory/code_registry.py` | 학습된 코드 패턴 |
| Project Store | `memory/project_store.py` | 프로젝트 단위 장기 맥락 |
| Unified Store | `memory/unified_store.py` | 통합 조회 진입점 |

---

## 9. 런타임 오케스트레이션 (30+ 모듈)

- **승인/액션 토큰**: `approval_store`, `action_token` — 위험한 도구 호출을 승인 큐에 적재.
- **정책/조정자**: `coordinator`, `policy_engine`, `policy_store` — 실행 전 정책 평가.
- **전달 정책 자동화(PLAN_15)**: `delivery_policy_store`, `delivery_rate_limiter`, `delivery_settings`, `digest_builder`, `outcome_delivery`, `operator_alert_state_store`, `operator_preferences_store` — 조용한 시간대, 다이제스트 주기·타임존, 제안되는 다음 액션, 반복 차단 상태 에스컬레이션.
- **센서/이벤트**: `sensor_hub`, `sensors/`, `event_classifier`, `runtime_event_log`.
- **세션/런/태스크**: `session_registry`, `run_registry`, `task_ledger`, `checkpoint_store`.
- **복구(PLAN_10)**: `startup_recovery` — 비정상 종료 후 중단된 런 재개.
- **채널/스레드 격리(PLAN_14)**: `channel_identity` — Telegram thread_id ↔ 세션.
- **기타**: `background_task_manager`, `goal_store`, `memory_query_service`, `organization_store`, `transcript_store`, `working_memory`, `tool_runtime_context`, `provider_factory`.

---

## 10. 자기개선 (`self_improve/`)

프로젝트 완료 후:
1. 패턴 추출 → Code Registry.
2. 도메인 KB 추출 → Domain KB.
3. 스킬 생성 → `skills/custom/`.
4. 독립 크로스-모델 평가자가 결과 품질 검증.

---

## 11. 멀티-프로바이더 LLM

| Provider | 타입 | 모델 예시 | 인증 |
|----------|------|-----------|------|
| Anthropic | API Key | `claude-sonnet-4-6`, `claude-opus-4-6`, `claude-haiku-4-5` | `ANTHROPIC_API_KEY` |
| OpenAI | API Key | `gpt-4.1`, `o3-mini` | `OPENAI_API_KEY` |
| Codex | OAuth | `codex/gpt-4.1`, `codex/o4-mini` | `codex login` (ChatGPT OAuth) |
| Gemini | OAuth / Key | `gemini/gemini-2.5-pro` | Google 로그인 또는 `GEMINI_API_KEY` |
| Groq | API Key | `groq/llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| Ollama | Local | `ollama/qwen2.5:32b` | `ollama serve` |
| vLLM / SGLang | Local | `vllm/...` | 로컬 서버 |
| LiteLLM | Proxy | 100+ | 각 서비스 키 |

- 라우터(`providers/router.py`)가 `provider/model` 프리픽스 또는 모델명 휴리스틱으로 자동 라우팅.
- 가격표: `providers/pricing.py` → 비용 거버넌스(P1-11) 연동.

---

## 12. 설정·시크릿·보안

- **설정**: Pydantic 스키마 v4 (`config/`), YAML + 환경변수 로더. 스키마 마이그레이션 러너가 7단계 컨벤션으로 이전 버전을 자동 업그레이드.
- **시크릿**: `KeyringSecretStorage` — OS 키링 기반. **Windows Credential Manager 2560B 제한**을 투명하게 우회하기 위해 1024자 초과 시 `key__part0`, `part1`, ... 로 청킹하고 마지막에 `__ds_chunked__:N` 헤더 기록(크래시 안전).
- **샌드박스 (P0-01)**: LLM이 작성한 파이썬 코드에 파일시스템/네트워크 제약을 부여하는 preamble 생성기 + 실행 러너(`_ds_sandbox_runner.py`). 위반 시 `sandbox.violation` 이벤트 → Electron 블로킹 승인 모달(Esc=거절, 사유 textarea) + 논블로킹 위반 토스트(8초 TTL, 동시 3개).
- **관측(P0-07)**: Sentry SDK(백엔드+Electron) 통합, PII 리덕션 필터, DSA-* 에러 카탈로그, 온보딩 단계 텔레메트리 동의 모달. (DSN 조달 블록.)
- **코드서명(P0-05)**: `scripts/sign_backend.py` + `check_av_clean.py` 파이프라인 준비 완료. **Windows EV 인증서 / Apple Developer ID 조달 블록**으로 활성화 대기.

---

## 13. 빌드·배포 파이프라인

```bash
# 백엔드 단독
python scripts/build_backend.py         # → build/ds-agent-backend/ds-agent-api.exe (43.5 MB)

# 전체 배포 파이프라인
python scripts/build_all.py
#   1. pytest 검증
#   2. PyInstaller 백엔드 번들
#   3. Electron 렌더러 + 메인 빌드
#   4. electron-builder → NSIS / DMG / AppImage
#   5. (P0-05 활성 시) signtool / codesign + VirusTotal

# Electron 단독
cd electron
npm run dev        # Vite + Electron 개발
npm run build      # 프로덕션 빌드
npm run dist:win   # DS Agent-Setup-0.1.0-win.exe (179 MB, per-user, UAC-free)
npm run dist:mac
npm run dist:linux
```

- 자동 업데이트(`electron-updater`)는 배선 완료, P0-05 블록과 함께 활성화 대기(P1-14).

---

## 14. 테스트·검증 현황

| 항목 | 명령 | 결과 |
|------|------|------|
| 단위 + 스모크 | `pytest tests/unit tests/smoke` | **1,382 통과** |
| 백엔드 스모크 | `pytest tests/smoke` | 5/5 (패키지 바이너리 부팅, `/health`, `/api/status`, `/ws`) |
| Electron 타입체크 | `cd electron && npm run typecheck` | Clean |
| 진단 창 E2E | `npm run test:e2e:smoke` | PASS (백엔드 실패 → 진단 UI) |
| Happy-path E2E | `npm run test:e2e:happy` | PASS (부팅 → `/health` → WS 핸드셰이크 → 메인 UI hero) |
| 커버리지 목표 | — | ≥ 78% |

**알려진 드리프트**: `tests/integration/test_runtime_wiring.py::test_all_25_hooks_registered` — 실제 훅 개수는 26이나 테스트는 25를 기대. 최근 변경과 무관한 선존재 드리프트.

### 14.1 Memory · Self-Improvement 기능 검증 (2026-04-15, 본 분석에서 실시)

본 분석 중 메모리 계층과 자기개선 파이프라인이 실제로 동작하는지 두 단계로 직접 검증했다.

**A. 기존 테스트 재실행 (36개 전원 통과)**

| 파일 | 통과 |
|------|------|
| `tests/integration/test_memory_modules.py` | 13/13 — ExperimentLog · CodeRegistry · DomainKB · ProjectStore |
| `tests/integration/test_unified_memory_integration.py` | 4/4 — 저장→검색 왕복, 세션 간 영속성, 다중 타입 공존, 프로토콜 적합 |
| `tests/unit/application/test_self_improvement.py` | 9/9 — ProjectOutcome, PostProjectLearner, PatternLearner, MemoryHintBuilder |
| `tests/unit/application/test_cross_session.py` | 2/2 — 성공 패턴 저장·복구, 실패 패턴 노출 |
| `tests/unit/application/test_skill_extractor.py` | 6/6 — 스킬 markdown 생성, 파싱 호환, 실패/미달 시 스킵 |
| `tests/unit/application/test_outcome_builder.py` | 2/2 — completed/blocked 목표 매핑 |
| `tests/unit/application/test_agent_factory.py` (메모리 힌트·프로젝트 컨텍스트 파트) | 7/7 |

**합계: 43/43 통과, 실행 시간 < 2초.**

**B. 실사용 시나리오 라이브 스모크 (임시 디렉터리에 실제 파일 생성·읽기)**

| 시나리오 | 결과 |
|----------|------|
| `UnifiedMemoryStore.store/search/get/list_by_type/update/delete` | ✅ FTS5 검색 동작, 타입 필터, upsert, 논리 삭제 모두 확인 |
| `UnifiedMemoryStore.search_sessions(session_id=...)` | ✅ 세션 스코프 필터 정확 (S1의 `LightGBM` 히트는 S1에만, S2 검색은 0건) |
| 프로세스 재시작 후 재오픈 → FTS5 재검색 | ✅ 데이터·인덱스 영속성 확인 |
| `ExperimentLog.log_experiment` + `get_best_experiment(metric_name="f1")` | ✅ 2건 기록 후 최고 F1 모델(LGBM f1=0.81) 정확 반환, 재오픈 시 2건 복구 |
| `CodeRegistry.store_pattern` + `search_patterns` + `increment_use_count` | ✅ 저장 · 검색 1건 히트 · use_count=1 증가 |
| `DomainKB.store_insight` · `get_insights` · `get_memory_hints` | ✅ 2개 인사이트 저장 → 힌트 문자열에 `leakage` 포함 |
| `ProjectStore.create_project` · `register_artifact` · `list_projects` | ✅ 프로젝트 디렉터리 자동 생성, 아티팩트 1건, 리스트 1건 |
| `PatternLearner.extract_patterns(code)` | ✅ 샘플 코드에서 `lightgbm, sklearn, pandas, train_test_split` 4개 라이브러리 패턴 감지 |
| `PostProjectLearner.learn(ProjectOutcome(success=True,...))` | ✅ experiments_logged=1, domain_insights_stored=2, retrospective_saved=1, custom_skills_extracted=1 |
| `PostProjectLearner.learn(ProjectOutcome(success=False,...))` | ✅ 실패 시에도 경험 기록 + 도메인 인사이트 저장, skill 추출은 스킵 (min_metric/success 게이트) |
| 추출된 custom skill 파일 검증 | ✅ `churn-churn-alpha.md` frontmatter(`name/description/category/tags/version/author/token_estimate/source_project_id/extracted_at`) + "When to Use" 섹션 + `LGBM` 본문 포함 |
| UnifiedMemoryStore 사후 조회 (`search("churn")`) | ✅ `alpha:retrospective` 레코드 적재 확인 |

**결론**: 5-layer 메모리(Immediate 제외 4종 + Unified) 및 자기개선 파이프라인 전부 **실기능 정상 동작**. 성공/실패 경로의 분기, 게이트(`min_steps`, `min_metric_value`, `success=True`), 영속성까지 모두 검증됨.

**검증 중 확인된 사항 (수정 필요 없음 — 단순 호출 관례 기록)**

- `UnifiedMemoryStore.search()`의 키워드 인자는 `max_results`(문서·README의 표현과 일관), `limit`이 아님.
- `ExperimentLog.get_best_experiment()`는 `project_id`를 필수로 받고, 정렬 키는 `metric_name`(+ `higher_is_better`)임 — `task_type` 인자는 `get_experiments()` 쪽에 존재.
- `CodeRegistry.store_pattern/get_pattern/increment_use_count`는 `name` 문자열 키 기반(ID가 아님).
- `ProjectStore.register_artifact(project_id, artifact_type, file_path, description)` 시그니처 (테스트 코드가 준 사실). 
- 자동생성 스킬 파일은 UTF-8 인코딩 고정 — Windows 기본 cp949 텍스트 리더로 읽지 말 것(`Path.read_text(encoding="utf-8")` 필요).
- `test_runtime_wiring.py::test_all_25_hooks_registered`의 선존재 드리프트는 본 검증과 무관.

---

## 15. 개발 도구·품질 게이트

```bash
pip install -e ".[dev]"

ruff check src/ tests/              # 린트
ruff format --check src/ tests/     # 포매팅
mypy src/ds_agent/                  # 타입체크
```

**퀄리티 게이트** (feature plan 단위 강제):
- TDD: 테스트 선행, Red-Green-Refactor.
- 빌드/테스트 통과, 린트/타입체크 클린.
- Clean Architecture 의존성 규칙 준수 (Domain 외부 의존성 0, Use case는 포트에만 의존, DTO로 경계 교차).
- 보안 이슈 없음.
- 기능 수동 검증 통과.

---

## 16. 최근(베타 출시 전) 안정화 이력

| 항목 | 파일 | 내용 |
|------|------|------|
| Backend READY 레이스 | `src/ds_agent/api/app.py` | `print("READY:port:token")`가 바인드 이전에 출력되어 Electron `/health` 프로브와 레이스. FastAPI `lifespan` 스타트업 훅으로 이동. |
| Windows 크리덴셜 크기 | `src/ds_agent/infrastructure/secrets/secret_storage.py` | Codex OAuth 번들(~4.3KB)이 2560B 한도를 초과해 `CredWrite error 1783` 발생. Chunk 저장 + `__ds_chunked__:N` 마커. |
| Sandbox UI | Electron renderer | `sandbox.violation` 이벤트 → 블로킹 승인 모달 + 위반 토스트. |
| E2E 훅 | Electron main | `DS_AGENT_BACKEND_COMMAND` (백엔드 커맨드 오버라이드), `DS_AGENT_E2E_USE_BUILT_RENDERER=1` (Vite 개발 서버 우회). |

---

## 17. 기능 플랜 진행 (Docs/plans)

### 완료된 대형 플랜
| ID | 제목 | 상태 |
|----|------|------|
| PLAN_10 | Autonomous agent runtime | ✅ |
| PLAN_11 | Electron frontend parity | ✅ |
| PLAN_12 | Telegram operator parity | ✅ |
| PLAN_13 | Telegram operator UX hardening | ✅ |
| PLAN_14 | Thread-aware session isolation | ✅ |
| PLAN_15 | Notification delivery policy automation | ✅ |

### 진행 중
- **PLAN_17 — Capability Roadmap** (P0 foundation → P6 advanced). 전 분야 교차하는 장기 로드맵.

### Productization (베타 출시)
| ID | 영역 | 상태 |
|----|------|------|
| P0-01 | 코드 실행 샌드박스 | ✅ Complete |
| P0-02 | 보안 크리덴셜 저장 | ✅ Complete (멀티플랫폼 실기기 검증 대기) |
| P0-03 | 기동 진단·복구 | ✅ Complete |
| P0-04 | 설정 마이그레이션 프레임워크 | ✅ Complete (schema v4) |
| P0-05 | 코드 서명·배포 | ⏸ **EV 인증서 조달 대기** |
| P0-06 | 패키지 QA·스모크 | ✅ (서명 인스톨러 E2E만 P0-05 대기) |
| P0-07 | 관측·크래시 리포팅 | ✅ (Sentry DSN 조달 대기) |
| P1-08 | 유즈케이스 온보딩 위저드 | ✅ |
| P1-09 | Provider/Model 추상화 UX | ✅ |
| P1-10 | 데이터 임포트 UX (Postgres) | ✅ (BigQuery/Snowflake 폴리시는 베타 후) |
| P1-11 | 비용 거버넌스 | ✅ |
| P1-12 | 아티팩트 내보내기 (PDF/docx/xlsx/ipynb, 한글 왕복) | ✅ (48 테스트) |
| P1-13 | i18n(한국어)·접근성 | ✅ (ARIA 7개 오버레이) |
| P1-14 | 자동 업데이트 | ⏸ (P0-05 블록) |

---

## 18. 강점

1. **LLM-orchestrator 원칙의 일관성**: 워크플로 자동화로 역행하지 않고, LLM이 결정권을 유지. 도구·스킬·메모리는 모두 "LLM이 필요할 때 호출"하는 구조.
2. **Clean Architecture 준수**: 퀄리티 게이트로 도메인 순도 강제. 프레임워크/DB 교체 시 내층 변경 없음.
3. **3-tier 인터페이스 공통 코어**: CLI·Telegram·Electron이 동일 에이전트 코어를 공유 → UX별 중복 로직 없음.
4. **런타임 운영 성숙도**: 승인, 정책, 센서, 전달 정책 자동화, 스레드 인식 세션 격리, 스타트업 복구 — 팀/엔터프라이즈 준비가 이미 배선되어 있음.
5. **테스트 베이스**: 1,382 단위+스모크 테스트, 패키지 바이너리·Electron E2E까지 포함. 회귀 방어선 견고. 추가로 본 분석에서 메모리 5계층 및 자기개선 파이프라인을 라이브 스모크(임시 디렉터리 실파일 I/O, FTS5 재검색, 스킬 추출 파일 content 검증)로 **실기능 정상 동작을 확인**(14.1절).
6. **배포 산출물 검증 완료**: 43.5MB 백엔드 바이너리 + 179MB Windows 인스톨러(UAC-free, per-user) 동작 확인.

---

## 19. 한계 및 리스크

### 19.1 외부 조달 블록
- **코드 서명 인증서 부재(P0-05)**: Windows EV, Apple Developer ID 미확보. SmartScreen/Gatekeeper 경고 + 자동 업데이트(P1-14) 활성화 불가.
- **Sentry DSN 미조달(P0-07)**: 관측 코드·동의 모달은 완비, 실제 이벤트 수집은 대기.

### 19.2 검증 보수 필요
- `test_all_25_hooks_registered` 사전 드리프트(25 vs 26). 다음 하드닝 패스에서 업데이트 필요.
- P0-02: 멀티플랫폼(실기기 macOS/Linux 키링) 검증 미수행.

### 19.3 범위 제한
- 데이터 커넥터: Postgres만 GA. BigQuery/Snowflake는 UI 폴리시가 베타 후로 이월.
- 로컬 LLM 경험: Ollama/vLLM/SGLang 통합은 되어 있으나 리소스 인식(P2 영역)은 로드맵.

### 19.4 복잡도 부채
- Runtime 모듈 30+ — 엔터프라이즈 운영 기능이 누적되며 런타임 계층이 두터워짐. 신규 기여자 온보딩 곡선.
- 스킬·도구·훅의 교차 매트릭스(특히 governance_hooks ↔ policy_engine ↔ approval_store)는 의도가 명시적이나 실수로 우회될 경로에 대한 테스트 매트릭스 보강 여지 존재.

### 19.5 플랫폼 의존성
- Windows 시크릿 청킹, Codex OAuth 번들 크기 등 "플랫폼 특수 케이스"가 다수 내재. 패키지 회귀 테스트 범위 지속 확장 필요.

---

## 20. 저장소 아티팩트 (현재 로컬 빌드)

| 경로 | 크기 | 설명 |
|------|------|------|
| `dist/ds-agent-backend/ds-agent-api.exe` | 43.5 MB | PyInstaller 단일 바이너리 (메인 프로세스가 `spawn()`) |
| `electron/release/DS Agent-Setup-0.1.0-win.exe` | 179 MB | NSIS 인스톨러 (per-user, 데스크톱+시작메뉴 단축, UAC-free) |

---

## 21. 결론

현재 시스템은 **기술적으로 베타 출시 직전** 단계다. 핵심 아키텍처·기능·테스트·배포 산출물이 모두 준비되어 있고, 남은 블록은 코드 서명 인증서 조달 및 Sentry DSN과 같은 **외부 공급망/조달 항목**에 집중되어 있다.

원칙 측면에서도 "LLM이 오케스트레이터"라는 자율형 에이전트 정체성을 유지하면서, 운영/거버넌스/전달 정책 자동화·스레드 인식 세션 격리 같은 엔터프라이즈 기능을 쌓아 올린 흔치 않은 구성이다. 다음 단계(To-Be)에서는 (1) 조달 블록 해소에 따른 실제 출시, (2) PLAN_17 P2~P6 수준의 고급 기능(분산·팀·마켓플레이스·고급 분석), (3) 런타임 계층 복잡도의 지속 가능한 문서화·테스트 매트릭스 유지가 주 축이 될 것으로 보인다.
