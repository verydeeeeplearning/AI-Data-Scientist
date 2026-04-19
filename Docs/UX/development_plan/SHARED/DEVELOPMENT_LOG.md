# DEVELOPMENT_LOG — 개발 진행 기록

모든 agent는 작업 완료 시 본 문서에 항목을 추가한다. **append-only, 시간 역순(최신 위)**.

---

## 작성 형식

```markdown
## YYYY-MM-DD HH:MM (UTC) — <agent-id> — <PLAN>

**Sub-Phase**: <ID>
**Worktree**: <path>
**소요 시간**: Xh
**상태**: completed | partial | blocked | reverted

### 변경 요약
- 1줄 요약 (≤ 80자)

### Touched Files
- `path/to/file1.ts` (created/modified/deleted)
- `path/to/file2.ts`

### 결정 (DECISIONS에 ADR로 등재된 경우 ID)
- ADR-NNNN: <짧은 요약>

### Deviation from PLAN
- (PLAN과 다르게 진행한 부분만)

### 다음 agent에게 전달
- (작업 결과를 활용할 다음 PLAN/agent에게 알릴 사항)

### 회귀 영향
- 영향 받을 수 있는 다른 PLAN/feature
```

---

## 기록 시작

### 2026-04-19 — agent-w0-foundation-001 — cross_cutting/PLAN_01 (Sub-Phase 1.1, 1.2)

**Sub-Phase**: 1.1, 1.2
**Worktree**: .claude/worktrees/agent-a1255b3f
**소요 시간**: ~1.5h
**상태**: completed

#### 변경 요약
a11y baseline: focus management + reduced-motion utility + axe placeholder + global styles

#### Touched Files
- `electron/scripts/lint-a11y.mjs` (created)
- `electron/src/renderer/application/a11y/focusManagement.ts` (created)
- `electron/src/renderer/application/a11y/reducedMotion.ts` (created)
- `electron/src/renderer/application/a11y/ariaLive.ts` (created)
- `electron/src/renderer/styles/globals.css` (modified — :focus-visible + reduced-motion @media)
- `electron/tests/contract/focusManagement.spec.ts` (created — 10 cases)
- `electron/tests/contract/reducedMotion.spec.ts` (created — 7 cases)
- `electron/package.json` (modified — lint:a11y + test:contract:focus-management, reduced-motion scripts)
- `Docs/UX/development_plan/cross_cutting/PLAN_01_accessibility.md` (modified — §8 + §9)

#### 결정 (DECISIONS)
- ADR-0008: a11y baseline = standalone axe-core script + framework-independent utilities

#### Deviation from PLAN
- @axe-core/playwright 즉시 install 미수행 (placeholder 전략) — ADR-0008 정당화
- focus-trap 라이브러리 대신 self-contained (138 LOC) 구현

#### 다음 agent에게 전달
- modal / drawer 컴포넌트 작성 시 `application/a11y/focusManagement.ts` 의 `createFocusTrap` 활용
- 애니메이션 사용 컴포넌트는 `application/a11y/reducedMotion.ts` 의 `prefersReducedMotion()` 체크 + globals.css 의 @media 가 자동 처리
- streaming 응답 등 status 메시지는 `application/a11y/ariaLive.ts` 의 `announce()` 사용
- npm install 시 axe-core 자동 활성 — `npm run lint:a11y` 가 자동으로 detect

#### 회귀 영향
- 없음 — globals.css 추가는 baseline 이며, 기존 컴포넌트에 무영향 (focus-visible 은 default browser 동작 대체)

---

### 2026-04-19 — agent-w0-foundation-001 — cross_cutting/PLAN_03 (전체)

**Sub-Phase**: 3.1, 3.2, 3.3, 3.4
**Worktree**: .claude/worktrees/agent-a1255b3f
**소요 시간**: ~2h
**상태**: completed

#### 변경 요약
WS event envelope baseline + schema registry + handshake + cross-language round-trip 검증

#### Touched Files
- `src/ds_agent/api/event_envelope.py` (created — 167 LOC)
- `src/ds_agent/api/callbacks.py` (modified — _emit envelope-versioned)
- `electron/src/renderer/infrastructure/ws/eventEnvelope.ts` (created — 105 LOC)
- `electron/src/renderer/infrastructure/ws/eventSchemaRegistry.ts` (created — 8 events pre-seeded)
- `electron/src/renderer/hooks/useWebSocket.ts` (modified — WsEvent에 version/source/correlationId 추가)
- `tests/unit/api/__init__.py` (created)
- `tests/unit/api/test_event_envelope.py` (created — 24 cases)
- `tests/unit/api/test_ws_callbacks_envelope.py` (created — 4 cases)
- `electron/tests/contract/wsEnvelope.spec.ts` (created — 10 cases)
- `electron/tests/contract/eventSchemaRegistry.spec.ts` (created — 8 cases)
- `electron/package.json` (modified — test:contract:ws-envelope, event-schema-registry, wave0 scripts)
- `Docs/UX/development_plan/SHARED/CONVENTIONS.md` (modified — §7.3 신규 이벤트 추가 체크리스트)
- `Docs/UX/development_plan/SHARED/INTEGRATION_POINTS.md` (modified — WS Event Stream 행 완료)
- `Docs/UX/development_plan/cross_cutting/PLAN_03_event_schema_versioning.md` (modified — §8 + §9)

#### 결정 (DECISIONS)
- ADR-0007: WS envelope = lightweight TS/Python 1:1 wire-compat, no zod/pydantic-extra

#### Deviation from PLAN
- zod 미도입 (placeholder, 후속 wave 가 필요 시 ADR 으로 결정)
- Negotiation 의 사용자 안내 UI 미구현 (server-side 헬퍼만, UI 는 후속 wave)

#### 다음 agent에게 전달
- 신규 WS 이벤트는 모두 `WsAgentCallbacks._emit()` 경유 — 자동 envelope 부착
- TypeScript 측: `infrastructure/ws/eventSchemaRegistry.ts` 에 `registerEventSchema(...)` 호출 필수
- 신규 event 추가 시 SHARED/CONVENTIONS.md §7.3 체크리스트 따름
- Phase 1 PLAN_02 (Mission Header), Phase 2 PLAN_02 (Cards), Phase 3 PLAN_01 (Plan Tree) 의 신규 이벤트는 본 envelope 인프라 위에 구현

#### 회귀 영향
- 없음 — 기존 frame 의 superset (optional 필드만 추가). 기존 renderer 의 `WsEvent` interface 가 graceful 처리

---

### 2026-04-19 — agent-w0-foundation-001 — cross_cutting/PLAN_02 (Sub-Phase 1.1, 1.2)

**Sub-Phase**: 1.1, 1.2
**Worktree**: .claude/worktrees/agent-a1255b3f
**소요 시간**: ~1.5h
**상태**: completed

#### 변경 요약
Clean Architecture layer 구조 신설 + standalone lint script + agentStore → executionStore 분할

#### Touched Files
- `electron/src/renderer/domain/` (created — README.md + execution/executionState.ts)
- `electron/src/renderer/application/` (created — README.md + a11y/* in PLAN_01)
- `electron/src/renderer/infrastructure/` (created — README.md + ws/* in PLAN_03)
- `electron/scripts/lintArchCore.cjs` (created — 134 LOC)
- `electron/scripts/lint-arch.mjs` (created — CLI wrapper)
- `electron/eslint.config.mjs` (created — flat config, future-activation)
- `electron/src/renderer/stores/executionStore.ts` (created — Zustand wrapper)
- `electron/src/renderer/stores/agentStore.ts` (modified — backward-compat shim)
- `electron/tests/contract/eslintArchRule.spec.ts` (created — 14 cases)
- `electron/tests/contract/executionStore.spec.ts` (created — 7 cases)
- `electron/tsconfig.contract-test.json` (modified — include domain/application/infrastructure paths)
- `electron/package.json` (modified — lint:arch + test:contract:eslint-arch-rule, execution-store scripts)
- `Docs/UX/development_plan/SHARED/INTEGRATION_POINTS.md` (modified — agentStore 행 완료)
- `Docs/UX/development_plan/cross_cutting/PLAN_02_state_management_refactor.md` (modified — §8 + §9)

#### 결정 (DECISIONS)
- ADR-0006: Clean Architecture layer enforcement = standalone Node script + ESLint config (dual)

#### Deviation from PLAN
- agentStore (52 LOC) 가 chat/run/execution 3분할이 아닌, 실제로는 execution 만 담당이므로 1-rename + reducer 추출 1step (chat/run 은 chatStore/runtimeStore 가 이미 존재). PLAN §4 Sub-Phase 1.2 의도와 본질 동일
- ESLint 즉시 install 미수행 (standalone script 가 primary CI 게이트)

#### 다음 agent에게 전달
- 모든 신규 파일은 `domain/` `application/` `infrastructure/` `components/` `hooks/` `stores/` 중 하나에 배치 + 본 lint rule 준수
- `useAgentStore` 는 deprecated — 새 코드는 `useExecutionStore` 사용
- Phase 2 종료 시 8개 consumer 일괄 마이그레이션 + agentStore.ts shim 삭제 예정
- npm run lint:arch 가 PR 게이트 — 위반 시 즉시 fail

#### 회귀 영향
- 없음 — typecheck PASS, 기존 11개 contract test PASS, agentStore shim 으로 8개 consumer 무수정 동작

---

### 2026-04-19 (이전) — leader — 디렉토리 초기 생성

**Sub-Phase**: N/A (메타)
**소요 시간**: ~2h
**상태**: completed

#### 변경 요약
24개 PLAN 작성, SHARED 디렉토리 신설, 협업 프로토콜 정의

#### Touched Files
- `Docs/UX/development_plan/**/*.md` (39개 + SHARED 신설)

#### 결정 (DECISIONS)
- ADR-0001: 디렉토리 구조
- ADR-0002: TDD 강제
- ADR-0003: i18next 채택
- ADR-0004: WS envelope
- ADR-0005: Result Card "other" fallback

#### 다음 agent에게 전달
- Wave 0 진입 가능 (cross_cutting PLAN_02 Sub-Phase 1.1, 1.2 → cross_cutting PLAN_03 Sub-Phase 1 → cross_cutting PLAN_01 Sub-Phase 1.1, 1.2)
- 모든 agent는 작업 시작 전 [`../00_overview/06_AGENT_COORDINATION.md`](../00_overview/06_AGENT_COORDINATION.md) 필독

#### 회귀 영향
없음 (문서만)

---

(이하 agent 작업 기록 추가)
