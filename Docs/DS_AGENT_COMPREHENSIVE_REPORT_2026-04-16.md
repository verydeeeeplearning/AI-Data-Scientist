# DS Agent — 자율형 AI 데이터 사이언티스트 종합 시스템 보고서

> **⚠️ 2026-04-17 업데이트 안내**: 본 문서는 2026-04-16 기준 스냅샷이며 이후 변동은 수정하지 않는다. Pre-Release QA 파이프라인(Tier 1~4 + Fix Sprint R1~R3)으로 변경된 수치·구조·이력은 별도 부록 `DS_AGENT_COMPREHENSIVE_REPORT_2026-04-17_ADDENDUM.md`에 정리되어 있다. **원본 본문과 Addendum이 충돌하면 Addendum이 우선**. 최종 릴리스 판정(CONDITIONAL_GO): `Docs/qa_run_2026-04-17/D18_release/RELEASE_GATE_DECISION.md`.

**작성일**: 2026-04-16
**기준 코드베이스**: `AI_Data_Scientist_Demo` (latest)
**분석 범위**: 전체 리포지토리 — 백엔드/Electron/Telegram/CLI, 10개 Enhancement Spec, 19개 제품화 계획 문서, 빌드/테스트 파이프라인
**목적**: 시스템 컨셉, 아키텍처, 핵심 기능, 제품화 현황에 대한 빠짐없는 종합 분석

---

## 목차

1. [제품 개요](#1-제품-개요)
2. [핵심 설계 철학](#2-핵심-설계-철학)
3. [기술 스택](#3-기술-스택)
4. [시스템 아키텍처](#4-시스템-아키텍처)
5. [핵심 기능 상세](#5-핵심-기능-상세)
   - 5.1 [LLM 오케스트레이터 (Agent Core)](#51-llm-오케스트레이터-agent-core)
   - 5.2 [도구 레지스트리 (100+ Tools)](#52-도구-레지스트리-100-tools)
   - 5.3 [스킬 허브 (Methodology Packs)](#53-스킬-허브-methodology-packs)
   - 5.4 [Hook 레지스트리 (분산 미들웨어)](#54-hook-레지스트리-분산-미들웨어)
   - 5.5 [5계층 메모리 시스템](#55-5계층-메모리-시스템)
   - 5.6 [자율 운영 프레임워크 (Runtime)](#56-자율-운영-프레임워크-runtime)
   - 5.7 [Task Contract 엔진](#57-task-contract-엔진)
   - 5.8 [검증 오케스트레이터 (Verifier)](#58-검증-오케스트레이터-verifier)
   - 5.9 [자율 제어 평면 (Autonomy Control Plane)](#59-자율-제어-평면-autonomy-control-plane)
   - 5.10 [평가 하네스 (Evaluation Harness)](#510-평가-하네스-evaluation-harness)
   - 5.11 [Decision OS](#511-decision-os)
   - 5.12 [이해관계자 커뮤니케이션 엔진](#512-이해관계자-커뮤니케이션-엔진)
   - 5.13 [워크플로우 통합 (Workflow Integration)](#513-워크플로우-통합-workflow-integration)
   - 5.14 [비동기 포트폴리오 매니저](#514-비동기-포트폴리오-매니저)
   - 5.15 [자기 개선 거버넌스](#515-자기-개선-거버넌스)
   - 5.16 [Enterprise Semantic Memory](#516-enterprise-semantic-memory)
   - 5.17 [멀티 프로바이더 LLM 라우터](#517-멀티-프로바이더-llm-라우터)
   - 5.18 [샌드박스 코드 실행](#518-샌드박스-코드-실행)
6. [3-Tier 인터페이스](#6-3-tier-인터페이스)
7. [코드베이스 정량 분석](#7-코드베이스-정량-분석)
8. [제품화 현황](#8-제품화-현황)
9. [테스트 및 품질 보증](#9-테스트-및-품질-보증)
10. [빌드 및 배포 파이프라인](#10-빌드-및-배포-파이프라인)
11. [프로젝트 구조 맵](#11-프로젝트-구조-맵)
12. [품질, 보안, 운영 성숙도 평가](#12-품질-보안-운영-성숙도-평가)
13. [잔존 과제, 기술 부채, 로드맵](#13-잔존-과제-기술-부채-로드맵)

---

## 1. 제품 개요

**DS Agent**는 Hermes-style 자율형 AI 데이터 사이언티스트이다. 사용자의 데이터 분석 요청을 받아 탐색적 데이터 분석(EDA), 피처 엔지니어링, 모델링, 평가, 보고서 작성까지 **엔드투엔드 데이터 사이언스 워크플로우를 자율적으로 수행**한다.

### 핵심 가치 제안

| 구분 | 설명 |
|------|------|
| **완전한 자율성** | LLM이 유일한 오케스트레이터 — 하드코딩된 파이프라인이나 state machine 없이 LLM이 스스로 판단하여 다음 단계를 결정 |
| **엔터프라이즈 신뢰성** | Task Contract, 4계층 검증, 승인 체인, 감사 추적으로 조직적 신뢰 확보 |
| **3-Tier 접근성** | CLI(개발자), Telegram(운영자), Electron Desktop(제품 사용자) — 동일한 에이전트 코어를 3개 채널로 제공 |
| **자기 학습** | 세션 간 학습, 도메인 지식 축적, 스킬 추출/승격으로 점진적 역량 향상 |
| **멀티 모델** | Anthropic Claude, OpenAI GPT, Gemini, Groq, Ollama, vLLM 등 100+ 모델 지원 |

### 대상 사용자

- **데이터 사이언티스트**: 반복적 분석 작업 자동화, 실험 추적, 모델 프로모션
- **분석 리더**: Task Contract를 통한 작업 위임, 결과 검증, 품질 거버넌스
- **비즈니스 이해관계자**: 맞춤형 보고서(Executive/Peer/Auditor 등) 자동 생성 및 배포

---

## 2. 핵심 설계 철학

### 2.1 LLM is the Orchestrator

> 코드가 flow를 결정하지 않는다. LLM이 유일한 오케스트레이터다.

시스템의 모든 결정 — 어떤 도구를 사용할지, 어떤 순서로 분석할지, 언제 사용자에게 질문할지 — 은 LLM이 내린다. 코드는 **도구(tool)**를 제공하고, **정보(prompt context)**를 보고하며, **안전 제약(hook/policy)**을 강제할 뿐이다.

이 원칙은 제품화 과정에서도 불변이다:
- Scheduler는 **정보 제공자**이지 controller가 아니다
- Governance는 **지식 품질 게이트**이지 LLM 추론 경로 제어가 아니다
- Hard constraint(SLA 상한, max_active_slots)만 코드가 강제한다
- Prompt에 주입되는 정보는 "상태 보고"이지 "지시"가 아니다

### 2.2 Clean Architecture (4 Layer)

```
┌─────────────────────────────────────────┐
│  Frameworks & Drivers                    │  Electron, FastAPI, Telegram, PyInstaller
│  ┌─────────────────────────────────┐    │
│  │  Interface Adapters              │    │  API routes, CLI, WebSocket, SQLite stores
│  │  ┌─────────────────────────┐    │    │
│  │  │  Application             │    │    │  Use Cases, DTOs, Application Ports
│  │  │  ┌─────────────────┐    │    │    │
│  │  │  │  Domain           │    │    │    │  Entities, Value Objects, Interfaces
│  │  │  │  (zero deps)      │    │    │    │  (Pydantic v2, no external imports)
│  │  │  └─────────────────┘    │    │    │
│  │  └─────────────────────────┘    │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

**의존성 규칙**: 외부→내부만 허용. Domain 계층은 어떤 외부 라이브러리도 import하지 않는다. `scripts/check_import_contracts.py`와 `tests/unit/architecture/test_import_contracts.py`가 CI에서 이를 자동 검증한다.

### 2.3 Typed Artifact Pattern

모든 주요 산출물(Task Contract, Goal, Experiment Run, Delivery Pack, Work Object 등)은 **Pydantic v2 모델**로 정의되고 SQLite에 영속화된다. LLM은 이들을 JSON으로 읽고 쓰며, 시스템 프롬프트에 현재 상태가 자동 주입된다.

### 2.4 TDD 기반 구현

모든 기능은 RED(실패 테스트 작성) → GREEN(최소 구현) → REFACTOR(품질 개선) 사이클을 따른다. 각 Enhancement Spec은 3~7개 Phase로 분할되며, Phase별 Quality Gate를 통과해야 다음 Phase로 진행한다.

---

## 3. 기술 스택

### 3.1 백엔드 (Python)

| 구분 | 기술 | 버전 |
|------|------|------|
| 언어 | Python | >= 3.11 |
| 빌드 | Hatchling | latest |
| 타입 모델 | Pydantic | >= 2.0.0 |
| 로깅 | structlog | >= 23.0.0 |
| 설정 | PyYAML + python-dotenv | >= 6.0, >= 1.0.0 |
| 크래시 리포팅 | Sentry SDK | 2.58.0 |
| 자격증명 | keyring | >= 24.0 |
| Web 프레임워크 | FastAPI + Uvicorn | >= 0.115.0, >= 0.32.0 |
| WebSocket | websockets | >= 13.0 |
| CLI | Typer + Rich | >= 0.12.0, >= 13.0 |
| Telegram | python-telegram-bot | >= 21.0 |
| LLM (Anthropic) | anthropic | >= 0.30.0 |
| LLM (OpenAI) | openai | >= 1.30.0 |
| LLM (기타) | litellm + tiktoken | >= 1.40.0, >= 0.7.0 |
| Export (Office) | python-pptx, python-docx, openpyxl | >= 1.0.0, >= 1.1.0, >= 3.1.0 |
| Export (Notebook) | nbformat | >= 5.10.0 |
| 분산 컴퓨팅 | Dask, Ray | optional |
| 벡터 검색 | sentence-transformers, LanceDB | optional |
| 테스트 | pytest, pytest-asyncio, pytest-cov | >= 8.0 |
| 린팅/타이핑 | ruff, mypy | >= 0.6.0, >= 1.10.0 |
| 아키텍처 검증 | import-linter | >= 2.0 |
| 패키징 | PyInstaller | single-file binary (43.5 MB) |

### 3.2 프론트엔드 (Electron Desktop)

| 구분 | 기술 | 버전 |
|------|------|------|
| 프레임워크 | Electron | 31.7.5 |
| UI | React + TypeScript | 18.3.1 + 5.7.2 |
| 빌드 | Vite | 5.4.11 |
| 스타일링 | TailwindCSS | 3.4.17 |
| 상태 관리 | Zustand | 4.5.5 |
| 아이콘 | Lucide React | 0.460.0 |
| 마크다운 | react-markdown + remark-gfm | 9.0.1 |
| 코드 하이라이팅 | react-syntax-highlighter | 15.6.1 |
| 크래시 리포팅 | @sentry/electron | 7.11.0 |
| 자동 업데이트 | electron-updater | 6.8.3 |
| E2E 테스트 | Playwright | 1.59.1 |
| 배포 | electron-builder | 24.13.3 |

### 3.3 데이터 저장소

| 용도 | 기술 |
|------|------|
| 세션/트랜스크립트 | SQLite + FTS5 (전문 검색) |
| Task Contract | SQLite |
| 실험 로그 | SQLite |
| 도메인 지식 | JSON (legacy) → SQLite semantic (마이그레이션 중) |
| 배달 로그 | SQLite + JSONL fallback |
| Portfolio | SQLite (portfolio.db, v12 migration) |
| Learning Governance | SQLite (learning.db, v13 migration) |
| 자격증명 | OS Keyring (Windows Credential Manager, macOS Keychain) |

---

## 4. 시스템 아키텍처

### 4.1 전체 아키텍처 다이어그램

```
┌──────────────────────────────────────────────────────────────────────┐
│                        사용자 인터페이스                               │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────────────────────┐ │
│  │ CLI (TUI) │    │ Telegram Bot │    │ Electron Desktop App       │ │
│  │ Rich/Typer│    │ python-      │    │ React 18 + Zustand         │ │
│  │           │    │ telegram-bot │    │ + TailwindCSS              │ │
│  └─────┬─────┘    └──────┬───────┘    └──────────┬──────────────────┘ │
│        │                 │                       │                    │
│        └─────────────────┼───────────────────────┘                    │
│                          ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │                  Gateway / API Layer                              │ │
│  │  FastAPI (REST + WebSocket RPC) / Agent Factory (create_agent)   │ │
│  └──────────────────────────────┬───────────────────────────────────┘ │
│                                 ▼                                     │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │                      DSAgent Core Loop                           │ │
│  │  while not budget.exhausted:                                     │ │
│  │    response = LLM.chat(messages, tools)                          │ │
│  │    for tool_call in response.tool_calls:                         │ │
│  │      pre_hooks → ToolRegistry.dispatch(tool_call) → post_hooks  │ │
│  │    messages.append(response)                                     │ │
│  └─────────────┬────────────────────────────────────┬───────────────┘ │
│                │                                    │                  │
│   ┌────────────▼──────────┐          ┌──────────────▼───────────────┐ │
│   │  PromptBuilder         │          │  HookRegistry (25+ hooks)   │ │
│   │  (Token-aware          │          │  Pre/Post/FinalResponse     │ │
│   │   composable sections) │          │  Permission, Audit, Budget, │ │
│   │                        │          │  DS-Workflow, Governance,   │ │
│   │  Identity / Authority  │          │  Semantic, Learning         │ │
│   │  / Skills / Memory /   │          │                             │ │
│   │  Portfolio / Learning  │          │                             │ │
│   └────────────────────────┘          └─────────────────────────────┘ │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │                    Tool Registry (100+ tools)                    │ │
│  │  code_execution | data_loader | eda | modeling | evaluation     │ │
│  │  reporting | sql | memory | governance | portfolio | learning   │ │
│  │  integration | deployment | web_search | artifact | verifier    │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │                   Runtime / Autonomous Layer                     │ │
│  │  SensorHub → PolicyEngine → AutonomousCoordinator → Dispatch    │ │
│  │  ApprovalStore | ActionMatrix | DeliveryPolicy | RunRegistry    │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │                   Infrastructure Layer                           │ │
│  │  LLM Providers | SQLite Persistence | External Connectors       │ │
│  │  Sandbox Runner | Secret Storage | Exporters | Migration        │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 데이터 흐름

```
사용자 입력
    ↓
Agent Factory (create_agent) — CLI/Telegram/Electron 모두 동일 배선
    ↓
PromptBuilder — token-aware 시스템 프롬프트 조립
  (Identity + Authority + Skills + Memory + Portfolio + Learning + Context)
    ↓
LLM Provider.chat(messages, tools) — timeout 120s, 스트리밍 delta 지원
    ↓
Tool Calls 파싱 → Pre-Hooks (Permission/Budget/Policy 검증)
    ↓  ┌─ DENY → 사용자 알림, 도구 실행 건너뜀
    ↓  ├─ MODIFY → 인자 수정 후 실행
    ↓  └─ ALLOW → 실행
    ↓
ToolRegistry.dispatch(name, arguments) — JSON Schema 검증 + timeout 강제
    ↓
Post-Hooks (Audit/Learning/Experiment Tracking)
    ↓
결과를 messages에 추가 → 다음 LLM 호출 (반복)
    ↓
Budget 소진 또는 LLM이 최종 응답 생성 → FinalResponse Hooks → 사용자에게 반환
    ↓
Post-session Learning (스킬 추출, 도메인 KB 갱신, 패턴 학습)
```

---

## 5. 핵심 기능 상세

### 5.1 LLM 오케스트레이터 (Agent Core)

**위치**: `src/ds_agent/agent/core.py`

`DSAgent` 클래스의 `run()` 메서드가 시스템의 심장이다. 단일 `while` 루프에서:

1. 시스템 프롬프트 조립 (PromptBuilder)
2. Session Init Hook 실행 (DS 방법론 규칙 주입)
3. LLM 호출 (timeout 120s, 스트리밍 지원)
4. Tool Call 파싱 및 Hook-gated 실행
5. 결과를 대화 이력에 추가
6. Budget(반복수/비용/시간) 확인
7. 반복 또는 최종 응답 반환

**핵심 설계 결정**: 코드에 state machine이 없다. LLM이 현재 Task Contract/Goal 상태를 읽고 자유롭게 다음 행동을 결정한다.

```python
class DSAgent:
    """Autonomous DS Agent — single while loop, LLM is the orchestrator."""

    async def run(self, user_message: str, ...) -> str:
        messages = self._prompt_builder.build(user_message, history=self._history)
        tool_defs = self._tools.get_definitions()

        while not self._budget.is_exhausted:
            response = await self._provider.chat(messages, tools=tool_defs)
            if not response.tool_calls:
                return await self._finalize_turn(messages, response.content)
            for tc in response.tool_calls:
                result = await self._execute_tool(tc, messages)  # pre_hooks → dispatch → post_hooks
                messages.append(result)
```

**Agent Factory** (`src/ds_agent/agent/factory.py`): 모든 진입점(CLI, Telegram, Electron API, 배치)이 `create_agent()`를 호출하여 동일한 배선(hooks, skills, memory, prompt builder)을 보장한다. 채널 간 동작 차이가 발생할 수 없는 구조이다.

**PromptBuilder** (`src/ds_agent/agent/prompt_builder.py`): 우선순위 기반 토큰 예산 관리. 필수 섹션(Identity, Authority, Safety)을 항상 포함하고, 선택 섹션(Skills, Memory hints, Portfolio, Learning)은 토큰 예산에 따라 동적 포함/제외한다.

### 5.2 도구 레지스트리 (100+ Tools)

**위치**: `src/ds_agent/tools/`

자기 등록(self-registering) 패턴으로 약 40개 모듈, 100+ 도구가 등록된다:

| 카테고리 | 주요 도구 | 설명 |
|---------|----------|------|
| **코드 실행** | `run_python`, `run_sql`, `run_bash` | 샌드박스 격리 실행, workspace 바운드 |
| **데이터 로딩** | `load_csv`, `load_parquet`, `load_sql`, `load_excel` | 다양한 데이터 소스 수집 |
| **데이터 프로파일링** | `profile_data` | 결측치, 중복, 분포 자동 분석 |
| **EDA** | `correlation_matrix`, `distribution_plots`, `missing_data_summary` | 탐색적 데이터 분석 |
| **피처 엔지니어링** | `create_features`, `feature_scaling`, `dimensionality_reduction` | 피처 생성/변환 |
| **모델링** | `train_model`, `hyperparameter_tuning`, `cross_validate` | ML 모델 학습 |
| **평가** | `evaluate_model`, `confusion_matrix`, `cross_validation_score` | 모델 성능 평가 |
| **보고서** | `generate_report`, `create_visualization` | 시각화 및 보고서 생성 |
| **SQL** | SQL 스키마 검사, 쿼리 실행 | 데이터 웨어하우스 연동 |
| **메모리** | `query_session`, `query_domain_kb`, `query_code_registry` | 5계층 메모리 조회 |
| **Semantic** | `lookup_metric`, `lookup_glossary_term` | 조직 지식 조회 |
| **Task Contract** | 계약 CRUD, 배달, 검증 | 작업 계약 관리 |
| **Portfolio** | `list_my_portfolio`, `pause_task`, `resume_task`, `set_sla` | 비동기 포트폴리오 관리 |
| **Learning** | `list_learning_inbox`, `review_learning_item`, `rollback_promotion` | 학습 거버넌스 |
| **Integration** | `publish_slack`, `create_jira_issue`, `send_email`, `create_calendar_event` | 외부 시스템 연동 |
| **Decision OS** | 피처 레지스트리, 실험 추적, 프로모션 게이트 | ML Ops |
| **A/B 테스트** | A/B 설계, 통계 검정 | 실험 설계 |
| **드리프트** | 데이터/모델 드리프트 감지 | 운영 모니터링 |
| **거버넌스** | 정책 확인, lineage 캡처 | 규정 준수 |
| **배포** | 모델 배포 | ML Ops |
| **웹 검색** | `search_web` | 외부 정보 조회 |

**도구 등록 패턴**:
```python
@tool(name="run_python", description="...", parameters={...}, timeout=60)
async def run_python(code: str) -> str:
    # 순수 함수, OOP 상태 없음
    # JSON Schema 파라미터 검증 → 실행 → 문자열 결과 반환
```

### 5.3 스킬 허브 (Methodology Packs)

**위치**: `src/ds_agent/skills/`

YAML 기반 AI-readable 방법론 가이드. LLM이 필요 시 `discover_skills` / `load_skill` 도구로 동적 로딩:

- **8개 빌트인 스킬**: scoping, data-profiling, eda, feature-engineering, modeling, evaluation, reporting, deployment
- **6개 공유 스킬**: backtesting, causal-assumption-check, hypothesis-ranking, resource-aware-planning, retrain-vs-rollback, uncertainty-quantification
- **도메인 팩**: finance, healthcare, marketing 각각 전용 스킬 + enterprise domain pack (glossary, metrics, trust, verified queries)
- **사용자 정의 스킬**: `custom/` 디렉토리에 자유 추가

### 5.4 Hook 레지스트리 (분산 미들웨어)

**위치**: `src/ds_agent/agent/hooks.py`, `builtin_hooks.py`, `ds_workflow_hooks.py`, `governance_hooks.py`, `semantic_hooks.py`

25+ Hook이 에이전트 루프의 **매 도구 호출 전후**에 실행된다:

#### 빌트인 Hook (7개)
| Hook | 역할 |
|------|------|
| `PermissionHook` | 액션 분류 → 권한 매트릭스 확인 → ALLOW/DENY/REQUIRE_APPROVAL |
| `AuditLogHook` | 모든 도구 호출을 감사 로그에 기록 |
| `BudgetGuardHook` | 반복수/비용/시간 예산 초과 시 DENY |
| `SessionInitHook` | 세션 시작 시 DS 방법론 규칙 주입 |
| `OrgPolicyHook` | 조직 정책 강제 |
| `PIIRedactionHook` | 개인정보 자동 마스킹 |
| `ExperimentTrackerHook` | 실험 자동 추적 |

#### DS 워크플로우 Hook (8개)
| Hook | 역할 |
|------|------|
| `WorkflowTrackerHook` | 분석 단계 자동 추적 (scoping→EDA→modeling→...) |
| `BaselineGuardHook` | 베이스라인 없이 고급 모델 시도 시 경고 |
| `LeakageDetectionHook` | 데이터 누수 패턴 감지 |
| `OverfittingDetectorHook` | 과적합 징후 감지 |
| `ModelSanityCheckHook` | 모델 결과 정상성 검증 |
| `ExperimentDesignHook` | 실험 설계 검증 |
| `StageQualityHook` | 단계별 품질 기준 충족 확인 |
| `DriftDetectionHook` | 실시간 드리프트 감지 |

#### 시맨틱/거버넌스 Hook
| Hook | 역할 |
|------|------|
| `SemanticReadGuardHook` | 시맨틱 메모리 읽기 시 신뢰 수준 검증 |
| `SemanticTrustHook` | 신뢰할 수 없는 메트릭 사용 경고 |
| `SemanticWritebackHook` | 분석 결과를 시맨틱 메모리에 자동 기록 |
| `ReviewArtifactCaptureHook` | LLM 응답에서 공유 스킬 아티팩트 자동 추출 (Final Response 단계) |
| `LineageCaptureHook` | 데이터 lineage 자동 기록 |
| `PolicyApprovalHook` | 정책 기반 승인 요구 |

**Hook 동작 모델**:
```
Pre-Hook Phase:
  PermissionHook → DENY (도구 실행 차단) 또는 ALLOW (계속)
  BudgetGuardHook → 예산 초과 시 DENY
  LeakageDetectionHook → 위험 파라미터 수정(MODIFY)

Tool 실행

Post-Hook Phase:
  AuditLogHook → 결과 기록
  ExperimentTrackerHook → 실험 데이터 축적
  SemanticWritebackHook → 메트릭/인사이트 자동 저장

Final Response Phase:
  ReviewArtifactCaptureHook → hidden artifact 추출 + 저장
```

### 5.5 5계층 메모리 시스템

**위치**: `src/ds_agent/memory/`

| 계층 | 저장소 | 범위 | 용도 |
|------|--------|------|------|
| **1. Immediate Context** | PromptBuilder 메시지 윈도우 | 현재 턴 | 대화 컨텍스트 |
| **2. Session DB** | SQLite + FTS5 전문 검색 | 세션 | 트랜스크립트 검색, 체크포인트 |
| **3. Domain KB** | JSON (legacy) | 프로젝트 | 도메인 용어, 메트릭, 인사이트 |
| **4. Semantic Memory** | SQLite (metric/glossary/trust/VQ) | 조직 | 검증된 메트릭, 비즈니스 용어, 신뢰 레지스트리 |
| **5. Project Store** | SQLite | 크로스세션 | 실험 로그, 코드 패턴, 스킬 후보 |

**Unified Store** (`unified_store.py`)가 모든 계층을 집계하여 통합 질의 인터페이스를 제공한다.

### 5.6 자율 운영 프레임워크 (Runtime)

**위치**: `src/ds_agent/runtime/` (28+ 모듈)

센서 기반 이벤트 구동 자율 시스템:

```
SensorHub (이벤트 큐)           PolicyEngine (정책 평가)
  ├─ FileWatcher (파일 변경)       ├─ 이벤트 x 정책 → dispatch 결정
  ├─ ScheduleSensor (cron tick)    ├─ 쿨다운 + 용량 확인
  ├─ RecoverySensor (복구 신호)    └─ 프롬프트 오버라이드 (선택)
  ├─ TelegramSensor (메시지)
  └─ ApprovalSensor (승인 완료)
         ↓
AutonomousCoordinator → Agent Factory → DSAgent.run()
```

**핵심 런타임 모듈**:

| 모듈 | 역할 |
|------|------|
| `coordinator.py` | 이벤트 → 정책 평가 → 자율 실행 디스패치 |
| `sensor_hub.py` | 이벤트 소스 통합 큐 |
| `policy_engine.py` | 운영자 정의 정책 기반 디스패치 판단 |
| `approval_store.py` | 도구 실행 승인 이력 영속화 |
| `action_classifier.py` | 도구 호출 위험 분류 (SQL/deployment/governance/python/tool-map 전략) |
| `action_matrix.py` | 역할 x 액션 → allow/deny/require-approval 매트릭스 |
| `autonomy_policy.py` | agent_will_do / ask / escalate 경계 |
| `authority_overlay.py` | 24시간 incident/freeze 오버라이드 |
| `delivery_policy_store.py` | quiet hours, digest 주기, 채널 라우팅 |
| `delivery_rate_limiter.py` | 스팸 방지 rate limiting |
| `operator_preferences_store.py` | 운영자 설정 (타임존, digest 빈도, ack 기본값) |
| `startup_recovery.py` | 앱 재시작 시 체크포인트 복원 |
| `task_ledger.py` | 결정 감사 추적 |
| `background_task_manager.py` | 비동기 백그라운드 작업 스케줄링 |
| `channel_identity.py` | 스레드-인식 세션 라우팅 (Telegram 토픽) |
| `run_registry.py` | 활성 실행 추적 |
| `session_registry.py` | 활성 세션 추적 |

### 5.7 Task Contract 엔진

**Enhancement Spec #01** | **상태: Complete**

데이터 사이언스 작업의 전체 수명주기를 typed artifact로 관리한다.

**수명주기**: `draft → agreed → in_progress → review → closed` (또는 `abandoned`)

**핵심 엔티티**:
- `TaskContract`: 루트 엔티티 — 목표, 범위, 제약 조건, 성공 기준
- `GoalBrief`: 작업 목표의 구조화된 설명
- `MetricSpec`: 성공 메트릭 정의
- `DatasetManifest`: 데이터셋 명세
- `AssumptionLog`: 가정 추적 + 검증 워크플로우 (운영자 UI에서 verify)
- `ReviewVerdict`: 검증 결과 (0.0-1.0 신뢰도)
- `DeliveryPack`: 이해관계자별 맞춤 결과물 패키지

**인터페이스**: CLI `ds-agent task ...` + Telegram `/task` + Electron `MissionBriefPanel` (assumption verify UX, authority/audience chips, lifecycle governance smoke) + HTTP API + WebSocket RPC

### 5.8 검증 오케스트레이터 (Verifier)

**Enhancement Spec #03** | **상태: Complete**

에이전트 산출물의 신뢰성을 4계층으로 검증:

| 계층 | 검증 대상 | 방법 |
|------|----------|------|
| **L1: Statistical** | 통계적 정확성 | 수치 검증, 분포 검정 |
| **L2: Data** | 데이터 무결성 | 결측치, 이상치, 스키마 일관성 |
| **L3: Policy** | 조직 정책 준수 | PII, 보안, 규정 준수 |
| **L4: Narrative** | 서술 정합성 | LLM Judge 기반 논리 검증 |

**10차원 평가 체계**: scoping / metric / leakage / trajectory / artifact / summary / approval / completeness / satisfaction / time-to-decision

**Shadow Comparison**: 동일 입력에 대해 두 모델의 결과를 비교하는 shadow evaluation 지원. CLI/Telegram/Electron verifier surface 완비.

### 5.9 자율 제어 평면 (Autonomy Control Plane)

**Enhancement Spec #04** | **상태: Complete**

에이전트의 자율성 수준을 3축으로 제어:

#### 축 1: Authority Mode (6개 수준)
| 모드 | 설명 |
|------|------|
| Shadow | 행동 제안만, 실행하지 않음 |
| Supervised | 매 도구 호출 전 운영자 승인 필요 |
| Delegate | 대부분 자율, 위험 액션만 승인 |
| Autopilot | 완전 자율 (예산 내) |
| Incident | 24시간 긴급 오버라이드 (자율성 일시 중단) |
| Freeze | 전체 자율 행동 동결 |

#### 축 2: Audience Profile (5개 페르소나)
Junior DS / Peer DS / Senior DS (Lead) / Executive / Auditor — 각각 톤, 깊이, 산출물 형태 자동 조정

#### 축 3: Mission Pack
YAML 기반 비즈니스 패키지. 시스템 프롬프트에 미션 목표/제약/경계를 자동 주입.

**ActionClassifier**: 도구 호출을 SQL/deployment/governance/python/tool-map 전략으로 분류. 분류 결과를 ActionMatrix에 조회하여 allow/deny/require-approval 판정.

**PolicyStudio (Electron)**: 운영자가 GUI로 Authority/Audience/Mission을 편집하고, Action Matrix를 셀 단위로 미리보기/수정/적용할 수 있는 관리 도구. Quick presets 지원 (delegated peer / executive review / audit guard / mentor walkthrough).

**추가 구현**: autonomy certification 영속화, CLI/TUI/Telegram/Electron certification flows, legacy-mode migration preview/apply helpers, import-boundary guard coverage.

### 5.10 평가 하네스 (Evaluation Harness)

**Enhancement Spec #05** | **상태: Complete**

에이전트 성능을 체계적으로 측정하고 회귀를 감지:

**Gold Task Set**: 도메인별(finance, healthcare, marketing, ops, retail, saas) 표준 평가 과제

**4가지 평가 모드**:
| 모드 | 설명 |
|------|------|
| Offline | 사전 정의된 Gold Task 대상 자동 평가 |
| Shadow | 운영 중 동일 입력에 두 모델 비교 |
| Online | 실시간 운영 메트릭 모니터링 |
| Human Rubric | 인간 평가자의 구조화된 점수 |

**Regression Board**: 베이스라인 동결 → 후보 평가 → 차원별 delta 계산 → Slack/Teams 알림. Runtime-triggered + daemon-scheduled regression alert dispatch.

**CLI**: `ds-agent eval ingest-human`, `eval shadow-session`, `eval board show|snapshot|freeze-baseline|send-alerts`, `eval run --with-candidate`

**Electron**: Runtime Regression Board freeze/diff inspector, per-mode/per-dimension deltas

### 5.11 Decision OS

**Enhancement Spec #06** | **상태: Complete**

ML 모델의 실험 → 검증 → 프로모션 → 모니터링 전체 수명주기를 관리:

| 구성요소 | 역할 |
|---------|------|
| **Feature Registry** | 피처 등록/버전/메타데이터 관리. YAML 임포터, SQLite 백엔드 |
| **Experiment Tracker** | 실험 실행 기록, 결정적(deterministic) RunDiffEngine |
| **Model Registry** | 모델 버전/메타데이터 관리 |
| **Promotion Gate** | staging→production 체크리스트 + 3-role 승인 (DS/Lead/MLOps) |
| **Post-Deploy Monitor** | 드리프트/메트릭/갱신 주기 모니터링. workspace snapshot, periodic sweep |
| **Review Artifacts** | backtesting, causal-check, uncertainty, retrain-vs-rollback 공유 스킬 아티팩트 |

**자동 캡처**: LLM 응답에서 `DS_REVIEW_ARTIFACTS` hidden block을 자동 파싱하여 실험 실행에 연결. `ReviewArtifactCaptureHook`이 Final Response 단계에서 처리.

**자동화**: 자동 retrain creation, 자동 rollback execution, daemon scheduler 등록, environment-driven trigger policy resolution

**Electron Review Tab**: 실험 비교(RunDiffPanel), 프로모션 요청/해결(PromotionGateModal), 공유 스킬 카드(SharedSkillReviewPanel), 사후 배포 모니터 상태 확인

### 5.12 이해관계자 커뮤니케이션 엔진

**Enhancement Spec #07** | **상태: Complete**

분석 결과를 이해관계자별 맞춤형 산출물로 자동 변환/배포:

**DeliveryPack**: 청중(Junior/Peer/Senior/Executive/Auditor)에 따라 톤, 깊이, 형식을 자동 조정.

**6가지 Export 포맷**: Markdown, PPTX, PDF, DOCX, XLSX, Jupyter Notebook (한국어 콘텐츠 round-trip 지원, 48 tests)

**DeliveryRouter**: 정책 기반 배포 라우팅
- Quiet hours 존중 (야간 알림 보류)
- Digest cadence (시간별/일별/주별 집계)
- 채널별 라우팅

**7개 실제 어댑터**: Email (SMTP), Slack, Notion, Confluence, Jira, Compliance, Git — 각각 feature flag + simulated fallback 지원. 글로벌 real-adapter kill switch.

**추가 기능**: LLM-backed narrative generation (provider-backed render toggle/model override), filesystem-based theme loading, readonly audit PDF, ML handoff spec (Confluence/Jira), tenant/project 오버라이드, pack-level delivery summary metadata

**Electron Mission Brief**: 청중 선택, 테마/tenant 제어, 프로바이더 기반 렌더링 toggle, 인라인 미리보기(markdown/ipynb/pdf + manifest-backed PPTX gallery), 배포 CTA, 채널 검사

### 5.13 워크플로우 통합 (Workflow Integration)

**Enhancement Spec #08** | **상태: Complete (Core)**

에이전트의 작업을 외부 프로젝트 관리/협업 도구와 연동:

**WorkObject**: 에이전트의 작업 단위. Intake → Executing → Review → Closed 수명주기.

**IntegrationHub**: 7개 커넥터를 통합하여 추적 가능한 외부 디스패치 제공

| 커넥터 | 기능 | 특이사항 |
|--------|------|---------|
| Slack | 메시지 발송/채널 관리 | mock-server 테스트 커버리지 |
| Jira | 이슈 생성/상태 변경 | mock-server 테스트 커버리지 |
| Confluence | 페이지 발행 | 마크다운 변환 헬퍼 |
| Notion | 페이지 발행 | 마크다운 변환 헬퍼 |
| Git | GitHub/GitLab PR 생성 | PR flow 지원 |
| Email | SMTP 기반 (HTML, 첨부파일) | STARTTLS, simulated fallback |
| Calendar | Google Calendar 이벤트 생성 | API 기반, simulated fallback |

**DLQ (Dead Letter Queue)**: 실패 이벤트 조회 + 재시도. `_REPLAY_REQUEST_TYPES` Pydantic 모델 매핑으로 저장된 payload를 올바른 request 모델로 복원.

**Rate Limiter**: 시스템별 TokenBucket rate limiting + exponential backoff + jitter

**Policy Gating**: 모든 outbound write는 `PolicyPort.check(...)` 게이트를 통과해야 실행

**Electron**: WorkObjectPanel (intake form/advance picker/close action/timeline), IntegrationSettings (connector health grid, 7 connectors)

### 5.14 비동기 포트폴리오 매니저

**Enhancement Spec #09** | **상태: Complete (12/12 phases)**

여러 데이터 사이언스 프로젝트를 동시에 관리하는 4분면 포트폴리오 시스템:

```
┌──────────────┬──────────────┐
│   Active      │   Waiting    │
│  (실행 중)     │  (조건 대기)   │
├──────────────┼──────────────┤
│  Monitoring   │  Candidates  │
│  (사후 모니터) │  (후보)       │
└──────────────┴──────────────┘
```

**PortfolioEntry**: 4분면 + 3 terminal 상태(completed/failed/cancelled). Pydantic v2, quadrant invariant validator.

**WaitCondition (4종)**:
| 종류 | 설명 | 기본 poll interval |
|------|------|-------------------|
| Timer | 지정 시간 후 재개 가능 | N/A |
| Approval | 운영자 승인 대기 | 60s |
| Data Freshness | 데이터 갱신 대기 | 300s |
| External | 외부 이벤트 대기 | 120s |

**SlotManager**: `max_active_slots` hard constraint만 강제. `acquire_or_refuse()` — 슬롯 초과 시 resume_task tool이 거부 응답을 반환. 어떤 작업을 먼저 할지는 LLM이 판단.

**PriorityCalculator**: business_weight + sla_urgency + age_factor 공식. **LLM에 정보 제공용** — 코드가 강제하는 실행 순서가 아님.

**PortfolioEvaluator**: resumable 후보, 슬롯 현황, 우선순위 순위를 **상태 보고**로 LLM에 제공. **자동 전이 금지**.

**Prompt Integration**: `build_portfolio_section()` — 4분면 현황, resumable 후보, SLA 위험, 슬롯 잔여를 1500 token budget 내에서 상태 보고 형식으로 주입. "You have N resumable tasks. Conditions satisfied: ..." 형태.

**Tools**: `list_my_portfolio` (SAFE), `pause_task` / `resume_task` / `set_sla` / `request_monitoring` (CAUTION)

**Electron ProjectControlTower**: 2x2 그리드 대시보드, entry card (priority badge, SLA countdown, tags, task contract reference), slot usage 표시

**Feature Flag**: `DS_AGENT_PORTFOLIO_ENABLED` (default off)

### 5.15 자기 개선 거버넌스

**Enhancement Spec #10** | **상태: Complete (12/12 phases)**

LLM이 참조하는 조직 지식의 품질을 관리하는 governance 계층. **LLM의 추론 경로를 제어하지 않는다** — 어떤 지식이 프롬프트에 주입되는지를 결정할 뿐이다.

**LearningItem**: 8-state machine
```
proposed → under_review → approved → promoted → monitored → deprecated → archived
```

3가지 유형: `pattern` / `kb_entry` / `custom_skill`

**품질 게이트 흐름**:
1. 세션에서 패턴/KB 엔트리/커스텀 스킬 추출 (`SubmitLearningProposalUseCase`, signature 기반 dedup)
2. LearningInbox에서 우선순위 정렬 (evidence x 0.4 + conflict x 0.3 + scope x 0.2 + staleness x 0.1)
3. 리뷰 (approve/modify/reject) + ReviewChecklist 5-field 검증 + second-reviewer 규칙 (custom_skill + unresolved conflicts)
4. ConflictRef 미해결 시 promotion 차단
5. Eval gate 통과 시 프로모션 (threshold: pattern=1.00, kb_entry=1.00, custom_skill=1.02)
6. 정기 재검증 (pattern 30일, kb_entry 60일, custom_skill 14일)
7. 2회 연속 Eval 실패 시 auto-deprecated (**hard constraint** — 품질 저하 지식의 프롬프트 오염 방지)

**Rollback**: `RollbackPromotionUseCase`로 PromotionRecord.rollback_ref 기반 atomic 복원

**Tools**: `list_learning_inbox` / `review_learning_item` / `get_learning_item` (SAFE), `rollback_promotion` (CAUTION)

**CLI**: `ds-agent learning inbox|review|promotions|deprecations|rollback`

**Telegram**: `/learning inbox`, `/learning review <id> approve|reject`

**Electron LearningInbox**: status filter + item list + review actions (approve/reject) + type/priority badges

**WebSocket RPC**: `learning.inbox` / `learning.review` / `learning.getItem` / `learning.promotions` / `learning.deprecations` / `learning.rollback`

**Prompt Integration**: `_build_learning_governance_context()` — pending review items summary (priority=8)

**Feature Flag**: `DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1` (default off)

### 5.16 Enterprise Semantic Memory

**Enhancement Spec #02** | **상태: Core Complete**

조직 수준의 검증된 지식을 관리하는 시맨틱 메모리 시스템:

| 저장소 | 내용 |
|--------|------|
| **MetricCatalog** | 검증된 비즈니스 메트릭 (정의, 산식, 소유자) |
| **BusinessGlossary** | 비즈니스 용어 사전 |
| **DataTrustRegistry** | 데이터 소스 신뢰 등급 |
| **VerifiedQueryStore** | 검증된 SQL 쿼리 |
| **OrgContextStore** | 조직 컨텍스트 |

**External Sync**: BigQuery, Snowflake, Postgres, dbt, Looker, Unity Catalog에서 메트릭/용어를 동기화

**Semantic Proposal**: 도메인 KB에서 시맨틱 메모리로의 점진적 마이그레이션 워크플로우. Telegram `/semantic_proposal` 인라인 승인/거부. `scripts/promote_domain_kb.py` (dry-run 기본)

**Dual-write**: `memory_query_service.py`에서 semantic-first 조회 + domain_kb fallback. `store("domain_knowledge")` 시 semantic proposal 동시 생성.

**YAML Metric Pack**: 표준 메트릭 팩을 YAML로 정의하고 로딩. `MetricPackLoader` Protocol + `LoadedMetricPack` dataclass (Clean Architecture 준수).

**Electron MetricSourcePanel**: metric/glossary 브라우저, trust context, VQ 표시

### 5.17 멀티 프로바이더 LLM 라우터

**위치**: `src/ds_agent/providers/router.py`

| 프로바이더 | 모델 | 인증 |
|-----------|------|------|
| Anthropic | Claude Opus 4.6, Sonnet 4.6, Haiku 4.5 | API Key |
| OpenAI | GPT-4.1, o3-mini | API Key |
| Codex (ChatGPT) | ChatGPT | OAuth 2.0 PKCE |
| Gemini (Google) | Gemini Pro | OAuth 2.0 PKCE |
| Groq | Mixtral, LLaMA | API Key |
| Mistral | Mistral Large | API Key |
| Ollama | 로컬 모델 | 없음 |
| vLLM / SGLang | 셀프 호스팅 | 없음 |
| LiteLLM | 100+ 프로바이더 라우팅 | 다양 |

**가격 테이블**: 모델별 입력/출력 토큰 가격 내장, 실시간 비용 추적

**OAuth Flows**: ChatGPT/Gemini용 PKCE + localhost callback 서버 내장 (`oauth_service.py` + `callback_server.py`)

### 5.18 샌드박스 코드 실행

**위치**: `src/ds_agent/infrastructure/sandbox/`

에이전트가 생성하는 Python/SQL 코드를 안전하게 격리 실행:

**관련 모듈**: `tools/sandbox.py`, `tools/_ds_sandbox_runner.py`, `tools/code_security.py`, `tools/network_sandbox.py`, `tools/path_utils.py`, `infrastructure/sandbox/preamble_generator.py`, `infrastructure/sandbox/sandbox_runner.py`

**3중 방어**:
1. **정적 분석** (`code_security.py`): AST/regex 기반 코드 스캐너가 위험 패턴을 사전 차단 (파일 시스템 탈출, 네트워크 접근, 위험 import 등)
2. **Runtime Preamble** (`preamble_generator.py`): LLM-proof 코드 전처리 (라이브러리, 헬퍼, 가드)
3. **Subprocess Isolation** (`sandbox_runner.py`): `ProcessSandbox`를 통한 격리 실행. timeout, 메모리 제한, 네트워크 allowlist 제어, `Path.is_relative_to()` 기반 workspace 바운드 경로 검증

**Electron UI**:
- `SandboxApprovalModal`: 위험 코드 실행 전 사용자 차단 승인 모달 (textarea, Esc=거부)
- `SandboxViolationToast`: 정책 위반 알림 (8초 auto-dismiss, 최대 3개 visible)
- `sandbox.violation` 이벤트 emit (5 tests)

---

## 6. 3-Tier 인터페이스

모든 인터페이스가 동일한 `create_agent()` 팩토리를 통해 동일한 에이전트를 사용한다.

### 6.1 CLI (Interactive TUI)

**위치**: `src/ds_agent/cli/`

- **Rich TUI**: 구문 강조, 테이블, 프로그레스 바
- **10+ 서브커맨드**: task, work, delivery, learning, portfolio, semantic, integration, certification, eval, mode, verdict
- **대화형 루프**: 실시간 도구 실행 스트리밍
- **진입점**: `ds-agent` (대화형), `ds-agent-daemon` (데몬 모드)

### 6.2 Telegram Bot

**위치**: `src/ds_agent/gateway/telegram_runner.py`

- **스레드 인식**: 토픽별 세션 격리 (`channel_identity.py`)
- **승인 흐름**: 인라인 키보드로 도구 실행 승인/거부
- **명령어**: `/task`, `/semantic_proposal`, `/learning`, `/mode`, 일반 대화
- **Autonomous Digest**: quiet hours, digest 주기에 따른 알림 배포
- **Semantic Proposal**: `/semantic_proposal list|approve|reject|diff <id>`

### 6.3 Electron Desktop App

**위치**: `electron/`

**아키텍처**: Electron Main → Python Backend (PyInstaller binary) spawn → READY:port:token 신호 → WebSocket 통신 → React Renderer

**Main Process** (`src/main/`):
- `python-backend.ts`: PyInstaller 바이너리 spawn/관리, 포트 선택, 토큰 생성
- `index.ts`: 앱 수명주기 — `/health` 프로브 성공 시 메인 윈도우, 실패 시 진단 윈도우
- `secret-vault.ts`: IPC를 통한 Keyring 접근
- `auto-updater.ts`: electron-updater 통합
- `observability.ts`: Sentry crash reporting

**Preload Bridge** (`src/preload/index.ts`): 안전한 IPC API — WebSocket control, secret vault, policy, updater, IPC calls를 sandboxed API로 노출

**Renderer (React 18 + Zustand)** — 주요 UI 영역:

| 영역 | 컴포넌트 | 설명 |
|------|---------|------|
| **Chat** | ChatPanel, ChatMessage, ToolActivity | 대화 + 실시간 도구 실행 스트림 |
| **Sidebar** | FileExplorer, PlotGallery, ModelSelector, UsageMeter | 파일/차트/모델/비용 |
| **Mission Brief** | MissionBriefPanel, ContractEditor, AssumptionDrawer | Task Contract 관리 |
| **Runtime** | SessionsPanel, RunsPanel, PolicyPanel, CertificationBoard, RegressionBoard | 런타임 상태 |
| **Workflow** | WorkObjectPanel, IntegrationSettings, ApprovalPanel | 워크플로우 통합 |
| **Review** | ReviewTab, RunDiffPanel, PromotionGateModal, SharedSkillReviewPanel | Decision OS |
| **Portfolio** | ProjectControlTower | 4분면 대시보드 |
| **Learning** | LearningInbox | 학습 거버넌스 |
| **Semantic** | MetricSourcePanel | 메트릭/용어 브라우저 |
| **Settings** | SettingsPanel, OnboardingWizard, PolicyStudio, AdminConsole, SkillManager | 설정/온보딩/정책 |
| **Diagnostic** | DiagnosticPanel | 백엔드 실패 진단 |
| **Sandbox** | SandboxApprovalModal, SandboxViolationToast | 코드 실행 안전 |

**11개 Zustand Stores**: chatStore, agentStore, runtimeStore, configStore, filesStore, policyStore, projectStore, workflowStore, authStore, i18nStore, usageStore

---

## 7. 코드베이스 정량 분석

### 7.1 백엔드 주요 패키지 규모

| 영역 | Python 파일 수 | 역할 |
|------|---------------|------|
| `agent/` | ~20 | 메인 루프, 프롬프트, 예산, hook/harness |
| `application/` | ~64 | 유스케이스 계층 |
| `domain/` | ~97 | 엔티티, value object, protocol |
| `infrastructure/` | ~96 | 저장소, auth, observability, secrets, migration |
| `runtime/` | ~48 | 자율 런타임, 정책, 알림, 회복, 레지스트리 |
| `memory/` | ~51 | 실험 로그, 프로젝트/도메인 지식, semantic memory |
| `tools/` | ~46 | DS/운영/거버넌스 도구 |

### 7.2 주요 동적 인터페이스 수치

| 항목 | 수치 | 근거 |
|------|------|------|
| `@tool(...)` 등록형 도구 수 | 76 | `src/ds_agent/tools/*.py` 집계 |
| Hook 수 | 30 | `agent/factory.py` 등록 목록 |
| WebSocket RPC 메서드 수 | 80 | `api/ws_handler.py` `_METHOD_MAP` |
| 기본/공유 스킬 수 | 14 | `skills/builtin` 8개 + `skills/shared` 6개 |
| HTTP 라우트 모듈 수 | 10 | `src/ds_agent/api/routes/*.py` |

### 7.3 프론트엔드 구성 수치

| 항목 | 수치 |
|------|------|
| Electron npm script 수 | 27 |
| Contract test script 수 | 9 |
| E2E/smoke script 수 | 6 |
| Electron 테스트 spec 수 | 19 |
| Python 테스트 소스 파일 수 | 333 |

### 7.4 유지보수 핫스팟 (대형 파일)

| 파일 | 줄 수 | 역할 | 비고 |
|------|-------|------|------|
| `api/ws_handler.py` | ~4,434 | 전체 WebSocket RPC control plane | 현재 가장 큰 집중 포인트 |
| `electron/src/main/ipc.ts` | ~1,509 | Electron IPC 핸들러 전체 | 기능 추가 시 충돌 위험 |
| `MissionBriefPanel.tsx` | ~863 | Task Contract 데스크톱 UI | 분리 검토 대상 |
| `SettingsPanel.tsx` | ~773 | 설정 UI 전체 | 분리 검토 대상 |

기능 폭은 매우 넓고 강력하지만, 이 파일들은 이미 **운영상 핫스팟**이 되기 시작했다. 향후 기능 확장 시 변경 충돌과 회귀 위험이 커질 수 있다.

---

## 8. 제품화 현황

### 8.1 Milestone A: 제품 안전 기반선 (P0 — 베타 출시 차단 조건)

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| P0-01 | 코드 실행 샌드박싱 | **Complete** | 런타임 preamble + 정적 분석 + Phase 3 UI (차단 승인 모달 + 위반 토스트) |
| P0-02 | 자격증명 보안 저장 | **Complete (코드)** | OS keyring + 청크 분할 (Windows 2560B 제한 우회). 멀티플랫폼 실측 대기 |
| P0-03 | 시작 진단 및 복구 | **Complete** | 실패 원인 분류 + 진단 패널 UI |
| P0-04 | 설정/데이터 마이그레이션 | **Complete** | Schema v4 (observability defaults), 7-step 규약 문서화 |
| P0-05 | 코드 서명 및 배포 | **Blocked** | CI 파이프라인 + electron-builder 구성 완료. Windows EV + Apple Developer ID 조달 대기 |
| P0-06 | 패키지 QA & 스모크 | **In Progress** | Backend smoke 5/5, Electron diagnostic/happy-path E2E pass. 서명 바이너리 E2E는 P0-05 의존 |
| P0-07 | 관찰 가능성 & 크래시 리포팅 | **Complete (코드)** | Sentry SDK 통합 (`sentry_backend.py` + `@sentry/electron/main`), DSA-XXX-YYY 에러 코드 카탈로그 (`error_mapping.py`), 온보딩 telemetry consent 3-choice UI, 1-click support bundle export. DSN 조달 대기 |

### 8.2 Milestone B: 엔드유저 제품 UX (P1 — Public Beta 품질)

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| P1-08 | Use-case 기반 온보딩 | **Complete** | 가이드 온보딩 플로우 |
| P1-09 | Provider/Model 추상화 UX | **Complete** | 모델 선택 UX |
| P1-10 | 데이터 수집 UX | **Complete** | Postgres GA, ConnectorWizard 구현, backend RPC 26 tests. BigQuery/Snowflake UI는 post-beta |
| P1-11 | 비용 거버넌스 & 사용량 | **Complete** | 예산 추적, 비용 추정, 한도 강제 |
| P1-12 | 결과물 Export & 리포팅 | **Complete** | PDF/DOCX/XLSX/IPYNB + 한국어 콘텐츠 round-trip (48 tests) |
| P1-13 | i18n (한국어) & 접근성 | **Complete** | ARIA 감사 7개 modal/overlay 컴포넌트 완료. 잔존: focus trap, axe-core (post-beta) |
| P1-14 | 자동 업데이트 & 릴리스 | **Blocked** | electron-updater 배선 완료. 코드 서명 의존 |

### 8.3 Milestone D: 팀 & 엔터프라이즈 (P2 — 베타 이후 연기)

| # | 항목 | 상태 |
|---|------|------|
| P2-15 | 팀/엔터프라이즈 제어 | Deferred (organization_store stub 존재) |
| P2-16 | 확장성 & 마켓플레이스 | Deferred |

### 8.4 2026-04-15 주요 하드닝 실적

실제 코드에 반영된 대표 hardening:

| 항목 | 구현 위치 | 설명 |
|------|----------|------|
| READY emission race 해결 | `api/app.py` | FastAPI lifespan startup hook으로 이동, 소켓 바인드 후 `READY:port:token` emit |
| Backend startup diagnostics | `electron/src/main/python-backend.ts` | `/health` 검증 + 실패 시 진단 윈도우 자동 전환 |
| Windows keyring chunking | `infrastructure/secrets/secret_storage.py` | Windows Credential Manager 2560-byte 제한 우회 (>1024 chars 청크 분할) |
| Sandbox violation UI | `electron/src/renderer/components/sandbox/` | `SandboxApprovalModal` (blocking) + `SandboxViolationToast` (8s auto-dismiss, max 3) |
| Sentry 3단 wiring | `sentry_backend.py`, `main/observability.ts`, `renderer/observability.ts` | Backend + Electron main + Renderer 각각 Sentry SDK 통합 + redaction filter |
| Telemetry consent UX | `OnboardingWizard.tsx`, `PrivacySettings.tsx` | 3-choice 동의 UI (full/limited/none) |
| Degraded-mode operator UX | `secret_storage.py`, CLI banner | `describe_secret_storage()` + in-memory fallback 경고 표시 |
| E2E test hooks | Electron main process | `DS_AGENT_BACKEND_COMMAND` (backend override), `DS_AGENT_E2E_USE_BUILT_RENDERER` (Vite dev 없이 빌드 결과물 로드) |

### 8.5 베타 출시 차단 요인 요약

**내부 코드 작업: 전부 완료**. 잔존 차단 요인은 외부 의존뿐:

| 항목 | 차단 원인 |
|------|----------|
| P0-05 코드 서명 | Windows EV 인증서 + Apple Developer ID 조달 |
| P0-06 signed E2E | P0-05 의존 |
| P0-07 Sentry 활성화 | Sentry DSN 발급 |
| P1-14 서명된 자동업데이트 | P0-05 의존 |
| P0-02 멀티플랫폼 keyring 실측 | 서명 바이너리 + 플랫폼별 실기 |

---

## 9. 테스트 및 품질 보증

### 9.1 테스트 구조

| 계층 | 위치 | 목적 |
|------|------|------|
| Unit Tests | `tests/unit/` | 도메인/애플리케이션 로직 |
| Integration Tests | `tests/integration/` | 영속화, 외부 커넥터 |
| Smoke Tests | `tests/smoke/` | 백엔드 기동, /health, WebSocket |
| Architecture Tests | `tests/unit/architecture/` | import 계약, 계층 의존성 검증 |
| Electron Contract Tests | `electron/tests/contract/` (9 suites) | 타입 계약, 컴포넌트 행동 |
| Electron E2E (Playwright) | `electron/tests/smoke/` (6+ suites) | 패키지 바이너리 엔드투엔드 |

### 9.2 검증 기준선 (2026-04-16)

| 검증 항목 | 결과 |
|----------|------|
| Python Unit + Smoke Tests | **1,382+ passed** |
| 패키지 바이너리 스모크 | **5/5** (기동, /health, /api/status, WS) |
| Electron E2E | **6 suites pass** (diagnostic, happy-path, autonomy, task-contract, decision-os, workflow) |
| Electron Contract Tests | **9 suites pass** (delivery-preview, mission-brief, policy-studio, work-objects, verifier, runtime, semantic, portfolio, learning) |
| Electron TypeScript typecheck | **Clean** |
| Electron build | **Clean** |
| `ruff check` (lint) | **Clean** |
| `mypy` (type check) | **Clean** |
| `python -m compileall` | **Clean** |
| Coverage threshold | **>= 78%** |
| Enhancement Spec 12-phase plan | **12/12 phases 100% complete** |

### 9.3 Enhancement Spec별 테스트 커버리지

| Spec | 대표 테스트 수 |
|------|--------------|
| 01 Task Contract | 39+ |
| 02 Semantic Memory | 15+ (architecture + pack + contract) |
| 03 Verifier Orchestrator | 다수 (nightly judge 포함) |
| 04 Autonomy Control Plane | 230+ |
| 05 Evaluation Harness | 다수 (regression board + daemon) |
| 06 Decision OS | 66+ |
| 07 Stakeholder Communication | 200+ (11 suites) |
| 08 Workflow Integration | 89+ |
| 09 Portfolio Manager | 39+ (domain 18 + integration 10 + application 11) |
| 10 Self-Improvement Governance | 92+ (domain 45 + application 14 + integration 13 + Phase 12: 20) |

---

## 10. 빌드 및 배포 파이프라인

### 10.1 빌드 스크립트

| 스크립트 | 역할 |
|---------|------|
| `scripts/build_backend.py` | PyInstaller → single-file binary (43.5 MB) |
| `scripts/build_all.py` | Backend + Electron NSIS installer |
| `scripts/sign_backend.py` | Windows signtool / macOS codesign 래퍼 |
| `scripts/check_av_clean.py` | VirusTotal 자동 스캔 (CI 선택) |
| `scripts/check_import_contracts.py` | Clean Architecture 의존성 검증 (AST 기반) |
| `scripts/check_layer_deps.py` | Semantic memory 계층 의존성 검증 |
| `scripts/promote_domain_kb.py` | DomainKB → SemanticProposal 마이그레이션 |
| `scripts/seed_*.py` (5+) | E2E 테스트용 workspace 시딩 (autonomy, decision-os, task-contract, workflow, etc.) |

### 10.2 배포 형태

| 플랫폼 | 형식 | 크기 | 비고 |
|--------|------|------|------|
| Windows | NSIS installer (per-user, UAC-free, 데스크톱+시작메뉴 바로가기) | ~179 MB | EV 인증서 대기 |
| macOS | DMG | 대기 중 | Apple Developer ID 대기 |
| Linux | AppImage | 대기 중 | - |

### 10.3 CI/CD

- `.github/workflows/build-release.yml`: tag/dispatch 기반 서명 + 업로드 파이프라인
- `electron/electron-builder.yml`: CSC_LINK, notarize, draft publish 설정
- `electron/resources/entitlements.mac.plist`: Hardened runtime entitlements

---

## 11. 프로젝트 구조 맵

```
AI_Data_Scientist_Demo/
│
├── src/ds_agent/                          # Python 백엔드 (핵심)
│   ├── agent/                             # LLM 오케스트레이터 코어
│   │   ├── core.py                        #   DSAgent 메인 루프
│   │   ├── factory.py                     #   통합 에이전트 팩토리
│   │   ├── prompt_builder.py              #   Token-aware 프롬프트 조립
│   │   ├── prompt_sections.py             #   프롬프트 섹션 상수 + 빌더
│   │   ├── hooks.py                       #   Hook 프레임워크
│   │   ├── builtin_hooks.py               #   15+ 빌트인 hook
│   │   ├── ds_workflow_hooks.py           #   8 DS 전용 hook
│   │   ├── governance_hooks.py            #   거버넌스 hook (PII, Policy, Lineage)
│   │   ├── semantic_hooks.py              #   시맨틱 메모리 hook
│   │   ├── budget_tracker.py              #   예산 추적 (반복수/비용/시간)
│   │   ├── permissions.py                 #   액션 기반 권한 모델
│   │   ├── context_manager.py             #   컨텍스트 윈도우 관리
│   │   └── confidence_scorer.py           #   신뢰도 점수
│   │
│   ├── domain/                            # 도메인 (Clean Architecture 최내부, zero deps)
│   │   ├── entities/                      #   30+ 비즈니스 엔티티 (Pydantic v2)
│   │   ├── value_objects/                 #   불변 값 타입
│   │   ├── interfaces/                    #   포트 인터페이스 (Protocol)
│   │   ├── services/                      #   도메인 서비스
│   │   ├── errors/                        #   예외 계층 구조
│   │   ├── portfolio/                     #   Portfolio 엔티티 (4분면, WaitCondition, Checkpoint)
│   │   ├── learning/                      #   Learning 엔티티 (8-state machine, Review, Promotion)
│   │   └── dtos/                          #   도메인 DTO
│   │
│   ├── application/                       # 유스케이스 & 애플리케이션 서비스
│   │   ├── usecases/                      #   ~20 유스케이스 클래스
│   │   ├── services/                      #   애플리케이션 서비스
│   │   ├── portfolio/                     #   Portfolio 유스케이스 (evaluator, slot, priority, wait)
│   │   ├── learning/                      #   Learning 유스케이스 (submit, inbox, review, promote, deprecate, rollback, revalidation)
│   │   ├── ports/                         #   애플리케이션 포트
│   │   └── dtos/                          #   요청/응답 DTO
│   │
│   ├── infrastructure/                    # 어댑터 & 프레임워크
│   │   ├── persistence/                   #   SQLite 저장소 (migration v1-v13)
│   │   ├── auth/                          #   인증 (OAuth 2.0 PKCE + localhost callback)
│   │   ├── secrets/                       #   자격증명 (OS keyring + chunking)
│   │   ├── sandbox/                       #   샌드박스 코드 실행 (preamble + subprocess isolation)
│   │   ├── observability/                 #   Sentry + structlog + DSA-* error catalog
│   │   ├── exporters/                     #   PDF/DOCX/XLSX/PPTX/IPYNB 변환
│   │   ├── external/                      #   Slack/Jira/Confluence/Notion/Git/Email/Calendar connectors
│   │   ├── migration/                     #   DB 마이그레이션 러너
│   │   ├── delivery/                      #   배달 라우팅 어댑터 (7개 + compliance)
│   │   ├── verifiers/                     #   품질 검증기
│   │   ├── artifact/                      #   아티팩트 저장
│   │   └── distributed/                   #   분산 컴퓨팅 (Spark, Dask)
│   │
│   ├── tools/                             # LLM 도구 레지스트리 (40 모듈, 100+ 도구)
│   ├── skills/                            # 방법론 팩 (8 builtin + 6 shared + domain + custom)
│   ├── memory/                            # 5계층 메모리 (session/domain/semantic/project/unified)
│   ├── runtime/                           # 자율 운영 (28+ 모듈)
│   ├── evaluation/                        # 평가 하네스 (Gold Task, 10-dim scorer, Regression Board)
│   ├── self_improve/                      # 자기 학습 파이프라인
│   ├── api/                               # FastAPI REST + WebSocket RPC
│   ├── cli/                               # Rich TUI CLI (10+ 서브커맨드)
│   ├── gateway/                           # Telegram 러너 + 세션 관리
│   ├── providers/                         # LLM 프로바이더 라우터 (10+ 프로바이더)
│   └── config/                            # Pydantic v2 설정 스키마 (v4) + YAML 로더
│
├── electron/                              # Electron 데스크톱 앱
│   ├── src/main/                          #   Main 프로세스 (backend spawn, diagnostic, IPC, vault, updater)
│   ├── src/preload/                       #   보안 IPC 브릿지
│   ├── src/renderer/                      #   React 18 + Zustand + TailwindCSS
│   │   ├── components/ (40+)              #     Chat, Sidebar, Runtime, Settings, Workflow, Review, Portfolio, Learning, Semantic, Sandbox, Diagnostic
│   │   ├── hooks/ (15+)                   #     useChat, useAgent, useRuntime, useWorkflow, useTaskContract, usePortfolio, useLearning, ...
│   │   ├── stores/ (11)                   #     chatStore, agentStore, runtimeStore, configStore, filesStore, policyStore, projectStore, workflowStore, authStore, i18nStore, usageStore
│   │   └── types/                         #     TypeScript 인터페이스
│   ├── tests/contract/ (9 suites)         #   타입 계약 테스트
│   ├── tests/smoke/ (6+ suites)           #   Playwright E2E 테스트
│   └── electron-builder.yml               #   배포 설정 (NSIS/DMG/AppImage)
│
├── tests/                                 # Python 테스트 (1,382+)
│   ├── unit/ (domain, application, architecture)
│   ├── integration/ (persistence, infrastructure)
│   ├── smoke/ (backend boot, health)
│   └── e2e/ (full workflow)
│
├── scripts/                               # 빌드/유틸리티/시딩
├── Docs/                                  # 문서 (enhancement-specs, plans, productization)
├── config/ + assets/                      # 설정 및 테마 에셋
├── gold_tasks/                            # 평가용 Gold Task (도메인별)
├── pyproject.toml                         # Python 프로젝트 메타데이터
├── .github/workflows/                     # CI/CD 파이프라인
└── .importlinter                          # 아키텍처 의존성 규칙
```

---

## 12. 품질, 보안, 운영 성숙도 평가

### 12.1 아키텍처 및 구현 강점

1. **아키텍처 의도와 구현이 일치한다.**
   Clean Architecture, Protocol 중심 의존성 역전, agent core 분리, runtime/store 분리가 코드 수준에서 지켜지고 있으며 `scripts/check_import_contracts.py`와 `tests/unit/architecture/` CI 검증으로 뒷받침된다.

2. **가드레일이 선언이 아니라 실행 코드다.**
   샌드박스(`ProcessSandbox` + AST/regex 코드 스캐너 + 네트워크 allowlist + `Path.is_relative_to()` 경로 검증), approval hook, safety level, audit log가 단순 문서가 아니라 매 도구 호출에서 실행된다.

3. **제품화 코드가 현실적이다.**
   READY emission race 해결(`api/app.py` lifespan startup hook), Windows keyring chunking(>1024 chars), Sentry backend/main/renderer 3단 wiring(`sentry_backend.py` + `@sentry/electron/main` + `renderer/observability.ts`), telemetry consent 3-choice UX, 진단 패널, auto-updater, E2E hook (`DS_AGENT_BACKEND_COMMAND`, `DS_AGENT_E2E_USE_BUILT_RENDERER`)가 모두 실제 코드로 존재한다.

4. **운영자 제어면이 강하다.**
   Telegram delivery policy, digest cadence, mute/ack/suppression state, quiet hours, operator preferences, runtime console, thread-aware session identity가 잘 갖춰져 있다. 운영자는 데스크톱 없이도 Telegram에서 승인/거부/모드 전환/학습 리뷰를 수행할 수 있다.

5. **장기적 지식 축적 구조가 있다.**
   5계층 메모리 + semantic memory(DomainKB → semantic-first + legacy fallback 전략) + learning governance(8-state 승격/폐기/롤백) + portfolio manager가 시스템의 점진적 역량 향상을 구조적으로 뒷받침한다.

6. **Hook 설계가 분석 품질을 코드로 강제한다.**
   30개 hook은 이 시스템의 핵심 차별점이다. "프롬프트에 지침을 넣는 수준"을 넘어, **도구 실행 자체를 품질/정책 이벤트로 감싼다**:
   - 권한/정책: `PermissionHook`, `OrgPolicyHook`, `PolicyApprovalHook`
   - 비용/리소스: `BudgetGuardHook`, `QueryCostGuardHook`, `ProcessMetricsHook`
   - DS 품질: `BaselineGuardHook`, `LeakageDetectionHook`, `OverfittingDetectorHook`, `ModelSanityCheckHook`, `StageQualityHook`
   - 의미/지식: `SemanticReadGuardHook`, `SemanticTrustHook`, `SemanticWritebackHook`
   - 추적성/감사: `AuditLogHook`, `LineageCaptureHook`, `ClaimTraceabilityHook`, `ReviewArtifactCaptureHook`

### 12.2 운영상 주의 포인트

1. **대형 파일 집중**: `ws_handler.py`(~4,434줄), `ipc.ts`(~1,509줄), `MissionBriefPanel.tsx`(~863줄), `SettingsPanel.tsx`(~773줄)는 기능 확장 시 변경 충돌과 회귀 위험이 커질 수 있다.

2. **JSON 파일 기반 런타임 store**: 여러 runtime store(policy, preferences, alert state 등)가 JSON 파일 기반이다. Beta 규모에는 충분하지만, 동시성/관찰성/운영 쿼리 측면에서는 추후 DB화 여지가 있다.

3. **외부 의존 차단 요인**: 서명 인증서, Apple Developer ID, Sentry DSN 없이는 최종 상용 배포 검증이 완료되지 않는다.

4. **문서 정합성 drift**: 일부 상위 문서(AGENTS.md 등)가 참조하는 `Docs/ARCHITECTURE.md`, `Docs/SECURITY.md`, `Docs/QUALITY_SCORE.md` 등이 현재 리포지토리에서 직접 확인되지 않는다. Enhancement spec 헤더와 본문 진행률 간에도 일부 비동기가 존재한다.

### 12.3 전략적 평가

현재 시스템은 "분석 실행" 수준을 넘어 **"조직 내 운영 가능한 AI 에이전트 제품"**의 골격을 갖췄다. 남은 핵심은 기능 구현보다 **배포 신뢰성, 운영 인증, 문서 정합성, 대형 파일 분해** 쪽이다.

이 시스템은 다음 세 가지가 동시에 구현된 보기 드문 구조이다:
1. **Autonomous Data Science Engine** — 자율 DS 워크플로 실행
2. **Operator-Controlled Runtime Platform** — 운영자 통제 런타임
3. **Productized Desktop/Deployment Surface** — 제품화된 데스크톱 UX/배포면

> 즉, "LLM을 분석가로 쓰는 앱"이 아니라,
> "자율형 AI Data Scientist를 제품 수준으로 운영하기 위한 풀스택 시스템"이다.

---

## 13. 잔존 과제, 기술 부채, 로드맵

### 13.1 Enhancement Spec 구현 상태 종합

| # | 영역 | Phase | 상태 |
|---|------|-------|------|
| 01 | Task Contract Engine | P0 | **Complete** |
| 02 | Enterprise Semantic Memory | P1 | **Core Complete** (DomainKB cutover/README 잔존) |
| 03 | Verifier Orchestrator | P0-P1 | **Complete** |
| 04 | Autonomy Control Plane | P0-P2 | **Complete** |
| 05 | Evaluation Harness | P1-P3 | **Complete** |
| 06 | Decision OS | P2 | **Complete** |
| 07 | Stakeholder Communication | P1 | **Complete** |
| 08 | Workflow Integration | P2-P3 | **Complete (Core)** (BI connector optional) |
| 09 | Async Portfolio Manager | P3 | **Complete** (feature flag, 12/12 phases) |
| 10 | Self-Improvement Governance | P3 | **Complete** (feature flag, 12/12 phases) |

### 13.2 기술 부채 및 추천 후속 작업

| 우선순위 | 항목 | 설명 |
|---------|------|------|
| **높음** | `ws_handler.py` 분해 | ~4,434줄 단일 파일을 기능군 단위 라우터/handler 모듈로 분리 (chat, policy, taskContract, decisionOs, delivery, workflow, portfolio, learning 등) |
| **높음** | `ipc.ts` 분해 | ~1,509줄 단일 파일을 기능 도메인별 IPC handler 모듈로 분리 |
| **중간** | 대형 React 컴포넌트 분리 | `MissionBriefPanel.tsx`(~863줄), `SettingsPanel.tsx`(~773줄) 등을 하위 컴포넌트로 분해 |
| **중간** | Runtime JSON store DB화 | policy, preferences, alert state 등 JSON 파일 기반 store를 운영 핵심 데이터부터 점진적 SQLite 전환 검토 |
| **중간** | 누락 상위 문서 복원 | AGENTS.md가 참조하는 `Docs/ARCHITECTURE.md`, `Docs/SECURITY.md`, `Docs/QUALITY_SCORE.md` 실제 파일 작성 또는 참조 정리 |
| **낮음** | Enhancement spec 헤더/본문 정합화 | 일부 spec의 헤더 상태와 본문 Progress Tracking 간 비동기 해소 |

### 13.3 Post-Beta 로드맵

| 우선순위 | 항목 | 설명 |
|---------|------|------|
| P2-15 | 팀/엔터프라이즈 제어 | 조직 관리, 역할/권한, 팀 대시보드 |
| P2-16 | 확장성 & 마켓플레이스 | 스킬/커넥터 마켓플레이스, 플러그인 API |
| Post-beta | BI 커넥터 확장 | BigQuery/Snowflake/Asana/Monday UI 연동 |
| Post-beta | 접근성 고도화 | Focus trap, axe-core 자동 측정, 단축키 헬프 |
| Post-beta | Notebook-native 스킬 편집 | Jupyter에서 직접 스킬 편집 |

---

## 부록: 핵심 수치 요약

| 지표 | 값 |
|------|-----|
| Python 소스 파일 | 422+ (domain 97, application 64, infrastructure 96, runtime 48, memory 51, tools 46, agent 20) |
| LLM 도구 (`@tool` 등록) | 76 (40 모듈) |
| Hook | 30 |
| WebSocket RPC 메서드 | 80 |
| HTTP 라우트 모듈 | 10 |
| 빌트인 스킬 | 14 (8 core + 6 shared) |
| Zustand Store | 11 |
| React 컴포넌트 | 40+ |
| Enhancement Specs | 10 (8 complete + 2 complete with feature flag) |
| 제품화 계획 문서 | 19 파일 |
| Python 테스트 | 1,382+ passing |
| Electron E2E | 6 suites passing |
| Electron Contract Tests | 9 suites passing |
| Electron test spec 파일 | 19 |
| Python 테스트 소스 파일 | 333 |
| Electron npm script 수 | 27 |
| 커버리지 임계값 | >= 78% |
| 지원 LLM 프로바이더 | 10+ (100+ via LiteLLM) |
| 외부 커넥터 | 7 (Slack, Jira, Confluence, Notion, Git, Email, Calendar) |
| Export 포맷 | 6 (MD, PPTX, PDF, DOCX, XLSX, IPYNB) |
| DB Migration 버전 | v13 |
| 패키지 바이너리 크기 | 43.5 MB (backend) / ~179 MB (installer) |

---

*본 보고서는 2026-04-16 기준 전체 리포지토리 분석, 제품화 계획 문서(Docs/plans/productization/ 19파일), 고도화 구현 결과(Docs/plans/PLAN_remaining-enhancement-specs.md 12 phases), 10개 Enhancement Spec 문서(Docs/enhancement-specs/), 코어 소스 코드를 기반으로 작성되었다.*
