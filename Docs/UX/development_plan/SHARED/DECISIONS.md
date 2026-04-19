# DECISIONS — 의사결정 로그 (ADR)

PLAN에 명시되지 않았으나 구현 중 발생한 결정을 ADR(Architecture Decision Record) 형식으로 기록한다.

**규칙**:
- 추가만 (수정 시 새 ADR로 supersede)
- ID는 `ADR-NNNN` 순번
- 모든 agent가 작업 시작 전 본 문서 전체 확인
- 기존 ADR 위반은 PR reject

---

## ADR 템플릿

```markdown
## ADR-NNNN: <한 줄 결정 요약>

**일자**: YYYY-MM-DD
**상태**: Proposed | Accepted | Superseded by ADR-MMMM | Deprecated
**제안자**: <agent ID 또는 leader>
**관련 PLAN**: <plan path>

### 컨텍스트
무엇이 결정을 필요하게 만들었는가.

### 결정
무엇을 결정했는가.

### 근거
왜 이 결정이 다른 옵션보다 나은가.

### 대안 (검토했으나 기각)
- Option A: ... (기각 사유)
- Option B: ... (기각 사유)

### 결과 / 영향
- 어떤 PLAN/파일에 영향
- 마이그레이션 필요 여부
```

---

## 결정 등록부

### ADR-0001: PLAN 디렉토리 구조 = phase × cross_cutting × overview × SHARED

**일자**: 2026-04-19
**상태**: Accepted
**제안자**: leader
**관련 PLAN**: 전체

#### 컨텍스트
24개 PLAN을 어떻게 디렉토리로 조직할지 결정 필요.

#### 결정
- `00_overview/` — 공통 사항
- `phase{1-4}_<name>/` — phase별 디렉토리
- `cross_cutting/` — 횡단
- `SHARED/` — agent 협업 자산

#### 근거
- Phase 단위가 시간 축으로 자연스러움
- Cross-cutting을 phase에 끼우면 의존성 표현 어려움
- SHARED를 별도 분리하여 협업 자산을 명확히

#### 대안
- 도메인별 (Mission/Run/Artifact/...) 묶기 — 시간 축 사라짐, 진입 어려움
- 단일 flat — 24개 파일 navigation 어려움

#### 결과
모든 PLAN이 본 구조 기반으로 작성됨.

---

### ADR-0002: 모든 PLAN은 RED → GREEN → REFACTOR 순서로 sub-phase 구성

**일자**: 2026-04-19
**상태**: Accepted
**제안자**: leader
**관련 PLAN**: 전체

#### 컨텍스트
TDD를 강제할지, 권장 수준으로 둘지 결정.

#### 결정
강제. 각 sub-phase의 §7 task는 반드시 RED → GREEN → REFACTOR.

#### 근거
- CLAUDE.md 가 TDD 강제 명시
- AI agent가 테스트 없이 구현하면 회귀 검증 어려움
- 백엔드가 762/762 baseline — UI도 동등 수준 필요

#### 대안
- Sketch first, then test — 거부: AI agent의 over-engineering 위험
- Test optional — 거부: 일관성 없음

#### 결과
모든 sub-phase에 RED/GREEN/REFACTOR 명시.

---

### ADR-0003: i18n 라이브러리는 i18next + react-i18next

**일자**: 2026-04-19
**상태**: Accepted
**제안자**: leader (Phase 1 PLAN_01 작성 시)
**관련 PLAN**: phase1/PLAN_01

#### 컨텍스트
i18n 라이브러리 선택.

#### 결정
`i18next` + `react-i18next` + `i18next-browser-languagedetector` + `i18next-parser`.

#### 근거
- Electron + React 생태계 최강 지원
- namespace 분할 → PLAN별 충돌 회피 가능
- i18next-parser 로 누락 키 자동 검출

#### 대안
- `formatjs/react-intl` — ICU MessageFormat 강력하나 namespace 분할 약함
- `lingui` — 컴파일 타임 추출 좋으나 생태계 작음

#### 결과
PLAN_01 Sub-Phase 1.1에서 도입.

---

### ADR-0004: WS 이벤트 envelope은 cross_cutting/PLAN_03에서 정의, 모든 신규 이벤트가 사용

**일자**: 2026-04-19
**상태**: Accepted
**제안자**: leader
**관련 PLAN**: cross_cutting/PLAN_03 + Phase 1+ 의 WS 이벤트 추가 PLAN 전체

#### 컨텍스트
Phase 2-3에서 신규 WS 이벤트 다수 추가 예정. backward compatibility 위험.

#### 결정
모든 WS 이벤트는 envelope wrapping (`type / version / ts / payload`). Schema는 zod로 검증.

#### 근거
- 클라이언트 버전 다양화 시 graceful 처리 필요
- 단일 이벤트 추가에 backward compatibility 깨질 위험 차단

#### 결과
cross_cutting/PLAN_03 가 baseline 인프라 제공. 모든 신규 이벤트 PLAN은 본 인프라 사용.

---

### ADR-0005: Result Card 분류 mismatch 시 "other" fallback 채택

**일자**: 2026-04-19
**상태**: Accepted
**제안자**: leader (Phase 2 PLAN_02 작성 시)
**관련 PLAN**: phase2/PLAN_02

#### 컨텍스트
LLM이 4종 카드 분류와 일치하지 않는 응답을 emit할 가능성.

#### 결정
4종 + `other` (5종)으로 확장. `other`는 markdown body 단순 표시.

#### 근거
- LLM 출력 100% 분류 강제는 unrealistic
- 사용자 응답 손실 방지

#### 대안
- LLM이 새 카드 타입 정의 가능 — 결정 보류 (Phase 3+)
- 잘못된 카드는 reject — 거부: 응답 손실

#### 결과
PLAN_02의 도메인 모델에 OtherCard 추가.

---

### ADR-0006: Clean Architecture layer enforcement = standalone Node script + ESLint config (dual)

**일자**: 2026-04-19
**상태**: Accepted
**제안자**: agent-w0-foundation-001
**관련 PLAN**: cross_cutting/PLAN_02

#### 컨텍스트
PLAN_02 Sub-Phase 1.1은 "domain은 react/zustand/axios import 금지" 를 ESLint custom rule로 enforce해야 한다. 그러나 현재 `electron/` 에는 ESLint 가 devDependency 로 설치되어 있지 않고, npm install 로 추가하면 의존 트리가 커진다 (eslint + parser + plugin 들). 또 후속 모든 wave가 본 lint 검사에 의존하므로 zero-install 로 동작 가능해야 CI 에서 빠르게 회귀 검출 가능.

#### 결정
**dual approach**:
1. **Primary (CI 차단)**: standalone Node.js script `electron/scripts/lint-arch.mjs` — 외부 의존 0, regex + import statement 파싱으로 layer rule 검사. `npm run lint:arch` 로 실행.
2. **Secondary (개발자 IDE)**: `electron/eslint.config.mjs` — `no-restricted-imports` 규칙 정의. ESLint 가 설치되면 IDE 가 즉시 빨간 줄 표시. CI 에서는 옵션 (eslint 없으면 skip).

#### 근거
- standalone script 는 Node 만으로 동작 → CI 빠름, contract-test 와 동일 패턴 (이미 `node_modules` 외 zero-dep 로 검증)
- ESLint config 는 개발자 경험 (DX) 용 — IDE 통합으로 작성 시점에 발견
- 향후 npm install eslint 추가 시 자동 활성, 추가 작업 0
- `tach` (Python 용) 또는 `dependency-cruiser` 도입은 추가 의존성 부담 → 미채택

#### 대안
- ESLint only — 거부: npm install 필요, CI 에서 캐시 미스 시 느림
- dependency-cruiser only — 거부: 동일 의존성 부담 + custom rule 작성 cost 동일
- TypeScript path mapping 으로만 강제 — 거부: 강제력 없음, 우회 가능

#### 결과 / 영향
- `electron/scripts/lint-arch.mjs` 신설 — agent-w0 가 작성
- `electron/eslint.config.mjs` 신설 — flat config 형식 (ESLint v9+)
- `electron/package.json` scripts 에 `lint:arch` 추가
- 후속 wave: 본 script 가 PR 차단 게이트로 작동 → Clean Architecture 위반 자동 검출
- sample 양/음성 fixture 로 self-test (`tests/contract/eslintArchRule.spec.ts`)

---

### ADR-0007: WS event envelope schema = inline TypeScript validator + Python dataclass (no zod/pydantic-extra)

**일자**: 2026-04-19
**상태**: Accepted
**제안자**: agent-w0-foundation-001
**관련 PLAN**: cross_cutting/PLAN_03

#### 컨텍스트
PLAN_03 §5 는 envelope 와 per-event schema 를 zod 로 검증하라고 명시. 그러나 `electron/` 에 zod 미설치. 백엔드도 별도 schema lib 도입 시 dependency 증가.

#### 결정
- TypeScript 측: 외부 lib 없이 `electron/src/renderer/infrastructure/ws/eventEnvelope.ts` 에 `parseEnvelope()` 순수 함수 — discriminated union + runtime guard 로 검증. 향후 zod 도입 시 adapter 만 교체.
- Python 측: `src/ds_agent/api/event_envelope.py` 에 dataclass + `wrap_event()` 함수. 기존 emit 경로 (`callbacks._emit`) 가 본 함수 경유.
- 양측 동일 envelope: `{type, version, ts, source?, correlationId?, payload}` (PLAN_03 §2 그대로).
- handshake: client 가 connect 시 supportedVersions 전송, server 가 selectedVersion ack. 본 단계에서는 negotiation 은 protocol 정의 + round-trip 테스트만 (사용자 안내 UI 는 후속 wave).

#### 근거
- 본 단계의 검증 핵심은 "envelope 양/음성 round-trip" 이며 schema lib 의 풍부한 API 는 over-engineering
- zod 미설치 → 도입은 후속 wave 가 필요 시 ADR 로 결정
- 양측 dataclass / TypeScript interface 가 동일 shape 이므로 새 이벤트 추가 시 양측 동기화 부담은 기존 event_schemas.py / events.ts 와 동일

#### 대안
- zod 즉시 도입 — 거부: 의존성 / 본 단계 핵심 가치 대비 과대
- Protocol Buffers / msgpack — 거부: JSON 호환성 손실
- JSON Schema + ajv — 거부: zod 와 동일 부담 + DX 떨어짐

#### 결과 / 영향
- 후속 wave 는 본 envelope 만 사용 (직접 `send_json` 금지 대신 `wrap_event()` 경유)
- minor version 변경: payload optional 필드 추가만 — 기존 consumer crash 없음
- major version 변경 (1.x → 2.0): `WsEventEnvelopeMajorMismatch` 에러 발생, handshake 단계에서 차단

---

### ADR-0008: a11y baseline = standalone axe-core script (CI 통합), focus/reducedMotion 은 framework 독립 utility

**일자**: 2026-04-19
**상태**: Accepted
**제안자**: agent-w0-foundation-001
**관련 PLAN**: cross_cutting/PLAN_01

#### 컨텍스트
PLAN_01 Sub-Phase 1.1 은 `@axe-core/playwright` 통합을, Sub-Phase 1.2 는 focus + prefers-reduced-motion utility 를 요구. 그러나 axe-core 는 미설치. focus trap 라이브러리 (focus-trap, react-focus-lock) 도입은 추가 의존.

#### 결정
- **a11y CI**: `electron/scripts/lint-a11y.mjs` 라는 placeholder 스크립트 신설 — 실제 axe-core 가 설치되면 자동 활성화 (`require('@axe-core/playwright')` 시도 후 fail-soft skip + 명확한 메시지 출력). 본 단계에서는 PR 차단 X 이지만 CI step 자리 확보. 또 contract-style spec 으로 a11y rule 메타데이터를 검증 (color contrast threshold, focus indicator 두께 등).
- **Focus utility**: `electron/src/renderer/application/a11y/focusManagement.ts` — 순수 함수. trap (`createFocusTrap(container)`), restore (`captureFocus()` / `restoreFocus(token)`), first focusable element 검색. React-independent (modal 등 컴포넌트 hook 은 후속 wave 가 wrapping).
- **Reduced motion**: `electron/src/renderer/application/a11y/reducedMotion.ts` — `prefersReducedMotion()` 함수, `subscribeReducedMotion(callback)` 함수. matchMedia 추상화. infrastructure 가 아닌 application 에 둠 (DOM 의존 있지만 외부 lib 0).

#### 근거
- 외부 lib 0 으로 즉시 동작 (focus-trap 같은 npm 패키지 의존 없음)
- axe-core 도입은 향후 npm install 시 자동 활성 → 본 단계 산출물은 placeholder + 양/음성 fixture 로 자체 검증
- focusManagement 는 순수 DOM API 만 사용 → application 레이어로 분류 가능 (domain 은 DOM도 모름)

#### 대안
- focus-trap npm install — 거부: 의존성, 100 LOC 미만으로 직접 작성 가능
- @axe-core/playwright 즉시 install — 거부: 본 worktree 에서 npm install 부담 + Playwright 도 별도 install 필요

#### 결과 / 영향
- 후속 wave 가 modal / drawer 만들 때 본 utility 가 baseline
- `tests/contract/focusManagement.spec.ts` 가 trap / restore / cycle 시나리오 검증
- npm install 후 axe-core 자동 활성: `lint-a11y.mjs` 에 detect 로직 포함

### ADR-0009: WS envelope `ts` 단위 = milliseconds since epoch (integer)

**일자**: 2026-04-19
**상태**: Accepted
**제안자**: agent-phaseA-wave0-fixes-001
**관련 PLAN**: cross_cutting/PLAN_03 + SHARED/WAVE_FINALIZATION_PLAN §3 Phase A (ID A4)

#### 컨텍스트
ADR-0007 의 envelope baseline 은 `ts: float` 만 명시했고 단위를 못 박지 않았다. 결과:
- Python `wrap_event` 가 `time.time()` (epoch seconds, float ~10^9) 을 기본으로 채움
- TypeScript `wrapEvent` 가 `Date.now()` (epoch milliseconds, integer ~10^12) 를 기본으로 채움

수신 측이 단위를 안 가정하고 정렬하면 같은 stream 안에 1000배 차이의 ts 가 섞여 정렬·집계·diff 가 깨진다 (외부 감사 finding F5).

#### 결정
**ms 단위 정수 (epoch milliseconds, JS `Date.now()` 표준) 로 통일**.

- Python `wrap_event` 의 default `ts = int(time.time() * 1000)` (이전: `time.time()`)
- TypeScript `wrapEvent` 는 이미 `Date.now()` 사용 (변경 없음)
- envelope dataclass / interface 의 `ts` 필드 type 은 그대로 (Python `float`, TS `number`) — 수신 측은 number 면 OK, default 만 ms 정수
- `parse_envelope` 의 ts 검증은 변경 없음 (수신은 number 면 OK)
- `CONVENTIONS.md §7.3` 신규 이벤트 체크리스트에 "ts 는 ms 정수" 1줄 추가

#### 근거
- **JS 표준 일치**: 브라우저 `Date.now()`, `performance.now()` 의 epoch 기반 ms 표현이 사실상 표준
- **분산 시스템 표준 일치**: Kafka, Kinesis, Pub/Sub 의 record timestamp 는 모두 ms (long integer)
- **정수 정렬 안정**: float ts 는 비교 시 부동소수점 epsilon 문제 가능 (대용량 batch 정렬에서 미세한 순서 뒤바뀜)
- **수정 범위 최소**: Python 측 1줄만 변경; TypeScript는 이미 ms

#### 대안 (검토했으나 기각)
- **Option A (TS 를 seconds 로 변경)**: 모든 frontend 코드 (Date.now() 사용처) 가 `Date.now() / 1000` 로 변경 — 광범위 회귀 + JS 관행 위반 → 기각
- **Option B (microseconds = 10^15 정수)**: ms 보다 정밀하지만 분산 시스템 표준 아님 + JSON 정수 안정성 (53-bit) 한계 접근 → 기각
- **Option C (RFC3339 string)**: 사람 가독성 좋으나 정렬 시 string 비교 비효율 + parsing 오버헤드 → 기각

#### 결과 / 영향
- `src/ds_agent/api/event_envelope.py:wrap_event` 의 default ts 변경
- `tests/unit/api/test_event_envelope.py` 에 `TestTimestampIsMilliseconds` 4 케이스 추가 (default ts 가 int 이고 >= 10^12, time window, override pass-through, round-trip 보존)
- `tests/unit/api/test_ws_callbacks_envelope.py` 의 `isinstance(frame["ts"], float)` → `isinstance(frame["ts"], int)` + window 검증
- 수신 클라이언트는 단위 변경 없음 (TS 측 default 가 이미 ms)
- 기존 Python emit 코드 중 explicit `ts=...` 를 넘기던 곳은 ms 정수로 호출하도록 후속 PR 에서 정렬 (현재 별도 emit 경로 0건)

---

### ADR-0010: a11y baseline = @axe-core/playwright dev 필수, lint:a11y exit 1 on missing, CI gate 강제

**일자**: 2026-04-19
**상태**: Accepted
**제안자**: agent-phaseB-a11y-baseline-001
**관련 PLAN**: cross_cutting/PLAN_01 — Wave 0–1 finalization Phase B

#### 컨텍스트
ADR-0008 은 `@axe-core/playwright` 미설치 환경에서 `lint-a11y.mjs` 가 SKIP + exit 0 하는 placeholder 정책을 채택했었음. 외부 감사 결과 (2026-04-19) — F4: "axe E2E assertion / CI gate 모두 미구현" 으로 baseline enforcement 가 실질적으로 비어 있었다는 지적. Wave 1+ 가 진행되면서 실측 axe scan 없는 a11y baseline 은 회귀 추적이 불가능.

#### 결정
1. `@axe-core/playwright` (4.11.2) 를 `electron/devDependencies` 에 명시. `npm ci` 환경에서 항상 install. `dependencies` 변경 0.
2. `electron/scripts/lint-a11y.mjs` 는 strict mode — axe-core 미설치 시 명확한 에러 메시지 + `exit 1` (placeholder 정책 종료).
3. E2E a11y suite 5 spec (`tests/e2e/a11y/{onboarding,mission,chat,settings,sidebar}.a11y.spec.ts`) — WCAG 2.1 A + AA 태그로 axe scan, critical/serious violation 0 강제. 각 spec 는 `playwright._electron` 기반 standalone Node 스크립트 (기존 smoke 패턴 답습).
4. `npm run test:e2e:a11y` 신규 script — build 후 5 spec 순차 실행.
5. CI gate `.github/workflows/a11y.yml` 신규 — backend binary build 후 a11y suite 실행. Phase A 의 wave0 gate 와는 별도 job 으로 격리 (병렬 실행 가능).
6. AxeBuilder 는 `setLegacyMode(true)` 호출 — Electron BrowserWindow 가 `Target.createTarget` 미지원하므로 in-context 단일 frame scan 으로 동작.
7. 기존 ADR-0008 의 framework-independent focus / reducedMotion / ariaLive utility 결정은 보존 — 본 ADR 은 axe 통합 정책만 강화.

#### 근거
- placeholder 가 baseline 의 **실질적 검증을 비움** — 회귀를 막지 못함
- 4.11.2 install 부담은 미미 (2 package, dev only) 대비 baseline 의 안정성 이득 큼
- 5 surface 가 현재 시점 거의 모든 user-facing flow 를 커버 (onboarding 첫진입 + main 작업환경 + 모달)
- Phase A (wave0 contract) 와 동일 workflow 로 묶지 않음 — 빌드 시간 (PyInstaller) 분리, 병렬 실행으로 PR 피드백 빠름
- `setLegacyMode` 는 axe-core/playwright maintainer 가 multi-process Electron 환경에 권장한 호환 모드

#### 대안 (검토했으나 기각)
- placeholder 유지 — 거부: 외부 감사 F4 그대로 (실효성 0)
- vitest-axe 같은 jsdom 기반 수단 — 거부: jsdom 의 layout 미지원으로 color-contrast / focus-visible 같은 visual rule 검증 불가
- @axe-core/playwright 즉시 install + monorepo lockfile 통합 (root package.json) — 거부: 본 프로젝트는 electron/ 가 자체 lockfile 을 가짐, root scope 변경은 본 PLAN 범위 밖
- known-violation allowlist (snapshot) 도입 — 거부: 부채 누적 위험. 발견 즉시 fix 가 baseline 의 가치
- Phase A workflow 와 단일 job 통합 — 거부: 본 job 이 PyInstaller build 까지 포함 → 30+ min, wave0 gate 의 빠른 피드백 손실

#### 결과 / 영향
- `electron/package.json` devDependencies + scripts 1개 append (`test:e2e:a11y`)
- `electron/package-lock.json` 갱신 (axe 트리)
- `electron/scripts/lint-a11y.mjs` placeholder → strict
- `electron/tsconfig.test.json` include glob 에 `tests/e2e/**/*.ts` 추가
- `electron/tests/e2e/a11y/_helpers.ts` + 5 spec 신규
- `.github/workflows/a11y.yml` 신규
- `electron/src/renderer/styles/globals.css` 의 `--ds-muted` / `--ds-accent` / `--ds-accent-hover` 토큰 dark mode + light mode 값 contrast 보강 (WCAG 1.4.3) + `button.bg-ds-accent` color override rule (light accent 위 dark text)
- `electron/src/renderer/components/settings/{PrivacySettings,CostSettings,PolicyStudio}.tsx` 에 `aria-label` 4 곳 추가 (button-name / select-name / form-label rule fix)
- 후속: minor / moderate violations 는 발견 즉시 PLAN_01 §12 에 기록, 즉시 fix 의무 없음. critical / serious 는 0 강제 (CI fail).

#### Migration note
ADR-0008 의 placeholder 정책은 본 ADR 로 superseded — `lint:a11y` 가 strict 모드. 신규 worktree / fresh clone 시 `npm ci` 후 lint:a11y 가 자동으로 4.11.2 detect 후 OK 출력.

---

### ADR-0011: i18next runtime + i18nStore shim (backward-compatible API)

**일자**: 2026-04-19
**상태**: Accepted
**제안자**: agent-phaseD-w1a-full-i18n-001
**관련 PLAN**: phase1_quick_wins/PLAN_01_i18n_introduction — Wave 0–1 finalization Phase D

#### 컨텍스트
W1-A baseline 은 `i18nStore.ts` 안에 ko/en/ja 3 locale 의 store-backed flat 사전을 보유하고 `useI18n().t(key, vars)` 인터페이스를 노출했다. 30+ consumer 가 본 인터페이스를 사용하며, ADR-0003 가 i18next + react-i18next 채택을 결정. 본 ADR 은 그 채택을 실제 구현으로 마감.

핵심 제약:
- 30+ consumer 의 `useI18n()` / `useI18n((s) => s.t)` 호출을 변경 0 으로 유지 (touch surface 최소화)
- 12 namespace × 3 locale = 36 JSON 파일을 build 시 inline import (Electron 오프라인 작동 보장)
- Phase A/B/C 가 추가한 mission/execution/llm/workspace/sidebar 키 보존
- i18next-parser 가 동적 키 (`t(variable)`) 에서 false positive 발생 → CI gate 는 별도 정책

#### 결정
1. **runtime**: `electron/src/renderer/i18n.ts` 가 `initReactI18next` 로 i18next 부트. resources 는 `public/locales/{ko,en,ja}/{12 namespaces}.json` 의 inline import. supportedLngs `['ko','en','ja']`, defaultNS `common`, fallbackLng `en`, keySeparator `.`, namespaceSeparator `:`, interpolation `{prefix:'{', suffix:'}'}`. localStorage 키는 i18next 표준 `i18nextLng` 로 통일. legacy `ds-agent-locale` 키는 1회 migration 후 보존.
2. **shim**: `i18nStore.ts` 가 Zustand store 를 제거하고 `useSyncExternalStore` 로 i18next.languageChanged 이벤트 구독. `useI18n()` 은 기존과 동일한 `{ locale, locales, setLocale, t }` 객체 반환. selector overload (`useI18n((s) => s.t)`) 도 지원하여 zustand 패턴 호출 변경 0.
3. **namespace 자동 추론**: shim 의 `t('mission.header.title')` 는 첫 dot-segment 가 등록 namespace 면 그것 사용 + segment 를 strip 후 i18next lookup. 예) `t('mission.header.title')` → `i18next.t('header.title', { ns: 'mission' })`. 모르는 prefix 는 common namespace + key 보존. 명시 `ns:key` 문법 지원.
4. **flat-key JSON 저장**: `header.title` 같은 dotted key 가 nested object 로 변환되면서 `mode.auto` (string) ↔ `mode.auto.desc` (string) 같은 prefix-conflict 가 leaf 손실을 일으킴. → 모든 namespace JSON 을 flat dict 로 저장 (`{"header.title": "..."}`) 하고 `keySeparator: '.'` 는 i18next 가 lookup 시 dotted lookup 을 정상 처리.
5. **CI gate**: `npm run lint:i18n:ci` (`scripts/lint-i18n.mjs`) 가 (a) ko/en/ja 키 set 동일 (b) renderer/components, renderer/hooks 안에 Hangul 문자열 literal 0 두 가지를 검증 + exit 1. i18next-parser 자체는 미사용 (variable 키 false positive 회피).
6. **Tailwind/CSS**: `tailwind.config.js` fontFamily.sans 에 Inter / Noto Sans KR / Noto Sans JP 추가. `globals.css` body font chain 에 동일 + system fallback (Apple SD Gothic Neo, Hiragino Sans 등) 추가. 오프라인 환경 (Electron) 이라 Google Fonts 미import — 시스템 fallback 의존. ko/ja 별 line-height + word-break 토큰 추가.

#### 근거
- Hand-off 호환성 최우선 → shim 패턴 (consumer 코드 0 변경) 가 Big-bang migration 보다 안전. 후속 wave 가 순차적으로 react-i18next 의 `useTranslation('namespace')` 직접 사용으로 전환 가능
- flat-key JSON: nested 형태는 prefix-conflict 시 데이터 손실. flat 은 항상 안전 + i18next 의 dotted lookup 동작과 호환
- inline import: Electron renderer 는 file:// scheme 으로 동작 → fetch backend 가 깨질 수 있어 build-time bundling 이 안정적. resources-to-backend 등 lazy 로더는 dev 환경에서만 가치 있어 본 단계에서는 미적용
- CI gate 가 i18next-parser 대신 custom script: parser 는 dynamic key 를 detect 못해 false positive 가 빈번. 핵심 가치 (locale parity + Hangul literal 0) 는 100 LOC custom 로 충족
- system font fallback: Noto Sans KR/JP 는 macOS 12+ / Windows 11+ 에 기본 install. self-host 는 ~10 MB 추가 — 본 단계에서는 deferred. Phase 2 PLAN_05 onboarding 재설계 에서 brand font 와 함께 결정

#### 대안 (검토했으나 기각)
- **Option A (i18next-resources-to-backend lazy load)**: HTTP fetch 기반 로딩 — Electron file:// scheme 에서 fetch fail 위험 + 네트워크 부재 시 first paint 깨짐 → 기각
- **Option B (Big-bang migration: 모든 consumer 가 useTranslation 직접 사용)**: 30+ 파일 touch + Phase D 단독 worktree 의 충돌 표면 광역 → 기각. 후속 wave 에서 순차 migration
- **Option C (formatjs/react-intl)**: ICU plural 강력 — Phase 1 scope 에 plural 미포함 + ADR-0003 결정 supersede 비용 큼 → 기각
- **Option D (i18next-parser CI gate enforce strict)**: dynamic key false positive 다수 — 본 단계의 baseline 50+ key 는 정적, 후속 wave 가 dynamic key 추가 시 parser fail 빈번 → 기각, custom script 가 선언적 검증 표면 더 작음
- **Option E (Google Fonts CDN import)**: 오프라인 부팅 시 깨짐 + Electron CSP 로 차단 가능 → 기각, system fallback 우선. self-host 는 차후 결정

#### 결과 / 영향
- `electron/package.json` dependencies: `i18next@^23.16.8`, `react-i18next@^14.1.3`, `i18next-resources-to-backend@^1.2.1` (현재 미사용, 차후 lazy load 옵션 위해 보존). devDependencies: `i18next-parser@^9.4.0` (script 직접 호출용, CI 미사용).
- `electron/src/renderer/i18n.ts` 신규 (~170 LOC) — bootstrap + locale detection + document.lang sync.
- `electron/src/renderer/stores/i18nStore.ts` rewrite (~150 LOC, 기존 ~1650 LOC 의 1/10) — i18next shim, useI18n / useI18n(selector) overload 지원.
- `electron/public/locales/{ko,en,ja}/{12 namespaces}.json` 신규 (총 36 파일, 각 ko/en/ja 동일 key set).
- `electron/scripts/{split-i18n-namespaces,strip-namespace-prefix,merge-phase-c-mission-keys}.mjs` 신규 (one-shot migration tools, 후속 wave 에서 재사용 가능).
- `electron/scripts/lint-i18n.mjs` 신규 — namespace parity + Hangul literal CI gate.
- `electron/i18next-parser.config.cjs` 신규 — i18next-parser 설정 (수동 실행 시 사용).
- `electron/tailwind.config.js` — fontFamily.sans extend.
- `electron/src/renderer/styles/globals.css` — body font chain 갱신 + ko/ja line-height tokens.
- `electron/tests/contract/{i18nNamespaces,i18nStoreShim}.spec.ts` 신규 (10 + 13 = 23 cases).
- `electron/main.tsx` — `import './i18n'` 1줄 append.
- `.github/workflows/i18n.yml` 신규 — Windows runner, npm ci → lint:i18n:ci → 2 contract specs.
- `electron/src/renderer/components/semantic/MetricSourcePanel.tsx` — Hangul literal 2 건 i18n key 로 치환 (cards.metricSource.*).
- `cards` namespace 가 placeholder → 4 keys (metricSource.*) 채워짐. approval/trust/chat 은 placeholder 유지 (후속 wave 작업 영역).

#### Migration note
ADR-0003 의 i18next 채택 결정이 본 ADR 로 구체화. 이후 wave 의 신규 컴포넌트는 react-i18next 의 `useTranslation(namespace)` 직접 사용 권장 (shim 은 backward compat 만 제공). 신규 namespace 추가 시 `i18n.ts` 의 `I18N_NAMESPACES` + `I18N_RESOURCES` 양쪽 갱신 + `lint-i18n.mjs` 의 NAMESPACES 배열 갱신 + JSON 36 파일 (ko/en/ja × 12 ns) 모두 추가 필요. 후속 wave 는 본 패턴 답습.

---

> 새 ADR 작성 시 일자/상태/제안자/관련 PLAN을 정확히 기록.
> 기존 ADR을 supersede할 때는 새 ADR 작성 + 기존 상태를 `Superseded by ADR-NNNN` 으로 변경.
