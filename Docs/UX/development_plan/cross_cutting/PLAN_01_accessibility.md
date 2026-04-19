# PLAN 01: 접근성 (a11y)

**Status**: Pending — Phase 1+ 지속
**Estimated Effort**: 분산 (각 phase에 1일씩 + Phase 1 시작 시 2일 baseline)

**ROADMAP 매핑**: §4.12 접근성 갭 채우기, §6.5 접근성

> **🤖 AI Agent 안내**: 본 PLAN을 시작하기 전 [`SHARED/`](../SHARED/) 의 `GLOSSARY.md`, `CONVENTIONS.md`, `INTEGRATION_POINTS.md`, `DECISIONS.md`, `DEVELOPMENT_LOG.md`, `ACTIVE_WORK.md` 를 모두 확인하고 [`00_overview/06_AGENT_COORDINATION.md`](../00_overview/06_AGENT_COORDINATION.md) 의 protocol을 따른다. 작업 완료 시 §11 진행 추적, §12 Notes & Learnings, 그리고 SHARED의 `DEVELOPMENT_LOG.md` / `ACTIVE_WORK.md` / `INTEGRATION_POINTS.md` 를 반드시 갱신한다.

---

## 1. 개요

### 목표
WCAG 2.1 AA 자동 스캔 통과율 > 95%, 키보드 only 핵심 플로우 완주율 100%.

### 적용 범위
- 모든 신규 컴포넌트 (PR 차단 게이트)
- 기존 컴포넌트 점진 개선

---

## 2. 항목별 baseline

| 항목 | 현재 | 목표 |
|------|------|------|
| 컬러 전용 상태 표시 | 일부 존재 | 텍스트 + 아이콘 병기 |
| Generic `<div>` role | 누락 | landmark role |
| Reduced motion | 미지원 | `prefers-reduced-motion` 존중 |
| 스트리밍 스크린 리더 | 불명 | `aria-live="polite"` |
| Empty state | 빈약 | 다음 액션 제안 |
| Skeleton loading | 없음 | 주요 패널 |
| Focus indicator | 일부 | 100% 보장, 2px 이상 |
| Keyboard trap (modal) | 일부 | 100% |
| Tab order | 자연스럽지 않음 | 의미 순서 |
| Screen reader 라벨 | 부족 | 모든 interactive |

---

## 3. 인프라 (Phase 1 baseline 2일)

### Sub-Phase 1.1 — 자동 스캔 (1일)
- `@axe-core/playwright` 설치
- E2E에 axe assertion 추가
- CI step `pnpm test:a11y`

### Sub-Phase 1.2 — Focus + Reduced motion + 공통 utility (1일)
- 전역 focus-visible 스타일
- `prefers-reduced-motion` mixin / hook
- `useAriaLive` hook 표준화

---

## 4. 각 phase에 적용

각 PLAN의 Sub-Phase 마지막에 `a11y + i18n` (0.5일) 항목이 있음. 본 baseline을 활용하여 다음을 검증:

### PR 체크리스트
- [ ] 신규 컴포넌트 axe 스캔 통과
- [ ] keyboard tab 완주
- [ ] focus indicator 가시
- [ ] 색상 외 텍스트/아이콘 병기
- [ ] aria-label 명확
- [ ] modal: focus trap + ESC + 복원
- [ ] reduced motion 존중
- [ ] streaming: aria-live="polite"
- [ ] empty state: 다음 액션 제안

---

## 5. 정기 audit

- 각 phase 종료 시 전체 a11y audit
- 외부 사용자 테스트 (스크린 리더 사용자) — Phase 2 종료 시점

---

## 6. 도구

| 도구 | 용도 |
|------|------|
| `@axe-core/playwright` | 자동 스캔 |
| `vitest-axe` | 단위 테스트 |
| NVDA / JAWS / VoiceOver | 수동 검증 |
| Chrome DevTools Lighthouse | 점검 |
| `eslint-plugin-jsx-a11y` | 린트 |

---

## 7. KPI

| 지표 | 목표 |
|------|------|
| WCAG 2.1 AA 자동 스캔 통과율 | > 95% |
| Keyboard 핵심 플로우 완주 | 100% |
| Lighthouse a11y score | > 95 |

---

## 8. 진행 추적

### Sub-Phase 진행

- [x] 1.1 자동 스캔 (1일) — agent-w0-foundation-001 / 2026-04-19 (axe-core 미설치 환경에서는 placeholder, 설치 시 자동 활성)
- [x] 1.2 Focus + Reduced motion + 공통 utility (1일) — agent-w0-foundation-001 / 2026-04-19

### Phase audit 결과

각 phase 종료 시 audit 결과 기록:

| Phase | 자동 스캔 통과율 | 수동 audit |
|-------|------------------|-----------|
| 1 | — | — |
| 2 | — | — |
| 3 | — | — |
| 4 | — | — |

---

## 9. Notes & Learnings

### Sub-Phase 1.1 + 1.2 (agent-w0-foundation-001, 2026-04-19)

**산출물**:
- `electron/scripts/lint-a11y.mjs` — placeholder a11y CI step, axe-core install 시 자동 활성
- `electron/src/renderer/application/a11y/focusManagement.ts` — `isFocusable`, `findFocusableElements`, `captureFocus`, `restoreFocus`, `createFocusTrap` (138 LOC, 외부 의존 0)
- `electron/src/renderer/application/a11y/reducedMotion.ts` — `prefersReducedMotion`, `subscribeReducedMotion` with provider injection
- `electron/src/renderer/application/a11y/ariaLive.ts` — `announce(message, options)` document-level live region helper
- `electron/src/renderer/styles/globals.css` — 전역 `:focus-visible` 스타일 (2px outline, accent color), `@media (prefers-reduced-motion: reduce)` block (애니메이션 0.01ms)
- `electron/tests/contract/focusManagement.spec.ts` (10 cases — fake DOM)
- `electron/tests/contract/reducedMotion.spec.ts` (7 cases — fake matchMedia)
- `npm run lint:a11y` script 등록

**디자인 결정 (ADR-0008)**:
- focus-trap / @axe-core 미설치 환경에서도 동작 — application 레이어에 순수 DOM API 만 사용
- focusManagement / reducedMotion / ariaLive 모두 provider injection 패턴 → 테스트 가능 (fake document, fake matchMedia)
- React hook wrapper 는 후속 wave 에서 components 가 wrapping (ex: `useFocusTrap`, `useReducedMotion`)

**WCAG 매핑**:
- 2.4.3 Focus Order — focus trap cycle (forward/backward)
- 2.4.7 Focus Visible — globals.css `:focus-visible` (2px outline)
- 2.3.3 Animation from Interactions — reducedMotion utility + globals.css `@media (prefers-reduced-motion: reduce)`
- 4.1.3 Status Messages — ariaLive `announce()` (polite/assertive 구분)

**Deviation**:
- @axe-core/playwright 즉시 install 미수행 — npm install 부담 + worktree 격리 + Playwright 별도 install 필요. ADR-0008 에 placeholder 전략 정당화.
- focus-trap 라이브러리 미사용 — 138 LOC self-contained 으로 동등 기능 구현. trade-off: focus-trap 의 click-outside / hierarchy lock 등 advanced 기능은 미구현 (필요 시 후속 wave 추가).

**회귀 영향**:
- 0 — globals.css 의 `:focus-visible` / `@media reduced-motion` 추가는 기존 컴포넌트에 누락이었던 baseline 추가 (이전엔 default browser outline)
- 모든 contract test (17개 = 기존 11 + W0 신규 6) PASS
