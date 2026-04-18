# Productization — Next Steps (2026-04-15)

**작성일**: 2026-04-15
**기준**: `Docs/productization/` 전체 plan 문서 및 실제 코드베이스 독립 감사 결과
**목적**: 문서 상태와 실구현 간 괴리 정정 + 베타 출시까지 남은 작업 우선순위 정리

> 불변 원칙: LLM is the orchestrator. 제품화는 LLM 판단을 돕는 레이어이며,
> 본 문서의 모든 잔존 작업은 이 원칙을 훼손하지 않아야 한다.

---

## 감사 요약 (2026-04-15 기준)

| 결과 | 개수 | 비고 |
|------|------|------|
| 문서 "Complete" 중 실구현 일치 | 4 | P0-03, P1-08, P1-09, P1-11, P1-13, P1-14 |
| 문서 "Complete"지만 실구현 약함 | 1 | **P1-10** (Postgres connector `ts-nocheck`, 헬퍼 미구현) |
| 문서 "In Progress" — 문서와 실상 일치 | 6 | P0-01, P0-02, P0-04, P0-05, P0-06, P0-07 |
| 문서가 과소 기술한 결함 | 1 | **P0-07 crash reporting 미통합** (bundle만 존재) |
| Electron 자동화 테스트 | **0건** | `electron/src/**/*.spec.ts`/`*.test.ts` 전무 |
| Python 테스트 | 140 파일 | smoke 포함 |

---

## A. 문서-구현 괴리 정정 (문서 + 코드 동시 작업)

| ID | 대상 | 현 문서 | 실 상태 | 액션 |
|----|------|---------|---------|------|
| A1 | P1-10 Data Import | `00_INDEX.md` Complete | `ConnectorWizard.tsx`가 `ts-nocheck`, `parseConnectorSummary` 등 헬퍼 미구현 | INDEX를 **"In Progress (Postgres only)"** 로 정정 + C1에서 마감 |
| A2 | P0-07 Observability | "1-click support bundle export 가능" 로 완료 뉘앙스 | support bundle ✅ / **crash reporting 자체 미통합** | `P0_07_*.md` 현구현 상태 섹션에 crash reporting 별도 트랙으로 명시, 인프라 선정 후 범위 확정 |
| A3 | 00_INDEX 체크리스트 | P0-07 한 줄 ✅ | 세분화 필요 | "support bundle ✅ / crash reporting ⏳" 로 분리 |

---

## B. 인증서 조달과 무관한 P0 잔존 — 지금 즉시 가능

| ID | 항목 | 잔존 작업 | 근거 |
|----|------|----------|------|
| B1 | **P0-01 Phase 3 Sandbox UI** | 런타임 차단 이벤트(workspace escape, 메모리 초과)를 채팅/분석 UI에서 사용자에게 명시적으로 표출 | `P0_01_*.md`: "Phase 3 UI 잔존" |
| B2 | P0-02 마무리 | legacy 평문 config 잔존 경로 마이그레이션 테스트 보강, `token_store` 엣지 케이스 통합 테스트 | `P0_02_*.md` In Progress 근거 유지 |
| B3 | P0-04 migration 규약 | v3 이후 schema 변경 시 migration 추가 절차 문서화 (현 runner 동작 양호) | `P0_04_*.md` |
| B4 | **P0-06 Electron smoke Playwright** | clean-install 후 온보딩→샘플 분석까지 Playwright spec 최소 1종 (서명 없는 dev 바이너리 대상부터) | 감사 결과: Electron spec 0건 |

---

## C. P1 마무리

| ID | 항목 | 잔존 작업 |
|----|------|----------|
| C1 | **P1-10 Postgres connector 마감** | `ts-nocheck` 제거, `parseConnectorSummary` 및 validation 헬퍼 구현, Postgres만 GA 선언 — BigQuery/Snowflake는 후속 스프린트로 분리 명시 |
| C2 | P1-12 Export/Reporting 검증 | PDF/docx/xlsx/ipynb IPC 핸들러 존재 확인됨 — 실제 생성 엔진 end-to-end 테스트 + 샘플 산출물 저장소 동봉 |
| C3 | P1-13 접근성 audit | i18n 키 배선 완료 — ARIA/키보드 네비게이션/포커스 트랩 실측 (`OnboardingWizard`, `SettingsPanel`, `DisconnectOverlay` 우선) |

---

## D. 인증서 조달 대기 (코드 작업 불필요)

| ID | 항목 | 차단 원인 |
|----|------|----------|
| D1 | P0-05 SmartScreen / Gatekeeper 실검증 | Windows EV 인증서 / Apple Developer ID 조달 대기 |
| D2 | P1-14 서명된 업데이트 채널 실검증 | D1 선행 |
| D3 | P0-06 signed binary 기반 full E2E | D1 선행 (B4로 사전 검증 가능) |

조달 담당/ETA 확인 필요.

---

## 우선순위 로드맵

### Sprint 1 (즉시 — 1~2일)
- [x] 본 문서 작성 (이 파일)
- [x] **A1**: `00_INDEX.md` P1-10 상태 → "In Progress (Postgres only)" *(2026-04-15)*
- [x] **A3**: `00_INDEX.md` P0-07 체크리스트를 a/b/c 로 분리 *(2026-04-15)*
- [x] **A2**: `P0_07_*.md` 헤더 + "현재 구현 상태" 섹션을 실측 기준(crash reporting ⏳)으로 갱신 *(2026-04-15)*
- [x] **A1 부속**: `P1_10_data_import_ux.md` 에 `ts-nocheck` 존재 명시 + Postgres GA 잔존 작업 기술 *(2026-04-15)*
- [x] **B1**: P0-01 Phase 3 sandbox UI 완료 — `sandbox.violation` 이벤트 emit (5 tests),
  `SandboxApprovalModal` (blocking, textarea, Esc=reject), `SandboxViolationToast`
  (8s auto-dismiss, max 3 visible), App.tsx 마운트, typecheck/pytest 모두 green *(2026-04-15)*

### Sprint 2 (3~5일)
- [x] **C1**: P1-10 Postgres connector 마감 — `ts-nocheck` 제거, typecheck clean.
  헬퍼는 이미 모두 구현되어 있었고 디렉티브만 stale했음. backend RPC 26 tests green
  (`test_connector_config.py` 20 + `test_connector_factory.py` 6). *(2026-04-15)*
- [x] **B4**: Electron Playwright smoke spec — `tests/smoke/diagnostic-window.spec.ts`
  로 backend startup 실패 → P0-03 diagnostic window 표출 검증. 두 개 env hook 추가:
  `DS_AGENT_BACKEND_COMMAND` (백엔드 명령 오버라이드, ops/test 양용),
  `DS_AGENT_E2E_USE_BUILT_RENDERER=1` (Vite dev 서버 없이 build 결과물 로드).
  `npm run test:e2e:smoke` 로 실행, **PASS**. *(2026-04-15)*
- [ ] **A2**: crash reporting 도구 선정 및 통합 설계 (Sentry vs 자체 엔드포인트)

### Sprint 3 (1~2주)
- [x] **C2**: export 엔진 end-to-end 검증 — 기존 테스트 16 (engine) + 7 (workspace)
  이 이미 실측 검증 (python-docx open / openpyxl load_workbook / numeric 타입 / path
  traversal). 한국어 파일명/컨텐츠 보존 케이스 2 추가. **48 tests green**. *(2026-04-15)*
- [x] **C3**: 접근성 1차 audit — 7개 modal/overlay 컴포넌트(SandboxApprovalModal,
  SandboxViolationToast, FilePreviewModal, PlotGallery modal, DiagnosticPanel,
  DisconnectOverlay, SettingsPanel)에 `role`/`aria-modal`/`aria-labelledby`/
  `aria-describedby`/`aria-label`/`aria-hidden`/`aria-live` 보강. typecheck clean.
  잔존 (post-beta): 진정한 focus trap, axe-core 자동 측정, 단축키 헬프 패널. *(2026-04-15)*
- [x] **B2**: P0-02 degraded-mode operator UX — `describe_secret_storage()` 추가, CLI banner 에 in-memory fallback 경고 표시, 단위 테스트 2 cases. *(2026-04-15)*
- [x] **B3**: P0-04 migration 작성 규약 문서화 — schema bump → 함수 작성 → registry 등록 → 테스트 → 백업 → 다른 저장소 확장 7-step 절차를 plan 파일에 추가. v3→v4 (observability defaults) migration 도 발견하여 plan 갱신. *(2026-04-15)*

### Sprint 1 추가 정정 (2026-04-15)
- [x] **P0-07 재감사**: 1차 감사가 잘못된 결론을 냈음. 실제로는 Sentry SDK
  통합 (`sentry_backend.py`), Electron `@sentry/electron/main`, DSA-* 에러 코드
  카탈로그 (`error_mapping.py`), 온보딩 3-choice telemetry consent 모두 구현
  완료. 활성화에 필요한 것은 DSN 조달뿐. INDEX/plan 정정.
- [x] **헤더 정합성 정정 (2026-04-15 마감)**:
  - P0-02: "In Progress" → "Complete (코드) / 멀티플랫폼 keyring 실측 대기".
    follow-up 4건 재분류 — degraded UX ✅(B2), packaged smoke ⏳(P0-05), 멀티플랫폼 keyring
    실측 ⏳(외부), broader redaction → post-beta.
  - P0-04: "In Progress" → "Complete (config.yaml) / 타 저장소는 post-beta".
    SQLite session DB / auth profiles / domain KB / project store migration runner 연결은
    backward-incompatible 변경 발생 시점에 재개.
  - P1-10 connector_gui_design: "In Progress" → "Complete for Postgres GA · BigQuery/
    Snowflake UI polish는 post-beta". backend/UI 양쪽 다 존재, 실 운영 회귀만 계정 확보
    시점에.

## 최종 상태 (2026-04-15 마감)

코드 측 내부 작업 완료. 베타 출시 차단 요인은 전부 외부 의존:

| 항목 | 차단 원인 |
|------|----------|
| P0-05 | Windows EV 인증서 + Apple Developer ID 조달 |
| P0-06 happy-path E2E | P0-05 의존 |
| P0-07 활성화 | Sentry DSN 발급 |
| P1-14 서명된 자동업데이트 | P0-05 의존 |
| P0-02 멀티플랫폼 keyring 실측 | 서명 바이너리 + 플랫폼별 실기 |

### 인증서 조달 후 (병렬 가능)
- [ ] **D1**: signed 바이너리로 SmartScreen/Gatekeeper 실검증
- [ ] **D2**: 서명된 업데이트 채널 검증
- [ ] **D3**: B4 위에 signed E2E 확장

---

## 베타 출시 차단 요인 (정제)

1. **EV 코드 서명 / Apple Developer ID 조달** — 외부 의존 (D1~D3)
2. **P0-01 Phase 3 Sandbox UI** — B1, 내부 작업으로 해결 가능
3. **Electron Playwright E2E** — B4, 내부 작업으로 해결 가능
4. **P1-10 Postgres connector 마감** — C1, 내부 작업 (문서상 Complete 주장은 정정 필요)
5. **P0-07 crash reporting 범위 확정** — A2, 범위 결정 후 구현

**내부 해결 가능한 4건(B1/B4/C1/A2)을 먼저 끝내면**, 나머지는 인증서 조달 완료 시점에 맞물려 베타 릴리스 윈도우 형성.

---

## 문서 유지보수 규약

- 각 plan 파일 최상단 `**상태**` 라인은 **실측 기준**으로 유지
- 감사 시점(2026-04-15) 이후 변경 시 해당 plan 파일의 "현재 구현 상태" 섹션에 날짜와 함께 갱신
- `00_INDEX.md` 체크리스트는 plan 파일 상태와 항상 동기화
- 본 `P_NEXT_STEPS_*.md` 는 스프린트 종료 시점마다 새 날짜 버전으로 신규 작성 (이전 버전은 아카이브)
