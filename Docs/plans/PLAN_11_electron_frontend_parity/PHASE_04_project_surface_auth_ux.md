# Phase 04: Project Surface and Auth UX

**Priority**: P2  
**Status**: Completed  
**Depends On**: current backend only

---

## 1. Goal

Expose project-level workflows in Electron and make provider/model auth status
easier to understand for non-developer operators.

---

## 2. Backend Capabilities Already Available

- `project.list`
- `project.create`
- `provider.models`
- `provider.authStatus`
- `config.getApiKeys`
- `config.setApiKey`
- `oauth.startLogin`
- `oauth.status`
- `oauth.disconnect`

---

## 3. Frontend Gap

Current Electron frontend:

- shows files, but not projects as first-class objects
- shows auth status, but not model-to-auth compatibility clearly
- allows auth actions, but does not explain which provider path the chosen model depends on

---

## 4. Implemented

New files:

- `electron/src/renderer/stores/authStore.ts`
- `electron/src/renderer/hooks/useProviderAuth.ts`
- `electron/src/renderer/stores/projectStore.ts`
- `electron/src/renderer/hooks/useProjects.ts`
- `electron/src/renderer/components/sidebar/ProjectPanel.tsx`
- `electron/src/renderer/utils/modelAuth.ts`

Modified files:

- `electron/src/renderer/components/layout/Sidebar.tsx`
- `electron/src/renderer/components/settings/SettingsPanel.tsx`
- `electron/src/renderer/components/sidebar/ModelSelector.tsx`
- `electron/src/renderer/components/layout/StatusBar.tsx`
- `electron/src/renderer/components/settings/OnboardingWizard.tsx`
- `electron/src/renderer/App.tsx`

Delivered behavior:

- `ProjectPanel` now loads, refreshes, creates, and selects projects from Electron
- selected project is shown in both the `Files` tab and the global status bar
- `useProviderAuth(...)` now keeps `provider.authStatus`, `oauth.status`, and `config.getApiKeys` in one shared frontend store
- auth snapshot polling means Electron can notice external auth changes such as Codex CLI login without reopening the app
- `ModelSelector` now shows provider, auth type, readiness, and the blocking reason for each model
- `SettingsPanel` now shows the selected model's auth dependency and current project context
- `OnboardingWizard` now skips redundant auth steps when the chosen model is already usable

---

## 5. UX Rules

- keep project actions simple: list, create, select
- do not overload project selection with file-management logic in the first pass
- prefer explicit badges over hidden auth assumptions
- surface why a model is blocked, not just that it is blocked

---

## 6. Verification

Executed:

```bash
cd electron && npm run typecheck
cd electron && npm run build
python -m pytest tests/unit/infrastructure/test_api.py tests/e2e/test_ws_e2e.py -q -p no:cacheprovider --basetemp='C:\Users\aquap\.codex\memories\pytest_electron_phase04_1'
```

Result:

- `npm run typecheck`: passed
- `npm run build`: passed
- `pytest ...`: `79 passed`
- `vite build` still reports the pre-existing chunk size warning, but the build completes successfully

---

## 7. Exit Criteria

- projects are visible and creatable from Electron
- selected project is visible in the app
- model and auth compatibility are understandable from the UI
- non-developer operators do not need to infer auth dependencies manually
