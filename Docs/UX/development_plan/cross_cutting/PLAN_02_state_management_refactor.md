# PLAN 02: 상태 관리 리팩터 (Zustand store 도메인 분할)

**Status**: Pending — Phase 1 시작 전 + Phase 2 진입 전
**Estimated Effort**: 4–6 작업일 (분산)

**ROADMAP 매핑**: §7.1 기술 리스크 → "Zustand 단일 store 비대화"
**Clean Architecture**: `00_overview/02_CLEAN_ARCHITECTURE_MAPPING.md §3.2 갭`

> **🤖 AI Agent 안내**: 본 PLAN을 시작하기 전 [`SHARED/`](../SHARED/) 의 `GLOSSARY.md`, `CONVENTIONS.md`, `INTEGRATION_POINTS.md`, `DECISIONS.md`, `DEVELOPMENT_LOG.md`, `ACTIVE_WORK.md` 를 모두 확인하고 [`00_overview/06_AGENT_COORDINATION.md`](../00_overview/06_AGENT_COORDINATION.md) 의 protocol을 따른다. 작업 완료 시 §11 진행 추적, §12 Notes & Learnings, 그리고 SHARED의 `DEVELOPMENT_LOG.md` / `ACTIVE_WORK.md` / `INTEGRATION_POINTS.md` 를 반드시 갱신한다.

---

## 1. 개요

현재 `electron/src/renderer/stores/` 의 store들이 도메인+UI state 혼재. 본 PLAN은 다음을 목표:

1. 도메인별 store 분할 + 명확한 책임
2. Use case 함수 분리 (store action에서 비즈니스 로직 추출)
3. ESLint custom rule로 layer violation 차단

---

## 2. 현재 상태

```
stores/
├── agentStore.ts
├── authStore.ts
├── chatStore.ts
├── configStore.ts
├── filesStore.ts
├── i18nStore.ts        # PLAN_01 Phase 1에서 교체
├── policyStore.ts
├── projectStore.ts
├── runtimeEventStore.ts
├── runtimeStore.ts
├── usageStore.ts
└── workflowStore.ts
```

### 문제
- `agentStore` 가 너무 많은 책임 (chat + workflow + tool events)
- store action에 fetch / IPC 직접 호출
- 컴포넌트가 store 직접 참조

---

## 3. 목표 구조

```
domain/             # 신설 — 순수 도메인
├── mission.ts
├── artifact.ts
├── trust.ts
├── run.ts
├── execution/
└── ...

application/        # 신설 — use case 함수
├── mission/
│   ├── getMissionContext.ts
│   ├── updateMode.ts
│   └── ...
├── artifact/
│   ├── pinCard.ts
│   ├── exportCard.ts
│   └── ...
└── run/

stores/             # action만 담당, 비즈니스 로직은 application으로
├── missionStore.ts        # 분할
├── chatStore.ts
├── artifactStore.ts       # 신설
├── runStore.ts            # 신설
├── trustStore.ts          # 신설
├── ...

infrastructure/     # 신설 — IPC, HTTP, WS 어댑터
├── api/
│   ├── missionApi.ts
│   ├── artifactApi.ts
│   └── ...
├── ws/
│   ├── wsClient.ts
│   └── subscribers/
├── ipc/
└── storage/
```

---

## 4. Sub-Phase

### Phase 1 시작 전 (2일)

#### Sub-Phase 1.1 — Domain 디렉토리 + ESLint rule (1일)
- [ ] `renderer/domain/`, `renderer/application/`, `renderer/infrastructure/` 디렉토리 생성
- [ ] ESLint custom rule: domain은 react/zustand/axios import 금지
- [ ] `tach` 또는 `dependency-cruiser` 설정
- [ ] CI step: `pnpm lint:arch`

#### Sub-Phase 1.2 — 가장 큰 store 분할 (1일)
- [ ] `agentStore` 를 `chatStore` + `runStore` + `executionStore` 로 분할
- [ ] 점진 — 한 PR에 한 store 이동
- [ ] 회귀 테스트

### Phase 2 진입 전 (2일)

#### Sub-Phase 2.1 — Use case 추출 (1일)
- [ ] store action의 비즈니스 로직 → `application/<feature>/<action>.ts` 함수
- [ ] store는 use case 호출만

#### Sub-Phase 2.2 — Infrastructure 분리 (1일)
- [ ] 컴포넌트의 fetch/ipcRenderer 직접 호출 → `infrastructure/api/` 어댑터
- [ ] 컴포넌트는 hook을 통해서만 호출

### 지속 개선 (Phase 2-4 각 0.5일)

- 새 기능 추가 시 본 구조 강제
- ESLint rule violation 발생하면 즉시 수정

---

## 5. 품질 게이트

- [ ] `domain/` 의 모든 파일이 순수 TS (외부 import 0)
- [ ] `application/` 이 `infrastructure/` 직접 import 안 함
- [ ] ESLint rule 위반 0
- [ ] 각 store 파일 < 300 lines (큰 store 분할 신호)
- [ ] 기존 기능 회귀 0

---

## 6. 마이그레이션 전략

- 점진적: 신규 기능부터 새 구조 적용
- 기존: PR별 1개 store 이동
- 호환: legacy store는 유지하되 deprecated 표시

---

## 7. 의존성

- 선행: 없음 (Phase 1 첫 작업)
- 후속: 모든 phase가 본 구조 기반

---

## 8. 진행 추적

- [x] Sub-Phase 1.1 — Domain 디렉토리 + ESLint (1일) — agent-w0-foundation-001 / 2026-04-19
- [x] Sub-Phase 1.2 — agentStore 분할 (1일) — agent-w0-foundation-001 / 2026-04-19
- [ ] Sub-Phase 2.1 — Use case 추출 (1일)
- [ ] Sub-Phase 2.2 — Infrastructure (1일)
- [ ] Phase 2 진입 시 잔여 store 분할
- [ ] Phase 3 진입 시 audit
- [ ] Phase 4 진입 시 audit

---

## 9. Notes & Learnings

### Sub-Phase 1.1 (agent-w0-foundation-001, 2026-04-19)

**산출물**:
- `electron/src/renderer/{domain,application,infrastructure}/` 신설 + 각 README.md
- `electron/scripts/lintArchCore.cjs` (134 LOC, 외부 의존 0)
- `electron/scripts/lint-arch.mjs` (CLI wrapper)
- `electron/eslint.config.mjs` (flat config — 향후 ESLint install 시 자동 활성)
- `electron/tests/contract/eslintArchRule.spec.ts` (14 cases, 양/음성 fixture)
- `npm run lint:arch` script 등록

**디자인 결정 (ADR-0006)**:
- ESLint 미설치 환경에서도 동작하도록 standalone Node script 를 primary CI 게이트로 채택
- ESLint config 는 IDE / 향후 install 시 즉시 보조

**Layer rules 구현**:
- domain → react/zustand/axios/application/infrastructure/components/hooks/stores 모두 차단
- application → react/react-dom/infrastructure/components/hooks 차단 (domain import 만 허용)
- components → infrastructure 직접 import 차단 (hook 경유 강제)

**Deviation**:
- `tach` / `dependency-cruiser` 미도입 — 14-case fixture-test 로 self-validate (ADR-0006 근거)
- `utils/` 는 layer rule 미정의 (현재는 framework-agnostic helper 만 존재). 향후 비순수 helper 발견 시 추가 결정 필요.

**회귀 영향**: 0 — 기존 11개 contract test 모두 PASS, renderer typecheck PASS

### Sub-Phase 1.2 (agent-w0-foundation-001, 2026-04-19)

**산출물**:
- `electron/src/renderer/domain/execution/executionState.ts` (87 LOC, 순수 reducer 함수 9개)
- `electron/src/renderer/stores/executionStore.ts` (Zustand wrapper, reducer 위임)
- `electron/src/renderer/stores/agentStore.ts` → backward-compat 재내보내기 shim (`useAgentStore = useExecutionStore`)
- `electron/tests/contract/executionStore.spec.ts` (7 cases)

**디자인 결정**:
- 본 단계의 "agentStore 분할" 은 명목상 chat/run/execution 3분할이지만, 실제 검사 결과:
  - chatStore (이미 존재) — messages + tool activities 담당
  - runtimeStore + runtimeEventStore (이미 존재) — sessions/runs/tasks 담당
  - agentStore (52 LOC) — 실제로는 model/mode/cost/step/connected 만 담당 → 의미상 "executionStore" 가 정확
- ⇒ agentStore → executionStore 로 rename + 도메인 reducer 추출 1step. 추가 분할은 불필요 (이미 적절히 분리됨).

**Backward compatibility**:
- 7개 consumer 파일 (App.tsx, Sidebar.tsx, SettingsPanel.tsx, useAgent.ts, ModelSelector.tsx, StatusBar.tsx, useChat.ts, ModeSelector.tsx) 모두 `useAgentStore` import 유지 — shim 으로 무수정
- Phase 2 종료 시 일괄 마이그레이션 (`useAgentStore` → `useExecutionStore`) 후 shim 삭제 예정

**Deviation**:
- chat/run/execution **3분할** 대신 **1-rename + reducer 추출** — 이미 chatStore/runtimeStore 가 존재하므로 PLAN 의도 충족
- 명시적으로 PLAN §4 와 다름 → 본 노트 + DEVELOPMENT_LOG 에 기재

**회귀 영향**: 0 — typecheck + 기존 11개 + 신규 2개 contract test 모두 PASS
