# DS Agent — UI/UX & 디자인 분석 보고서

**문서 버전**: 1.0
**작성일**: 2026-04-18
**문서 범위**: 사용자 인터페이스, 인터랙션 디자인, 비주얼 디자인 시스템, UX 플로우, 접근성
**관련 문서**: 시스템 아키텍처 및 기능 설계는 [`SYSTEM_ARCHITECTURE_AND_FEATURES.md`](./SYSTEM_ARCHITECTURE_AND_FEATURES.md) 참조

---

## 0. 문서 구성 안내 (Cross-Reference Guide)

본 프로젝트는 두 개의 분리된 분석 문서로 관리됩니다. 본 문서는 **사용자가 체감하는 표면**에 집중하고, 내부 아키텍처는 파트너 문서에서 다룹니다.

| 문서 | 범위 | 주요 독자 |
|------|------|----------|
| [`SYSTEM_ARCHITECTURE_AND_FEATURES.md`](./SYSTEM_ARCHITECTURE_AND_FEATURES.md) | Clean Architecture 레이어, LLM Provider 설계, 도구 시스템, 샌드박스, 패키징, 보안 | 백엔드/플랫폼 엔지니어 |
| **본 문서** (`UI_UX_DESIGN_ANALYSIS.md`) | Electron/CLI/Telegram 인터페이스, 디자인 시스템, 컬러·타이포, 접근성, UX 플로우 | 디자이너, 프론트엔드 엔지니어, PM |

**교차 참조 표기**: 본 문서 내에서 시스템 내부 구조가 필요한 부분은 `→ [ARCH §N.N]` 형태로 표기합니다.

### 빠른 네비게이션 (UI/UX ↔ 아키텍처 매핑)

| 주제 | 본 문서 섹션 | 아키텍처 문서 섹션 |
|------|--------------|-------------------|
| 인터페이스 종류 | [§1. Interface Inventory](#1-interface-inventory) | [ARCH §4. Interface Surface](./SYSTEM_ARCHITECTURE_AND_FEATURES.md#4-interface-surface-3-tier) |
| 모델 선택/OAuth 연결 | [§8.1–8.2 온보딩 & 모델 UX](#8-ux-플로우--인터랙션-패턴) | [ARCH §5. LLM Provider](./SYSTEM_ARCHITECTURE_AND_FEATURES.md#5-llm-provider-architecture-3-way-model) |
| Tool 호출 시각화 | [§2.4 Tool Activity](#24-tool-activity-시각화) | [ARCH §6. Tool System](./SYSTEM_ARCHITECTURE_AND_FEATURES.md#6-tool-system) |
| 샌드박스 UI (승인/위반) | [§2.9 오류 & 오버레이](#29-오류-처리--오버레이) | [ARCH §7. Sandbox](./SYSTEM_ARCHITECTURE_AND_FEATURES.md#7-sandbox--code-execution) |
| 오류 복구/폴백 배너 | [§8.4](#84-오류-복구) | [ARCH §5.5 Parity Harness](./SYSTEM_ARCHITECTURE_AND_FEATURES.md#55-parity-harness-fixture-기반-재생) |
| 결과 렌더링 (markdown/플롯/테이블) | [§5. Information Architecture](#5-information-architecture) | [ARCH §9.4 Experiment](./SYSTEM_ARCHITECTURE_AND_FEATURES.md#94-experiment--lineage) |

---

## 1. Interface Inventory

DS Agent는 세 가지 구별되는 상호작용 패러다임을 지원합니다.

### 1.1 Electron 데스크탑 앱 (Primary Surface)

- **위치**: `electron/`
- **스택**: React 18 + TypeScript + Tailwind CSS + Lucide React (아이콘) + Zustand (상태)
- **빌드**: Vite + TypeScript
- **규모**: 130+ `.tsx/.ts` 파일, 66 컴포넌트
- **상태**: 제품화 릴리즈 후보 (production-ready)

### 1.2 CLI 터미널 인터페이스

- **위치**: `src/ds_agent/cli/`
- **스택**: Python Typer + Rich 라이브러리 (Rich Panel, Markdown, Table 렌더러)
- **특징**: 테마 기반 컬러 출력, 10+ 슬래시 커맨드, 온보딩 위저드 (P1-08)

### 1.3 Telegram 봇 채널

- **위치**: `src/ds_agent/channels/bundled/telegram/`, `src/ds_agent/gateway/telegram_runner.py` (~3800 LOC)
- **제한**: 4096 자/메시지, 스트리밍 미지원 → 배치 전송 + 인라인 버튼
- **특징**: Markdown 렌더링, 스레드 격리 (topic-aware), approval 인라인 키보드

> 기술 스택 세부는 [ARCH §4. Interface Surface](./SYSTEM_ARCHITECTURE_AND_FEATURES.md#4-interface-surface-3-tier) 참조.

---

## 2. Electron Desktop App (Primary Focus)

### 2.1 레이아웃 아키텍처

Tripartite 레이아웃 (`electron/src/renderer/components/MainPanel.tsx:38-62`):

```
┌──────────────────────────────────────────────────────────────┐
│ Sidebar (7 tabs)  │    Chat Panel         │  Detail Drawer   │
│                   │                       │  (run detail,    │
│   Files           │  Message List         │   conditional)   │
│   Workflow        │  ToolActivity         │                  │
│   Review          │  ChatInput            │                  │
│   Runtime         │                       │                  │
│   Experiments     │                       │                  │
│   Portfolio       │                       │                  │
│   Learning        │                       │                  │
│                   │  StatusBar (footer)  ───────────────────│
└──────────────────────────────────────────────────────────────┘
```

**핵심 컴포넌트**:
- `App.tsx` (1-217 LOC): 루트 오케스트레이터 — splash, onboarding, settings, WebSocket 연결 관리
- `MainPanel.tsx`: Sidebar + ChatPanel + RunDetailDrawer 조율
- `ChatPanel.tsx`: 메시지 리스트 + ToolActivity + ChatInput (새 메시지 시 자동 스크롤)
- `Sidebar.tsx`: 7-탭 네비게이션

### 2.2 비주얼 디자인 시스템

**컬러 토큰** (`electron/src/renderer/styles/globals.css:6-30`):

```css
/* Dark Mode (기본) */
--ds-bg:      #0f1117;   /* 진한 블루-그레이 배경 */
--ds-surface: #1a1d27;   /* 약간 밝은 표면 */
--ds-border:  #2a2d3a;   /* 구분선 */
--ds-text:    #e4e4e7;   /* 오프-화이트 본문 */
--ds-muted:   #71717a;   /* 2차 텍스트 */
--ds-accent:  #6366f1;   /* 인디고 (1차 액션) */
--ds-success: #22c55e;   /* 그린 */
--ds-warning: #f59e0b;   /* 앰버 */
--ds-error:   #ef4444;   /* 레드 */

/* Light Mode */
--ds-bg:      #f8f9fa;
--ds-surface: #ffffff;
--ds-text:    #1a1d27;
--ds-accent:  #4f46e5;   /* 짙은 인디고 */
```

**타이포그래피**:
- 본문: System stack `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- 코드/Mono: `JetBrains Mono`, `Fira Code` fallback
- 마크다운 prose: `react-markdown` + `one-dark` 신택스 하이라이팅

**테마 전환**: Tailwind `darkMode: 'class'` — `:root.dark` 클래스 토글

### 2.3 Chat Message 렌더링

`ChatMessage.tsx` (18-120 LOC):

| 요소 | 세부 |
|------|------|
| **아바타** | User: 인디고 배경 / Bot: 그린 배경, 7×7 px, `rounded-md` |
| **라벨** | "You" vs "DS Agent" (muted 색상) |
| **본문** | `react-markdown` + GFM: 테이블, 인라인 코드 (`ds-surface` 배경), 링크 (accent 컬러) |
| **코드 블록** | 언어 자동 감지 + `one-dark` 신택스 하이라이팅 |
| **이미지** | 백엔드 `/api/plots/:filename` 동적 URL 구성 |
| **스트리밍** | `isStreaming` prop → 마지막 메시지에만 애니메이션 |

### 2.4 Tool Activity 시각화

`ToolActivity.tsx` (12-49 LOC) — 실행 중/완료 도구를 컴팩트 리스트로 표시:

```
┌─────────────────────────────────┐
│ Tool Activity                    │
│   ⟳ read_csv                     │ (Loader2 회전, accent)
│   ✓ analyze_data       0.5s       │ (CheckCircle2, success)
│   ✗ plot_results                  │ (XCircle, error)
└─────────────────────────────────┘
```

- 아이콘: Lucide `Loader2` (회전) / `CheckCircle2` / `XCircle`
- 사이즈: `text-xs` 타이트 레이아웃
- 시간: 완료된 도구에 ms 단위 표시
- 기본 접힘 (collapsed) — 데이터 과학 워크플로우에서 40+ 도구 호출이 화면을 점유하지 않도록 설계

> 내부 도구 카테고리는 [ARCH §6.2](./SYSTEM_ARCHITECTURE_AND_FEATURES.md#62-도구-카테고리) 참조.

### 2.5 ChatInput 컴포넌트

`ChatInput.tsx` (16-100+ LOC):

- 확장형 textarea: `max-height: 200px` + 스크롤바
- 연결 시 auto-focus
- 온보딩에서 선택한 **starter prompt** 자동 채움
- **Send 버튼** (Send 아이콘) ↔ **Abort 버튼** (StopCircle, 스트리밍 중)
- 미연결 상태: disabled + muted 스타일
- 스트리밍 상태: accent 테두리 강조

### 2.6 Settings & Configuration

`SettingsPanel.tsx`:
- Model selection (그룹화: OAuth / Free / API / Local)
- Quality preset (`SimpleQualityPreset` enum)
- Execution mode switcher (auto / supervised / step-by-step)
- Cost governance (budget caps)
- Provider 인증 상태 (OAuth 연결/해제)
- Advanced admin console: `ConnectorWizard`, `PolicyStudio`, `SkillManager`

### 2.7 Keyboard Shortcuts

`App.tsx:114-143` — 전역 리스너:

| Shortcut | 동작 |
|----------|------|
| `Ctrl + ,` | 설정 패널 토글 |
| `Ctrl + M` | 실행 모드 순환 (auto → supervised → step-by-step) |
| `Escape` | 열린 패널 닫기 |
| `Enter` (input) | 메시지 전송 |
| `Ctrl/Cmd + Enter` | 강제 전송 |
| `Shift + Enter` | 줄바꿈 (textarea) |

### 2.8 Splash & 연결 상태

- **SplashScreen**: Bot 아이콘 애니메이션 + 진행 상태 ("Starting backend...")
- **ErrorBoundary**: 앱 전체 graceful 오류 표시
- **DisconnectOverlay**: 연결 후 끊김 시에만 등장, `role="alertdialog"` + 재시도 버튼

### 2.9 오류 처리 & 오버레이

**Sandbox UI (P0-01 Phase 3)**:

| 컴포넌트 | 역할 | 상호작용 |
|----------|------|---------|
| `SandboxApprovalModal` | 보안 위반 코드 승인 요청 | `Esc` 거부, textarea로 거부 사유 입력 |
| `SandboxViolationToast` | 위반 알림 | 8s TTL, 최대 3개 동시 표시 |
| `UpdateNotification` | 자동 업데이트 배너 (P1-14 pending) | `role="status"`, `aria-live="polite"` |

> 내부 보안 메커니즘은 [ARCH §10.5 Code Execution Security](./SYSTEM_ARCHITECTURE_AND_FEATURES.md#105-code-execution-security) 참조.

### 2.10 접근성 (WCAG 2.1 AA 목표)

**ARIA 속성**:
- `role="textbox"` + `aria-label="Chat message input"` on ChatInput
- `role="main"` on DiagnosticPanel
- `role="alertdialog"`, `aria-modal="true"`, `aria-labelledby`, `aria-describedby` on 모달
- `role="status"` + `aria-live="polite"` on UpdateNotification

**키보드 네비게이션**: Tab 순서 보존, 모든 버튼 접근 가능, textarea auto-focus

**컬러 콘트라스트**: 다크/라이트 페어 WCAG AA 준수

**갭**:
- 일부 `<div>` 컨테이너의 역할 속성 부재
- 컬러 전용 상태 표시자 (일부 텍스트 라벨 추가 권장)

---

## 3. CLI UX

### 3.1 엔트리 & 시각적 계층

`main.py` (44-79 LOC):
- **배너**: 시안 테두리 Panel — 모드 아이콘 + 모델명 + 누적 비용
- **Muted 상태 라인**: 모드 + 프로젝트 ID + cost
- **Secret 경고**: keyring 실패 시 노란색 "⚠ Secrets in volatile storage" → [ARCH §10.1](./SYSTEM_ARCHITECTURE_AND_FEATURES.md#101-credential-handling--infrastructuresecretssecret_storagepy)

### 3.2 테마 (`cli/theme.py`)

```
[status.mode.auto]auto[/]              (bold green)
[status.mode.supervised]supervised[/]  (bold yellow)
[status.mode.step]step-by-step[/]      (bold cyan)
[tool.name]tool_name[/]                (bold yellow)
[tool.done] / [tool.error]             (green / red)
```

### 3.3 Slash Commands (`cli/commands.py:12-31`)

```
/help           → Command reference
/mode           → Switch execution mode
/status         → Project metrics
/files          → List artifacts
/model <name>   → Change LLM
/budget         → Cost breakdown
/contract       → Show task contract
/certification  → Mission status
/verdict        → Verifier output
/history        → Last 10 messages
/clear          → Clear screen
/quit           → Exit
```

**REPL 스타일**: `> ` 프롬프트, Rich Markdown 렌더러가 테이블/리스트/코드 블록 렌더링.

### 3.4 스트리밍 & 진행 표시

- Tool 실행: Rich Panel 실시간 로깅
- 상태 메시지: 이모지 + 텍스트 (Korean-friendly)
- 응답: Markdown → Rich Markdown 객체

### 3.5 Delivery Presenter 출력 (`presentation/delivery_presenters.py`)

```
Delivery Build
─────────────────────────────────
Status: SUCCESS | Artifacts: 3 | Version: v2.1
Path: workspace/deliveries/2026-04-18/
```

---

## 4. Telegram Bot UX

### 4.1 Capability

`ChannelCapabilities` (`plugin.py:56-65`):

```python
threads=True           # Telegram topics
media=True             # 첨부
markdown=True          # 포맷팅
reactions=True         # 리액션
max_message_length=4096
streaming=False        # 실시간 스트리밍 미지원
```

### 4.2 메시지 처리

**Inbound** (`plugin.py:121-143`):
- Text + command 핸들러
- User whitelist (`allow_from` 리스트)
- Async 큐 기반
- `message_thread_id`로 대화 격리

**Outbound** (폴링 기반):
- Markdown 렌더링
- InlineKeyboard (CallbackQueryHandler)
- 재시도 로직 (`_MAX_SEND_RETRIES = 3`)
- Batch 전송 + rate limiting

### 4.3 장시간 태스크 피드백

- Approval 인라인 키보드 버튼
- 구조화 JSON payload를 메시지 metadata에 첨부
- Workspace 경로 검증 → 파일 참조 안전성

---

## 5. Information Architecture

### 5.1 결과 표시 패턴

| 콘텐츠 유형 | 렌더링 방식 |
|------------|-----------|
| 텍스트 답변 | Markdown (GFM) |
| 플롯/차트 | 백엔드 `/api/plots/:filename` PNG → `<img>` |
| 테이블 | HTML 테이블 + `prose-table:text-ds-text` Tailwind 스타일 |
| 코드 | Fenced block + 언어별 하이라이팅 |
| 에러 | 인라인 빨간 텍스트 + ToolActivity 에러 아이콘 |

### 5.2 오류 메시지 & 복구

**UI 패턴**:
- **인라인 에러**: 채팅 내 빨간 텍스트
- **모달 에러**: `ErrorBoundary`가 catch + graceful 렌더
- **연결 에러**: `DisconnectOverlay` + reason + 재시도
- **Fallback 알림**: 노란 배너, 5분 TTL — "Switched to a backup model for this session" → [ARCH §4.5 Provider Router](./SYSTEM_ARCHITECTURE_AND_FEATURES.md#45-provider-router--src_ds_agent_providers_routerpy)

**재시도**: 수동 재시도 버튼 + splash에서 배경 자동 재연결

### 5.3 Tool Call 시각화

- **기본**: `ToolActivity` 섹션에 접힌(collapsed) 컴팩트 리스트
- **확장**: 도구 이름 클릭 시 세부 (future enhancement)
- **진행**: 실시간 상태 업데이트 (running → done/error)

---

## 6. 접근성 & 국제화 (i18n)

### 6.1 언어 지원 (LLM Layer)

`prompt_builder.py` (1-219 LOC) — 시스템 프롬프트에 언어 지시문 주입:

| Code | 언어 | 시스템 프롬프트 |
|------|------|----------------|
| `ko` | 한국어 | "모든 사용자 응답은 한국어로 작성하세요..." (코드=영어, 설명=한국어) |
| `en` | English | "Respond to the user in English." |
| `ja` | 日本語 | "ユーザーへの応答はすべて日本語で..." |

**흐름**: 온보딩 위저드 → `agent_factory.create_agent(language=…)` → `PromptBuilder` 주입 → LLM이 응답 언어 준수.

### 6.2 UI 텍스트 i18n 상태

- **Electron 앱**: 현재 영어만. `i18next`/`react-intl` 미도입
- **CLI**: 영어 메시지 + Rich 포맷
- **Telegram**: Python-side 포맷 (영어)
- **향후 과제**: 버튼 라벨, 모달 제목, help 텍스트 번역

### 6.3 키보드 접근성

| 기능 | 상태 |
|------|------|
| Tab 순서 | ✅ 전체 키보드 네비게이션 |
| Shortcut 매핑 | ✅ `Ctrl+M`, `Ctrl+,`, `Esc`, `Enter`, `Ctrl+Enter` |
| Textarea auto-focus | ✅ 연결 완료 시 |
| 모든 버튼 Tab 도달 | ✅ |

### 6.4 ARIA 커버리지

| 포함됨 | 부족 |
|--------|------|
| 모달 (`aria-modal`, `aria-labelledby`, `aria-describedby`) | Generic `<div>` 컨테이너 역할 누락 |
| 알림 영역 (`aria-live="polite"`) | 일부 컬러-전용 상태 표시자 |
| 입력 필드 (`aria-label`) | - |
| 상태 인디케이터 (`role="status"`) | - |

---

## 7. 에셋 & 스타일링 인프라

### 7.1 CSS 아키텍처

**Tailwind 설정** (`electron/tailwind.config.js`):
- Content: `src/renderer/**/*.{ts,tsx,html}`
- Dark mode: `class` 기반 (`:root.dark`)
- Custom colors: 9개 CSS 변수 (`ds-*`)
- 글꼴: JetBrains Mono (code 우선)

**Global Styles** (`styles/globals.css`):
- CSS 변수 (light/dark)
- 스크롤바 커스텀 (thin, ds-* 컬러)
- 마크다운 prose 코드 블록 오버라이드
- 커서 blink `@keyframes`

**커스텀 컴포넌트 라이브러리 없음** — 순수 Tailwind utility.

### 7.2 아이콘 시스템

- **라이브러리**: Lucide React 0.460.0
- **사용된 아이콘**: 40+ (Bot, User, Loader2, CheckCircle2, XCircle, Send, StopCircle, BarChart3, Settings, FolderOpen, Globe, Key, Monitor 등)
- **크기 계층**: 12px (tool activity) / 16px (아바타) / 32px+ (splash)
- **컬러 바인딩**: `text-ds-accent`, `text-ds-success` Tailwind 클래스

### 7.3 이미지 에셋

| 위치 | 용도 |
|------|------|
| `electron/resources/` | 앱 아이콘, tray 아이콘 |
| `assets/` | 프로젝트 수준 자원 (브랜드, 스크린샷) |
| Backend-served | `/api/plots/:filename` 동적 PNG (matplotlib/seaborn 결과) |

---

## 8. UX 플로우 & 인터랙션 패턴

### 8.1 온보딩 플로우

`OnboardingWizard.tsx` (1-100+ LOC) — 4단계 마법사:

1. **Welcome**: 브랜드 소개 + 기능 개요
2. **Use Case 선택**: 6개 카드 (Data Analysis / Reporting / Prediction / Dashboard / SQL / General)
3. **연결 방식 선택**: OAuth vs API Key vs Local/Free
4. **인증 구성**: API 토큰 입력 또는 OAuth 리다이렉트
5. **Done**: 확인 화면

**Model Group**: `oauth`, `free_api_key`, `api_key`, `local` — 접근 방식별 분류
**그룹 아이콘**: `Globe` (OAuth) / `Key` (API) / `Monitor` (Local)

**플로우 완료 후**: Starter prompt 자동 채움 → ChatInput에 대기

> 내부 OAuth 플로우 상세는 [ARCH §10.2 OAuth Flows](./SYSTEM_ARCHITECTURE_AND_FEATURES.md#102-oauth-flows) 참조.

### 8.2 모델 선택 UX

- **온보딩 단계**: `GroupedModelList` (OAuth / Free / Paid / Local 탭)
- **런타임**: 사이드바의 `ModelSelector`
  - 그룹별 드롭다운
  - 인증 방식 아이콘 (Globe/Key/Monitor)
  - 현재 모델 하이라이트
  - 미인증 시 "OAuth 연결" 링크

> 3-way LLM 모델 구조는 [ARCH §5](./SYSTEM_ARCHITECTURE_AND_FEATURES.md#5-llm-provider-architecture-3-way-model) 참조.

### 8.3 채팅 플로우

**User → Agent → Tool → Result** 흐름:

1. 사용자 `ChatInput`에 입력 (`Enter` 또는 `Ctrl+Enter`)
2. 메시지가 `ChatStore`에 append
3. WebSocket 전송 (`useChat` hook) — [ARCH §4.4](./SYSTEM_ARCHITECTURE_AND_FEATURES.md#44-api-gateway--src_ds_agent_api)
4. 백엔드 처리, tool call 이벤트 전송
5. `ToolActivity` 실시간 업데이트 (running → done)
6. Assistant 응답 스트리밍 + Markdown 렌더
7. 이미지/테이블 인라인 표시
8. 최하단 자동 스크롤

**중단**: `StopCircle` 버튼 → abort 신호 → 스트리밍 취소

### 8.4 오류 복구

**연결 끊김**:
- `DisconnectOverlay` 등장 (이전 메시지가 있을 때만)
- 끊김 사유 표시 (timeout/network error)
- 재시도 버튼 + splash 자동 재연결

**Provider Fallback**:
- 노란 배너, 5분 TTL
- "Switched to a backup model for this session"
- Fallback 사유 표시 + 사용자가 설정에서 변경 가능

> Fallback 메커니즘은 [ARCH §4.5](./SYSTEM_ARCHITECTURE_AND_FEATURES.md#45-provider-router--src_ds_agent_providers_routerpy) 참조.

### 8.5 Execution Mode 전환

| 모드 | 컬러 | 동작 |
|------|------|------|
| `auto` | 초록 | 모든 도구 자율 실행 |
| `supervised` | 노랑 | 일부 위험 도구만 승인 요청 |
| `step-by-step` | 시안 | 모든 도구 호출 사전 승인 |

사이드바 헤더의 mode pill + `Ctrl+M`로 순환 전환.

---

## 9. 디자인 언어 & 원칙

### 9.1 핵심 원칙 (Implicit Design Principles)

| 원칙 | 구현 |
|------|------|
| **미니멀리즘** | 그라데이션/3D 효과 無, 평면 디자인 + 서브틀 보더 |
| **Dark-First** | 기본 다크 테마 (데이터 과학 장시간 작업 눈부심 감소) |
| **투명성 & 상태** | ToolActivity 상시 노출, 세션 ID/비용 영구 표시 |
| **효율성** | 키보드 우선 (슬래시 커맨드, shortcut), 7-탭 사이드바 |
| **데이터 중심** | Chat이 뷰포트 지배, 플롯/테이블 인라인, 코드 하이라이팅 |

### 9.2 인터랙션 패턴

- **Modeless dialog**: Settings, Onboarding은 전체 화면 (플로팅 팝업 아님)
- **패널 > 팝오버**: Sidebar 탭이 패널 공개, 드롭다운 최소화
- **실시간 피드백**: 스트리밍 메시지, 라이브 ToolActivity
- **Progressive disclosure**: `RunDetailDrawer` 등 우측 서랍에 상세 정보
- **Admin Console**: 고급 설정은 2차 레벨에 (`ConnectorWizard`, `PolicyStudio`, `SkillManager`)

### 9.3 컴포넌트 구조 패턴

- **프레젠테이션 컴포넌트**: `ChatMessage`, `ToolActivity`, `Sidebar`
- **컨테이너 컴포넌트**: `MainPanel`, `App` (WebSocket 연결/상태 조율)
- **Zustand 스토어**: `ChatStore` (메시지), `ConfigStore` (설정), `ConnectionStore` (연결 상태)
- **Hooks**: `useChat`, `useConnection`, `getBackendBase`

---

## 10. 디자인 품질 평가

### 10.1 강점

- ✅ 통일된 컬러 시스템 (9개 변수 기반 토큰)
- ✅ ARIA/키보드 기반 접근성 토대
- ✅ 멀티-모달 UX (데스크탑 + CLI + Telegram)
- ✅ 한국어/일본어 LLM-layer 지원
- ✅ 실시간 피드백 (스트리밍, Tool Activity)
- ✅ 반응형 flex 레이아웃
- ✅ 다크/라이트 테마
- ✅ ErrorBoundary + graceful degradation

### 10.2 개선 여지

- ❌ UI 텍스트 i18n 미도입 (영어 전용)
- ⚠ 커스텀 컴포넌트 라이브러리 부재 (raw Tailwind 전면 사용)
- ⚠ Sidebar collapse 미구현
- ⚠ Drag-and-drop 파일 업로드 미지원 (버튼 기반)
- ⚠ 모바일 반응형 미고려 (Electron 데스크탑 전용)
- ⚠ Tooltip/도움말 최소
- ⚠ 일부 컬러-전용 상태 표시자 (텍스트 라벨 보강 필요)

---

## 11. 컴포넌트 인벤토리 요약

### Electron 주요 컴포넌트

| 카테고리 | 컴포넌트 |
|---------|---------|
| **루트 & 레이아웃** | `App`, `MainPanel`, `Sidebar`, `StatusBar`, `RunDetailDrawer` |
| **채팅** | `ChatPanel`, `ChatMessage`, `ChatInput`, `ToolActivity` |
| **온보딩** | `OnboardingWizard`, `GroupedModelList` |
| **설정** | `SettingsPanel`, `ModelSelector`, `ConnectorWizard`, `PolicyStudio`, `SkillManager` |
| **오류/상태** | `ErrorBoundary`, `SplashScreen`, `DisconnectOverlay`, `UpdateNotification` |
| **샌드박스** | `SandboxApprovalModal`, `SandboxViolationToast` |
| **사이드바 탭** | `FilesPanel`, `WorkflowPanel`, `ReviewPanel`, `RuntimePanel`, `ExperimentsPanel`, `PortfolioPanel`, `LearningPanel` |
| **고급** | `DiagnosticPanel`, `PolicyStudioPanel`, `DeliveryPreviewPanel` |

---

## 12. 관련 문서 (Related Documents)

### 12.1 내부 참조

- [시스템 아키텍처 & 주요 기능](./SYSTEM_ARCHITECTURE_AND_FEATURES.md) — **본 문서와 쌍으로 작성된 파트너 문서**
- [DS Agent 종합 보고서 (2026-04-16)](./DS_AGENT_COMPREHENSIVE_REPORT_2026-04-16.md)
- [2026-04-17 Addendum](./DS_AGENT_COMPREHENSIVE_REPORT_2026-04-17_ADDENDUM.md)

### 12.2 관련 Electron 테스트 & 계약

- E2E Smoke: `electron/tests/smoke/{diagnostic-window, happy-path, autonomy-control-plane, task-contract-*, decision-os-review, workflow-integration}.spec.ts`
- Contract: `delivery-preview`, `mission-brief`, `policy-studio`, `work-objects`, `verifier-quality-panel`, `regression-board`, `semantic-metric-panel`, `project-control-tower`, `learning-inbox`

### 12.3 Epic 완료 로그

- `qa_run_2026-04-17/S21_gemini_cli_oauth/CHANGELOG.md` — OAuth 연결 온보딩 UX 복구 경로
- `Docs/plans/PLAN_llm_oauth_and_ml_execution_2026-04-18.md` — 8-Phase Epic 완료 보고

---

## 13. 요약

**DS Agent**는 **React 기반 Electron 데스크탑 앱**을 주요 인터페이스로 하는 정교한 멀티-서피스 UX를 제공합니다. 디자인은 **데이터 과학자 워크플로우**에 집중하여, 실시간 도구 시각화(`ToolActivity`), 마크다운 채팅, 그리고 7개 운영 탭(Files / Workflow / Review / Runtime / Experiments / Portfolio / Learning)이 있는 사이드바를 통해 구현되었습니다.

핵심 인프라는 **9개 CSS 변수 기반 Tailwind 테마**, **Lucide React 아이콘**, **Zustand + React Hooks 상태 관리**로 견고하고 유지보수 가능한 기반을 제공합니다. **접근성**은 잘 고려되어 있으며(ARIA, 키보드 단축키, 컬러 콘트라스트), **국제화**는 LLM 수준(한국어/일본어 시스템 프롬프트)에서 구현되어 있지만 UI 텍스트 번역은 향후 과제입니다.

**CLI**와 **Telegram** 서피스는 터미널과 모바일 워크플로우로 플랫폼을 확장하며, 각각 입출력 제약에 맞춘 UX 패턴(Rich 패널, 인라인 버튼)을 갖추고 있습니다.

디자인 언어는 **미니멀리즘, 효율성, 투명성**을 우선시하며 — 이는 장식보다 명확성을, 마우스보다 키보드 효율을 중시하는 데이터 과학자 대상 사용자층을 반영합니다.

---

*본 문서는 `SYSTEM_ARCHITECTURE_AND_FEATURES.md`와 상호 참조되어 작성되었습니다. 시스템 내부 설계/아키텍처의 상세한 내용은 해당 문서를 참조하십시오.*
