# Wave 0–1 Finalization Plan

**작성일**: 2026-04-19
**작성자**: leader
**대상**: Wave 0 / Wave 1 미완 항목을 처리하는 모든 agent
**선행**: `WAVE_0_HANDOFF.md` — 이 문서는 그 후속

---

## 0. 배경

Wave 0 의 산출물과 isolated contract test 는 들어왔지만 **end-to-end baseline enforcement** 가 완료되지 않았다는 외부 감사 결과(2026-04-19). 이 문서는 감사 지적 4가지 + 추가 리스크 1가지 + Wave 1 미완 항목을 완결시키는 작업 분배 플랜이다.

Wave 2 진입 전 본 플랜의 모든 Phase 가 종료되어야 한다.

---

## 1. 감사 Finding 요약

| # | Severity | 제목 | 실증 위치 |
|---|----------|------|-----------|
| F1 | High | WS envelope 가 실제 수신 경로에 미연결 | `electron/src/renderer/hooks/useWebSocket.ts:148` (`JSON.parse` 후 `msg.payload` 직통, `parseEnvelope`/`validateEventPayload` 미사용) |
| F2 | High | Wave 0 CI gate 가 workflow 에 미등록 | `.github/workflows/{smoke,build-release,eval-nightly}.yml` 어디에도 `lint:arch` / `test:contract:wave0` 없음 |
| F3 | Medium | `lint:arch` 우회 가능 | `lintArchCore.cjs:67` line-by-line regex — multi-line import 미매칭 / `lintArchCore.cjs:100` non-relative 전부 package 로 — `tsconfig.json` 의 `@/*` alias 탐지 불가 |
| F4 | Medium | a11y Sub-Phase 1.1 placeholder | `lint-a11y.mjs:15` 가 axe 미설치 시 SKIP + exit 0. E2E axe assertion / CI gate 모두 미구현 |
| F5 (추가) | Medium | envelope `ts` 단위 cross-language 불일치 | Python `time.time()` (초) vs TS `Date.now()` (ms) |

---

## 2. Wave 1 미완 잔여

| PLAN | 미완 항목 |
|------|-----------|
| PLAN_02 Mission Header (W1-E) | Sub-Phase 2.4 integration test 4 시나리오 / 2.5 drawer 9종 전체 wiring / 2.6 `Ctrl+Shift+M` / 2.7 pause-snooze + agent pause API / 실시간 task contract emission / WS 재연결 재구독 검증 |
| PLAN_01 i18n (W1-A) | 풀 i18next migration — 전 컴포넌트 hardcoded 제거 / namespace 정리 (공통 + 각 PLAN namespace 통합) / CJK 폰트 / i18next parser + CI 키 검증 / 전용 contract test |

---

## 3. Phase 분해

### Phase A — Wave 0 connection & enforcement fixes

**Owner**: Phase A agent (1 명)
**Worktree branch**: `agent-phaseA-wave0-fixes`
**병렬 가능**: B, C

| ID | 작업 | 파일 |
|----|------|------|
| A1 | useWebSocket envelope 통합 — parse → validate → handler | `electron/src/renderer/hooks/useWebSocket.ts` |
| A2 | CI wave0 gate 등록 — 기존 `smoke.yml` 확장 또는 신규 workflow | `.github/workflows/` |
| A3 | `lintArchCore.cjs` 강화 — multi-line import regex + `@/*` alias resolve (tsconfig paths 파싱) + require multi-line | `electron/scripts/lintArchCore.cjs` + contract test `eslintArchRule.spec.ts` 확장 |
| A4 | envelope ts 통일 — **Python 을 ms 로** (`int(time.time() * 1000)`). 결정 근거: JS/분산 시스템 표준 + 정수 정렬 안정 | `src/ds_agent/api/event_envelope.py` + 관련 pytest 수정 |
| A5 | `eventSchemaRegistry` — schema 에 version 필드 강제 + `validate` 시 major version 비교 로직 | `electron/src/renderer/infrastructure/ws/eventSchemaRegistry.ts` + spec |

**검증 게이트**:
- `npm run lint:arch` 0 violations (A3 강화 후에도)
- 신규 contract test: `import {\n useState\n} from 'react'` 와 `import { api } from '@/infrastructure/...'` 모두 **violation 감지**
- `npm run test:contract:wave0` PASS
- `pytest tests/unit/api/test_event_envelope.py tests/unit/api/test_ws_callbacks_envelope.py` PASS
- envelope round-trip: Python ms ↔ TS ms 일치

**신규 ADR**: ADR-0009 (envelope ts 단위 = ms, integer) — DECISIONS.md append

---

### Phase B — Wave 0 a11y baseline 완성

**Owner**: Phase B agent (1 명)
**Worktree branch**: `agent-phaseB-a11y-baseline`
**병렬 가능**: A, C

| ID | 작업 | 파일 |
|----|------|------|
| B1 | `@axe-core/playwright` devDep 실제 install | `electron/package.json` |
| B2 | E2E a11y test 5종 | `electron/tests/e2e/a11y/{mission,onboarding,chat,settings,sidebar}.a11y.spec.ts` |
| B3 | `lint-a11y.mjs` 가 axe 미설치 시 SKIP 대신 **exit 1** + 친절한 메시지 | `electron/scripts/lint-a11y.mjs` |
| B4 | CI 에 `npm run test:e2e:a11y` 추가 | `.github/workflows/` (Phase A 와 hotspot — append only) |
| B5 | 신규 ADR-0010 — axe-core 는 devDep 필수, CI gate | `SHARED/DECISIONS.md` |

**검증 게이트**:
- `npm run lint:a11y` exit 0 (axe 설치 후)
- `npm run test:e2e:a11y` PASS, violation 0
- 각 화면 critical / serious violation 0

---

### Phase C — W1-E Mission Header finalize

**Owner**: Phase C agent (1 명)
**Worktree branch**: `agent-phaseC-w1e-finalize`
**병렬 가능**: A, B
**참조**: 이전 `agent-w1e-mission-finalize-003` dispatch prompt 와 동일 — `PLAN_02 §12 Hand-off` 6 항목

| ID | 작업 |
|----|------|
| C1 | MissionHeader integration test 4 시나리오 (RED) |
| C2 | 9 슬롯 drawer/dropdown 전체 + 공통 `MissionDrawerShell` + `MissionDropdownMenu` + lazy load |
| C3 | `Ctrl+Shift+M` 단축키 (useKeyboardShortcut 재사용) |
| C4 | Budget warning **pause/snooze** + agent pause API wiring |
| C5 | Task contract 수정 시 `dataSources/deliverables/constraints` delta emission |
| C6 | WS 재연결 자동 재구독 검증 |

**검증 게이트**: PLAN_02 §8 Phase DoD 6 항목 + `npm run lint:arch` + wave0 + `tsc --noEmit` + pytest

**Hotspot (C 가 touch할 가능성)**:
- `electron/src/renderer/components/mission/*` (C 독점)
- `electron/src/renderer/application/mission/*` (C 독점)
- `electron/src/renderer/stores/i18nStore.ts` (`mission.*` namespace 만 append — D가 Phase D 에서 통합할 예정)
- `src/ds_agent/api/routes/mission.py` (`POST /api/mission/pause` 추가) / `ws_handler.py` (task contract emit) / `pause_agent_usecase.py` (신규)

---

### Phase D — W1-A 풀 i18n migration (Phase A/B/C 모두 종료 후 단독)

**Owner**: Phase D agent (1 명)
**Worktree branch**: `agent-phaseD-w1a-full-i18n`
**병렬 불가**: 모든 컴포넌트 touch

| ID | 작업 |
|----|------|
| D1 | i18next + react-i18next install, `i18n.ts` bootstrap, Provider wrap |
| D2 | namespace 파일 분리 — `common / mission / workspace / execution / llm / sidebar / onboarding / settings / approval / trust / cards / chat` — `public/locales/{ko,en,ja}/*.json` |
| D3 | 기존 `i18nStore.ts` 의 store-backed translation → i18next 로 마이그레이션 (backward-compat: `useI18n().t` 인터페이스 유지) |
| D4 | 전 컴포넌트 hardcoded 검출 + i18n key 치환 (Phase C 가 완료한 mission/* 도 포함) |
| D5 | Tailwind config — CJK font-family (Noto Sans KR/JP) |
| D6 | i18next-parser CI — 미사용 키 / 누락 키 검출 |
| D7 | 신규 contract test — 각 namespace 모든 키가 ko/en/ja 에 존재 |

**검증 게이트**:
- `grep -rE "['\"][가-힣]" electron/src/renderer/components` → 0 matches (한국어 hardcoded 없음)
- i18next-parser 실행 시 extraneous / missing 0
- 각 locale JSON key count 일치

---

## 4. 타임라인 및 병렬성

```
  시각 → ──────────────────────────────────────
  T0:   ┌─Phase A─┐ ┌─Phase B─┐ ┌─Phase C─┐    (3개 동시 발주)
        └─────┬───┘ └─────┬───┘ └─────┬───┘
  T1:          leader 검수 (3개 종료 후)
  T2:                           ┌─Phase D─┐    (단독)
                                └─────┬───┘
  T3:                  leader 머지 (Wave 0 + 1 종료)
  T4:                           Wave 2 진입
```

**예상 공수 (각 Phase 독립 실시간)**:
- Phase A: 4–6h
- Phase B: 3–5h
- Phase C: 8–12h (6 항목 중 C2 drawer 9종이 핵심 공수)
- Phase D: 10–15h (전 컴포넌트 + CI)

총 wall-clock (3 병렬 + 1 순차): ~18–26h

---

## 5. Agent 간 협업 프로토콜

### 공통
- 모든 agent 는 작업 시작 시 `SHARED/ACTIVE_WORK.md` 에 lock append
- 종료 시 본인 lock 제거 + `SHARED/DEVELOPMENT_LOG.md` 항목 append + `SHARED/INTEGRATION_POINTS.md` 행 갱신
- Commit 은 의미 단위 분리 (각 ID 별 1 commit 이상)

### `electron/package.json` hotspot (A / B / D 가능)
- **A** 는 scripts 만 append (lint / test) — dependencies 변경 금지
- **B** 는 devDependencies 에 `@axe-core/playwright` 1개 append
- **D** 는 dependencies 에 `i18next` + `react-i18next` append
- 충돌 시 leader 가 manual merge (의미 단위 유지)

### `.github/workflows/*.yml` hotspot (A / B)
- **A** 가 wave0 gate job 추가 (신규 step)
- **B** 가 a11y gate job 추가 (신규 step)
- 각자 별도 step 으로 분리 — merge 자동

### `SHARED/DECISIONS.md` ADR 번호
- A: ADR-0009 (envelope ts = ms)
- B: ADR-0010 (axe-core CI gate)
- C: 신규 없음 (기존 패턴 답습)
- D: ADR-0011 (i18next runtime + store backward-compat)

---

## 6. Wave 2 진입 조건 (완결 체크리스트)

- [x] Phase A 완료 — useWebSocket envelope 연결, CI wave0 gate 활성, lint:arch 강화 (multi-line + alias), envelope ts 통일 (ms), eventSchemaRegistry version enforce (agent-phaseA-wave0-fixes-001, 2026-04-19)
- [x] Phase B 완료 — axe (4.11.2) 설치, E2E a11y 5종 (onboarding/mission/chat/settings/sidebar) 모두 PASS / 0 critical+serious violation, lint:a11y exit 1 on missing, `.github/workflows/a11y.yml` CI gate 등록 (agent-phaseB-a11y-baseline-001, 2026-04-19)
- [x] Phase C 완료 — PLAN_02 §8 Phase DoD 6 항목 모두 PASS (agent-phaseC-w1e-finalize-001, 2026-04-19)
- [ ] Phase D 완료 — 한국어 hardcoded 0, parser 검증 0 violation, 3 locale 키 count 일치
- [ ] leader 머지 — Wave 0 + Wave 1 모든 변경 main 에 병합, worktree branch 정리
- [ ] Regression 확인 — 기존 E2E (`test:e2e:smoke`, `test:e2e:happy`) PASS
- [ ] Wave 2 prerequisite 문서 갱신 — `SHARED/INTEGRATION_POINTS.md` Wave 1 모든 행 "완료"

---

## 7. 변경 이력

| 일자 | 버전 | 변경 |
|------|------|------|
| 2026-04-19 | 1.0 | 초기 작성 — 외부 감사 결과 대응 |
