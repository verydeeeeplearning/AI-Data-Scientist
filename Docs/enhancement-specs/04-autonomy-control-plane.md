# 04. Autonomy Control Plane — 3축 자율성 제어

> 본 문서는 `Docs/ds-agent-enhancement-roadmap.md` §4의 상세 구현 스펙이다.
> 기존 `runtime/policy_engine.py`, `agent/prompt_sections.py`, `skills/` (builtin 8 + shared 6) 위에 얹는 확장 레이어를 정의한다.

---

## 0. 2026-04-16 진행 상황

### Mission Pack update

- Added `src/ds_agent/domain/entities/mission_pack.py` with typed `MissionPack` / `MissionBoundary` validation.
- Added `src/ds_agent/skills/mission_pack_loader.py` and bundled `src/ds_agent/skills/missions/weekly-kpi-triage.yaml`.
- Extended `src/ds_agent/agent/prompt_sections.py` with `build_mission_section()` and conservative fallback rendering.
- Extended `src/ds_agent/agent/prompt_builder.py` and `src/ds_agent/agent/factory.py` so an active `TaskContract.mission` loads a mission pack, injects a `MISSION:` section, applies mission default authority/audience when the contract omits them, and appends `skills_required` to prompt-time active skills.
- Updated `pyproject.toml` mypy overrides to ignore missing `yaml.*` stubs during targeted type-check runs.
- Added `tests/unit/domain/test_mission_pack.py`, `tests/unit/skills/test_mission_pack_loader.py`, `tests/unit/presentation/test_prompt_mission_section.py`, and expanded `tests/unit/application/test_prompt_builder.py`.
- Verification:
  - `pytest tests/unit/domain/test_mission_pack.py tests/unit/skills/test_mission_pack_loader.py tests/unit/presentation/test_prompt_mission_section.py tests/unit/application/test_prompt_builder.py` -> **40 passed**
  - `pytest tests/unit/domain/test_mission_pack.py tests/unit/skills/test_mission_pack_loader.py tests/unit/skills/test_domain_skills.py tests/unit/presentation/test_prompt_mission_section.py tests/unit/presentation/test_prompt_sections_authority_and_audience.py tests/unit/application/test_prompt_builder.py tests/unit/application/test_agent_factory.py` -> **52 passed**
  - `python -m compileall src/ds_agent/domain/entities/mission_pack.py src/ds_agent/skills/mission_pack_loader.py src/ds_agent/agent/prompt_sections.py src/ds_agent/agent/prompt_builder.py src/ds_agent/agent/factory.py tests/unit/domain/test_mission_pack.py tests/unit/skills/test_mission_pack_loader.py tests/unit/presentation/test_prompt_mission_section.py tests/unit/application/test_prompt_builder.py` -> **ok**
  - `ruff check src/ds_agent/domain/entities/mission_pack.py src/ds_agent/skills/mission_pack_loader.py src/ds_agent/agent/prompt_sections.py src/ds_agent/agent/prompt_builder.py src/ds_agent/agent/factory.py tests/unit/domain/test_mission_pack.py tests/unit/skills/test_mission_pack_loader.py tests/unit/presentation/test_prompt_mission_section.py tests/unit/application/test_prompt_builder.py pyproject.toml` -> **ok**
  - `mypy src/ds_agent/domain/entities/mission_pack.py src/ds_agent/skills/mission_pack_loader.py src/ds_agent/agent/prompt_sections.py src/ds_agent/agent/prompt_builder.py src/ds_agent/agent/factory.py` -> **ok** (tool note: existing `pyproject.toml` still reports unused override entries for `google.generativeai.*`, `telegram.*`, `uvicorn.*`)

### Mission boundary enforcement update

- Extended `src/ds_agent/domain/entities/mission_pack.py` with `action_policy_overrides`, `policy_override()`, and `is_within_boundary()`.
- Extended `src/ds_agent/runtime/autonomy_policy.py` so Mission overrides can change the matrix verdict and out-of-boundary actions escalate to approval.
- Extended `src/ds_agent/agent/permissions.py`, `src/ds_agent/agent/builtin_hooks.py`, and `src/ds_agent/agent/factory.py` so `PermissionHook` resolves the active `TaskContract`, loads the active mission pack, and enforces mission boundary rules during tool execution.
- Updated `src/ds_agent/skills/missions/weekly-kpi-triage.yaml` with a mission-local override that allows `jira_create` in `delegate`.
- Added `tests/integration/test_mission_boundary_enforcement.py` and expanded `tests/unit/runtime/test_autonomy_policy_basic.py`, `tests/unit/application/test_hooks.py`, and `tests/unit/domain/test_mission_pack.py`.
- Verification:
  - `pytest tests/unit/domain/test_mission_pack.py tests/unit/runtime/test_autonomy_policy_basic.py tests/unit/application/test_hooks.py tests/integration/test_mission_boundary_enforcement.py` -> **51 passed**
  - `pytest tests/unit/domain/test_mission_pack.py tests/unit/skills/test_mission_pack_loader.py tests/unit/skills/test_domain_skills.py tests/unit/presentation/test_prompt_mission_section.py tests/unit/presentation/test_prompt_sections_authority_and_audience.py tests/unit/application/test_prompt_builder.py tests/unit/application/test_agent_factory.py tests/unit/application/test_hooks.py tests/unit/runtime/test_autonomy_policy_basic.py tests/integration/test_mission_boundary_enforcement.py tests/integration/test_autonomy_policy_matrix.py` -> **104 passed**
  - `python -m compileall src/ds_agent/domain/entities/mission_pack.py src/ds_agent/skills/mission_pack_loader.py src/ds_agent/runtime/autonomy_policy.py src/ds_agent/agent/permissions.py src/ds_agent/agent/builtin_hooks.py src/ds_agent/agent/prompt_sections.py src/ds_agent/agent/prompt_builder.py src/ds_agent/agent/factory.py tests/unit/domain/test_mission_pack.py tests/unit/skills/test_mission_pack_loader.py tests/unit/presentation/test_prompt_mission_section.py tests/unit/application/test_prompt_builder.py tests/unit/application/test_hooks.py tests/unit/runtime/test_autonomy_policy_basic.py tests/integration/test_mission_boundary_enforcement.py tests/integration/test_autonomy_policy_matrix.py` -> **ok**
  - `ruff check src/ds_agent/domain/entities/mission_pack.py src/ds_agent/runtime/autonomy_policy.py src/ds_agent/agent/permissions.py src/ds_agent/agent/builtin_hooks.py src/ds_agent/agent/factory.py tests/unit/domain/test_mission_pack.py tests/unit/runtime/test_autonomy_policy_basic.py tests/unit/application/test_hooks.py tests/integration/test_mission_boundary_enforcement.py` -> **ok**
  - `mypy src/ds_agent/domain/entities/mission_pack.py src/ds_agent/skills/mission_pack_loader.py src/ds_agent/runtime/autonomy_policy.py src/ds_agent/agent/permissions.py src/ds_agent/agent/builtin_hooks.py src/ds_agent/agent/prompt_sections.py src/ds_agent/agent/prompt_builder.py src/ds_agent/agent/factory.py` -> **ok** (tool note: existing `pyproject.toml` still reports unused override entries for `google.generativeai.*`, `telegram.*`, `uvicorn.*`)

### Certification persistence + CLI update

- Added `src/ds_agent/domain/entities/certification.py` and `src/ds_agent/domain/interfaces/certification.py` for `CertificationSpec`, `CertificationRequirement`, `CertificationStats`, `CertificationRecord`, and `AutonomyRunStat`.
- Extended `src/ds_agent/domain/entities/mission_pack.py` and `src/ds_agent/skills/missions/weekly-kpi-triage.yaml` so Mission Packs now carry certification policy/history/deprecation metadata.
- Added `src/ds_agent/infrastructure/persistence/certification_store.py` with SQLite-backed certification history + run-stat aggregation.
- Added `src/ds_agent/application/services/certification_usecases.py` and `src/ds_agent/cli/certification_cli.py` for `status`/`submit` flows.
- Extended `src/ds_agent/runtime/autonomy_policy.py`, `src/ds_agent/agent/permissions.py`, `src/ds_agent/agent/builtin_hooks.py`, `src/ds_agent/agent/factory.py`, `src/ds_agent/cli/commands.py`, and `src/ds_agent/cli/main.py` so `autopilot` execution demotes to approval when mission certification is missing and operators can inspect/submit certification from CLI/TUI.
- Added `tests/unit/domain/test_certification_spec.py`, `tests/unit/application/test_submit_certification.py`, `tests/integration/infrastructure/test_sqlite_certification_store.py`, `tests/unit/infrastructure/test_certification_cli.py`, and expanded `tests/unit/runtime/test_autonomy_policy_basic.py`, `tests/unit/application/test_hooks.py`, `tests/unit/infrastructure/test_tui.py`, `tests/unit/infrastructure/test_cli_main.py`, `tests/unit/domain/test_mission_pack.py`, and `tests/unit/skills/test_mission_pack_loader.py`.
- Verification:
  - `pytest tests/unit/domain/test_certification_spec.py tests/unit/application/test_submit_certification.py tests/integration/infrastructure/test_sqlite_certification_store.py tests/unit/infrastructure/test_certification_cli.py tests/unit/infrastructure/test_cli_main.py tests/unit/infrastructure/test_tui.py tests/unit/domain/test_mission_pack.py tests/unit/skills/test_mission_pack_loader.py tests/unit/skills/test_domain_skills.py tests/unit/presentation/test_prompt_mission_section.py tests/unit/presentation/test_prompt_sections_authority_and_audience.py tests/unit/application/test_prompt_builder.py tests/unit/application/test_agent_factory.py tests/unit/application/test_hooks.py tests/unit/runtime/test_autonomy_policy_basic.py tests/integration/test_mission_boundary_enforcement.py tests/integration/test_autonomy_policy_matrix.py` -> **166 passed**
  - `ruff check src/ds_agent/domain/entities/certification.py src/ds_agent/domain/interfaces/certification.py src/ds_agent/domain/entities/mission_pack.py src/ds_agent/infrastructure/persistence/certification_store.py src/ds_agent/application/services/certification_usecases.py src/ds_agent/cli/certification_cli.py src/ds_agent/cli/commands.py src/ds_agent/cli/main.py src/ds_agent/runtime/autonomy_policy.py src/ds_agent/agent/permissions.py src/ds_agent/agent/builtin_hooks.py src/ds_agent/agent/factory.py tests/unit/domain/test_certification_spec.py tests/unit/application/test_submit_certification.py tests/integration/infrastructure/test_sqlite_certification_store.py tests/unit/infrastructure/test_certification_cli.py tests/unit/domain/test_mission_pack.py tests/unit/skills/test_mission_pack_loader.py tests/unit/runtime/test_autonomy_policy_basic.py tests/unit/application/test_hooks.py tests/unit/infrastructure/test_tui.py tests/unit/infrastructure/test_cli_main.py` -> **ok**
  - `mypy src/ds_agent/domain/entities/certification.py src/ds_agent/domain/interfaces/certification.py src/ds_agent/domain/entities/mission_pack.py src/ds_agent/infrastructure/persistence/certification_store.py src/ds_agent/application/services/certification_usecases.py src/ds_agent/cli/certification_cli.py src/ds_agent/runtime/autonomy_policy.py src/ds_agent/agent/permissions.py src/ds_agent/agent/builtin_hooks.py src/ds_agent/agent/factory.py` -> **ok** (tool note: existing `pyproject.toml` still reports unused override entries for `google.generativeai.*`, `telegram.*`, `uvicorn.*`)
  - `python -m compileall src/ds_agent/domain/entities/certification.py src/ds_agent/domain/interfaces/certification.py src/ds_agent/domain/entities/mission_pack.py src/ds_agent/infrastructure/persistence/certification_store.py src/ds_agent/application/services/certification_usecases.py src/ds_agent/cli/certification_cli.py src/ds_agent/cli/commands.py src/ds_agent/cli/main.py src/ds_agent/runtime/autonomy_policy.py src/ds_agent/agent/permissions.py src/ds_agent/agent/builtin_hooks.py src/ds_agent/agent/factory.py tests/unit/domain/test_certification_spec.py tests/unit/application/test_submit_certification.py tests/integration/infrastructure/test_sqlite_certification_store.py tests/unit/infrastructure/test_certification_cli.py tests/unit/domain/test_mission_pack.py tests/unit/skills/test_mission_pack_loader.py tests/unit/runtime/test_autonomy_policy_basic.py tests/unit/application/test_hooks.py tests/unit/infrastructure/test_tui.py tests/unit/infrastructure/test_cli_main.py` -> **ok**

### Telegram certification surface update

- Added `src/ds_agent/presentation/certification_presenters.py` so CLI and Telegram share one plain-text certification renderer.
- Extended `src/ds_agent/gateway/telegram_runner.py` with `/certification` support:
  - `/certification <mission>` or `/certification status <mission>` for mission readiness/status
  - `/certification submit <mission> <level> [approver...]` for operator-side certification submission
- Updated Telegram help/menu surfaces so certification appears alongside contract/verdict policy controls.
- Added Telegram coverage in `tests/unit/infrastructure/test_task_contract_telegram.py` and presenter coverage in `tests/unit/presentation/test_certification_presenters.py`.
- Verification:
  - `pytest tests/unit/presentation/test_certification_presenters.py tests/unit/infrastructure/test_certification_cli.py tests/unit/infrastructure/test_task_contract_telegram.py` -> **9 passed**
  - `pytest tests/unit/domain/test_certification_spec.py tests/unit/application/test_submit_certification.py tests/integration/infrastructure/test_sqlite_certification_store.py tests/unit/presentation/test_certification_presenters.py tests/unit/infrastructure/test_certification_cli.py tests/unit/infrastructure/test_task_contract_telegram.py tests/unit/infrastructure/test_cli_main.py tests/unit/infrastructure/test_tui.py tests/unit/domain/test_mission_pack.py tests/unit/skills/test_mission_pack_loader.py tests/unit/skills/test_domain_skills.py tests/unit/presentation/test_prompt_mission_section.py tests/unit/presentation/test_prompt_sections_authority_and_audience.py tests/unit/application/test_prompt_builder.py tests/unit/application/test_agent_factory.py tests/unit/application/test_hooks.py tests/unit/runtime/test_autonomy_policy_basic.py tests/integration/test_mission_boundary_enforcement.py tests/integration/test_autonomy_policy_matrix.py` -> **174 passed**
  - `ruff check src/ds_agent/presentation/certification_presenters.py src/ds_agent/cli/certification_cli.py src/ds_agent/gateway/telegram_runner.py tests/unit/presentation/test_certification_presenters.py tests/unit/infrastructure/test_certification_cli.py tests/unit/infrastructure/test_task_contract_telegram.py` -> **ok**
  - `mypy src/ds_agent/presentation/certification_presenters.py src/ds_agent/cli/certification_cli.py` -> **ok** (note: `telegram_runner.py` still has pre-existing broad typing debt outside this change set)
  - `python -m compileall src/ds_agent/presentation/certification_presenters.py src/ds_agent/cli/certification_cli.py src/ds_agent/gateway/telegram_runner.py tests/unit/presentation/test_certification_presenters.py tests/unit/infrastructure/test_certification_cli.py tests/unit/infrastructure/test_task_contract_telegram.py` -> **ok**

### Electron certification surface update

- Added `src/ds_agent/api/routes/certification.py` and wired it into `src/ds_agent/api/app.py` so Electron can list mission certification snapshots, inspect one mission, and submit approvals through HTTP.
- Extended `electron/src/main/ipc.ts`, `electron/src/preload/index.ts`, and `electron/src/renderer/vite-env.d.ts` with a typed `certification` bridge (`list/status/submit`).
- Added `electron/src/renderer/types/certification.ts`, `electron/src/renderer/hooks/useCertificationBoard.ts`, and `electron/src/renderer/components/runtime/CertificationBoard.tsx`.
- Updated `electron/src/renderer/components/layout/Sidebar.tsx` so the Runtime tab now exposes a certification board with mission selection, readiness summary, evidence metrics, approval input, and submit action.
- Added `tests/unit/infrastructure/test_certification_api_routes.py` for certification HTTP route coverage.
- Verification:
  - `pytest tests/unit/infrastructure/test_certification_api_routes.py tests/unit/infrastructure/test_certification_cli.py tests/unit/infrastructure/test_task_contract_api_routes.py` -> **10 passed**
  - `pytest tests/unit/infrastructure/test_certification_api_routes.py tests/unit/infrastructure/test_certification_cli.py tests/unit/infrastructure/test_task_contract_api_routes.py tests/unit/infrastructure/test_api.py` -> **95 passed**
  - `ruff check src/ds_agent/api/routes/certification.py tests/unit/infrastructure/test_certification_api_routes.py` -> **ok**
  - `mypy src/ds_agent/api/routes/certification.py` -> **ok**
  - `python -m compileall src/ds_agent/api/routes/certification.py tests/unit/infrastructure/test_certification_api_routes.py` -> **ok**
  - `cd electron && npm run typecheck` -> **ok**
  - `cd electron && npm run build` -> **ok** (note: existing Vite bundle-size warning on large chunks remains unchanged)

### Policy Studio + Audience preview update

- Added `electron/src/renderer/components/settings/PolicyStudio.tsx` and `electron/src/renderer/components/settings/policyStudioCatalog.ts`.
- Extended `electron/src/renderer/components/settings/SettingsPanel.tsx` so Electron Settings now exposes a `Policy Studio` section.
- Reused the existing TaskContract + certification surfaces so operators can edit the current session contract's `authority`, `audience`, and `mission`, inspect runtime overlay precedence, browse certification-aware mission options, and preview audience-shaped sample responses before applying contract changes.
- This first slice left Action Matrix editing as the immediate follow-up handled in the next update below.
- Verification:
  - `cd electron && npm run typecheck` -> **ok**
  - `cd electron && npm run build` -> **ok** (note: existing Vite bundle-size warning on large chunks remains unchanged)

### Policy Studio Action Matrix override update

- Extended `src/ds_agent/runtime/action_matrix.py` with `with_overrides()` so persisted operator overrides can layer on top of the default authority matrix.
- Extended `src/ds_agent/runtime/policy_store.py` with `get_action_matrix_overrides()`, `set_action_matrix_overrides()`, and `build_action_matrix()` backed by `policy.json`.
- Extended `src/ds_agent/api/ws_handler.py`, `src/ds_agent/agent/permissions.py`, `src/ds_agent/agent/builtin_hooks.py`, and `src/ds_agent/agent/factory.py` so `policy.get` now returns matrix rows/overrides, `policy.setActionMatrixOverrides` persists operator edits, and runtime tool decisions enforce the persisted matrix.
- Extended `electron/src/renderer/stores/policyStore.ts`, `electron/src/renderer/hooks/usePolicy.ts`, and `electron/src/renderer/components/runtime/PolicyPanel.tsx` so the renderer keeps a typed Action Matrix snapshot and exposes override counts in Runtime policy status.
- Extended `electron/src/renderer/components/settings/policyStudioCatalog.ts` and `electron/src/renderer/components/settings/PolicyStudio.tsx` so Settings now provides Action Matrix preview/diff/apply with per-cell override editing, live draft counts, preview verdicts, reset/clear actions, and save-through to the backend.
- Added regression coverage in `tests/unit/runtime/test_action_matrix.py`, `tests/unit/infrastructure/test_policy_runtime.py`, `tests/unit/application/test_hooks.py`, and `tests/unit/infrastructure/test_api.py`.
- Verification:
  - `pytest tests/unit/runtime/test_action_matrix.py tests/unit/infrastructure/test_policy_runtime.py tests/unit/application/test_hooks.py tests/unit/infrastructure/test_api.py tests/integration/test_autonomy_policy_matrix.py` -> **162 passed**
  - `ruff check src/ds_agent/runtime/action_matrix.py src/ds_agent/runtime/policy_store.py src/ds_agent/agent/permissions.py src/ds_agent/agent/builtin_hooks.py src/ds_agent/api/ws_handler.py src/ds_agent/agent/factory.py tests/unit/runtime/test_action_matrix.py tests/unit/infrastructure/test_policy_runtime.py tests/unit/application/test_hooks.py tests/unit/infrastructure/test_api.py tests/integration/test_autonomy_policy_matrix.py` -> **ok**
  - `mypy src/ds_agent/runtime/action_matrix.py src/ds_agent/agent/permissions.py src/ds_agent/agent/builtin_hooks.py src/ds_agent/agent/factory.py` -> **ok**
  - `python -m compileall src/ds_agent/runtime/action_matrix.py src/ds_agent/runtime/policy_store.py src/ds_agent/agent/permissions.py src/ds_agent/agent/builtin_hooks.py src/ds_agent/api/ws_handler.py src/ds_agent/agent/factory.py` -> **ok**
  - `cd electron && npm run typecheck` -> **ok**
  - `cd electron && npm run build` -> **ok** (note: existing Vite bundle-size warning on large chunks remains unchanged)

### ActionClassifier strategy coverage update

- Refactored `src/ds_agent/runtime/action_classifier.py` into ordered classification strategies for fixed tool maps, SQL actions, deployment targets, governance/autonomy mutations, and generic Python execution.
- Expanded internal tool coverage for read-only coordination/search, artifact-generation, governance controls, and Git/Jira-style mutation tools so high-traffic autonomy actions no longer fall through the generic path by default.
- Updated `src/ds_agent/agent/permissions.py` so `PermissionPolicy` always passes the classifier result into `AutonomyPolicy`, including `unknown`, which now routes through the matrix's conservative unknown row instead of bypassing matrix enforcement.
- Expanded `tests/unit/runtime/test_action_classifier.py`, `tests/unit/application/test_hooks.py`, and `tests/integration/test_autonomy_policy_matrix.py` to cover strategy separation, broader tool mappings, destructive SQL / Python heuristics, conservative `unknown` behavior, and matrix-aware permission enforcement for Git PR creation.
- Verification:
  - `pytest tests/unit/runtime/test_action_classifier.py tests/unit/runtime/test_action_matrix.py tests/unit/runtime/test_autonomy_policy_basic.py tests/unit/infrastructure/test_policy_runtime.py tests/unit/application/test_hooks.py tests/unit/infrastructure/test_api.py tests/integration/test_autonomy_policy_matrix.py` -> **230 passed**
  - `ruff check src/ds_agent/runtime/action_classifier.py src/ds_agent/agent/permissions.py tests/unit/runtime/test_action_classifier.py tests/unit/application/test_hooks.py tests/integration/test_autonomy_policy_matrix.py` -> **ok**
  - `mypy src/ds_agent/runtime/action_classifier.py src/ds_agent/agent/permissions.py` -> **ok** (tool note: existing `pyproject.toml` still reports unused override entries for `anthropic.*`, `fastapi.*`, `google.*`, `google.generativeai.*`, `litellm.*`, `openai.*`, `starlette.*`, `telegram.*`, `tiktoken.*`, `uvicorn.*`, `yaml.*`)
  - `python -m compileall src/ds_agent/runtime/action_classifier.py src/ds_agent/agent/permissions.py tests/unit/runtime/test_action_classifier.py tests/unit/application/test_hooks.py tests/integration/test_autonomy_policy_matrix.py` -> **ok**

### Incident + Freeze overlay update

- Added `src/ds_agent/runtime/authority_overlay.py` with typed overlay resolution, 24-hour incident expiry, and effective-authority fallback helpers.
- Extended `src/ds_agent/config/schema.py`, `src/ds_agent/api/routes/config.py`, `src/ds_agent/api/config_manager.py`, and `src/ds_agent/api/ws_handler.py` so `gateway.authority_overlay` persists, incident start time is auto-stamped, expired incidents auto-clear, and runtime status now exposes `authorityOverlay`, `authorityOverlayStartedAt`, `authorityOverlayExpiresAt`, and `effectiveAuthorityMode`.
- Extended `src/ds_agent/api/agent_session_registry.py`, `src/ds_agent/agent/factory.py`, `src/ds_agent/agent/core.py`, `src/ds_agent/agent/hooks.py`, `src/ds_agent/agent/prompt_builder.py`, `src/ds_agent/agent/builtin_hooks.py`, `src/ds_agent/runtime/autonomy_policy.py`, and `src/ds_agent/agent/permissions.py` so cached session agents are recreated when the overlay changes, incident/freeze overrides the TaskContract authority in prompts + hooks, freeze blocks write-side actions, incident keeps irreversible actions on the approval path, and audit logs record the active overlay.
- Added `src/ds_agent/cli/mode_cli.py` and extended `src/ds_agent/cli/main.py` with `ds-agent mode status|incident start|incident end|freeze|freeze end`.
- Extended `src/ds_agent/gateway/telegram_runner.py`, `electron/src/renderer/stores/runtimeStore.ts`, and `electron/src/renderer/components/runtime/GatewayStatusPanel.tsx` so Telegram-created agents respect the same overlay and Electron Runtime Console can view/change it.
- Added `tests/unit/runtime/test_authority_overlay.py`, `tests/unit/infrastructure/test_mode_cli.py`, and expanded `tests/unit/runtime/test_autonomy_policy_basic.py`, `tests/unit/application/test_hooks.py`, `tests/unit/application/test_prompt_builder.py`, `tests/unit/infrastructure/test_agent_session_registry.py`, `tests/unit/infrastructure/test_api.py`, `tests/unit/infrastructure/test_policy_runtime.py`, `tests/unit/infrastructure/test_autonomous_runtime.py`, `tests/unit/infrastructure/test_config.py`, `tests/unit/infrastructure/test_config_manager.py`, and `tests/unit/infrastructure/test_cli_main.py`.
- Verification:
  - `pytest tests/unit/runtime/test_authority_overlay.py tests/unit/runtime/test_autonomy_policy_basic.py tests/unit/application/test_hooks.py tests/unit/application/test_prompt_builder.py tests/unit/infrastructure/test_agent_session_registry.py tests/unit/infrastructure/test_config.py tests/unit/infrastructure/test_config_manager.py tests/unit/infrastructure/test_api.py tests/unit/infrastructure/test_policy_runtime.py tests/unit/infrastructure/test_autonomous_runtime.py tests/unit/infrastructure/test_mode_cli.py tests/unit/infrastructure/test_cli_main.py` -> **291 passed**
  - `ruff check src/ds_agent/runtime/authority_overlay.py src/ds_agent/api/agent_session_registry.py src/ds_agent/agent/hooks.py src/ds_agent/agent/core.py src/ds_agent/agent/factory.py src/ds_agent/agent/prompt_builder.py src/ds_agent/agent/builtin_hooks.py src/ds_agent/agent/permissions.py src/ds_agent/api/ws_handler.py src/ds_agent/cli/main.py src/ds_agent/cli/mode_cli.py src/ds_agent/gateway/telegram_runner.py tests/unit/runtime/test_authority_overlay.py tests/unit/runtime/test_autonomy_policy_basic.py tests/unit/application/test_hooks.py tests/unit/application/test_prompt_builder.py tests/unit/infrastructure/test_agent_session_registry.py tests/unit/infrastructure/test_config.py tests/unit/infrastructure/test_config_manager.py tests/unit/infrastructure/test_api.py tests/unit/infrastructure/test_policy_runtime.py tests/unit/infrastructure/test_autonomous_runtime.py tests/unit/infrastructure/test_mode_cli.py tests/unit/infrastructure/test_cli_main.py` -> **ok**
  - `mypy src/ds_agent/runtime/authority_overlay.py src/ds_agent/api/agent_session_registry.py src/ds_agent/agent/factory.py src/ds_agent/agent/prompt_builder.py src/ds_agent/cli/main.py src/ds_agent/cli/mode_cli.py` -> **ok** (tool note: `pyproject.toml` still reports unused override entries for `google.generativeai.*`, `telegram.*`, `uvicorn.*`)
  - `python -m compileall src/ds_agent/runtime/authority_overlay.py src/ds_agent/api/agent_session_registry.py src/ds_agent/agent/hooks.py src/ds_agent/agent/core.py src/ds_agent/agent/factory.py src/ds_agent/agent/prompt_builder.py src/ds_agent/agent/builtin_hooks.py src/ds_agent/agent/permissions.py src/ds_agent/api/ws_handler.py src/ds_agent/cli/main.py src/ds_agent/cli/mode_cli.py src/ds_agent/gateway/telegram_runner.py` -> **ok**
  - `cd electron && npm run typecheck` -> **ok**
  - `cd electron && npm run build` -> **ok** (note: existing Vite bundle-size warning on large chunks remains unchanged)

- **현재 상태**: Phase 0 완료권 진입, Phase 1 기반 연결, Phase 2 Mission Pack 초기 연결, 그리고 Phase 3 certification operator surface가 CLI/TUI/Telegram/Electron까지 확장되었다. Authority/Audience 축의 typed value object, matrix-aware permission, MissionPack YAML loader, prompt mission injection, certification persistence, operator submit/status surface가 코드에 들어갔다.
- **이번 세션 반영 코드**
  - `src/ds_agent/domain/value_objects/authority_mode.py`
  - `src/ds_agent/domain/value_objects/audience_persona.py`
  - `src/ds_agent/runtime/autonomy_policy.py`
  - `src/ds_agent/domain/value_objects/action_class.py`
  - `src/ds_agent/runtime/action_matrix.py`
  - `src/ds_agent/runtime/action_classifier.py`
  - `src/ds_agent/domain/entities/task_contract.py`
  - `src/ds_agent/application/dtos/task_contract.py`
  - `src/ds_agent/application/services/task_contract_usecases.py`
  - `src/ds_agent/infrastructure/persistence/task_contract_store.py`
  - `src/ds_agent/agent/prompt_sections.py`
  - `src/ds_agent/agent/prompt_builder.py`
  - `src/ds_agent/agent/factory.py`
  - `src/ds_agent/tools/task_contract_tools.py`
  - `src/ds_agent/presentation/task_contract_presenters.py`
  - `tests/unit/domain/test_authority_mode.py`
  - `tests/unit/domain/test_audience_persona.py`
  - `tests/unit/domain/test_action_class.py`
  - `tests/unit/domain/test_task_contract_entity.py`
  - `tests/unit/presentation/test_prompt_sections_authority_and_audience.py`
  - `tests/unit/runtime/test_action_classifier.py`
  - `tests/unit/runtime/test_action_matrix.py`
  - `tests/unit/runtime/test_autonomy_policy_basic.py`
  - `tests/integration/test_autonomy_policy_matrix.py`
  - `tests/unit/application/test_task_contract_usecases.py`
  - `tests/integration/infrastructure/test_sqlite_task_contract_store.py`
  - `tests/unit/tools/test_task_contract_tools.py`
  - `tests/unit/application/test_hooks.py`
  - `tests/unit/application/test_prompt_builder.py`
- **반영 범위**
  - legacy `auto/supervised/step_by_step` → `AuthorityMode`/`AudiencePersona` 매핑 추가
  - `AuthorityMode.transition_requirement()` / `blocks_external_writes` 등 Phase 0 수준 정책 값 객체 도입
  - `AudiencePersona.spec()` 기반 기본 산출물/불확실성 스타일 정의
  - system prompt에 `AUTHORITY MODE`, `AUDIENCE PROFILE` 섹션 상시 주입
  - `PromptBuilder`가 legacy mode 없이 생성되더라도 기본값(`delegate`, `peer_ds`)을 해석하도록 연결
  - `TaskContract`에 `authority`, `audience`, `mission` 필드 추가 및 DTO/usecase/tool/store 경로 전체 round-trip 연결
  - 활성 TaskContract가 있으면 `PromptBuilder`가 계약의 authority/audience를 legacy mode보다 우선 사용하도록 연결
  - Task contract SQLite store에 compatibility migration v6 추가 (`authority`, `audience`, `mission` 컬럼)
  - CLI/Telegram 요약 surface가 계약의 3축 컨텍스트를 함께 보여주도록 presenter 확장
  - `ActionClass` 카탈로그와 기본 `ActionMatrix` 구현
  - core tool(`sql_query`, `train_model`, `create_jira_ticket`, `send_to_slack`, `generate_deployment`) 기준 initial `ActionClassifier` 구현
  - `AutonomyPolicy.evaluate()`가 optional `action_class`를 해석해 `auto/ask/approve/dual/skip` verdict를 approval/block으로 변환
  - `PermissionPolicy`가 legacy 분기문 대신 `AutonomyPolicy`를 사용하고, known tool은 `ActionClassifier` + `ActionMatrix` verdict까지 반영하도록 연결
  - `PermissionPolicy.check()` / `PermissionHook`이 tool arguments를 classifier에 전달하도록 리팩터링
  - integration test로 `sql_query(pii|bronze)`, `generate_deployment(production)`의 classifier→matrix→permission flow 고정
- **검증 결과**
  - `pytest tests/unit/domain/test_authority_mode.py tests/unit/domain/test_audience_persona.py tests/unit/presentation/test_prompt_sections_authority_and_audience.py tests/unit/runtime/test_autonomy_policy_basic.py tests/unit/application/test_prompt_builder.py` → **42 passed**
  - `pytest tests/unit/domain/test_task_contract_entity.py tests/integration/infrastructure/test_sqlite_task_contract_store.py tests/unit/application/test_task_contract_usecases.py tests/unit/tools/test_task_contract_tools.py tests/unit/application/test_prompt_builder.py` → **42 passed**
  - `pytest tests/unit/domain/test_action_class.py tests/unit/runtime/test_action_matrix.py tests/unit/runtime/test_autonomy_policy_basic.py tests/unit/application/test_hooks.py` → **46 passed**
  - `pytest tests/unit/runtime/test_action_classifier.py tests/unit/runtime/test_action_matrix.py tests/unit/runtime/test_autonomy_policy_basic.py tests/unit/domain/test_action_class.py` → **23 passed**
  - `pytest tests/unit/application/test_hooks.py tests/unit/runtime/test_action_classifier.py tests/unit/runtime/test_action_matrix.py tests/unit/runtime/test_autonomy_policy_basic.py` → **50 passed**
  - `pytest tests/integration/test_autonomy_policy_matrix.py tests/unit/application/test_hooks.py tests/unit/runtime/test_action_classifier.py tests/unit/runtime/test_action_matrix.py tests/unit/runtime/test_autonomy_policy_basic.py` → **55 passed**
  - `python -m compileall src/ds_agent/domain/value_objects/authority_mode.py src/ds_agent/domain/value_objects/audience_persona.py src/ds_agent/runtime/autonomy_policy.py src/ds_agent/agent/prompt_sections.py src/ds_agent/agent/prompt_builder.py src/ds_agent/agent/factory.py` → **ok**
  - `python -m compileall src/ds_agent/domain/entities/task_contract.py src/ds_agent/application/dtos/task_contract.py src/ds_agent/application/services/task_contract_usecases.py src/ds_agent/tools/task_contract_tools.py src/ds_agent/presentation/task_contract_presenters.py src/ds_agent/infrastructure/persistence/task_contract_store.py src/ds_agent/agent/prompt_sections.py src/ds_agent/agent/prompt_builder.py` → **ok**
  - `python -m compileall src/ds_agent/domain/value_objects/action_class.py src/ds_agent/runtime/action_matrix.py src/ds_agent/runtime/autonomy_policy.py` → **ok**
  - `python -m compileall src/ds_agent/runtime/action_classifier.py tests/unit/runtime/test_action_classifier.py` → **ok**
  - `python -m compileall src/ds_agent/agent/permissions.py src/ds_agent/runtime/action_classifier.py src/ds_agent/runtime/action_matrix.py src/ds_agent/runtime/autonomy_policy.py` → **ok**
  - `python -m compileall src/ds_agent/agent/permissions.py src/ds_agent/agent/builtin_hooks.py tests/integration/test_autonomy_policy_matrix.py` → **ok**
- **미완료 / 다음 단계**
  - `ActionClassifier` 구현 및 tool → action class 매핑
  - incident / freeze overlay
  - Completed on 2026-04-16. Remaining next steps are PolicyStudio / Audience preview and legacy migration helper/docs.
  - Update on 2026-04-16: PolicyStudio / Audience preview is now complete. The remaining next steps are Action Matrix preview/diff/apply, broader `ActionClassifier` strategy coverage, and legacy migration helper/docs.
  - Update on 2026-04-16: PolicyStudio Action Matrix preview/diff/apply is now complete. The remaining next steps are broader `ActionClassifier` strategy coverage, visual regression / Playwright E2E, and legacy migration helper/docs.
  - Update on 2026-04-16: ActionClassifier strategy separation and broader tool coverage are now complete, including conservative matrix handling for `unknown`. The remaining next steps are visual regression / Playwright E2E and legacy migration helper/docs.
  - Update on 2026-04-16: packaged-backend visual regression / Playwright E2E is now complete through `electron/tests/smoke/autonomy-control-plane.spec.ts` and isolated workspace seeding.
  - Update on 2026-04-16: legacy migration helper/docs is now complete through `ds-agent mode migrate [legacy-mode]` and the PolicyStudio legacy-mapping helper card.
  - Update on 2026-04-16: rollout polish now includes PolicyStudio quick presets for delegated peer, executive review, audit guard, and mentor walkthrough draft shaping.
  - Update on 2026-04-16: import-boundary coverage is now added through `.importlinter`, `scripts/check_import_contracts.py`, and `tests/unit/architecture/test_import_contracts.py`.
  - Current remaining follow-up: no explicit feature-scope gaps remain inside the current autonomy-control-plane plan slice.

---

## 1. 배경 및 문제 정의

### 1.1 현재 상태

DS Agent는 전역 실행 모드를 단일 enum으로 관리한다.

```
runtime/policy_engine.py
    ├── RunMode = Literal["auto", "supervised", "step_by_step"]
    ├── PolicyEngine.requires_approval(tool_call) -> bool
    └── PolicyEngine.notify_blocked(...) → hook emission
```

- `auto`: 모든 도구 자동 실행. 승인 프롬프트 없음.
- `supervised`: 쓰기/외부 호출 전 승인 프롬프트.
- `step_by_step`: 모든 단계 전 승인.

### 1.2 한계

1. **전역 스위치의 경직성** — 사용자는 "read-only는 자율, 배포는 승인"을 원하지만 mode를 auto로 두면 배포까지 자동, supervised로 두면 SQL 한 줄마다 승인을 받아야 한다.
2. **행동 종류에 무감각** — `tool_call.tool == "sql"` 수준에서만 판단하고, `data_domain`, `sensitivity`, `side_effect_magnitude`를 고려하지 않는다.
3. **청중 고려 없음** — 주니어 DS에게도, 임원에게도, 감사자에게도 같은 산출물과 같은 tone으로 응답한다.
4. **업무 맥락 부재** — "주간 KPI 트리아지"처럼 반복되는 업무에서 필수 검증/산출물/에스컬레이션 조건이 매번 새로 지정되어야 한다.
5. **인증 개념 없음** — Autopilot은 단순히 "자동 실행 허용 여부"로만 존재하며, 특정 playbook이 충분히 검증된 뒤에만 자율 실행을 허용하는 승급 제도가 없다.
6. **인시던트/프리즈 부재** — 장애 대응 시 속도를 올리거나, 감사 기간 동안 외부 write를 일괄 차단하는 정책 프리셋이 없다.

### 1.3 이 문서의 범위

자율성을 **3개의 독립 축** (Authority × Audience × Mission) 위에 재설계하고, 행동 단위로 정책을 적용하는 Autonomy Matrix, Playbook Certification 제도를 정의한다. LLM이 orchestrator라는 원칙은 훼손하지 않는다: Mission Pack은 하드코딩된 워크플로가 아니라, 스킬과 같은 **프롬프트 자산**이다.

---

## 2. 핵심 테제

> **자율성은 하나의 스위치가 아니라 3축 벡터다.**
>
> 동일한 도구 호출도 (1) 에이전트가 어떤 권한을 위임받았는지(Authority), (2) 누구에게 보고하는지(Audience), (3) 어떤 업무를 수행 중인지(Mission)에 따라 승인/거절/자율 실행 여부와 산출물 포맷이 달라진다.

세 축은 서로 직교한다.

- **Authority × Audience**: Shadow 모드에서도 Executive 청중에게는 1-page brief를 산출한다.
- **Authority × Mission**: 동일한 Delegate 모드라도 `weekly-kpi-triage` 안에서는 Jira 티켓 생성이 허용되고, `ad-hoc-exploration` 안에서는 허용되지 않는다.
- **Audience × Mission**: 동일한 `weekly-kpi-triage`라도 Auditor 청중에게는 lineage 문서가, Executive 청중에게는 impact/risk 카드가 기본 산출물이 된다.

3축을 조합한 뒤 **Action Class별 매트릭스**를 통해 최종 실행 정책을 도출한다.

---

## 3. 축 1: Authority Mode (6종)

### 3.1 정의

```
domain/value_objects/authority_mode.py

class AuthorityMode(str, Enum):
    SHADOW     = "shadow"
    SUPERVISED = "supervised"
    DELEGATE   = "delegate"
    AUTOPILOT  = "autopilot"
    INCIDENT   = "incident"
    FREEZE     = "freeze"
```

### 3.2 각 모드 상세

#### 3.2.1 Shadow

- **의도**: 에이전트가 전체 plan을 수행하되 외부 side effect는 전혀 발생시키지 않는다. 리허설/검증 모드.
- **Side Effect**: 금지. 모든 write 계열 action은 "시뮬레이션"으로 기록되고 실제 호출은 되지 않는다.
- **승인 정책**: 승인 프롬프트 없음 (어차피 실행되지 않으므로).
- **산출물**: "이렇게 실행했을 것이다" 형식의 reasoning trace + dry-run diff.
- **전환 규칙**: 모든 모드 → Shadow 즉시 허용. Shadow → Supervised/Delegate는 사용자 명령으로만.
- **사용 시나리오**: 새 Mission Pack 도입기, 인증 요건인 `shadow_runs_passed` 누적.

#### 3.2.2 Supervised

- **의도**: 보수적 기본값. 모든 의미 있는 액션 전 사람 승인.
- **Side Effect**: 승인 후 허용.
- **승인 정책**: read-only(gold tier)를 제외한 모든 action class에서 approve 요청.
- **산출물**: 승인 단위마다 "왜 이 액션이 필요한가" 설명.
- **전환 규칙**: Authority 다운그레이드 (→ Shadow/Freeze)는 자유. 업그레이드 (→ Delegate 이상)는 오너 2명 승인 필요.
- **사용 시나리오**: 신규 사용자 온보딩, 검증되지 않은 Mission Pack.

#### 3.2.3 Delegate

- **의도**: 반복적 저위험 액션은 자동, 고위험은 승인. 대부분 사용자의 일상 기본값.
- **Side Effect**: 조건부 — Action Class가 `low_sensitivity / low_cost`인 경우 자동.
- **승인 정책**: 고위험 action class (sensitive_read, prod_deploy, external_comms)만 approve.
- **산출물**: 자동 실행 결과 요약 + 위임 범위를 초과한 액션 목록.
- **전환 규칙**: Supervised ↔ Delegate는 오너 승인 1회. Delegate → Autopilot은 Certification 통과 필요.
- **사용 시나리오**: 숙련 DS 개인 사용, 승인된 반복 업무.

#### 3.2.4 Autopilot

- **의도**: 인증된 Mission Pack의 boundary 안에서 무인 실행.
- **Side Effect**: Mission Pack이 명시한 `allowed_data_domains`, `required_checks`, `auto_escalate_when` 범위 내 자동.
- **승인 정책**: boundary 이탈 시에만 approve 또는 escalate.
- **산출물**: 실행 완료 리포트 + Certification 조건 충족 지표 업데이트.
- **전환 규칙**: Mission Pack Certification이 `autopilot` 레벨에 도달한 경우에만 활성화. 단일 critical violation 발생 시 자동으로 Delegate로 다운그레이드.
- **사용 시나리오**: 주간 KPI 트리아지, 일간 데이터 퀄리티 체크.

#### 3.2.5 Incident

- **의도**: 장애/긴급 상황. 속도와 근본 원인 파악을 최우선으로 하며 설명은 축약.
- **Side Effect**: 긴급 실행 허용. 단, 모든 액션은 사후 감사 로그에 상세 기록.
- **승인 정책**: 사전 승인 대신 **사후 보고**. 단, `prod_deploy`, `external_comms`는 여전히 사전 승인.
- **산출물**: 타임라인, 영향 범위, 즉시 mitigation, 근본 원인 가설.
- **전환 규칙**: 수동 활성화만. 자동 종료 조건 — 24시간 경과 또는 사용자 명시적 종료.
- **사용 시나리오**: 프로덕션 모델 성능 급락, 데이터 파이프 장애.

#### 3.2.6 Freeze

- **의도**: 읽기 전용. 모든 외부 write와 비용 발생 작업 차단.
- **Side Effect**: 금지.
- **승인 정책**: 모든 write action은 거절(skip). 승인 프롬프트도 뜨지 않음 — 아예 불가.
- **산출물**: 분석/조회 결과만.
- **전환 규칙**: 해제하려면 오너 승인.
- **사용 시나리오**: 분기 결산 기간, 외부 감사 진행 중, 규제 동결 기간.

### 3.3 Authority Mode 전환 매트릭스

| From \ To  | Shadow | Supervised | Delegate | Autopilot | Incident | Freeze |
|------------|--------|------------|----------|-----------|----------|--------|
| Shadow     | —      | 자유        | 오너 승인 1 | Cert 필요 | 수동 활성 | 자유 |
| Supervised | 자유   | —          | 오너 승인 1 | Cert 필요 | 수동 활성 | 자유 |
| Delegate   | 자유   | 자유        | —        | Cert 필요  | 수동 활성 | 자유 |
| Autopilot  | 자유   | 자유        | 자유      | —         | 수동 활성 | 자유 |
| Incident   | 자유   | 자유        | 자유      | —          | —       | 자유 |
| Freeze     | 오너 승인 | 오너 승인 | 오너 승인 | 오너 승인  | 오너 승인 | — |

다운그레이드(Autopilot → Supervised 등)는 안전 방향이므로 항상 허용. 업그레이드는 승인/인증 필요.

---

## 4. 축 2: Audience Profile (5종)

### 4.1 정의

```
domain/value_objects/audience_persona.py

class AudiencePersona(str, Enum):
    JUNIOR_MENTOR = "junior_mentor"
    PEER_DS       = "peer_ds"
    SENIOR_STAFF  = "senior_staff"
    EXECUTIVE     = "executive"
    AUDITOR       = "auditor"
```

### 4.2 Persona 사양

| 프로필 | Tone | 설명 Depth | 기본 산출물 | Challenge Level | 불확실성 표현 |
|--------|------|-----------|------------|-----------------|---------------|
| Junior Mentor | 교육적, 친절, 질문 유도 | 매우 상세 — "왜 이걸 선택했는지" 포함 | 체크리스트 + 설명 노트 + 코드 주석 | 낮음 — 보수적 임계값 | 명시적 — "이 결과는 ~이유로 불확실합니다" |
| Peer DS | 동료적, 간결, 전문 용어 허용 | 중간 — 대안과 trade-off 포함 | 재현 가능한 artifact (노트북, SQL) | 중간 — 대안 2-3개 제시 | 기술적 — "CI: [0.72, 0.81], p=0.03" |
| Senior/Staff | 단단하고 짧게 | 핵심만 — 가정, 리스크, decision point | 의사결정 메모 + diff | 높음 — scope 재정의 역제안 | 요약형 — "high confidence, one caveat" |
| Executive | 비즈니스 중심, TL;DR 선행 | 최소 — impact/risk/ETA/needed decision | 1-page brief + 액션 카드 | 의사결정 초점 | 직관적 — 🟢/🟡/🔴 (구현 시 문자 토큰 사용) |
| Auditor | provenance 중심, 법정 진술서 톤 | 매우 상세 — 데이터 출처, 정책, 승인 이력 | 감사 추적 문서 + lineage | 제로 — 사실만 기술 | 정량적 + 정책 참조 |

### 4.3 Persona 템플릿 레이어

현재 `agent/prompt_sections.py`는 시스템 프롬프트를 섹션 단위로 조립한다. 여기에 `audience_persona`를 파라미터로 받는 레이어를 추가한다.

```
# agent/prompt_sections.py (확장)

def build_audience_section(persona: AudiencePersona) -> str:
    template = AUDIENCE_TEMPLATES[persona]
    return _render(template, now=datetime.utcnow())

AUDIENCE_TEMPLATES: dict[AudiencePersona, str] = {
    AudiencePersona.EXECUTIVE: """
        AUDIENCE: Executive
        - Lead with business impact and required decision.
        - Use one-page brief format: Situation, Impact, Options, Recommendation.
        - Avoid technical jargon unless it is the decision criterion.
        - Risk labels: SAFE / REVIEW / DANGER (use exact tokens).
        - Cite numbers with business units (revenue, users, margin).
    """,
    AudiencePersona.AUDITOR: """
        AUDIENCE: Auditor
        - Every claim must carry a source reference: table@snapshot or policy clause.
        - Include lineage: source -> transform -> output for each number.
        - Never speculate. If unknown, state 'Not available in current records'.
        - Attach approval history for any write action.
    """,
    # ... 나머지 3종
}
```

### 4.4 Persona 자동 선택

현재 `TaskContract`(§1 스펙 참조)가 `audience` 필드를 포함한다. `PromptBuilder`는 contract.audience → `AudiencePersona`로 매핑하고 해당 섹션을 시스템 프롬프트에 주입한다. 사용자가 런타임에 `/persona executive`로 override 가능.

---

## 5. 축 3: Mission Pack

### 5.1 위치와 위상

```
skills/
├── builtin/           # 기존 markdown 스킬 (기술 조각)
│   ├── eda.md
│   ├── evaluation.md
│   └── ...
├── shared/            # 기존 markdown 스킬 (기술 조각, 조직 공유)
│   ├── hypothesis-ranking.md
│   └── ...
└── missions/          # 신규 — YAML 기반 업무 패키지
    ├── weekly-kpi-triage.yaml
    ├── ab-test-readout.yaml
    └── ...
```

- **skill (markdown)**: "어떻게 하는가" — 방법론 조각.
- **mission (YAML)**: "무엇을 하는가" — 업무 단위. 필수 검증/산출물/에스컬레이션 조건/기본 Authority & Audience를 선언.

### 5.2 Mission Pack 스키마

```yaml
# skills/missions/weekly-kpi-triage.yaml
name: weekly-kpi-triage
display_name: "주간 KPI 이상치 진단"
version: 1
description: "주요 KPI 이상 감지 시 원인 분석 및 액션 제안"

# 기본 Authority & Audience
authority_default: delegate
audience_default: senior_staff

# 데이터 범위 (semantic_layer와 연결 — §2 스펙 참조)
allowed_data_domains: [growth, sales, marketing]
required_semantic_metrics:
  - monthly_churn_rate
  - revenue_per_user
  - dau

# 필수 검증 (각 항목은 verifier skill id)
required_checks:
  - schema_drift
  - temporal_leakage
  - baseline_compare
  - subgroup_stability
  - causal_assumption_check

# 필수 산출물 (각 항목은 artifact type id)
required_artifacts:
  - exec_brief       # Executive 요약
  - ds_appendix      # DS 상세 분석
  - jira_ticket      # 후속 액션 티켓

# 자동 에스컬레이션 조건 — 하나라도 hit 시 Authority 다운그레이드 + 사람 호출
auto_escalate_when:
  - confidence_low
  - deploy_needed
  - sensitive_data_detected
  - anomaly_severity: critical

# 성공 기준 (자동 verification에 사용)
success_criteria:
  - issue_classified
  - root_cause_identified
  - owner_assigned
  - next_action_proposed

# 연결되는 skill (markdown)
skills_required:
  - builtin/eda
  - builtin/evaluation
  - shared/hypothesis-ranking
  - shared/causal-assumption-check

# Action Matrix override — Mission 내부에서만 적용
action_policy_overrides:
  jira_ticket_create:
    delegate: auto      # weekly-kpi-triage 안에서는 Jira 자동 생성 허용
  slack_message:
    delegate: ask       # 다른 Mission에서는 approve였던 것이 ask로 완화

# Certification (§9 참조)
certification:
  current_level: delegate
  next_target: autopilot
```

### 5.3 Mission Pack Loader

```
skills/mission_pack_loader.py

class MissionPackLoader:
    def __init__(self, root: Path, schema_validator: SchemaValidator):
        self._root = root
        self._validator = schema_validator
        self._cache: dict[str, MissionPack] = {}

    def load(self, name: str) -> MissionPack:
        if name in self._cache:
            return self._cache[name]
        path = self._root / f"{name}.yaml"
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        self._validator.validate(raw, schema=MISSION_PACK_SCHEMA)
        pack = MissionPack.from_dict(raw)
        self._cache[name] = pack
        return pack

    def list(self) -> list[MissionPackSummary]: ...
    def reload(self, name: str) -> MissionPack: ...
```

- 파일 시스템이 source of truth. SQLite는 `certification` 이력과 사용 통계만 저장.
- Loader는 도메인 엔티티 `MissionPack`(§11.3)을 반환하고, infrastructure 계층에 속한다.

### 5.4 Mission Pack과 markdown skill의 관계

| 축 | markdown skill | Mission Pack |
|----|----------------|--------------|
| 포맷 | `.md` | `.yaml` |
| 역할 | 방법론 ("t-test 수행 방법") | 업무 ("주간 KPI 트리아지") |
| 프롬프트 주입 방식 | 필요 시 발췌 문단 | 전체 선언을 system prompt에 구조화 주입 |
| Authority/Audience 기본값 | 없음 | 있음 |
| 필수 검증/산출물 선언 | 없음 | 있음 |
| Certification | 없음 | 있음 |

Mission은 여러 skill을 `skills_required`로 참조한다. skill 자체는 여전히 LLM이 본문을 읽고 판단할 재료다.

---

## 6. Action-Level Autonomy Matrix

### 6.1 Action Class 체계

모든 도구 호출/계획 액션은 하나의 `ActionClass`로 분류된다.

```
domain/value_objects/action_class.py

@dataclass(frozen=True)
class ActionClass:
    name: str                      # 'read_sql_gold', 'jira_create', ...
    data_sensitivity: Sensitivity  # public / internal / restricted / pii
    write_side_effect: WriteEffect # none / local / external / irreversible
    cost_impact: CostImpact        # free / low / medium / high
    reversibility: Reversibility   # reversible / soft_reversible / irreversible
    audit_required: bool
```

표준 Action Class 카탈로그 (초기 버전):

| name | data_sensitivity | write_side_effect | cost_impact | reversibility |
|------|------------------|-------------------|-------------|---------------|
| read_sql_gold | internal | none | low | reversible |
| read_sql_bronze | internal | none | medium | reversible |
| read_sensitive_table | restricted | none | low | reversible |
| read_pii_table | pii | none | low | reversible |
| feature_engineering | internal | local | low | reversible |
| model_training | internal | local | medium | soft_reversible |
| artifact_draft | internal | local | free | reversible |
| jira_create | internal | external | free | soft_reversible |
| slack_post | internal | external | free | soft_reversible |
| email_send | internal | external | free | irreversible |
| staging_deploy | internal | external | low | soft_reversible |
| prod_deploy | internal | external | high | irreversible |
| delete_table | restricted | external | free | irreversible |

### 6.2 Action Class × Authority Mode 기본 매트릭스

결정값은 `auto` / `ask` / `approve` / `dual` / `skip` 5종.

- `auto` — 바로 실행
- `ask` — 짧은 확인 (yes/no) — 기본 "yes"
- `approve` — 명시적 승인 프롬프트 + 이유 기록
- `dual` — 승인자 2명 필요
- `skip` — 실행 거절 (이유 기록, 대체 계획 제안)

| Action Class \ Mode | Shadow | Supervised | Delegate | Autopilot | Incident | Freeze |
|---------------------|--------|------------|----------|-----------|----------|--------|
| read_sql_gold       | auto   | auto       | auto     | auto      | auto     | auto   |
| read_sql_bronze     | auto   | ask        | ask      | auto      | auto     | auto   |
| read_sensitive_table| skip   | approve    | approve  | approve   | approve  | approve|
| read_pii_table      | skip   | approve    | approve  | approve   | approve  | skip   |
| feature_engineering | auto   | auto       | auto     | auto      | auto     | auto   |
| model_training      | auto   | ask        | auto     | auto      | auto     | skip   |
| artifact_draft      | auto   | auto       | auto     | auto      | auto     | auto   |
| jira_create         | skip   | approve    | ask      | auto      | auto     | skip   |
| slack_post          | skip   | approve    | approve  | ask       | auto*    | skip   |
| email_send          | skip   | approve    | approve  | approve   | approve  | skip   |
| staging_deploy      | skip   | approve    | approve  | ask       | auto*    | skip   |
| prod_deploy         | skip   | dual       | dual     | approve   | approve  | skip   |
| delete_table        | skip   | dual       | dual     | dual      | dual     | skip   |

`*` = Incident 모드에서 자동 실행되지만 사후 감사 로그와 오너 알림 필수.

### 6.3 커스터마이즈 메커니즘

세 층위에서 override 가능 (뒤쪽이 우선):

1. **시스템 기본 매트릭스** — 위 6.2 표.
2. **조직 정책** (`runtime/policy_profiles/*.yaml`) — 예: "우리 회사는 Freeze에서도 read_sql_gold 금지".
3. **Mission Pack `action_policy_overrides`** — Mission 안에서만 적용.
4. **Authority Mode 즉시 효과** — Freeze/Incident는 다른 모든 override를 가리는 최상위 레이어.

---

## 7. ActionClassifier

### 7.1 역할

`ActionClassifier`는 에이전트가 실행하려는 도구 호출/계획된 액션을 `ActionClass`로 분류한다. policy_engine는 분류 결과를 매트릭스에 대입하여 결정을 내린다.

### 7.2 입력/출력

```
runtime/action_classifier.py

@dataclass
class ActionCandidate:
    tool: str                 # 'sql', 'python', 'jira', 'slack', ...
    arguments: dict
    mission: Optional[str]
    cost_estimate: Optional[CostEstimate]

class ActionClassifier(Protocol):
    def classify(self, candidate: ActionCandidate) -> ActionClass: ...
```

### 7.3 분류 규칙

다차원 분류를 (1) tool-level base class + (2) argument inspection으로 결합한다.

- `tool="sql"`이면 기본 `read_sql_*`. `arguments.target_schema`의 `domain_tier` (gold/silver/bronze)를 조회해 gold/bronze를 확정.
- `arguments.statement`에 `INSERT/UPDATE/DELETE/DROP/TRUNCATE`가 있으면 `write_table` 또는 `delete_table`로 재분류.
- Semantic Layer(§2 스펙)의 테이블 메타데이터에서 `sensitivity=pii`면 `read_pii_table`.
- `tool="jira"` + `arguments.action=create` → `jira_create`.
- `tool="python"`은 실행 컨텍스트에 따라 `feature_engineering` / `model_training`. `ModelRegistry.is_training_call(...)` 유틸로 판정.
- `cost_estimate.usd > threshold`면 `cost_impact`를 한 단계 상향.

### 7.4 미분류 처리

분류기가 확신하지 못하면 `ActionClass(name="unknown", ...)`를 반환하고, policy_engine은 현재 Authority Mode에 따라 보수적 결정 — Shadow/Supervised/Delegate는 `approve`, Autopilot은 Mission boundary에 포함되지 않는 것으로 간주하여 `escalate`.

---

## 8. AutonomyPolicy Engine

### 8.1 현 policy_engine 대비

현재:

```
runtime/policy_engine.py
    def requires_approval(tool_call) -> bool:
        if self.mode == "auto": return False
        if self.mode == "supervised" and tool_call.has_side_effect: return True
        ...
```

확장 후:

```
runtime/autonomy_policy.py  (policy_engine을 대체하는 것이 아니라 감싸는 확장)

class AutonomyPolicy:
    def __init__(self,
                 authority: AuthorityMode,
                 audience: AudiencePersona,
                 mission: Optional[MissionPack],
                 matrix: ActionMatrix,
                 classifier: ActionClassifier,
                 certification_store: CertificationStore):
        ...

    def evaluate(self, candidate: ActionCandidate) -> PolicyDecision:
        cls = self.classifier.classify(candidate)
        base = self.matrix.lookup(cls, self.authority)

        # Mission override
        if self.mission:
            override = self.mission.policy_override(cls, self.authority)
            decision = override or base
            if not self.mission.is_within_boundary(cls, candidate):
                decision = decision.escalated()
        else:
            decision = base

        # Autopilot은 Certification 통과 조건부
        if self.authority == AuthorityMode.AUTOPILOT:
            if not self.certification_store.is_autopilot_certified(self.mission.name):
                decision = PolicyDecision.demote_to(Decision.APPROVE,
                                                    reason="missing_certification")

        # Escalation 조건 평가
        if self.mission and self.mission.should_auto_escalate(candidate):
            decision = decision.escalated()

        return decision
```

### 8.2 PolicyDecision value object

```
@dataclass(frozen=True)
class PolicyDecision:
    verdict: Literal["auto", "ask", "approve", "dual", "skip"]
    rationale: str
    required_approvers: int
    escalated_from: Optional[str]       # 원래 결정 (감사용)
    action_class: ActionClass

    def escalated(self) -> "PolicyDecision":
        # auto → ask → approve → dual 한 단계 상향
        ...
```

### 8.3 의사코드 — evaluate_action_policy

```
function evaluate_action_policy(candidate, authority, audience, mission, ctx):
    action_class ← ActionClassifier.classify(candidate)

    base_decision ← ActionMatrix.lookup(action_class, authority)

    if mission is not None:
        override ← mission.action_policy_overrides.get(action_class.name, authority)
        decision ← override or base_decision
        if candidate.data_domain not in mission.allowed_data_domains:
            decision ← decision.escalated()
            decision.rationale += " (out_of_mission_domain)"
    else:
        decision ← base_decision

    # Authority 최상위 레이어
    if authority == FREEZE and action_class.write_side_effect != "none":
        decision ← PolicyDecision(verdict="skip",
                                   rationale="freeze_mode_blocks_writes")

    if authority == INCIDENT and action_class.name in {"prod_deploy", "email_send"}:
        decision ← PolicyDecision(verdict="approve",
                                   rationale="incident_still_requires_approval_for_irreversible")

    # Autopilot certification 확인
    if authority == AUTOPILOT:
        if mission is None or not CertificationStore.is_certified(mission.name, "autopilot"):
            decision ← decision.demoted("no_autopilot_certification")

    # 자동 에스컬레이션 조건 (confidence, severity 등)
    if mission and mission.auto_escalate_matches(ctx):
        decision ← decision.escalated()

    audit_log(decision, candidate, ctx)
    return decision
```

### 8.4 훅 통합

`PolicyDecision`은 기존 `hooks.on_policy_decision(event)`로 방출되어 Electron UI에서 확인/수정 가능하다.

---

## 9. Autonomy Certification (Playbook 승급)

### 9.1 목적

Autopilot은 "스위치 on/off"가 아니라 **Mission Pack별 승급 제도**다. Mission이 shadow → supervised → delegate → autopilot 단계를 밟을 때마다 요건 검증과 인증자 승인을 거친다.

### 9.2 스키마

```yaml
# skills/missions/weekly-kpi-triage.yaml 의 certification 필드
certification:
  current_level: delegate           # shadow | supervised | delegate | autopilot
  next_target: autopilot
  autopilot_requirements:
    shadow_runs_passed: 10
    critical_violations: 0
    verifier_avg_score: 0.85
    rollback_rehearsal: passed
    owner_approvals: 2
  history:
    - date: 2026-03-01
      level: "shadow -> supervised"
      approved_by: "박경순 이사"
      evidence_ref: certification/ev-2026-03-01.md
    - date: 2026-03-20
      level: "supervised -> delegate"
      approved_by: "조상덕 책임"
      evidence_ref: certification/ev-2026-03-20.md
  next_review: 2026-06-01
  deprecation:
    trigger_conditions:
      - critical_violations_in_30d: ">=1"
      - verifier_avg_score_in_30d: "<0.75"
    action: demote_one_level
```

### 9.3 승급 워크플로

1. **Evidence 누적** — 각 Mission 실행 시 `CertificationStore`가 runs, violations, verifier_score, rollback 이력을 기록.
2. **요건 충족 판정** — `submit_certification(mission, target_level)` use case가 요건 대비 현재 지표를 계산, 부족분을 리포트.
3. **리뷰 보드 소집** — Electron `CertificationBoard` UI에서 오너가 evidence 문서 링크와 함께 승인.
4. **승급 적용** — `current_level` 업데이트. SQLite migration v8에 이력 저장.
5. **모니터링** — `deprecation.trigger_conditions`가 hit되면 자동 1단계 강등 + 사용자 알림.

### 9.4 Deprecation 경로

- **자동 강등**: critical violation 발생 or verifier_avg 저하 시 현재 레벨에서 한 단계 다운.
- **강제 Freeze**: 연속 강등 2회 시 해당 Mission을 Freeze로 고정, 수동 재인증 전까지 실행 불가.
- **버전 폐기**: Mission Pack version이 변경되면 Certification은 초기화된다 (명시 override 없는 한).

---

## 10. Clean Architecture 매핑

| 레이어 | 컴포넌트 |
|--------|----------|
| Domain | `AuthorityMode`, `AudiencePersona`, `ActionClass`, `PolicyDecision`, `MissionPack`, `CertificationLevel`, `CertificationRequirement` |
| Application (use cases / ports) | `ClassifyActionUseCase`, `EvaluateActionPolicyUseCase`, `SubmitCertificationUseCase`, `SwitchAuthorityModeUseCase`, `LoadMissionPackUseCase`, ports: `MissionPackRepository`, `CertificationStore`, `ActionMatrixRepository`, `PolicyAuditLogger` |
| Infrastructure | `YamlMissionPackLoader`, `SQLiteCertificationStore`, `SQLiteAuditLogger`, `FileSystemMatrixRepository`, `ToolClassifierAdapters` (tool별 분류 전략) |
| Presentation | `PolicyStudio` (Electron), `CertificationBoard` (Electron), CLI `mode`/`persona`/`mission` 서브커맨드, `PromptSectionsBuilder` |

**원칙 준수**:

- Domain은 YAML/파일시스템/SQLite를 모른다.
- Application layer는 `MissionPackRepository` 포트만 알고, `YamlMissionPackLoader`는 infrastructure.
- `prompt_sections.py`는 Presentation 성격 (LLM에 전달되는 문자열 생성) — domain value object를 입력으로 받아 문자열만 생성.
- DI 조립은 `infrastructure/config/container.py`의 composition root에서만.

---

## 11. 주요 도메인 / 유스케이스

### 11.1 AuthorityMode (value object)

```
domain/value_objects/authority_mode.py

class AuthorityMode(str, Enum):
    SHADOW     = "shadow"
    SUPERVISED = "supervised"
    DELEGATE   = "delegate"
    AUTOPILOT  = "autopilot"
    INCIDENT   = "incident"
    FREEZE     = "freeze"

    @property
    def blocks_external_writes(self) -> bool:
        return self in (AuthorityMode.SHADOW, AuthorityMode.FREEZE)

    @property
    def requires_certification(self) -> bool:
        return self == AuthorityMode.AUTOPILOT

    def can_transition_to(self, target: "AuthorityMode") -> Transition:
        return TRANSITION_MATRIX[self][target]
```

`Transition`은 `free | owner_approval_1 | owner_approval_2 | cert_required | incident_only`.

### 11.2 AudiencePersona (value object)

```
class AudiencePersona(str, Enum):
    ...

    @property
    def default_artifacts(self) -> tuple[str, ...]:
        return PERSONA_DEFAULT_ARTIFACTS[self]

    @property
    def uncertainty_style(self) -> UncertaintyStyle:
        return PERSONA_UNCERTAINTY_STYLE[self]
```

### 11.3 MissionPack (entity)

```
domain/entities/mission_pack.py

@dataclass
class MissionPack:
    name: str
    version: int
    display_name: str
    description: str
    authority_default: AuthorityMode
    audience_default: AudiencePersona
    allowed_data_domains: frozenset[str]
    required_semantic_metrics: tuple[str, ...]
    required_checks: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    auto_escalate_when: tuple[EscalationRule, ...]
    success_criteria: tuple[str, ...]
    skills_required: tuple[str, ...]
    action_policy_overrides: Mapping[tuple[str, AuthorityMode], Verdict]
    certification: CertificationSpec

    def is_within_boundary(self, action_class: ActionClass,
                           candidate: ActionCandidate) -> bool: ...
    def policy_override(self, action_class: ActionClass,
                        authority: AuthorityMode) -> Optional[PolicyDecision]: ...
    def auto_escalate_matches(self, ctx: RunContext) -> bool: ...
```

### 11.4 ClassifyActionUseCase

```
application/use_cases/classify_action.py

class ClassifyActionUseCase:
    def __init__(self, classifier: ActionClassifier):
        self._classifier = classifier

    def execute(self, candidate: ActionCandidate) -> ActionClass:
        return self._classifier.classify(candidate)
```

### 11.5 EvaluateActionPolicyUseCase

```
class EvaluateActionPolicyUseCase:
    def __init__(self,
                 classifier: ActionClassifier,
                 matrix_repo: ActionMatrixRepository,
                 cert_store: CertificationStore,
                 audit: PolicyAuditLogger):
        ...

    def execute(self, input: EvaluateActionInput) -> PolicyDecision:
        cls = self._classifier.classify(input.candidate)
        matrix = self._matrix_repo.current()
        decision = matrix.lookup(cls, input.authority)
        if input.mission:
            decision = input.mission.apply_overrides(decision, cls, input.authority)
            if not input.mission.is_within_boundary(cls, input.candidate):
                decision = decision.escalated(reason="out_of_boundary")
        if input.authority.requires_certification:
            if not self._cert_store.is_certified(input.mission.name, "autopilot"):
                decision = decision.demoted(reason="no_cert")
        decision = self._apply_authority_overlay(decision, input.authority, cls)
        self._audit.log(decision, input.candidate)
        return decision
```

### 11.6 SubmitCertificationUseCase

```
class SubmitCertificationUseCase:
    def execute(self, input: SubmitCertificationInput) -> CertificationResult:
        pack = self._mission_repo.get(input.mission_name)
        stats = self._cert_store.stats_for(input.mission_name)
        gaps = pack.certification.evaluate(input.target_level, stats)
        if gaps:
            return CertificationResult.pending(gaps=gaps)
        # 오너 승인 필요
        return CertificationResult.awaiting_approval(
            required_approvers=pack.certification.requirements(input.target_level).owner_approvals)
```

### 11.7 SwitchAuthorityModeUseCase

오너 승인 1-2명 요구 여부를 `AuthorityMode.can_transition_to` 판정에 위임.

### 11.8 LoadMissionPackUseCase

무거운 파일 IO는 infrastructure에 두고, 이 use case는 캐시 확인 + 검증 오케스트레이션만 담당.

---

## 12. SQLite 스키마 — migration v8

```sql
-- 012_autonomy_control_plane.sql

CREATE TABLE autonomy_certification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_name TEXT NOT NULL,
    mission_version INTEGER NOT NULL,
    level TEXT NOT NULL,          -- shadow/supervised/delegate/autopilot
    transition_from TEXT,
    approved_by TEXT,              -- user id
    approved_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    evidence_ref TEXT,
    next_review TIMESTAMP,
    UNIQUE (mission_name, mission_version, approved_at)
);

CREATE INDEX idx_cert_mission ON autonomy_certification(mission_name, mission_version);

CREATE TABLE autonomy_run_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_name TEXT NOT NULL,
    mission_version INTEGER NOT NULL,
    run_id TEXT NOT NULL,
    authority TEXT NOT NULL,
    audience TEXT NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    outcome TEXT,                   -- success/violation/rolled_back
    verifier_score REAL,
    violations_critical INTEGER DEFAULT 0,
    violations_warn INTEGER DEFAULT 0,
    rollback_rehearsal INTEGER DEFAULT 0
);

CREATE INDEX idx_run_stats_mission ON autonomy_run_stats(mission_name, started_at DESC);

CREATE TABLE autonomy_policy_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    action_class TEXT NOT NULL,
    verdict TEXT NOT NULL,
    escalated_from TEXT,
    rationale TEXT,
    candidate_json TEXT,             -- serialized ActionCandidate
    decided_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE mission_pack_cache (
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (name, version)
);
```

SQLite는 source of truth가 아니라 **캐시 + 감사 로그**다. Mission Pack 자체의 source는 YAML 파일.

---

## 13. Prompt 통합

### 13.1 주입 구조

`PromptBuilder`가 조립하는 system prompt는 다음 섹션 순서로 확장된다.

```
[SYSTEM IDENTITY]                ← 기존
[AUTHORITY MODE]                 ← 신규 — 현재 Authority Mode의 계약
[AUDIENCE PROFILE]               ← 신규 — 현재 persona 톤/산출물
[MISSION PACK]                   ← 신규 — 활성 Mission Pack의 boundary/검증/산출물
[ACTIVE SKILLS]                  ← 기존 skill 목록, Mission.skills_required에 따라 선택
[TASK CONTRACT]                  ← §1 스펙
[ENVIRONMENT & TOOLS]            ← 기존
[EXAMPLES / FEW-SHOT]            ← 기존
```

### 13.2 AUTHORITY MODE 섹션 템플릿 (예시)

```
AUTHORITY MODE: Delegate
- You are authorized to execute low-risk, repeatable actions without approval.
- You MUST request explicit approval for: sensitive reads, production deploys, external communications.
- You MUST NOT bypass Mission boundary even if you can technically do so.
- If uncertain whether an action is within scope, escalate rather than proceed.
```

### 13.3 MISSION PACK 섹션 템플릿 (예시, weekly-kpi-triage)

```
MISSION: weekly-kpi-triage (v1) — 주간 KPI 이상치 진단
Boundary:
  - allowed_data_domains: growth, sales, marketing
  - required_semantic_metrics: monthly_churn_rate, revenue_per_user, dau
Required checks (must execute and report):
  - schema_drift, temporal_leakage, baseline_compare,
    subgroup_stability, causal_assumption_check
Required artifacts:
  - exec_brief, ds_appendix, jira_ticket
Auto-escalate if any of:
  - confidence_low, deploy_needed, sensitive_data_detected,
    anomaly_severity == critical
Success criteria: issue_classified, root_cause_identified,
                  owner_assigned, next_action_proposed
```

### 13.4 Persona-적응 산출물

`AUDIENCE PROFILE` 섹션이 기본 산출물 포맷을 지시하더라도, `MISSION PACK.required_artifacts`가 더 구체적인 요구를 강제한다. 충돌 시 Mission 우선.

---

## 14. UX

### 14.1 Electron — PolicyStudio

`components/settings/PolicyStudio.tsx`

- **Authority Mode 선택**: 6종 카드 UI. 현재 모드 하이라이트. 업그레이드 시 전환 규칙에 따른 승인 플로우 자동 트리거.
- **Audience Persona 선택**: 5종. 프리뷰 패널에 "샘플 응답" 표시.
- **Mission Pack 목록**: 설치된 Mission 리스트, Certification 뱃지 (shadow/supervised/delegate/autopilot) 표시.
- **Action Matrix 편집기**: 조직 정책 override를 표 형태로 편집. 시스템 기본값과 override를 색상으로 구분. 변경 시 preview + diff + apply.

### 14.2 Electron — CertificationBoard

`components/runtime/CertificationBoard.tsx`

- Mission별 Certification 현재 상태, 다음 레벨까지 남은 요건 진척도 바.
- Recent violations, Verifier score trend.
- 승인 요청 inbox — 오너는 evidence 문서 확인 후 승인/반려.
- History 타임라인.

### 14.3 CLI

```
ds mode show                                      # 현재 Authority 표시
ds mode set delegate                              # Authority 전환
ds persona set executive                          # Persona 전환
ds mission activate weekly-kpi-triage             # Mission 활성화
ds mission deactivate                             # 활성 Mission 해제
ds certification status weekly-kpi-triage         # Cert 상태
ds certification submit weekly-kpi-triage --to autopilot
```

Telegram 프론트엔드는 CLI와 동일한 명령을 short form으로 지원 (`/mode delegate`, `/persona exec`).

---

## 15. 기존 3모드 (auto/supervised/step-by-step)와의 하위 호환

### 15.1 Legacy Preset 매핑

레거시 flag `--mode auto | supervised | step_by_step`는 내부적으로 다음 3축 조합으로 해석된다.

| Legacy | Authority | Audience | Mission |
|--------|-----------|----------|---------|
| auto | Delegate | Peer DS | None (ad-hoc) |
| supervised | Supervised | Peer DS | None |
| step_by_step | Supervised | Junior Mentor | None |

`--mode` 플래그는 release N+2까지 유지 후 deprecated 경고 후 제거. 신규 플래그는 `--authority`, `--persona`, `--mission`.

### 15.2 Migration helper

런타임 기동 시 기존 사용자 설정(`~/.ds-agent/config.json`)에 `mode` 필드만 있으면 위 표에 따라 3축 필드로 마이그레이션하고, 이전 값을 `legacy_mode` 키로 백업.

### 15.3 정책 파일

`runtime/policy_profiles/legacy.yaml`을 제공해 "예전과 동일한 승인 동작"을 원하는 조직이 명시적으로 선택 가능.

---

## 16. 구현 Phases (TDD)

### Phase 0: Authority Mode 확장 + Audience Profile (P0)

**2026-04-16 구현 체크포인트**
- [x] `tests/unit/domain/test_authority_mode.py`
- [x] `tests/unit/domain/test_audience_persona.py`
- [x] `tests/unit/presentation/test_prompt_sections_authority_and_audience.py`
- [x] `tests/unit/runtime/test_autonomy_policy_basic.py`
- [x] `domain/value_objects/authority_mode.py`, `audience_persona.py`
- [x] `agent/prompt_sections.py`의 `build_authority_section`, `build_audience_section`
- [x] `runtime/autonomy_policy.py` 초기 버전
- [x] `PromptBuilder` / `factory.build_prompt_builder()` 연결
- [x] `TaskContract`의 `authority/audience/mission` persistence 및 prompt override 연결
- [x] targeted `pytest` 및 `compileall` 검증
- [ ] 기존 권한/approval 경로(`PermissionPolicy`, hook approval flow)와의 통합 refactor
- [ ] legacy CLI surface 동작 확인

**RED**
- `tests/unit/domain/test_authority_mode.py` — 6종 enum, `blocks_external_writes`, 전환 매트릭스.
- `tests/unit/domain/test_audience_persona.py` — 5종, default artifacts/uncertainty style.
- `tests/unit/presentation/test_prompt_sections_authority_and_audience.py` — 섹션 문자열 스냅샷.
- `tests/unit/runtime/test_autonomy_policy_basic.py` — legacy 3모드가 여전히 동작하는지 (`auto → delegate+peer_ds` 매핑).

**GREEN**
- `domain/value_objects/authority_mode.py`, `audience_persona.py`
- `agent/prompt_sections.py`에 `build_authority_section`, `build_audience_section` 추가.
- `runtime/autonomy_policy.py` 초기 버전 — legacy fallback 포함.

- `PermissionHook` / `PermissionPolicy` / `AutonomyPolicy` runtime mission boundary enforcement.

**REFACTOR**
- 기존 `policy_engine.py`의 `requires_approval`을 `AutonomyPolicy.evaluate` 위임 호출로 교체.

**DoD**
- 기존 189개 테스트 + 신규 ≥ 25개 모두 green.
- legacy `--mode` CLI 경로 동작 유지.

### Phase 1: Action Matrix + Classifier (P0)

**2026-04-16 구현 체크포인트**
- [x] `tests/unit/domain/test_action_class.py`
- [x] `tests/unit/runtime/test_action_classifier.py`
- [x] `tests/unit/runtime/test_action_matrix.py`
- [x] `domain/value_objects/action_class.py`
- [x] `runtime/action_matrix.py`
- [x] `runtime/action_classifier.py` 초기 버전
- [x] `AutonomyPolicy.evaluate()`의 optional `action_class` verdict 반영
- [x] known tool에 대한 `PermissionPolicy` matrix enforcement 연결
- [x] `tests/integration/test_autonomy_policy_matrix.py`
- [x] classifier strategy 분리

**RED**
- `tests/unit/domain/test_action_class.py` — 카탈로그, 분류 속성.
- `tests/unit/runtime/test_action_classifier.py` — SQL/Python/Jira/Slack 분류 케이스.
- `tests/unit/runtime/test_action_matrix.py` — 6.2 표 셀 단위 검증.
- `tests/integration/runtime/test_autonomy_policy_matrix.py` — Authority × ActionClass 매트릭스 통합.

**GREEN**
- `domain/value_objects/action_class.py`
- `runtime/action_classifier.py` + tool별 adapter.
- `runtime/action_matrix.py` + 기본 매트릭스 YAML.
- `AutonomyPolicy.evaluate` 확장.

**REFACTOR**
- classifier adapter를 strategy pattern으로 분리.

### Phase 2: Mission Pack (P1)
**2026-04-16 Mission Pack checkpoint**
- [x] `tests/unit/domain/test_mission_pack.py`
- [x] `tests/unit/skills/test_mission_pack_loader.py`
- [x] `tests/unit/presentation/test_prompt_mission_section.py`
- [x] `domain/entities/mission_pack.py`
- [x] `skills/mission_pack_loader.py`
- [x] `skills/missions/weekly-kpi-triage.yaml`
- [x] `PromptBuilder` Mission section injection
- [x] mission default `authority` / `audience` fallback from pack metadata
- [x] mission `skills_required` prompt-time extension
- [x] `tests/integration/test_mission_boundary_enforcement.py`
- [x] runtime mission boundary enforcement
- [x] Electron certification surface


**RED**
- `tests/unit/domain/test_mission_pack.py`
- `tests/unit/skills/test_mission_pack_loader.py` (스키마 validation)
- `tests/integration/test_mission_boundary_enforcement.py`
- `tests/unit/presentation/test_prompt_mission_section.py` — 섹션 템플릿 스냅샷.

**GREEN**
- `domain/entities/mission_pack.py`
- `skills/mission_pack_loader.py` + `schemas/mission_pack.schema.json`
- `skills/missions/weekly-kpi-triage.yaml` (실사용 예시)
- `PromptBuilder` Mission 섹션 주입.

**REFACTOR**
- Mission override 해석을 pure function으로 분리.

### Phase 3: Autonomy Certification (P1)

- Checkpoint (2026-04-16): domain certification spec, MissionPack certification metadata, SQLite certification store, `submit/status` use cases, CLI/TUI + Telegram + Electron `certification` surfaces, and runtime autopilot demotion on missing certification are implemented.

**RED**
- `tests/unit/domain/test_certification_spec.py`
- `tests/unit/application/test_submit_certification.py`
- `tests/integration/infrastructure/test_sqlite_certification_store.py`

**GREEN**
- Migration v8
- `infrastructure/persistence/sqlite_certification_store.py`
- `application/use_cases/submit_certification.py`
- CLI `ds certification submit/status`

**REFACTOR**
- Evidence aggregation 로직을 domain service로.

### Phase 4: Incident + Freeze 모드 (P1)

**RED**
- 모드별 정책 오버레이 테스트.
- Incident 활성화 시 24h 타임아웃 테스트.

**GREEN**
- AuthorityMode 오버레이 로직, CLI `ds mode incident start/end`, `ds mode freeze`.
- Audit logger 강화 (Incident 사후 보고).

Checkpoint (2026-04-16): Phase 4 incident/freeze overlay now covers persistent `gateway.authority_overlay`, 24h incident expiry/auto-clear, session-agent recreation on overlay change, prompt/hook override, `ds-agent mode ...`, Telegram-aware agent creation, Electron Runtime Console selector, and audit-log authority metadata.

### Phase 5: Electron UI (P2)

- CertificationBoard API/UI surface landed. Runtime Console authority-overlay selector/status surface also landed. Remaining: PolicyStudio and Audience preview.
- Checkpoint (2026-04-16): Settings `Policy Studio` now covers current-session TaskContract authority/audience/mission editing, certification-aware mission selection, runtime overlay precedence, and audience sample preview. Remaining: Action Matrix preview/diff/apply plus visual regression / Playwright E2E.
- Checkpoint (2026-04-16): Settings `Policy Studio` now also covers Action Matrix preview/diff/apply with persisted operator overrides, runtime verdict preview, and reset/clear/apply flows wired through `policy.get` + `policy.setActionMatrixOverrides`. Remaining: visual regression / Playwright E2E, broader `ActionClassifier` coverage, and legacy migration helper/docs.
- Checkpoint (2026-04-16): `ActionClassifier` now uses separated SQL/deployment/governance/python/tool-map strategies, broader internal tool coverage, and conservative matrix enforcement for `unknown` actions in `PermissionPolicy`. Remaining: visual regression / Playwright E2E and legacy migration helper/docs.
- Visual regression / Playwright E2E.
- Checkpoint (2026-04-16): Phase 5 is now complete for the current scope. CertificationBoard, Runtime Console overlay controls, PolicyStudio authority/audience/mission editing, audience preview, Action Matrix preview/diff/apply, broader `ActionClassifier` coverage, and the packaged-backend Playwright smoke flow are all landed.
- Checkpoint (2026-04-16): Phase 6 legacy migration work is now complete for the current scope through `ds-agent mode migrate [legacy-mode]`, runtime migration previews, PolicyStudio draft-apply assistance, and the 2026-04-16 addendum notes.
- Definition of Done status update (2026-04-16): this status note supersedes the stale checklist in Section 19 below.
- [x] Authority/Audience/Mission domain axes, TaskContract persistence, Mission Pack loading, and mission boundary enforcement are landed.
- [x] `ActionClassifier` strategy coverage is landed for the autonomy-critical and high-traffic tool paths, with conservative matrix fallback for `unknown`.
- [x] `AutonomyPolicy.evaluate()` reflects Authority x ActionClass x Mission decisions, certification demotion, and incident/freeze overlays for the shipped scope.
- [x] `weekly-kpi-triage` mission YAML, certification policy, CLI/TUI/Telegram/Electron operator surfaces, and PolicyStudio preview/diff/apply flows are landed.
- [x] Packaged-backend autonomy-control-plane Playwright E2E is green via `electron/tests/smoke/autonomy-control-plane.spec.ts`.
- [x] Legacy `--mode` migration helper/docs are landed via `ds-agent mode migrate [legacy-mode]`, runtime migration previews, and the PolicyStudio legacy-mapping helper.
- [x] Targeted `pytest`, `ruff check`, `ruff format --check`, `mypy`, `compileall`, packaged backend build, and Electron `typecheck` / autonomy E2E are green on the touched scope.
- [x] Import-boundary coverage for this slice is now added through `.importlinter` plus the repo-local static contract check.

### Phase 6: Legacy 마이그레이션 정리 (P2)

- Deprecation 경고, migration helper, docs.

---

## 17. 테스트 전략

### 17.1 단위 테스트

- **Domain**: value object 불변성, 전환 규칙, MissionPack invariant (예: `allowed_data_domains`는 비어있을 수 없음).
- **Application**: use case를 mock port만으로 검증.

### 17.2 통합 테스트

- YAML loader ↔ MissionPack 엔티티 ↔ AutonomyPolicy 경로.
- Authority × Mission × ActionClass 조합 매트릭스 샘플링 (property-based test 추천 — `hypothesis`).
- SQLite migration v8 forward/backward.

### 17.3 시나리오 테스트

- **S1**: Supervised + weekly-kpi-triage Mission에서 Jira 생성 → approve 프롬프트 발생.
- **S2**: Delegate + 동일 Mission → Mission override로 Jira 자동 실행.
- **S3**: Autopilot 요청했으나 Cert 미달 → Delegate로 demote + 사용자 알림.
- **S4**: Freeze 모드에서 모델 training 시도 → skip + 대안 제안.
- **S5**: Incident 모드 활성 → Slack 자동 전송, prod_deploy는 여전히 approve.
- **S6**: Executive persona → exec_brief artifact 포맷 자동 생성.

### 17.4 회귀 테스트

- 기존 189 테스트가 legacy mode 경로에서 모두 동일하게 통과.
- `--mode auto` CLI로 기동 시 3축이 (Delegate, Peer DS, None)로 세팅되는지 확인.

### 17.5 Property-based

- "Shadow 모드에서는 어떤 Mission에서도 write action의 verdict가 auto가 될 수 없다" — 불변식.
- "Freeze 모드에서는 verdict가 auto인 경우 action_class.write_side_effect는 none" — 불변식.

---

## 18. 의존성 및 통합 지점

| 대상 | 변경 성격 |
|------|-----------|
| `runtime/policy_engine.py` | `AutonomyPolicy`로 위임. 표면 API 유지. |
| `runtime/hooks.py` | `on_policy_decision`, `on_authority_change`, `on_mission_activate`, `on_certification_submit` 이벤트 추가. |
| `agent/prompt_sections.py` | Authority/Audience/Mission 섹션 추가. |
| `skills/` | `missions/` 하위 디렉터리 신설. 기존 `builtin/`, `shared/` 변경 없음. |
| `interfaces/cli/commands.py` | `mode`, `persona`, `mission`, `certification` 서브커맨드 추가. |
| `interfaces/telegram/handlers.py` | 동일 서브커맨드 매핑. |
| `infrastructure/persistence/` | migration v8. |
| `frontend-electron/` | PolicyStudio, CertificationBoard 컴포넌트. |
| `domain/entities/task_contract.py` (§1 스펙) | `authority`, `audience`, `mission` 필드 추가. |
| `semantic_layer` (§2 스펙) | `ActionClassifier`가 테이블 sensitivity 조회 시 사용. |

---

## 19. 성공 기준 (Definition of Done)

- [ ] 6종 AuthorityMode, 5종 AudiencePersona, MissionPack 스키마가 domain에 정의됨.
- [ ] `ActionClassifier`가 내부 도구 카탈로그의 모든 tool을 분류.
- [ ] `AutonomyPolicy.evaluate`가 Authority × ActionClass × Mission 매트릭스를 모두 반영.
- [ ] `skills/missions/weekly-kpi-triage.yaml` 실사용 예시 1개 이상 포함.
- [ ] Certification 승급/강등 워크플로 E2E 동작.
- [x] Electron PolicyStudio + CertificationBoard 출시.
- [ ] 기존 `--mode` CLI 하위 호환 유지 (legacy preset 매핑).
- [ ] 회귀 테스트 189 + 신규 ≥ 80 테스트 모두 green.
- [ ] `ruff check`, `ruff format --check`, `mypy` 전부 통과.
- [ ] 도메인 파일이 infrastructure 패키지를 import하지 않음 (import-linter 룰 추가).

---

## 20. 리스크 및 롤백

### 20.1 리스크

| 리스크 | 확률 | 영향 | 완화 |
|--------|------|------|------|
| 3축 조합 복잡도 증가로 사용자 혼란 | 중 | 중 | legacy preset 매핑 + PolicyStudio "Quick presets" 제공. |
| Mission Pack이 워크플로 자동화로 회귀 (LLM orchestrator 원칙 훼손) | 중 | 고 | Mission은 선언적 boundary만. 실행 순서 하드코딩 금지. 스펙 리뷰 체크리스트에 명시. |
| ActionClassifier 오분류 → 보수적 접근 과다 | 고 | 중 | "unknown" 분류 시 기본 approve + 사용자가 rule 추가 UX. |
| Certification 제도가 권한 체계에 대한 정치적 부담 | 중 | 중 | 초기는 shadow/supervised만 의무, delegate/autopilot은 opt-in. |
| SQLite migration v8 중 실패 | 저 | 고 | migration script idempotent + 백업 자동. |
| prompt 길이 증가로 토큰 비용 상승 | 중 | 저 | Audience/Authority 섹션은 짧은 directive. Mission 섹션은 활성 시에만 주입. |

### 20.2 롤백 전략

- **Phase 단위 롤백**: 각 phase는 feature flag (`autonomy.v2.enabled`, `autonomy.mission_pack.enabled`, `autonomy.certification.enabled`)로 gating. off 시 기존 policy_engine 경로 사용.
- **Migration v8 롤back**: downgrade SQL 포함. 테이블 drop 시 SQLite backup file에서 복원.
- **Mission Pack 파일 문제**: loader failure 시 해당 Mission만 disable, agent는 Mission 없이 동작.
- **Certification 잘못된 승급**: `ds certification revoke <mission> --to <level>` CLI 제공.

---

## 21. Open Questions

1. **Audience 자동 추론**: 사용자가 persona를 명시하지 않았을 때, 과거 대화 로그/조직 role metadata로 자동 추론할 것인가? (Phase 2 이후 검토)
2. **Mission 버전 관리**: Mission Pack version bump 시 실행 중 세션을 어떻게 처리? 진행 중 세션은 기존 version 유지, 신규 세션만 새 version으로 시작을 기본으로 제안.
3. **Multi-Mission 동시 활성화**: 하나의 세션에서 `weekly-kpi-triage` + `data-quality-check`를 동시에 운영 가능한가? 초기에는 단일 Mission만 허용, 이후 compose 연구.
4. **Audience override 권한**: Junior Mentor persona로 응답받던 사용자가 임시로 Executive 응답을 원할 때 session-scope override UX를 어떻게? 제안: `/as exec` one-shot.
5. **Action Class 카탈로그 확장성**: 조직이 자체 action class를 정의할 수 있도록 plugin 인터페이스를 공개할지? Phase 6에서 결정.
6. **Incident 종료 트리거**: 수동 종료 + 24h 타임아웃 외에, "verifier_score가 baseline 복귀"를 자동 종료 시그널로 사용할지 (P3 검토).
7. **Certification 투표 vs 단독 승인**: owner_approvals = 2가 "2명 각각 독립 승인"인지 "2명 합의"인지 정책 문구 확정 필요. 기본은 "독립 승인 2건".
8. **MCP 자원 연결**: 외부 MCP 툴이 추가될 때 ActionClass 자동 분류 규칙을 어떻게 기술할지 (tool manifest에 `action_class_hint` 필드 추가 제안).

---
