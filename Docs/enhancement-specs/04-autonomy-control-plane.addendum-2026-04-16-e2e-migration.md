# 04. Autonomy Control Plane Addendum (2026-04-16)

This addendum records the autonomy-control-plane work completed after the main `04-autonomy-control-plane.md` update sequence reached strategy-based `ActionClassifier` coverage.

## 1. Playwright autonomy-control-plane smoke path

- Added `electron/tests/smoke/autonomy-control-plane.spec.ts` so the Electron smoke suite now exercises runtime overlay changes, seeded session attach, PolicyStudio task-contract edits, and Action Matrix override persistence against the packaged backend.
- Added `scripts/seed_autonomy_e2e_workspace.py` plus `DS_AGENT_CONFIG_PATH` support in `src/ds_agent/config/loader.py`, `electron/src/main/observability.ts`, and `electron/src/main/diagnostics-collector.ts` so the smoke test runs in an isolated workspace without mutating operator config.
- Added stable E2E hooks in `electron/src/main/window.ts`, `electron/src/renderer/stores/configStore.ts`, `electron/src/renderer/components/layout/Sidebar.tsx`, `electron/src/renderer/components/runtime/GatewayStatusPanel.tsx`, `electron/src/renderer/components/runtime/CertificationBoard.tsx`, `electron/src/renderer/components/runtime/SessionsPanel.tsx`, and `electron/src/renderer/components/settings/PolicyStudio.tsx`.
- Narrowed `electron/tsconfig.test.json`, added `npm run test:e2e:autonomy` in `electron/package.json`, and restored typed runtime regression renderer files so the smoke harness compiles cleanly.
- Hardened packaged-backend startup for this flow by keeping Pillow available in `ds-agent-api.spec` and lazily importing heavy exporter / verifier dependencies inside `src/ds_agent/infrastructure/task_contract_container.py` and `src/ds_agent/infrastructure/verifier_container.py`.

## 2. Legacy mode migration helper

- Added `src/ds_agent/runtime/legacy_mode_migration.py` with exact vs approximate previews for translating legacy `auto`, `supervised`, and `step-by-step` into explicit `authority` + `audience` choices.
- Extended `src/ds_agent/cli/mode_cli.py` with `ds-agent mode migrate [legacy-mode]` so operators can inspect the recommended explicit mapping before changing current-session policy surfaces.
- Extended `electron/src/renderer/components/settings/policyStudioCatalog.ts` and `electron/src/renderer/components/settings/PolicyStudio.tsx` with a Legacy mode migration helper card and an `Apply legacy mapping to draft` control for current-session TaskContract editing.
- Added `tests/unit/runtime/test_legacy_mode_migration.py` and expanded `tests/unit/infrastructure/test_mode_cli.py`.

## 3. Verification

- `pytest tests/unit/infrastructure/test_config.py tests/unit/infrastructure/test_certification_api_routes.py` -> **30 passed**
- `pytest tests/unit/runtime/test_legacy_mode_migration.py tests/unit/infrastructure/test_mode_cli.py tests/unit/infrastructure/test_cli_main.py` -> **36 passed**
- `ruff check src/ds_agent/runtime/legacy_mode_migration.py src/ds_agent/cli/mode_cli.py tests/unit/runtime/test_legacy_mode_migration.py tests/unit/infrastructure/test_mode_cli.py` -> **ok**
- `ruff format --check src/ds_agent/runtime/legacy_mode_migration.py src/ds_agent/cli/mode_cli.py tests/unit/runtime/test_legacy_mode_migration.py tests/unit/infrastructure/test_mode_cli.py` -> **ok**
- `mypy src/ds_agent/runtime/legacy_mode_migration.py src/ds_agent/cli/mode_cli.py` -> **ok**
- `python -m compileall src/ds_agent/config/loader.py src/ds_agent/infrastructure/task_contract_container.py src/ds_agent/infrastructure/verifier_container.py src/ds_agent/runtime/legacy_mode_migration.py src/ds_agent/cli/mode_cli.py tests/unit/infrastructure/test_config.py tests/unit/runtime/test_legacy_mode_migration.py tests/unit/infrastructure/test_mode_cli.py` -> **ok**
- `python scripts/build_backend.py` -> **ok**
- `cd electron && npm run typecheck` -> **ok**
- `cd electron && npm run test:e2e:autonomy` -> **ok** (includes `npm run build`; existing Vite chunk-size warning remains unchanged)

## 4. Status

- Visual regression / Playwright E2E is now complete for the packaged autonomy-control-plane flow.
- Legacy migration helper/docs is now complete for CLI preview and PolicyStudio draft migration.

## 5. Rollout polish + import-contract coverage

- Added PolicyStudio quick presets for `Delegated Peer`, `Executive Review`, `Audit Guard`, and `Mentor Walkthrough` so operators can stamp common authority/audience draft pairs without manually editing each field.
- Added `electron/tests/contract/policy-studio.spec.ts` plus `npm run test:contract:policy-studio` to pin the quick preset catalog and legacy migration preview semantics.
- Added `.importlinter`, `scripts/check_import_contracts.py`, and `tests/unit/architecture/test_import_contracts.py` so the Clean Architecture rule "domain must not depend on outer layers" is now enforced in-repo even when the external Import Linter package is not installed.
- Added `import-linter>=2.0` to the dev dependency set so teams can also run the external tool directly.

## 6. Verification override

- `python scripts/check_import_contracts.py` -> **ok**
- `pytest tests/unit/architecture/test_import_contracts.py` -> **1 passed**
- `ruff check scripts/check_import_contracts.py tests/unit/architecture/test_import_contracts.py pyproject.toml` -> **ok**
- `ruff format --check scripts/check_import_contracts.py tests/unit/architecture/test_import_contracts.py` -> **ok**
- `mypy scripts/check_import_contracts.py` -> **ok**
- `cd electron && npm run typecheck` -> **ok**
- `cd electron && npm run test:contract:policy-studio` -> **ok**
- `cd electron && npm run test:e2e:autonomy` -> **ok** (includes `npm run build`; existing Vite chunk-size warning remains unchanged)

## 7. Status override

- Broader rollout polish is now complete for the current autonomy-control-plane slice.
- Import-boundary coverage is now complete for the current autonomy-control-plane slice.
- No explicit feature-scope gaps remain in the current `04` plan slice; follow-up work now depends on defining a new autonomy backlog increment.
