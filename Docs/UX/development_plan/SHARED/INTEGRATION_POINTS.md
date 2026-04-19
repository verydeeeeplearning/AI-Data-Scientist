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
