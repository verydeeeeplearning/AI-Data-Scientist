# INTEGRATION_POINTS ??PLAN 媛?肄붾뱶 ?묒젏 留ㅽ듃由?뒪

?щ윭 PLAN???숈씪 ?뚯씪/紐⑤뱢??touch?섎뒗 吏?먯쓣 紐낆떆. **agent???먭린 PLAN ?됰쭔 異붽?/?섏젙**?쒕떎.

---

## 1. ?ъ슜 諛⑸쾿

### ?묒뾽 ??- 蹂몄씤 PLAN??짠10 ?섏〈?깆뿉 紐낆떆???뚯씪?ㅼ씠 蹂??쒖뿉 ?덈뒗吏 ?뺤씤
- ?숈씪 ?뚯씪???ㅻⅨ PLAN(?뱁엳 吏꾪뻾 以????쒖떆?섏뼱 ?덉쑝硫???ACTIVE_WORK ?뺤씤 + 異⑸룎 寃??
### ?묒뾽 以?- PLAN??紐낆떆?섏? ?딆븯???뚯씪??touch?섍쾶 ?섎㈃ 蹂??쒖뿉 異붽?
- ?곹깭: `?덉긽 (planned)` / `吏꾪뻾以?(in_progress)` / `?꾨즺 (done)`

### ?묒뾽 ??- 蹂몄씤 PLAN ?됱쓣 `?꾨즺` 濡?媛깆떊
- ?ㅼ젣 touch???뚯씪 紐⑸줉???뺥솗??湲곕줉 (?덉긽怨??ㅻⅤ硫?媛깆떊)

---

## 2. Frontend ?듭떖 ?뚯씪蹂??묒젏

## Latest Reconciled Updates (2026-04-19)

- Phase 1 PLAN_01: `electron/src/renderer/stores/i18nStore.ts`, `electron/src/renderer/components/settings/LocaleSelector.tsx`, `SettingsPanel.tsx`, and `OnboardingWizard.tsx` already provide a store-backed `ko/en/ja` locale switching baseline.
- Phase 1 PLAN_03: `electron/src/renderer/components/chat/ToolActivity.tsx` is now live-wired to `ExecutionTimeline.tsx`, with `useChat.ts` / `chatStore.ts` preserving per-tool `result` payloads and announcing stage transitions.
- Phase 1 PLAN_04: `electron/src/renderer/hooks/useAgent.ts` now uploads through `POST /api/workspace/upload`, and `FileUpload.tsx` renders `SchemaPreviewCard.tsx` / `SuggestedActions.tsx` immediately after upload. Follow-up slice (agent-w1d-upload-ui-002, 2026-04-19): suggested-action button wiring (`buildSuggestedActionPrompt`, `useSuggestedAction`, `configStore.pendingStarterPrompt`), global drag-drop overlay (`components/workspace/GlobalDropOverlay.tsx` mounted via single line in `App.tsx`, listens window events through `hooks/useGlobalFileDrop.ts`), error-state polish (`UploadErrorState.tsx` + `application/workspace/classifyUploadError.ts`), Wave 0 a11y primitives (focus trap, reduced-motion, aria-live announcements), and Clean Architecture fix on `application/workspace/uploadFile.ts` via new `uploadFilePort.ts`. All Wave 0 contract tests stay green.
- Phase 1 PLAN_06: renderer-side capability grouping landed in `ModelSelector.tsx`, `OnboardingWizard.tsx`, `useModels.ts`, `domain/llm/*`, `application/llm/*`; backend capability metadata + provider.models RPC enrichment + provider tooltip (4-week migration) + dedicated tests landed by agent-w1c-models-backend-002 (2026-04-19). `OnboardingWizard.tsx` typecheck breakage from leader slice still pending follow-up.
- Shared docs note: W1-A and W1-C no longer have active locks in `ACTIVE_WORK.md`; W1-E remains the active Wave 1 lock.

---
### `electron/src/renderer/App.tsx`

| PLAN | 蹂寃??댁슜 | ?곹깭 |
|------|----------|------|
| Phase 1 PLAN_01 i18n | I18nProvider wrap | ?덉긽 |
| Phase 1 PLAN_02 Mission Header | Layout ?곷떒??Mission Header (ChatPanel 상단 mount, configStore.missionHeaderEnabled 분기) | 완료 (codex-w1e + agent-phaseC-w1e-finalize-001, 2026-04-19) |
| Phase 1 PLAN_04 Drag-drop upload | `<GlobalDropOverlay onUploadFile={uploadFile} />` 단일 mount + import | 완료 (agent-w1d-upload-ui-002, 2026-04-19) |
| Phase 1 PLAN_05 Sidebar collapse | Layout ???숈쟻??| ?덉긽 |
| Phase 2 PLAN_01 IA | Router 5+1 area | ?덉긽 |
| Phase 2 PLAN_04 Workspace | Layout 3-pane | ?덉긽 |
| Phase 4 PLAN_01 Design system | Theme provider | ?덉긽 |
| Phase 4 PLAN_02 Density | DensityProvider | ?덉긽 |

### `electron/src/renderer/components/layout/Sidebar.tsx`

| PLAN | 蹂寃??댁슜 | ?곹깭 |
|------|----------|------|
| Phase 1 PLAN_05 Sidebar collapse | collapsible rail, tooltip, shortcut, reduced-motion, focus restore | ?꾨즺 (agent-w1-sidebar-001, 2026-04-19) |
| Phase 2 PLAN_01 IA | ??ぉ 5+1 area濡??ш뎄??| ?덉긽 |

### `electron/src/renderer/components/chat/ChatPanel.tsx` (?먮뒗 ?숇벑)

| PLAN | 蹂寃??댁슜 | ?곹깭 |
|------|----------|------|
| Phase 1 PLAN_02 Mission Header | ?곷떒 ?곸뿭 異붽? | ?덉긽 |
| Phase 2 PLAN_02 Result Cards | 硫붿떆吏 ?뚮뜑留곸뿉??移대뱶 異붿텧/?쒖떆 | ?덉긽 |

### `electron/src/renderer/stores/agentStore.ts`

| PLAN | 蹂寃??댁슜 | ?곹깭 |
|------|----------|------|
| cross_cutting PLAN_02 Sub-Phase 1.2 | rename ??executionStore + ?꾨찓??reducer 異붿텧, agentStore.ts ??backward-compat shim | **?꾨즺** (agent-w0-foundation-001, 2026-04-19) ??chat/run ? chatStore/runtimeStore 媛 ?대? 遺꾨━?섏뼱 ?덉뼱 1-rename ?쇰줈 PLAN ?섎룄 ?ъ꽦. ?ㅼ젣 splitting ? Phase 2 ??異붽? 寃?? |

### `electron/src/renderer/stores/i18nStore.ts`

| PLAN | 蹂寃??댁슜 | ?곹깭 |
|------|----------|------|
| Phase 1 PLAN_01 i18n (Phase D) | i18next shim 으로 rewrite (~150 LOC). useI18n() + useI18n(selector) overload. namespace 자동 추론 + dotted prefix strip. 30+ consumer 코드 변경 0. ADR-0011. | 완료 (agent-phaseD-w1a-full-i18n-001, 2026-04-19) |
| Phase 1 PLAN_05 Sidebar collapse | collapse tooltip / aria-live / 異붽? tab ?쇰꺼 踰덉뿭 ??| ?꾨즺 (agent-w1-sidebar-001, 2026-04-19) |
| Phase 1 PLAN_06 Model labels | capability group / badge / recommendation copy + llm.provider_label_legacy keys (en/ko/ja) | DONE (leader copy 2026-04-19, llm.provider_label_legacy by agent-w1c-models-backend-002 2026-04-19) |

### `electron/src/renderer/components/sidebar/ModelSelector.tsx`

| PLAN | 蹂寃??댁슜 | ?곹깭 |
|------|----------|------|
| Phase 1 PLAN_06 Model labels | capability-grouped selector + recommendation badge + capability badges + provider tooltip (MIGRATION-2026-05-17) | DONE (leader UI 2026-04-19, provider tooltip + i18n key + tests by agent-w1c-models-backend-002 2026-04-19) |

### `electron/src/renderer/components/settings/OnboardingWizard.tsx`

| PLAN | 蹂寃??댁슜 | ?곹깭 |
|------|----------|------|
| Phase 1 PLAN_01 i18n | locale selection + onboarding copy baseline | ?꾨즺 湲곗????뺣낫 (agent-w1-i18n-001, 2026-04-19) |
| Phase 1 PLAN_06 Model labels | capability-grouped connect step, recommendation copy, badge surface | 吏꾪뻾以?(leader, 2026-04-19) |

### `electron/src/renderer/components/chat/ToolActivity.tsx` / `electron/src/renderer/components/runtime/ExecutionTimeline.tsx`

| PLAN | 蹂寃??댁슜 | ?곹깭 |
|------|----------|------|
| Phase 1 PLAN_03 Execution Timeline | `useExecutionTimeline` hook + `selectExecutionTimeline` selector + `ExecutionTimeline.tsx`/`StageRow.tsx`/`RawToolLog.tsx`/`StageOutcomeLink.tsx`, feature flag(`useNewExecutionTimeline`) 분기, 87 backend tool 매핑, i18n `execution.*` ko/en/ja, `LegacyToolActivity.tsx` rollback 안전망. `ChatMessage.tsx` 에 anchor id 1줄 추가 (jump target). | 완료 (agent-w1f-timeline-finalize-002, 2026-04-19) |
| Phase 3 PLAN_01 Plan Tree | Layer 2 (reasoning) 異붽? | ?덉긽 |

### `electron/src/renderer/components/sidebar/SidebarItem.tsx`

| PLAN | 蹂寃??댁슜 | ?곹깭 |
|------|----------|------|
| Phase 1 PLAN_05 Sidebar collapse | rail item label/tooltip wrapper, collapsed a11y surface | ?꾨즺 (agent-w1-sidebar-001, 2026-04-19) |

### `electron/src/renderer/hooks/useKeyboardShortcut.ts`

| PLAN | 蹂寃??댁슜 | ?곹깭 |
|------|----------|------|
| Phase 1 PLAN_05 Sidebar collapse | `Ctrl+\` / `Cmd+\` shortcut binding helper | ?꾨즺 (agent-w1-sidebar-001, 2026-04-19) |

### `electron/src/renderer/hooks/useSidebarCollapse.ts`

| PLAN | 蹂寃??댁슜 | ?곹깭 |
|------|----------|------|
| Phase 1 PLAN_05 Sidebar collapse | localStorage persistence + responsive collapse state | ?꾨즺 (agent-w1-sidebar-001, 2026-04-19) |

### `electron/src/renderer/components/sandbox/SandboxApprovalModal.tsx`

| PLAN | 蹂寃??댁슜 | ?곹깭 |
|------|----------|------|
| Phase 2 PLAN_06 Approval v2 | ?꾨㈃ ?ъ꽕怨?| ?덉긽 |
| Phase 3 PLAN_05 Risk-tier Policy | "?뺤콉???먮룞 ?덉슜" ?듭뀡 異붽? | ?덉긽 |

### `electron/src/renderer/components/settings/SettingsPanel.tsx` (?먮뒗 ?숇벑)

| PLAN | 蹂寃??댁슜 | ?곹깭 |
|------|----------|------|
| Phase 1 PLAN_01 i18n | LocaleSelector 異붽? | ?덉긽 |
| Phase 1 PLAN_06 Model labels | capability terminology ?뺣젹 (?ㅼ젙 surface ?꾩냽) | ?덉긽 |
| Phase 2 PLAN_01 IA | Admin area濡?遺꾪빐 | ?덉긽 |
| Phase 4 PLAN_02 Density | DensityMode ?좏깮 異붽? | ?덉긽 |

### `electron/src/renderer/components/sidebar/FileUpload.tsx`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 1 PLAN_04 Drag-drop upload | 100MB 검증 + SchemaPreviewCard 표시 + UploadErrorState 통합 + announce() | 완료 (agent-w1d-upload-ui-002, 2026-04-19) |

### `electron/src/renderer/components/layout/MainPanel.tsx`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 1 PLAN_04 Drag-drop upload | onUploadFile prop 전달 (기존 유지, FileUpload 으로 wiring) | 완료 (leader 1차 + agent-w1d-upload-ui-002 보강, 2026-04-19) |

### `electron/src/renderer/components/workspace/` (신규 디렉토리)

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 1 PLAN_04 Drag-drop upload | `SchemaPreviewCard.tsx`, `SuggestedActions.tsx`, `GlobalDropOverlay.tsx`, `UploadErrorState.tsx` | 완료 (leader 1차 + agent-w1d-upload-ui-002 보강, 2026-04-19) |


### Tailwind config / theme

| PLAN | 蹂寃??댁슜 | ?곹깭 |
|------|----------|------|
| Phase 1 PLAN_01 i18n (Phase D) | fontFamily.sans extend — Inter / Noto Sans KR / Noto Sans JP / system fallback. fontFamily.mono 보존. | 완료 (agent-phaseD-w1a-full-i18n-001, 2026-04-19) |
| Phase 4 PLAN_01 Design system | ?좏겙 ?쒖뒪???꾩엯 | ?덉긽 |
| Phase 4 PLAN_02 Density | Density-aware spacing tokens | ?덉긽 |

### `electron/src/renderer/styles/globals.css`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| cross_cutting PLAN_01 (Wave 0 Sub-Phase 1.2) | `:focus-visible` outline + `@media (prefers-reduced-motion: reduce)` | 완료 (agent-w0-foundation-001, 2026-04-19) |
| cross_cutting PLAN_01 (Phase B finalize) | dark/light `--ds-muted` / `--ds-accent` / `--ds-accent-hover` 토큰 contrast 보강 (WCAG 1.4.3) + `button.bg-ds-accent { color: var(--ds-bg) }` rule (light accent 위 dark text 강제) | 완료 (agent-phaseB-a11y-baseline-001, 2026-04-19) |
| Phase 1 PLAN_01 i18n (Phase D) | body font-family chain (Inter, Noto Sans KR/JP, system fallback) + ko/ja line-height + word-break tokens. Phase B contrast 토큰 보존. | 완료 (agent-phaseD-w1a-full-i18n-001, 2026-04-19) |

### `electron/src/renderer/components/settings/PrivacySettings.tsx`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| cross_cutting PLAN_01 (Phase B) | ToggleCard switch button 에 `aria-label={title}` (button-name rule fix) | 완료 (agent-phaseB-a11y-baseline-001, 2026-04-19) |

### `electron/src/renderer/components/settings/CostSettings.tsx`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| cross_cutting PLAN_01 (Phase B) | budget input + warning select 에 `aria-label` (label / select-name rule fix) | 완료 (agent-phaseB-a11y-baseline-001, 2026-04-19) |

### `electron/src/renderer/components/settings/PolicyStudio.tsx`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| cross_cutting PLAN_01 (Phase B) | action-matrix select 셀에 `aria-label` (select-name rule fix) | 완료 (agent-phaseB-a11y-baseline-001, 2026-04-19) |

### `electron/src/renderer/i18n.ts` (신규)

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 1 PLAN_01 i18n (Phase D) | i18next bootstrap — initReactI18next, 36 inline JSON imports, lng detection (i18nextLng → ds-agent-locale legacy migration → navigator.language → en), document.documentElement.lang sync. ADR-0011. | 완료 (agent-phaseD-w1a-full-i18n-001, 2026-04-19) |

### `electron/public/locales/{ko,en,ja}/{12 namespaces}.json` (신규 디렉토리)

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 1 PLAN_01 i18n (Phase D) | 12 namespace × 3 locale = 36 JSON 파일. flat-key form (e.g. `"header.title"`). ko/en/ja 키 set 동일 (511 키 / namespace 합계). approval/trust/chat namespace 는 placeholder 빈 객체 (Phase 2 PLAN_05/06 에서 확장). | 완료 (agent-phaseD-w1a-full-i18n-001, 2026-04-19) |

### `electron/scripts/lint-i18n.mjs` (신규)

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 1 PLAN_01 i18n (Phase D) | namespace parity (ko/en/ja key set 동일) + Hangul literal CI gate (renderer/components, hooks 안에 한국어 string literal 0). exit 1 on violation. | 완료 (agent-phaseD-w1a-full-i18n-001, 2026-04-19) |

### `.github/workflows/i18n.yml` (신규)

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 1 PLAN_01 i18n (Phase D) | Windows runner, npm ci → lint:i18n:ci → test:contract:i18n-namespaces (10 cases) → test:contract:i18n-store-shim (13 cases). Phase A wave0 / Phase B a11y workflow 와 별도 job, 충돌 0. | 완료 (agent-phaseD-w1a-full-i18n-001, 2026-04-19) |

### `electron/src/renderer/components/semantic/MetricSourcePanel.tsx`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase 1 PLAN_01 i18n (Phase D) | Hangul literal 2 건 (`'이탈률'` SUGGESTED_QUERIES, placeholder 'Hover ... / 이탈률 / LTV') → `useI18n` + `cards.metricSource.*` 키로 치환. | 완료 (agent-phaseD-w1a-full-i18n-001, 2026-04-19) |

### `electron/scripts/lint-a11y.mjs`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| cross_cutting PLAN_01 (Wave 0 Sub-Phase 1.1) | placeholder + SKIP on missing | 완료 (agent-w0-foundation-001, 2026-04-19) |
| cross_cutting PLAN_01 (Phase B) | strict mode — exit 1 on missing axe, version detect on success (ADR-0010) | 완료 (agent-phaseB-a11y-baseline-001, 2026-04-19) |

### `electron/tests/e2e/a11y/` (신규 디렉토리)

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| cross_cutting PLAN_01 (Phase B) | `_helpers.ts` + 5 spec (`onboarding/mission/chat/settings/sidebar`) WCAG 2.1 A+AA axe gate | 완료 (agent-phaseB-a11y-baseline-001, 2026-04-19) |

### `.github/workflows/a11y.yml` (신규)

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| cross_cutting PLAN_01 (Phase B) | windows-latest, PyInstaller backend build → npm ci → lint:a11y → test:e2e:a11y. Phase A 의 wave0 gate 와 별도 job | 완료 (agent-phaseB-a11y-baseline-001, 2026-04-19) |

---

## 3. Backend ?듭떖 ?뚯씪蹂??묒젏

### `src/ds_agent/api/routes/`

| ?뚯씪 | PLAN | ?곹깭 |
|------|------|------|
| `mission.py` (신규) | Phase 1 PLAN_02 — `GET /api/mission/current`, `POST /api/mission/pause` (PauseAgentUseCase) | 완료 (codex-w1e + agent-phaseC-w1e-finalize-001, 2026-04-19) |
| `workspace.py` 확장 | Phase 1 PLAN_04, Phase 2 PLAN_04 | 완료 (codex-w1d backend + agent-w1d-upload-ui-002 UI wiring, 2026-04-19) — `POST /api/workspace/upload` end-to-end (sidebar FileUpload + global drag-drop overlay + suggested-action prompt prefill) |
| `trust.py` (?좎꽕) | Phase 2 PLAN_03 | ?덉긽 |
| `approval.py` ?뺤옣 | Phase 2 PLAN_06 | ?덉긽 |
| `onboarding.py` (?좎꽕) | Phase 2 PLAN_05 | ?덉긽 |
| `runs.py` ?뺤옣 (checkpoints, branches) | Phase 3 PLAN_03 | ?덉긽 |
| `policy.py` (?좎꽕) | Phase 3 PLAN_05 | ?덉긽 |
| `export.py` ?뺤옣 | Phase 2 PLAN_04, Phase 3 PLAN_06 | ?덉긽 |

### `src/ds_agent/application/use_cases/`

| ?뚯씪 | PLAN | ?곹깭 |
|------|------|------|
| `preview_uploaded_file_usecase.py` (repo actual path: `application/usecases/preview_uploaded_file_usecase.py`) | Phase 1 PLAN_04 | ?꾨즺 (codex-w1d, 2026-04-19) |
| `schema_preview_dto.py` (repo actual path: `application/dtos/schema_preview_dto.py`) | Phase 1 PLAN_04 | ?꾨즺 (codex-w1d, 2026-04-19) |

### `src/ds_agent/infrastructure/llm/prompt_builder.py`

| PLAN | 蹂寃??댁슜 | ?곹깭 |
|------|----------|------|
| Phase 2 PLAN_02 Result Cards | 4醫?移대뱶 emit 媛?대뱶 system prompt | ?덉긽 |
| Phase 3 PLAN_01 Reasoning Trace | 4-tuple emit 媛?대뱶 異붽? | ?덉긽 |

### `src/ds_agent/infrastructure/llm/model_registry.py` (actual: `src/ds_agent/providers/model_metadata.py`)

| PLAN | Change | Status |
|------|--------|--------|
| Phase 1 PLAN_06 Model labels | capability_group / capability_badges / recommended_for / providerLabelLegacy curated registry + heuristic fallback; provider.models RPC enrichment; model_registry.py path absent in codebase, implemented as new providers/model_metadata.py | DONE (agent-w1c-models-backend-002, 2026-04-19) |

### `src/ds_agent/channels/bundled/telegram/` + `domain/notification/`

**Telegram Notification + PII masking + deep link** (added 2026-04-20 by agent-w4d-telegram-finalize-001)

| PLAN | Change | Status |
|------|--------|--------|
| Phase 4 PLAN_04 Telegram close-out | `domain/notification/{notification,quiet_hours,digest}.py` (5-bucket category, tz-aware quiet hours, daily/weekly digest aggregation - zero external deps) + `application/use_cases/{send_notification,check_quiet_hours,build_digest}_usecase.py` (port-based) + `channels/bundled/telegram/message_builder.py` (4096 truncation -> 3-line summary + Open in Electron deep-link button via W4-C `build_deep_link_uri`; PII masking via `infrastructure/pii_detector` + sensitive-keyword set: email/ssn/phone/password/token/api_key/...) + `channels/bundled/telegram/callback_handler.py` (approval inline keyboard wire-format `approval:<approve\|reject>:<id>[:<reason>]`, 2s response budget with `on_late` hook) + `gateway/telegram_runner.py` dispatches runtime alerts/digests through `dispatch_notification()` so callback actions and deep-link buttons coexist on the live operator path. ERROR/APPROVAL bypass quiet hours; INFO/MILESTONE/DIGEST suppressed inside window. 57 new tests across runner/message-builder migration coverage, 0 regressions in `test_telegram_plugin.py`. | DONE (agent-w4d-telegram-finalize-001 + follow-up migration, 2026-04-20) |

### `src/ds_agent/infrastructure/telegram/`

| PLAN | 蹂寃??댁슜 | ?곹깭 |
|------|----------|------|
| Phase 4 PLAN_04 Telegram redesign | ?꾨㈃ ?ы룷吏?붾떇 | ?덉긽 |

---

## 4. 怨듭쑀 ?꾨찓??媛앹껜

### `Mission / Goal / TaskContract`

| PLAN | ?ъ슜 諛⑹떇 | ?곹깭 |
|------|---------|------|
| Phase 1 PLAN_02 Mission Header | 議고쉶 | ?덉긽 |
| Phase 2 PLAN_05 Onboarding | ?앹꽦 | ?덉긽 |
| Phase 3 PLAN_03 Checkpoint | snapshot???ы븿 | ?덉긽 |

### `ResultCard 4醫?

| PLAN | ??븷 | ?곹깭 |
|------|------|------|
| Phase 2 PLAN_02 | ?뺤쓽/CRUD | ?덉긽 |
| Phase 2 PLAN_03 | TrustStrip 遺李?| ?덉긽 |
| Phase 2 PLAN_04 | Workspace???쒖떆 | ?덉긽 |
| Phase 3 PLAN_03 | promote_to_artifact | ?덉긽 |
| Phase 3 PLAN_06 | audience蹂??뚮뜑 | ?덉긽 |

### `WS Event Stream`

| PLAN | 異붽? ?대깽??| ?곹깭 |
|------|-----------|------|
| Phase 1 PLAN_02 | `mission.context.updated` (with optional `delta: { dataSources?, deliverables?, constraints? }` per Phase C) | 완료 (codex-w1e baseline + agent-phaseC-w1e-finalize-001 delta payload, 2026-04-19) |
| Phase 1 PLAN_03 | (湲곗〈 tool event ?쒖슜) | ??|
| Phase 2 PLAN_02 | `card.created`, `card.updated`, `card.pinned` | ?덉긽 (registry pre-seeded by W0) |
| Phase 3 PLAN_01 | `plan.created`, `plan.updated`, `plan.replanned`, `reasoning.emitted` | ?덉긽 (registry pre-seeded by W0) |
| Phase A finalization | useWebSocket onmessage envelope-aware + version-major-mismatch graceful skip; envelope ts ms 정수 (ADR-0009); CI wave0 gate (frontend-quality.yml) | 완료 (agent-phaseA-wave0-fixes-001, 2026-04-19) |

### `electron/src/renderer/hooks/useWebSocket.ts`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase A finalization (Wave 0 F1) | onmessage 가 parseEnvelope + validateEventPayload 통과; WsEnvelopeError graceful warn+skip; unknown-type / major-mismatch / invalid-shape 모두 console.warn + 무시 | 완료 (agent-phaseA-wave0-fixes-001, 2026-04-19) |

### `electron/scripts/lintArchCore.cjs`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase A finalization (Wave 0 F3) | multi-line static/dynamic/require import regex (/g + DOTALL); tsconfig.json compilerOptions.paths 파싱 + `@/*` alias resolve; scanProject(rootDir, options) 시그니처 확장; loadTsconfigPaths/resolveAlias export | 완료 (agent-phaseA-wave0-fixes-001, 2026-04-19) |

### `electron/src/renderer/infrastructure/ws/eventSchemaRegistry.ts`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase A finalization (Wave 0 F-extra) | `validateEventPayload(type, payload, envelopeVersion?)` 시그니처 확장; ValidationResult `'major-mismatch'` reason 추가; major mismatch 또는 lower-minor envelope 거부 (forward compat 만 허용); backward compat (envelopeVersion 생략 시 version gate skip) | 완료 (agent-phaseA-wave0-fixes-001, 2026-04-19) |

### `src/ds_agent/api/event_envelope.py`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase A finalization (Wave 0 F5) | `wrap_event` default ts = `int(time.time() * 1000)` (ms 정수). ADR-0009 — JS Date.now() 표준 + 분산 시스템 표준 일치 | 완료 (agent-phaseA-wave0-fixes-001, 2026-04-19) |

### `.github/workflows/frontend-quality.yml`

| PLAN | 변경 내용 | 상태 |
|------|----------|------|
| Phase A finalization (Wave 0 F2) | wave0-baseline job (npm ci + lint:arch + test:contract:wave0 + typecheck) + envelope-python job (pytest envelope+callbacks) — 신규 workflow | 완료 (agent-phaseA-wave0-fixes-001, 2026-04-19) |
| cross_cutting PLAN_03 | envelope + versioning (紐⑤뱺 ?대깽??wrap) | **?꾨즺** (ADR-0007, agent-w0-foundation-001, 2026-04-19) |

---

## 5. 異⑸룎 ?닿껐 媛?대뱶

### ?숈씪 ?뚯씪??touch?댁빞 ????
1. **?쒖감 吏꾪뻾**: ?섏〈 愿怨꾧? ?덉쑝硫?紐낅갚???쒖꽌 (?? PLAN_05 sidebar ??PLAN_02 mission header)
2. **PR 遺꾨━**: 媛숈? ?뚯씪?대씪???ㅻⅨ ?⑥닔/?뱀뀡?대㈃ PR濡?遺꾨━
3. **癒몄? 異⑸룎**: 諛쒖깮 ??leader媛 寃곗젙 (?대뒓 PR???곗꽑 base)
4. **?ъ옉??*: ??PR 癒몄? ???ㅻⅨ PR??rebase

### ?숈씪 ?꾨찓??媛앹껜 ?뺤옣

- ?꾨뱶 異붽???backward compatible
- ?꾨뱶 ?쒓굅/蹂寃쎌? leader ?⑹쓽 + DECISIONS??ADR

---

## Wave 3 First Slice (2026-04-20)

### Renderer

| Surface | Integration | Status |
|---|---|---|
| `AreaMainPanel.tsx` | IA v2 only `Cmd/Ctrl + K` mount point for the new command palette | landed |
| `components/palette/` | `CommandPalette.tsx` + `CommandRow.tsx` render grouped command results with keyboard navigation | landed |
| `application/command/` | command registry helpers, lightweight fuzzy-ish search, and first-slice command builders | landed |
| `pages/runs/RunsPage.tsx` | `/runs` right rail now hosts `RunsCompareBoard` above the detail drawer | landed |
| `components/runtime/RunsCompareBoard.tsx` | runtime-run-driven compare board using `decisionOs.compareRuns` | landed |

### Event contract

| Surface | Integration | Status |
|---|---|---|
| `src/ds_agent/api/event_schemas.py` | canonical Python contract for `plan.created`, `plan.updated`, `plan.replanned`, `reasoning.emitted` | landed |
| `electron/src/renderer/types/events.ts` | matching TS payload types added to `EventPayloadMap` | landed |
| `electron/src/renderer/infrastructure/ws/eventSchemaRegistry.ts` | concrete plan/reasoning validators replace placeholder permissive schemas | landed |
| `electron/src/renderer/hooks/useWebSocket.ts` | envelope normalization + schema validation before dispatch for registered events | landed |
| `src/ds_agent/agent/core.py` | existing provider thinking path now also emits `reasoning.emitted` | landed |

### Deferred follow-ups

- Plan Tree UI / stage-linked reasoning panel / replan overlay
- workspace compare tab + artifact diff + decision trace diff
- command sources for files / slash / agent plus full focus trap parity
## Wave 3 Second Slice (2026-04-20)

### Runtime reasoning surface

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/components/runtime/ExecutionTimeline.tsx` | mounts `useReasoningTraceBridge(true)` so the timeline subscribes to `reasoning.emitted` and `plan.*` | landed |
| `electron/src/renderer/components/runtime/StageRow.tsx` | stage expansion now renders `ReasoningTracePanel` above the raw tool log | landed |
| `electron/src/renderer/components/runtime/ReasoningTracePanel.tsx` | shows per-stage reasoning cards with timestamp, plan-node ref, thinking, hypothesis, action, observation, and decision | landed |
| `electron/src/renderer/hooks/useReasoningTrace.ts` | bridges WS payloads into stage-linked trace entries using the current execution timeline | landed |
| `electron/src/renderer/stores/reasoningTraceStore.ts` | in-memory trace buffer and plan-state markers (`created`, `updated`, `replanned`) | landed |

### Checkpoint / resume surface

| Surface | Integration | Status |
|---|---|---|
| `src/ds_agent/api/ws_handler.py` (`run.start`, `AppState.start_run`) | `run.start` accepts `resumeFromCheckpoint: bool`; when set and a `JsonCheckpointStore` entry exists, it replays the checkpoint via `agent.run(resume_from_checkpoint=...)` and returns `resumedFromCheckpoint` in the run payload | landed (Wave 3 Fourth Slice) |
| `src/ds_agent/domain/entities/runtime_state.py` | `RunState.resumed_from_checkpoint` carries the replay flag through serialization | landed (Wave 3 Fourth Slice) |
| `electron/src/renderer/application/run/{resumeFromCheckpoint,resumeFromCheckpointPort}.ts` | renderer use case + port for resume-from-checkpoint with input guards | landed (Wave 3 Fourth Slice) |
| `electron/src/renderer/hooks/useResumeFromCheckpoint.ts` | composition root that binds the port to `rpc('run.start', { resumeFromCheckpoint: true })` | landed (Wave 3 Fourth Slice) |
| `electron/src/renderer/components/mission/MissionHeader.tsx` | `Resume via Chat` button now invokes the real RPC and surfaces resumed/no-checkpoint outcomes; clipboard prompt path is kept only as graceful fallback on RPC failure | landed (Wave 3 Fourth Slice) |
| `electron/src/renderer/components/runtime/RunDetailDrawer.tsx` | run inspector uses the same resume RPC; clipboard fallback retained on RPC failure | landed (Wave 3 Fourth Slice) |
| `electron/src/renderer/infrastructure/api/checkpointResume.ts` | shared prompt builder and clipboard helper kept as the resume message body and as the fallback path on RPC failure | landed |

### Save Checkpoint / Branch Run surface (Wave 3 Fifth Slice)

| Surface | Integration | Status |
|---|---|---|
| `src/ds_agent/runtime/checkpoint_store.py` (`JsonCheckpointStore.save_named/list_named/get_named`) | named checkpoints stored under `<workspace>/runtime/checkpoints/named/`, isolated from the implicit per-session checkpoint flow | landed (Wave 3 Fifth Slice) |
| `src/ds_agent/domain/entities/session_checkpoint.py` (`NamedCheckpoint`) | sibling dataclass to `SessionCheckpoint` carrying `id, session_id, name, transcript_step, created_at, description` | landed (Wave 3 Fifth Slice) |
| `src/ds_agent/application/use_cases/save_named_checkpoint_usecase.py` + `branch_run_usecase.py` | port-DI use cases (fakeable in tests); resolve transcript step from implicit `JsonCheckpointStore.load(session_id).step` with transcript-message fallback | landed (Wave 3 Fifth Slice) |
| `src/ds_agent/api/ws_handler.py` (`checkpoint.save`, `checkpoint.list`, `run.branch`) | new RPC handlers; `start_run` accepts `branched_from_run_id` keyword and threads it onto `RunState`; `_serialize_run` exposes `branchedFromRunId` | landed (Wave 3 Fifth Slice) |
| `src/ds_agent/domain/entities/runtime_state.py` (`RunState.branched_from_run_id`) | branch lineage marker through serialization | landed (Wave 3 Fifth Slice) |
| `electron/src/renderer/application/run/{saveCheckpoint,saveCheckpointPort,branchRun,branchRunPort}.ts` | renderer ports + use cases mirroring the existing `resumeFromCheckpoint*` pattern | landed (Wave 3 Fifth Slice) |
| `electron/src/renderer/hooks/{useSaveCheckpoint,useBranchRun}.ts` | composition roots binding ports to `rpc('checkpoint.save'\|'run.branch', ...)` | landed (Wave 3 Fifth Slice) |
| `electron/src/renderer/components/mission/MissionHeader.tsx` (Save Checkpoint button) | first slice uses `window.prompt` for name; surfaces success/failure via existing `setCheckpointResumeStatus` banner pattern | landed (Wave 3 Fifth Slice) |
| `electron/src/renderer/components/runtime/RunDetailDrawer.tsx` (Branch Run button) | first slice uses `window.prompt` for branch message; dedicated `branchStatus`/`branchError` banners | landed (Wave 3 Fifth Slice) |

### Plan replan + reasoning↔plan-node linkage surface (Wave 3 Fifth Slice)

| Surface | Integration | Status |
|---|---|---|
| `src/ds_agent/agent/ds_workflow_hooks.py` (`mark_replan`, `_emit_plan_replanned`, `record_reasoning_ref`, `current_active_stage_id`) | explicit replan trigger contract + reasoning↔stage linkage; auto-emits `plan.replanned` when `pre_tool_use` re-enters a previously-terminal stage | landed (Wave 3 Fifth Slice) |
| `src/ds_agent/agent/core.py` (reasoning emission) | reasoning events now carry a 12-hex `id` and a `planNodeId` resolved from the workflow tracker's active stage; calls `record_reasoning_ref` so the plan node's `reasoningRefs` lists every event id during its lifetime | landed (Wave 3 Fifth Slice) |
| `electron/src/renderer/application/runtime/applyPlanReplannedDiff.ts` | pure reducer applying `{added, removed, modified}` diff onto a plan-tree snapshot | landed (Wave 3 Fifth Slice) |
| `electron/src/renderer/stores/reasoningTraceStore.ts` (`applyReplanDiff`, `clearReplanHighlights`, `runId`, `setRunId`, `hydrateFromPersistence`, `clearPersistence`) | versioned localStorage snapshot (`ds-agent-plan-tree-snapshot`, v1); transient `replanAdded/Removed/ModifiedIds` for visual highlights | landed (Wave 3 Fifth Slice) |
| `electron/src/renderer/hooks/useReasoningTrace.ts` (reconnect-safe hydration) | rehydrates the persisted snapshot on WS reconnect with a 1.5s replacement window so live `plan.created` events take precedence; `task.started` clears persistence | landed (Wave 3 Fifth Slice) |
| `electron/src/renderer/components/runtime/PlanTreePanel.tsx` | added/removed/modified visual states with ~3000ms TTL + replanned timestamp pill | landed (Wave 3 Fifth Slice) |
| `electron/src/renderer/components/runtime/ReasoningTracePanel.tsx` | renders a `planNodeId` chip with looked-up node label | landed (Wave 3 Fifth Slice) |

### Audience View Switcher surface (Wave 3 Fifth Slice)

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/domain/workspace/audienceView.ts` | `AudienceView` ('ds'\|'exec'\|'ml'), `AUDIENCE_VIEW_PROFILES` (DS=all 5 tabs detail, Exec=summary+charts+export summary, ML=summary+tables+charts+files+export detail), `isAudienceView`, `getAudienceViewProfile` | landed (Wave 3 Fifth Slice) |
| `electron/src/renderer/application/workspace/applyAudienceView.ts` | pure helpers `applyAudienceViewToTabs`, `resolveActiveTabForAudience`, `applyAudienceViewToCard`, `emphasisToDisplayMode` | landed (Wave 3 Fifth Slice) |
| `electron/src/renderer/stores/workspaceStore.ts` (`audienceView`, `setAudienceView`, `loadAudienceView`, `__setAudienceViewStorageForTests`) | localStorage persistence under `ds-agent-workspace-audience-view`; invalid stored value falls back to `DEFAULT_AUDIENCE_VIEW` | landed (Wave 3 Fifth Slice) |
| `electron/src/renderer/components/workspace/AudienceViewSwitcher.tsx` | segmented control, ARIA radiogroup, arrow/Home/End nav, Check icon (no color-only signaling) | landed (Wave 3 Fifth Slice) |
| `electron/src/renderer/components/workspace/EvidenceWorkspace.tsx` | mounts the switcher; filters tabs through the active profile; auto-switches `activeTab` when filtered out via `resolveActiveTabForAudience` | landed (Wave 3 Fifth Slice) |
| `electron/public/locales/{en,ko,ja}/workspace.json` (`workspace.audienceView.*`) | label / description / 3 option labels / 3 option hints, parity-locked | landed (Wave 3 Fifth Slice) |

### CLI slash parity catalog surface (Wave 3 Fifth Slice)

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/domain/command/cliSlashCatalog.ts` | single source of truth `CLI_SLASH_CATALOG` + `paletteVisibleSlashEntries()` filter helper | landed (Wave 3 Fifth Slice) |
| `electron/src/renderer/application/command/buildPaletteCommands.ts` | derives slash entries from the catalog; preserves existing 6 ids plus `mode`/`model`/`certification` | landed (Wave 3 Fifth Slice) |
| `electron/src/renderer/components/palette/CommandPalette.tsx` | announces `slash:`/`agent:` execution via `aria-live="polite"` using existing `cmd:announce.sentToChat` / `cmd:announce.agentSentToChat` keys | landed (Wave 3 Fifth Slice) |

### Rerun-from-Step + Promote-to-Artifact surface (Wave 3 Sixth Slice)

| Surface | Integration | Status |
|---|---|---|
| `src/ds_agent/domain/entities/run_lineage.py` (`PromotedArtifact`) | frozen dataclass with whitelisted audience union | landed (Wave 3 Sixth Slice) |
| `src/ds_agent/domain/entities/runtime_state.py` (`RunState.rerun_from_node_id`) | rerun lineage marker carried through `_serialize_run` as `rerunFromNodeId` | landed (Wave 3 Sixth Slice) |
| `src/ds_agent/runtime/promoted_artifact_store.py` (`JsonPromotedArtifactStore`) | per-artifact JSON files under `<workspace>/runtime/promoted/` | landed (Wave 3 Sixth Slice) |
| `src/ds_agent/application/use_cases/rerun_from_step_usecase.py` + `promote_to_artifact_usecase.py` | port-DI use cases (parent run lookup port, start-rerun port, promoted-artifact-store port) | landed (Wave 3 Sixth Slice) |
| `src/ds_agent/api/ws_handler.py` (`run.rerun`, `run.promote`) | new RPC handlers; `_RerunFromStepStarter` adapter mounts use case onto existing `start_run` mechanics with branched_from_run_id threading | landed (Wave 3 Sixth Slice) |
| `electron/src/renderer/application/run/{rerunFromStep,promoteToArtifact}{,Port}.ts` | renderer ports + use cases with input guards | landed (Wave 3 Sixth Slice) |
| `electron/src/renderer/hooks/{useRerunFromStep,usePromoteToArtifact}.ts` | composition roots binding ports to `rpc('run.rerun'\|'run.promote', ...)` | landed (Wave 3 Sixth Slice) |
| `electron/src/renderer/components/runtime/RerunFromStepDialog.tsx` | depth-prefixed plan-node selector consuming `reasoningTraceStore.planState.planTree`; empty state when no plan available | landed (Wave 3 Sixth Slice) |
| `electron/src/renderer/components/mission/MissionHeader.tsx` (Rerun from Step button) | gated on `reasoningTraceStore.runId`; opens dialog | landed (Wave 3 Sixth Slice) |
| `electron/src/renderer/components/cards/ResultCard.tsx` (`PromoteCardAction`) | window.prompt for audience+title (validated against `'ds'\|'exec'\|'ml'`); inline status banner | landed (Wave 3 Sixth Slice) |

### Risk-tier matrix persistence surface (Wave 3 Sixth Slice)

| Surface | Integration | Status |
|---|---|---|
| `src/ds_agent/domain/entities/risk_tier_matrix.py` (`RiskTierMatrixSnapshot`) | frozen dataclass `{saved_at, matrix, saved_by}` | landed (Wave 3 Sixth Slice) |
| `src/ds_agent/runtime/policy_store.py` (`save_risk_tier_matrix`, `load_risk_tier_matrix`, `risk_tier_matrix_history`) | persists current at `<workspace>/runtime/policy/risk_tier_matrix.json` and appends to `risk_tier_matrix_history.jsonl` on every save | landed (Wave 3 Sixth Slice) |
| `src/ds_agent/application/use_cases/risk_tier_matrix_usecases.py` | `LoadRiskTierMatrixUseCase`, `SaveRiskTierMatrixUseCase`, `BuildHistoryBackedImpactPreview` (last 200 snapshots aggregated into per-cell tier counts) | landed (Wave 3 Sixth Slice) |
| `src/ds_agent/api/ws_handler.py` (`policy.matrix.get`/`policy.matrix.save`/`policy.matrix.preview`) | RPCs for matrix CRUD + history-backed preview | landed (Wave 3 Sixth Slice) |
| `electron/src/renderer/application/policy/{matrixPort,loadRiskTierMatrix,saveRiskTierMatrix,previewMatrixImpact}.ts` | port-DI use cases + pure helpers `mergeImpactPreview`, `formatLastSavedLabel`, `countMatrixCellDiff` | landed (Wave 3 Sixth Slice) |
| `electron/src/renderer/hooks/usePolicyMatrix.ts` | composition root | landed (Wave 3 Sixth Slice) |
| `electron/src/renderer/components/settings/PolicyStudio.tsx` | loads persisted matrix on mount, sequence-guarded preview RPC on draft change, "Last saved: <iso> by <savedBy>" line, Save Matrix Draft now persists via RPC | landed (Wave 3 Sixth Slice) |

### Per-card emphasis adoption surface (Wave 3 Sixth Slice)

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/application/workspace/cardEmphasisAdopter.ts` | pure `resolveCardDisplayMode(inputs, audienceView)` with precedence `userExpanded > forceExpanded > forceCollapsed > audience emphasis` | landed (Wave 3 Sixth Slice) |
| `electron/src/renderer/hooks/useAudienceView.ts` | `{view, profile, setView}` facade over the workspace store | landed (Wave 3 Sixth Slice) |
| `electron/src/renderer/components/cards/ResultCard.tsx` (emphasis adoption) | local `userExpanded` state; gates body+footer on `displayMode === 'expanded'`; `aria-expanded` toggle, audience-hint badge, manual-override badge, `data-audience-view`/`data-display-mode` for telemetry | landed (Wave 3 Sixth Slice) |
| `electron/src/renderer/components/workspace/WorkspacePinnedProjectionList.tsx` | calls `resolveCardDisplayMode` (rail variant `forceCollapsed`); item summary + meta gated | landed (Wave 3 Sixth Slice) |
| `electron/public/locales/{en,ko,ja}/workspace.json` (`audienceView.cardHint.*`) | 4 new keys + filled in previously-missing `audienceView.label/description/option.*` keys (latent bug from prior round) | landed (Wave 3 Sixth Slice) |

### Plan Tree a11y + setRunId wiring surface (Wave 3 Sixth Slice)

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/hooks/useReasoningTrace.ts` (`task.started` handler) | `clearPersistence()` → `reset()` → `setRunId(payload.runId)` sequence; bumps `lastPlanCreatedAtRef` so the 1.5s reconnect window can't restore the just-cleared snapshot | landed (Wave 3 Sixth Slice) |
| `electron/src/renderer/application/runtime/planTreeKeyboardNav.ts` | pure reducer for ArrowDown/Up/Right/Left/Home/End — testable without React | landed (Wave 3 Sixth Slice) |
| `electron/src/renderer/components/runtime/PlanTreePanel.tsx` (ARIA tree) | `role="tree"`/`treeitem`, `aria-level`/`aria-setsize`/`aria-posinset`/`aria-expanded`, roving `tabindex`, `aria-label` combining label+status+reasoning-note count, replan-flagged nodes get `sr-only` describing text. Stable DOM id via exported `planTreeNodeDomId(id)` | landed (Wave 3 Sixth Slice) |
| `electron/src/renderer/components/runtime/ReasoningTracePanel.tsx` (planNodeId jump) | `role="region"`; `planNodeId` chip is now a `<button>` that DOM-id-jumps and focuses the matching tree node | landed (Wave 3 Sixth Slice) |

### Policy surface

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/components/settings/PolicyStudio.tsx` | read-only `Wave 3 Derived Risk Preview` summarizes current matrix rows into T0-T3 derived tiers | landed |
| `electron/src/renderer/components/settings/policyStudioCatalog.ts` | centralized risk-tier definitions plus `derivePolicyRiskTier()` helper | landed |

## Wave 4 First Slice (2026-04-20)

### Design system foundation surface

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/design-system/tokens/*` | spacing / typography / radius / shadow / motion token maps introduced as Wave 4 foundation | landed |
| `electron/src/renderer/design-system/themes/*` | `dark / light / high-contrast` theme definitions + `applyThemeToDocument()` root CSS-variable application | landed |
| `electron/src/renderer/components/providers/ThemeProvider.tsx` | root theme sync wrapper mounted above `App` in `main.tsx` | landed |
| `electron/src/renderer/styles/globals.css` | legacy `--ds-*` aliases now resolve from canonical design-system CSS variables | landed |
| `electron/tailwind.config.js` | semantic color aliases retained; spacing / radius / shadow / typography / motion token hooks added | landed |
| `electron/.storybook/*` | Storybook 8.6.14 preview + toolbar-based theme switch for design-system primitives | landed |
| `electron/scripts/lint-design-system.mjs` | managed-surface lint gate for primitives/composites/providers; raw tokens remain allowed only in tokens/themes | landed |
| `electron/src/renderer/components/settings/{SettingsPanel.tsx,LocaleSelector.tsx}` | theme selector + locale selector moved onto design-system `Select` / `Button` primitives | landed |
| `electron/src/renderer/pages/admin/AdminPage.tsx` | admin appearance/onboarding actions now reuse design-system primitives | landed |
| `electron/src/renderer/components/trust/{TrustStrip.tsx,TrustBadge.tsx}` | trust badges/containers now reuse design-system `Badge`, `Card`, `Button` | landed |
| `electron/src/renderer/components/mission/MissionSlot.tsx` | mission slot styling now uses design-system spacing/radius/shadow utilities | landed |

## Wave 4 Second Slice (2026-04-20)

### Primitive expansion

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/design-system/primitives/{Input,Textarea,Spinner,Skeleton,DialogShell}.tsx` | text-entry, loading, and modal-shell primitives added with token-driven styling | landed |
| `electron/src/renderer/design-system/primitives/*.stories.tsx` | Storybook coverage expanded for the new primitive family | landed |
| `electron/tests/contract/designSystemPrimitives.spec.ts` | contract gate now checks that the new primitive exports remain wired into the public DS surface | landed |
| `electron/package.json` | `test:contract:design-system` now runs theme + lint + primitive export contracts together | landed |

### Composite / live-surface adoption

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/design-system/composites/ResultCardShell.tsx` | first Result Card composite shell centralizes meta pills, section panels, footer chrome, and action buttons | landed |
| `electron/src/renderer/design-system/composites/ResultCardShell.stories.tsx` | Storybook composite example added for the shared Result Card shell | landed |
| `electron/src/renderer/components/cards/ResultCard.tsx` | live result cards now consume the composite shell instead of repeating card chrome inline | landed |
| `electron/src/renderer/components/mission/MissionHeader.tsx` | top mission summary shell now reuses design-system `Card`, `Button`, and `Badge` primitives | landed |
| `electron/src/renderer/components/mission/ConnectionTooltip.tsx` | connection hover/detail surface now aligns to the same DS card/badge framing | landed |

## Wave 4 Third Slice (2026-04-20)

### Primitive expansion

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/design-system/primitives/{Checkbox,Radio,Chip}.tsx` | approval/dialog selection primitives added with token-driven states and form wiring | landed |
| `electron/src/renderer/design-system/primitives/{Checkbox,Radio,Chip}.stories.tsx` | Storybook coverage expanded for the new selection/control primitives | landed |
| `electron/tests/contract/designSystemPrimitives.spec.ts` | public DS primitive contract now asserts the expanded export surface (`Checkbox`, `Radio`, `Chip`) | landed |

### Dialog / approval adoption

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/components/runtime/{PromoteDialog,SaveCheckpointDialog,ResumePromptFallbackDialog,RerunFromStepDialog}.tsx` | runtime dialogs now reuse `DialogShell` plus DS input/button primitives while keeping their existing focus-trap controller and runtime flow | landed |
| `electron/src/renderer/components/sandbox/SandboxApprovalModal.tsx` | approval modal shell, section framing, quick choices, text areas, and footer actions now align to DS primitives | landed |

### Command palette follow-through

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/application/command/buildPaletteCommands.ts` | palette now emits `slash` and `agent` prompt commands through the existing `onSend` path | landed |
| `electron/src/renderer/domain/command/command.ts` | command categories extended with `slash` and `agent` | landed |
| `electron/src/renderer/components/layout/AreaMainPanel.tsx` | palette builder now receives `onSend` so non-navigation commands can dispatch into mission chat | landed |
| `electron/src/renderer/components/palette/CommandPalette.tsx` | category labels now have code fallbacks, so missing locale keys do not break grouping | landed |

## Wave 3 Third Slice (2026-04-20)

### Plan Tree surface

| Surface | Integration | Status |
|---|---|---|
| `src/ds_agent/agent/ds_workflow_hooks.py` | `WorkflowTrackerHook` now emits `plan.created` on session init and `plan.updated` for stage and root node state transitions | landed |
| `electron/src/renderer/stores/reasoningTraceStore.ts` | store now persists live `planTree` snapshots alongside reasoning traces and plan lifecycle timestamps | landed |
| `electron/src/renderer/hooks/useReasoningTrace.ts` | bridge now applies `plan.created` / `plan.updated` payloads and resets state on `task.started` | landed |
| `electron/src/renderer/components/runtime/PlanTreePanel.tsx` | new compact Plan Tree renderer for the execution timeline | landed |
| `electron/src/renderer/components/runtime/ExecutionTimeline.tsx` | timeline now mounts `PlanTreePanel` above the stage rows | landed |

### Command palette accessibility / file routing

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/application/command/buildPaletteCommands.ts` | recent workspace files now map to safe existing destinations (`tables`, `charts`, `files`) | landed |
| `electron/src/renderer/components/palette/CommandPalette.tsx` | palette traps `Tab` / `Shift+Tab` and restores focus on close | landed |
| `electron/src/renderer/components/layout/AreaMainPanel.tsx` | palette file sources continue to come from existing renderer file state | landed |

### Policy preview follow-through

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/components/settings/PolicyStudio.tsx` | draft impact preview compares current effective verdict buckets against draft overrides per authority column | landed |

### Confirmed gaps after backend/runtime review

- `plan.replanned` is still typed but not produced by the backend.
- Checkpoint resume beyond chat prompt preparation still needs a transport path in `ws_handler.py`.
- Branch creation, rerun-from-step, and promote-to-artifact remain below the transport layer and are not honestly wired to the renderer yet.

## Wave 3 Seventh Slice (2026-04-20)

### PLAN_03 dialogs / lineage

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/components/runtime/RerunFromStepDialog.tsx` | dedicated rerun dialog replaces the prompt-driven rerun path and consumes the plan-tree snapshot | landed (Wave 3 Seventh Slice) |
| `electron/src/renderer/components/mission/MissionHeader.tsx` / `electron/src/renderer/components/runtime/RunDetailDrawer.tsx` | dialog entrypoints for rerun / promote / branch flows now route through the modal surface instead of inline prompts | landed (Wave 3 Seventh Slice) |
| `electron/src/renderer/components/runtime/ReasoningTracePanel.tsx` / `PlanTreePanel.tsx` | lineage jump targets and node references remain the visible hand-off from rerun/promote actions | landed (Wave 3 Seventh Slice) |

### PLAN_05 risk-tier matrix editor / runtime overlay

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/components/settings/RiskTierMatrixEditor.tsx` | first-class matrix editor surface for live cell edits and diff preview | landed (Wave 3 Seventh Slice) |
| `electron/src/renderer/hooks/usePolicyMatrix.ts` / `electron/src/renderer/application/policy/*` | save/load/preview path feeds the runtime overlay and persisted matrix model | landed (Wave 3 Seventh Slice) |
| `electron/src/renderer/components/settings/PolicyStudio.tsx` | mounts the editor and runtime overlay inside the policy workflow | landed (Wave 3 Seventh Slice) |

### PLAN_06 audience card rendering

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/hooks/useAudienceRenderedCard.ts` | selects audience-specific render data for each result card | landed (Wave 3 Seventh Slice) |
| `electron/src/renderer/application/cards/renderCardForAudiencePort.ts` | port boundary for renderer-shaped audience rendering | landed (Wave 3 Seventh Slice) |
| `electron/src/renderer/components/cards/ResultCard.tsx` / `electron/src/renderer/components/workspace/WorkspacePinnedProjectionList.tsx` | cards and pinned projections now render by audience profile instead of a single flat body | landed (Wave 3 Seventh Slice) |

### PLAN_02 compare board

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/components/runtime/RunsCompareBoard.tsx` | compare board remains the runtime view for run diffs and now shares the Wave 3 follow-through path | landed (Wave 3 Seventh Slice) |
| `electron/src/renderer/pages/runs/RunsPage.tsx` | `/runs` rail continues to mount the compare board above the detail drawer | landed (Wave 3 Seventh Slice) |

### PLAN_04 slash dispatcher + palette e2e

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/application/command/cliSlashDispatcher.ts` | slash input normalization and palette dispatch routing | landed (Wave 3 Seventh Slice) |
| `electron/src/renderer/components/palette/CommandPalette.tsx` | slash command execution is routed through the dispatcher before falling back to natural language | landed (Wave 3 Seventh Slice) |
| `electron/tests/e2e/palette.spec.ts` | Playwright palette e2e coverage for slash dispatch and related UX paths | landed (Wave 3 Seventh Slice) |

## Wave 4 Fourth Slice (2026-04-20)

### PLAN_01 drawer/runtime design-system adoption

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/design-system/primitives/{DrawerShell,Tabs,Accordion}.tsx` | drawer/tabs/accordion primitives now extend the token-driven DS surface with Storybook coverage and contract export checks | landed |
| `electron/src/renderer/design-system/primitives/Select.tsx` | select now generates a fallback control id so labels stay associated on lightweight dialog forms | landed |
| `electron/src/renderer/design-system/composites/DrawerSurface.tsx` | inline drawer header/body/section/stat chrome introduced for runtime inspector-style rails | landed |
| `electron/src/renderer/components/mission/{MissionDrawerShell,AssumptionDrawer}.tsx` | mission drawers now consume shared overlay drawer shell chrome instead of repeating ad-hoc focus/dismiss layout | landed |
| `electron/src/renderer/components/runtime/RunDetailDrawer.tsx` | run inspector rail now consumes `DrawerSurface` for shared section framing and action chrome while preserving runtime logic | landed |
| `electron/src/renderer/components/runtime/BranchRunDialog.tsx` | branch dialog now consumes `DialogShell` + DS form primitives while preserving stable ids and runtime dialog a11y control | landed |

## Wave 4 Fifth Slice (2026-04-20)

### PLAN_01 primitives completion + runtime composite follow-through

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/design-system/primitives/{Tooltip,Popover,Toast}.tsx` | tooltip/popover/toast primitives now complete the planned foundational DS surface with Storybook coverage | landed |
| `electron/src/renderer/components/sandbox/SandboxViolationToast.tsx` | sandbox violation stack now renders through the shared `Toast` / `ToastViewport` primitives | landed |
| `electron/src/renderer/components/runtime/{LineagePanel,ReasoningTracePanel}.tsx` | lineage and reasoning panels now consume shared DS sections/cards/badges while preserving navigation and data flow | landed |
| `electron/src/renderer/components/runtime/PlanTreePanel.tsx` | plan tree header/status pills now use DS `Card` / `Badge` chrome instead of bespoke shell styling | landed |
| `electron/src/renderer/components/runtime/RunDiffPanel.tsx` | runtime run-diff surface now uses DS card/badge framing with tighter semantic structure | landed |
| `electron/src/renderer/components/runtime/RunsCompareBoard.tsx` | compare board filters, selectors, status pills, summary cards, and supporting sections now consume DS primitives | landed |
| `electron/tests/contract/designSystemInteractiveA11y.spec.ts` | DS contract coverage now locks `Select` fallback-id wiring plus `Tabs` / `DrawerShell` semantic markup | landed |

## Wave 4 Sixth Slice (2026-04-20)

### PLAN_01 approval/workflow follow-through + tooltip live adoption

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/components/workflow/ApprovalPanel.tsx` | pending approval cards now use DS `Card` / `Badge` / `Button` chrome and replace the last `window.prompt(...)` response path with an inline `Popover` + `Textarea` approval flow | landed |
| `electron/src/renderer/components/admin/ApprovalGrantsPanel.tsx` | approval-grants settings view now uses DS `Card` / `Button` / `Badge` for feedback banners, refresh/revoke actions, empty state, scope pills, and table shell while preserving the existing ports and i18n copy | landed |
| `electron/src/renderer/components/sidebar/SidebarItem.tsx` | collapsed rail labels now render through the shared `Tooltip` primitive instead of bespoke hover/focus tooltip markup | landed |
| `electron/src/renderer/components/workflow/DecisionOsReviewPrimitives.tsx` | shared review/promotion stat and inline-error shells now reuse DS `Card` chrome, lifting the review surfaces onto the common visual baseline | landed |
| `electron/tests/contract/designSystemInteractiveA11y.spec.ts` | DS interactive contract coverage now also asserts `Tooltip` described-by wiring and `Popover` dialog-trigger semantics | landed |
| `electron/tests/contract/sidebarCollapse.spec.ts` | sidebar contract now checks collapsed `SidebarItem` tooltip-wrapper behavior and confirms the rail item keeps its accessible label without a duplicate native title | landed |

## Wave 4 Seventh Slice (2026-04-20)

### PLAN_01 runtime/governance panel follow-through

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/components/runtime/{GatewayStatusPanel,PolicyPanel,RecurringGoalsPanel,StandingOrdersPanel}.tsx` | runtime console, policy, recurring-goal, and standing-order surfaces now use DS cards, badges, buttons, selects, and textareas while preserving their existing runtime store / RPC flows | landed |
| `electron/src/renderer/components/runtime/{CertificationBoard,RegressionBoard}.tsx` | certification and regression boards now use DS primitives/composites for filters, section chrome, and status summaries without changing their hook-driven logic | landed |
| `electron/src/renderer/components/workflow/{ReviewTab,SharedSkillReviewPanel,RunDiffPanel,WorkObjectPanel}.tsx` | governance review/select surfaces now expose accessible names so governance-panel axe coverage stays green under the IA v2 navigation shell | landed |
| `electron/src/renderer/components/{layout/StatusBar,settings/SettingsPanel,layout/DisconnectOverlay,sidebar/ModelSelector,runtime/SessionsPanel,runtime/RuntimeAlertsPanel}.tsx` | warning-state badges/text now normalize on DS warning tokens so the expanded runtime/governance axe lane passes without contrast regressions | landed |
| `electron/src/renderer/pages/admin/AdminPage.tsx` | the admin theme selector now uses an explicit label path so the existing settings/admin axe coverage stays green after the wider runtime panel scan | landed |
| `electron/tests/e2e/a11y/runtime-panels.a11y.spec.ts` | new axe coverage scans `area-nav-governance` and `area-nav-runs` after onboarding, extending from rail-only coverage to visible governance/runtime panel surfaces | landed |
| `electron/package.json` | `test:e2e:a11y` now includes the compiled `runtime-panels.a11y.spec.js` lane | landed |

## Wave 4 Eighth Slice (2026-04-20)

### PLAN_01 sidebar/workspace rail follow-through + composite Storybook expansion

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/components/sidebar/{ProjectPanel,FileExplorer}.tsx` | sidebar project/file surfaces now use DS cards, badges, buttons, inputs, and selects for shell chrome, row states, create flows, and file actions while preserving store/RPC behavior | landed |
| `electron/src/renderer/components/workspace/{WorkspaceOverviewRail,WorkspaceContextRail}.tsx` | evidence workspace side rails now use DS cards, badges, and buttons for overview sections, recent-file panels, and export affordances, with labelled regions and semantic list treatment | landed |
| `electron/src/renderer/design-system/composites/DrawerSurface.stories.tsx` | new Storybook coverage documents inspector-style composite usage for `DrawerSurface` and its stat/section helpers | landed |
| `electron/src/renderer/design-system/composites/ResultCardShell.stories.tsx` | composite Storybook coverage now spans multiple operational result-card states instead of a single happy-path demo | landed |

## Wave 4 Ninth Slice (2026-04-20)

### PLAN_01 workspace/support surface follow-through + workspace a11y expansion

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/components/sidebar/{FileUpload,PlotGallery,UsageMeter}.tsx` | sidebar upload/plot/usage surfaces now use DS cards, badges, buttons, and structured status chrome while preserving upload/delete/store flows | landed |
| `electron/src/renderer/components/workspace/{SchemaPreviewCard,SuggestedActions,UploadErrorState,WorkspaceEmptyState}.tsx` | workspace upload-preview and empty/error surfaces now use DS cards, badges, and buttons, with stronger semantic labeling and action consistency | landed |
| `electron/src/renderer/components/workspace/{AudienceViewSwitcher,WorkspaceTabContent,EvidenceWorkspace}.tsx` | evidence workspace center surfaces now use DS cards, badges, and buttons for tabs, summary metrics, export sections, and audience controls while preserving route-driven behavior | landed |
| `electron/tests/e2e/a11y/workspace-panels.a11y.spec.ts` | new axe coverage scans both the artifacts files view and the workspace evidence view after navigating through `area-nav-artifacts` | landed |
| `electron/package.json` | `test:e2e:a11y` now includes the compiled `workspace-panels.a11y.spec.js` lane | landed |

## Wave 4 Tenth Slice (2026-04-20)

### PLAN_01 final close-out (sidebar legacy cleanup + quantitative audit)

| Surface | Integration | Status |
|---|---|---|
| `electron/src/renderer/components/sidebar/FilePreviewModal.tsx` | file preview modal now uses DS cards, buttons, badges, selects, and inputs while preserving preview RPC, Excel sheet/header-row controls, backdrop close, and Escape dismiss | landed |
| `electron/src/renderer/components/sidebar/ModeSelector.tsx` | execution mode control now uses DS `Radio` inside a semantic `fieldset`/`legend` group instead of bespoke button-only markup | landed |
| `electron/src/renderer/components/sidebar/ModelSelector.tsx` | model/preset picker now uses DS `Button` / `Badge` / `Card` chrome plus explicit popup trigger semantics while preserving recommendation/store wiring | landed |
| `electron/tests/contract/{filePreviewModal,sidebarSelectors}.spec.ts` | focused contract coverage now locks preview request building/clamping and selector semantic output | landed |
| `electron/scripts/audit-design-system-usage.mjs` | close-out audit now reports Storybook story count plus Wave 4 live-surface and legacy-migration DS adoption metrics from an explicit PLAN_01 target set | landed |
| `electron/tests/contract/designSystemAudit.spec.ts` | DS contract lane now validates the audit output shape and PLAN_01 thresholds (50+ stories, 80% live-surface adoption, 30% legacy migration) | landed |
| `electron/package.json` | added `audit:design-system`, `test:contract:file-preview-modal`, `test:contract:sidebar-selectors`, and extended `test:contract:design-system` with the audit contract | landed |

## Wave 4 PLAN_03 Cross-Surface Deep Link (2026-04-20)

### Deep Link CLI + Backend Mirror (Sub-Phase 3.3 + 3.5)

| Surface | Integration | Status |
|---|---|---|
| `src/ds_agent/domain/value_objects/deep_link.py` | Python wire-format mirror of `electron/src/renderer/domain/deepLink/deepLink.ts` — `parse_deep_link` / `build_deep_link_uri` / `DeepLinkParseError` enum / `DeepLinkParseFailedError`. Stdlib only, zero external deps. Byte-by-byte identical wire-format with renderer (16 sanitize cases verified). | landed (agent-w4c-cli-backend-001, 2026-04-20) |
| `src/ds_agent/application/use_cases/resolve_deep_link_usecase.py` | `ResolveDeepLinkUseCase` + `WorkspaceAuthorizationPort` / `ReauthSessionPort` Protocols, `DefaultWorkspaceAuthorization` (sole-user impl) + `InMemoryReauthSession`, `ReauthPolicy.{NONE, ONCE_PER_SESSION, ALWAYS}` (default `ONCE_PER_SESSION` per ADR D-W4-1). Pure application layer — depends only on domain. | landed (agent-w4c-cli-backend-001, 2026-04-20) |
| `src/ds_agent/cli/commands.py` | `run_open_command` + `run_share_command` (Win/macOS/Linux launcher branch, optional `pyperclip` clipboard, re-parse round-trip guard before output). Slash-command surface untouched. | landed (agent-w4c-cli-backend-001, 2026-04-20) |
| `src/ds_agent/cli/main.py` | `ds-agent open <url>` and `ds-agent share <type> <id> [--workspace W] [--action A]` subcommand dispatch wired into existing `main()`. | landed (agent-w4c-cli-backend-001, 2026-04-20) |
| `tests/unit/domain/test_deep_link.py` | 24 cases — full parity with renderer 16-case contract spec + build/raise variants. **Drift guard**: changes here MUST mirror `electron/tests/contract/deepLinkParse.spec.ts`. | landed (agent-w4c-cli-backend-001, 2026-04-20) |
| `tests/unit/application/test_resolve_deep_link_usecase.py` | 14 cases — invalid URI propagation, workspace-mismatch FORBIDDEN, port-level deny, all 3 reauth policies + parametrized matrix, default-policy assertion (ADR D-W4-1). | landed (agent-w4c-cli-backend-001, 2026-04-20) |
| `tests/unit/cli/test_deep_link_cli.py` | 12 cases — `run_open_command` rejects bad URI without invoking launcher, propagates RC, share command happy + sad paths, clipboard injection point. | landed (agent-w4c-cli-backend-001, 2026-04-20) |

**Cross-surface contract**: all four surfaces (renderer / Electron main / CLI / Telegram) MUST use either `parseDeepLink` (TS) or `parse_deep_link` (Python) before any side effect. Both implementations share the same wire format: scheme `ds-agent:`, host `workspace`, resource types `run|artifact|checkpoint|verifier_result`, ID `^[A-Za-z0-9_:.-]{1,128}$`, action `^[A-Za-z0-9_-]{1,64}$`, max URI 2048 bytes, no extra path segments. Error vocabularies are identical strings.
