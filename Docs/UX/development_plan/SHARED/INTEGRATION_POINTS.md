# INTEGRATION_POINTS — PLAN 간 코드 접점 매트릭스

여러 PLAN이 동일 파일/모듈을 touch하는 지점을 명시. **agent는 자기 PLAN 행만 추가/수정**한다.

---

## 1. 사용 방법

### 작업 전
- 본인 PLAN의 §10 의존성에 명시된 파일들이 본 표에 있는지 확인
- 동일 파일에 다른 PLAN(특히 진행 중)이 표시되어 있으면 → ACTIVE_WORK 확인 + 충돌 검토

### 작업 중
- PLAN에 명시되지 않았던 파일을 touch하게 되면 본 표에 추가
- 상태: `예상 (planned)` / `진행중 (in_progress)` / `완료 (done)`

### 작업 후
- 본인 PLAN 행을 `완료` 로 갱신
- 실제 touch한 파일 목록을 정확히 기록 (예상과 다르면 갱신)

---

## 2. Frontend 핵심 파일별 접점

### `electron/src/renderer/App.tsx`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 1 PLAN_01 i18n | I18nProvider wrap | 예상 |
| Phase 1 PLAN_02 Mission Header | Layout 상단에 Mission Header | 예상 |
| Phase 1 PLAN_05 Sidebar collapse | Layout 폭 동적화 | 예상 |
| Phase 2 PLAN_01 IA | Router 5+1 area | 예상 |
| Phase 2 PLAN_04 Workspace | Layout 3-pane | 예상 |
| Phase 4 PLAN_01 Design system | Theme provider | 예상 |
| Phase 4 PLAN_02 Density | DensityProvider | 예상 |

### `electron/src/renderer/components/sidebar/Sidebar.tsx`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 1 PLAN_05 Sidebar collapse | 핵심 변경 (collapsed state, tooltip) | 예상 |
| Phase 2 PLAN_01 IA | 항목 5+1 area로 재구성 | 예상 |

### `electron/src/renderer/components/chat/ChatPanel.tsx` (또는 동등)

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 1 PLAN_02 Mission Header | 상단 영역 추가 | 예상 |
| Phase 2 PLAN_02 Result Cards | 메시지 렌더링에서 카드 추출/표시 | 예상 |

### `electron/src/renderer/stores/agentStore.ts`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| cross_cutting PLAN_02 Sub-Phase 1.2 | rename → executionStore + 도메인 reducer 추출, agentStore.ts → backward-compat shim | **완료** (agent-w0-foundation-001, 2026-04-19) — chat/run 은 chatStore/runtimeStore 가 이미 분리되어 있어 1-rename 으로 PLAN 의도 달성. 실제 splitting 은 Phase 2 시 추가 검토. |

### `electron/src/renderer/stores/i18nStore.ts`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 1 PLAN_01 i18n | 교체 (i18next로) | 예상 |

### `electron/src/renderer/components/runtime/ToolActivity.tsx` (또는 동등)

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 1 PLAN_03 Execution Timeline | ExecutionTimeline으로 교체 | 예상 |
| Phase 3 PLAN_01 Plan Tree | Layer 2 (reasoning) 추가 | 예상 |

### `electron/src/renderer/components/sandbox/SandboxApprovalModal.tsx`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 2 PLAN_06 Approval v2 | 전면 재설계 | 예상 |
| Phase 3 PLAN_05 Risk-tier Policy | "정책에 자동 허용" 옵션 추가 | 예상 |

### `electron/src/renderer/components/settings/SettingsPanel.tsx` (또는 동등)

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 1 PLAN_01 i18n | LocaleSelector 추가 | 예상 |
| Phase 1 PLAN_06 Model labels | ModelSelector 재설계 | 예상 |
| Phase 2 PLAN_01 IA | Admin area로 분해 | 예상 |
| Phase 4 PLAN_02 Density | DensityMode 선택 추가 | 예상 |

### Tailwind config / theme

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 1 PLAN_01 i18n | CJK font-family | 예상 |
| Phase 4 PLAN_01 Design system | 토큰 시스템 도입 | 예상 |
| Phase 4 PLAN_02 Density | Density-aware spacing tokens | 예상 |

---

## 3. Backend 핵심 파일별 접점

### `src/ds_agent/api/routes/`

| 파일 | PLAN | 상태 |
|------|------|------|
| `mission.py` (신설) | Phase 1 PLAN_02 | 예상 |
| `workspace.py` 확장 | Phase 1 PLAN_04, Phase 2 PLAN_04 | 예상 |
| `trust.py` (신설) | Phase 2 PLAN_03 | 예상 |
| `approval.py` 확장 | Phase 2 PLAN_06 | 예상 |
| `onboarding.py` (신설) | Phase 2 PLAN_05 | 예상 |
| `runs.py` 확장 (checkpoints, branches) | Phase 3 PLAN_03 | 예상 |
| `policy.py` (신설) | Phase 3 PLAN_05 | 예상 |
| `export.py` 확장 | Phase 2 PLAN_04, Phase 3 PLAN_06 | 예상 |

### `src/ds_agent/application/use_cases/`

(신규 use case 다수 — 각 PLAN의 §4 참조)

### `src/ds_agent/infrastructure/llm/prompt_builder.py`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 2 PLAN_02 Result Cards | 4종 카드 emit 가이드 system prompt | 예상 |
| Phase 3 PLAN_01 Reasoning Trace | 4-tuple emit 가이드 추가 | 예상 |

### `src/ds_agent/infrastructure/llm/model_registry.py`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 1 PLAN_06 Model labels | capability_group, badges 메타 | 예상 |

### `src/ds_agent/infrastructure/telegram/`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 4 PLAN_04 Telegram redesign | 전면 재포지셔닝 | 예상 |

---

## 4. 공유 도메인 객체

### `Mission / Goal / TaskContract`

| PLAN | 사용 방식 | 상태 |
|------|---------|------|
| Phase 1 PLAN_02 Mission Header | 조회 | 예상 |
| Phase 2 PLAN_05 Onboarding | 생성 | 예상 |
| Phase 3 PLAN_03 Checkpoint | snapshot에 포함 | 예상 |

### `ResultCard 4종`

| PLAN | 역할 | 상태 |
|------|------|------|
| Phase 2 PLAN_02 | 정의/CRUD | 예상 |
| Phase 2 PLAN_03 | TrustStrip 부착 | 예상 |
| Phase 2 PLAN_04 | Workspace에 표시 | 예상 |
| Phase 3 PLAN_03 | promote_to_artifact | 예상 |
| Phase 3 PLAN_06 | audience별 렌더 | 예상 |

### `WS Event Stream`

| PLAN | 추가 이벤트 | 상태 |
|------|-----------|------|
| Phase 1 PLAN_02 | `mission.context.updated` | 예상 (registry pre-seeded by W0) |
| Phase 1 PLAN_03 | (기존 tool event 활용) | — |
| Phase 2 PLAN_02 | `card.created`, `card.updated`, `card.pinned` | 예상 (registry pre-seeded by W0) |
| Phase 3 PLAN_01 | `plan.created`, `plan.updated`, `plan.replanned`, `reasoning.emitted` | 예상 (registry pre-seeded by W0) |
| cross_cutting PLAN_03 | envelope + versioning (모든 이벤트 wrap) | **완료** (ADR-0007, agent-w0-foundation-001, 2026-04-19) |

---

## 5. 충돌 해결 가이드

### 동일 파일을 touch해야 할 때

1. **순차 진행**: 의존 관계가 있으면 명백한 순서 (예: PLAN_05 sidebar → PLAN_02 mission header)
2. **PR 분리**: 같은 파일이라도 다른 함수/섹션이면 PR로 분리
3. **머지 충돌**: 발생 시 leader가 결정 (어느 PR이 우선 base)
4. **재작업**: 한 PR 머지 후 다른 PR이 rebase

### 동일 도메인 객체 확장

- 필드 추가는 backward compatible
- 필드 제거/변경은 leader 합의 + DECISIONS에 ADR
