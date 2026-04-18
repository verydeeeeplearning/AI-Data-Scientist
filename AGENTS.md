# DS Agent — Knowledge Map

> 이 문서는 에이전트와 개발자를 위한 **진입점(목차)**입니다.
> 상세 내용은 하위 문서에 분리되어 있으며, 필요할 때만 펼쳐 읽으세요.

---

## Project Overview

Autonomous AI Data Scientist Agent — end-to-end DS 워크플로우를 자율 수행하는 에이전트.

- **Backend**: Python 3.11+, Clean Architecture, async agent loop
- **Frontend**: Electron 31 + React 18 + Vite + TailwindCSS + Zustand
- **Protocol**: WebSocket (JSON-RPC style) with one-time token auth (SEC-01)
- **Default Model**: `anthropic/claude-sonnet-4-6`
- **Harness Engineering**: hooks enforce DS methodology via code, not docs
- **Runtime Operations**: Telegram operator UX, thread-aware session isolation, delivery policy automation — all implemented across gateway/runtime/Electron surfaces
- **Packaging**: PyInstaller backend binary + Electron NSIS/DMG/AppImage via electron-builder

---

## Current Runtime / Operator Implementation

- **PLAN_10~12** Autonomous runtime + Electron parity + Telegram parity — **Complete**
- **PLAN_13**: Telegram operator UX hardening — **Complete** (subscriptions, ack/mute/digest, inline callback actions, `/menu`, command registration, audit)
- **PLAN_14**: Thread-aware session isolation — **Complete** (canonical channel identity, topic-aware recovery routing, WebSocket session serialization, Electron runtime labels)
- **PLAN_15**: Notification delivery policy automation — **Complete** (quiet hours, effective delivery settings, digest cadence/timezone, suggested next actions, repeated blocked-state escalation)
- **PLAN_17**: Capability roadmap master — active across 7 tracks (P0 foundation → P6 advanced). See `Docs/plans/PLAN_17/`
- **Productization (베타)**: see `Docs/plans/productization/00_INDEX.md` — code-side work complete for P0-01/02/03/04/07 and P1-08/09/10/11/12/13. External-blocked: P0-05 (EV/Developer ID), P0-06 signed E2E, P0-07 DSN, P1-14 signed auto-update. Latest status in `P_NEXT_STEPS_2026-04-15.md`.

---

## Latest Hardening (pre-beta, 2026-04-15)

- **Backend READY race** — READY emission moved into FastAPI lifespan startup hook so `/health` is guaranteed to respond when Electron probes. Prevented false `health_check_failed` on slow machines. (`src/ds_agent/api/app.py`)
- **Windows credential size limit** — `KeyringSecretStorage` now chunks values >1024 chars across `key__part0/1/2/...` with `__ds_chunked__:N` header written last (crash-safe). Fixes `CredWrite error 1783` on Codex OAuth payloads (~4.3 KB). (`src/ds_agent/infrastructure/secrets/secret_storage.py`)
- **Sandbox UI (P0-01 Phase 3)** — `sandbox.violation` event emit in `_ds_sandbox_runner`, blocking `SandboxApprovalModal` (Esc=reject, textarea rationale), non-blocking `SandboxViolationToast` (8s TTL, max 3 visible). App.tsx mounted.
- **Electron E2E** — `DS_AGENT_BACKEND_COMMAND` (backend override) + `DS_AGENT_E2E_USE_BUILT_RENDERER` (bypass Vite dev server) env hooks. `tests/smoke/diagnostic-window.spec.ts` (P0-03 failure path) + `tests/smoke/happy-path.spec.ts` (full backend→WS handshake). Both green.
- **Export engine (P1-12)** — 48 tests green including Korean filename/content round-trip (python-docx, openpyxl, nbformat, path traversal guard).
- **Accessibility (P1-13)** — `role=dialog` / `aria-modal` / `aria-labelledby` / `aria-describedby` / `aria-label` / `aria-hidden` / `aria-live` across 7 modal/overlay components (SandboxApprovalModal, SandboxViolationToast, FilePreviewModal, PlotGallery modal, DiagnosticPanel, DisconnectOverlay, SettingsPanel).
- **Secure storage degraded UX (P0-02)** — `describe_secret_storage()` + CLI banner surface in-memory fallback warning when keyring unavailable.
- **Migration convention (P0-04)** — 7-step authoring procedure documented; v3→v4 observability defaults migration landed.
- **P1-10 Postgres connector** — stale `ts-nocheck` removed; helpers confirmed present; typecheck clean; backend RPC 26 tests green.

---

## Project Structure

```
src/ds_agent/
├── agent/           # Core loop, hooks, permissions, prompt builder, budget tracker
│   ├── core.py          — Single while-loop agent orchestrator
│   ├── factory.py       — Shared agent factory (hooks + skills + memory wiring)
│   ├── hooks.py         — ToolHook base + HookRegistry (pre/post lifecycle)
│   ├── builtin_hooks.py — Permission, Audit, BudgetGuard, SessionInit, ProcessMetrics,
│   │                      ExperimentTracker, ExecPlanSave
│   ├── ds_workflow_hooks.py — WorkflowTracker, LeakageDetection, BaselineGuard,
│   │                          OverfittingDetector, StageQuality, ModelSanityCheck,
│   │                          ProfileResults
│   ├── callbacks.py     — NullCallbacks (agent-side no-op)
│   ├── permissions.py   — 3-tier policy (READ_ONLY / WORKSPACE / FULL_ACCESS)
│   ├── prompt_builder.py — Composable system prompt assembly (priority-based)
│   ├── prompt_sections.py — Prompt section definitions
│   ├── context_manager.py — Token-aware context compression (80% threshold)
│   └── budget_tracker.py — Token + cost budget enforcement
├── domain/              # Clean Architecture innermost
│   ├── entities/        — ChatMessage, Role, LLMResponse, ToolCall, Usage, ...
│   ├── value_objects/   — BudgetPolicy
│   └── interfaces/      — LLMProvider, AgentCallbacks, ToolRegistry, PricingPort,
│                          PostLearningPort
├── application/         # Use cases, DTOs, application ports
├── tools/               # Self-registering @tool decorator. Core DS tools:
│   ├── registry.py      — @tool decorator, ToolRegistry class
│   ├── sandbox.py       — ProcessSandbox (subprocess isolation + timeout)
│   ├── sandbox_context.py — Runtime context propagation
│   ├── _ds_sandbox_runner.py — Subprocess runner; emits sandbox.violation events
│   ├── network_sandbox.py — Egress allowlist for LLM-authored code
│   ├── code_security.py — Regex + AST code scanner (30+ blocked patterns)
│   ├── path_utils.py    — Workspace boundary validation (is_relative_to)
│   ├── data_loader.py, data_profiler.py, eda.py, feature_eng.py, modeling.py,
│   │   evaluation.py, reporting.py, deployment.py, sampling_utils.py
│   ├── ab_test_tools.py, drift_tools.py, schema_tools.py, sql_tools.py,
│   │   sql_result_summarizer.py, integration_tools.py, governance_tools.py,
│   │   distributed_tools.py, artifact_tools.py
│   ├── code_execution.py — General-purpose Python sandbox
│   ├── file_ops.py      — read_file, write_file, list_files
│   ├── memory_tools.py  — memory_search, memory_store
│   ├── skill_tools.py   — skill_list, skill_view, skill_search
│   └── ds_error_translator.py — Context-aware Python error translation
├── skills/              # 8 builtin + 6 shared methodology skills (Markdown)
│   ├── hub.py           — Skill discovery, search, progressive disclosure
│   ├── builtin/         — scoping, data-profiling, eda, feature-engineering,
│   │                      modeling, evaluation, reporting, deployment
│   └── shared/          — backtesting, causal-assumption-check, hypothesis-ranking,
│                          resource-aware-planning, retrain-vs-rollback,
│                          uncertainty-quantification
├── memory/              # 5-layer persistent memory (SQLite + FTS5)
│   ├── session_db.py    — Session/message persistence
│   ├── experiment_log.py — Experiment tracking
│   ├── experiment_compare.py — Cross-experiment comparison
│   ├── code_registry.py — Learned code patterns
│   ├── domain_kb.py     — Domain knowledge with confidence scores
│   ├── project_store.py — Project metadata
│   └── unified_store.py — Unified query surface
├── providers/           # LLM providers
│   ├── router.py        — Smart model string parsing + fallback chain
│   ├── anthropic.py     — Claude Opus 4.6, Sonnet 4.6, Haiku 4.5
│   ├── openai_provider.py — GPT-4.1 series, o-series
│   ├── codex_oauth.py   — Codex OAuth (ChatGPT account)
│   ├── gemini_oauth.py  — Gemini (OAuth/API key)
│   ├── litellm_provider.py — 100+ models via LiteLLM (Groq, DeepSeek, Qwen, ...)
│   ├── ollama.py        — Ollama local models
│   ├── local_discovery.py — vLLM/SGLang/Ollama autodetect
│   ├── pricing.py       — Provider pricing table (current + legacy)
│   └── base.py          — Base provider utilities
├── self_improve/        # Post-project learning pipeline
│   ├── post_project.py  — Experiment logging + domain insight extraction
│   ├── pattern_learner.py — Code pattern detection
│   ├── memory_hints.py  — Domain KB → system prompt injection
│   ├── skill_extractor.py — Learned skill generation
│   ├── independent_evaluator.py — Cross-model blind evaluation
│   └── learning_adapter.py — PostLearningPort implementation
├── runtime/             # 28 orchestration modules. Key entries:
│   ├── coordinator.py              — Runtime coordination, policy-driven flow
│   ├── approval_store.py           — Approval inbox persistence
│   ├── policy_engine.py / policy_store.py — Policy evaluation + persistence
│   ├── delivery_policy_store.py    — Operator delivery policy persistence
│   ├── delivery_rate_limiter.py    — Quiet-hours / escalation-aware limits
│   ├── delivery_settings.py        — Effective delivery settings resolver
│   ├── digest_builder.py           — Digest composition + suggested next actions
│   ├── event_classifier.py         — Runtime event classification + urgency
│   ├── operator_alert_state_store.py — Alert lifecycle, ack/mute, scheduling
│   ├── operator_preferences_store.py — Per-chat subscriptions, cadence, timezone
│   ├── organization_store.py       — Org metadata (P2 deferred feature)
│   ├── outcome_delivery.py         — Outcome-oriented operator notifications
│   ├── run_registry.py / session_registry.py — Run/session persistence
│   ├── runtime_event_log.py        — Event persistence + replay
│   ├── sensor_hub.py               — External trigger aggregation
│   ├── startup_recovery.py         — Resume/recovery bootstrap
│   ├── task_ledger.py              — Task graph persistence
│   ├── transcript_store.py         — Session transcript isolation
│   ├── working_memory.py           — Short-term memory for the agent loop
│   ├── channel_identity.py         — Canonical channel/session identity
│   ├── goal_store.py               — Recurring goal persistence
│   ├── checkpoint_store.py         — Run checkpoints for recovery
│   ├── background_task_manager.py  — Long-running task lifecycle
│   ├── memory_query_service.py     — Unified memory query facade
│   ├── action_token.py             — Operator action token issuance
│   ├── provider_factory.py         — Provider instance construction
│   └── tool_runtime_context.py     — Per-tool runtime context
├── infrastructure/
│   ├── auth/            — oauth_service, pkce, callback_server, token_store
│   ├── secrets/         — secret_storage (keyring + chunking), config_secret_manager,
│   │                      connector_secret_manager, api_key_manager
│   ├── sandbox/         — preamble generator for LLM-authored code
│   ├── observability/   — sentry_backend (P0-07, DSN-gated activation)
│   ├── persistence/     — Store implementations
│   ├── migration/       — Schema migration runner + registry (v1→v4)
│   ├── artifact/, distributed/, external/, support/
│   ├── cron_runner.py, pii_detector.py, process_subagent.py, sql_validator.py
├── config/              # Pydantic config (schema v4)
│   ├── schema.py            — DSAgentConfig, AgentConfig, ProviderConfig,
│   │                          GatewayConfig, TelegramConfig, ChannelsConfig,
│   │                          ObservabilityConfig (telemetry consent 3-choice)
│   └── loader.py            — YAML/env loader + migration entry
├── cli/                 # Interactive TUI (Rich), slash commands, onboarding wizard
├── api/                 # Interface layer
│   ├── app.py               — FastAPI app factory, lifespan READY emit (race-free)
│   ├── ws_handler.py        — WebSocket handler (JSON-RPC + streaming events)
│   ├── callbacks.py         — WsAgentCallbacks (emit sync→async bridge)
│   ├── error_mapping.py     — DSA-XXX-YYY error code catalog (P0-07)
│   └── routes/              — admin, config, files, status, support, usage
├── channels/            # Channel plugin system (Telegram, ...)
└── gateway/             # Session manager, Telegram runner

electron/src/
├── main/
│   ├── index.ts             — Main bootstrap, diagnostic window entry on failure
│   ├── python-backend.ts    — Backend spawn + READY/health verification
│   │                          Env overrides: DS_AGENT_BACKEND_COMMAND,
│   │                                         DS_AGENT_BACKEND_ARGS
│   ├── window.ts            — Window creation; DS_AGENT_E2E_USE_BUILT_RENDERER=1
│   │                          forces loadFile even in dev (for E2E)
│   ├── secret-vault.ts      — Desktop safeStorage vault (P0-02)
│   ├── ipc.ts               — IPC surface (secrets, updates, policies)
│   ├── observability.ts     — @sentry/electron/main wiring (DSN-gated)
│   ├── diagnostic.ts        — Startup failure classification
│   └── updater.ts           — electron-updater wiring (P1-14, cert-gated)
├── preload/
│   └── index.ts             — Secure IPC bridge (contextBridge exposeInMainWorld)
└── renderer/
    ├── App.tsx              — Root orchestration; mounts SandboxApprovalModal +
    │                          SandboxViolationToast + SettingsPanel + OnboardingWizard
    ├── stores/              — Zustand (chat, agent, files, config, i18n, workflow)
    ├── hooks/               — useWebSocket, WsProvider, useChat, useAgent, useModels,
    │                          useWorkflow, useRuntime, useRuntimeEvents,
    │                          useProviderAuth, useUsageSummary
    ├── components/
    │   ├── chat/            — ChatPanel, ChatMessage (Markdown), ChatInput, ToolActivity
    │   ├── sidebar/         — FileExplorer, FileUpload, FilePreviewModal, PlotGallery,
    │   │                      ModelSelector, ModeSelector
    │   ├── layout/          — MainPanel, Sidebar, StatusBar, SplashScreen,
    │   │                      ErrorBoundary, DisconnectOverlay, UpdateNotification
    │   ├── runtime/         — SessionsPanel, RunsPanel, RunDetailDrawer, ApprovalInbox
    │   ├── sandbox/         — SandboxApprovalModal, SandboxViolationToast (P0-01 Phase 3)
    │   ├── settings/        — SettingsPanel, OnboardingWizard, ConnectorWizard (P1-10)
    │   ├── diagnostic/      — DiagnosticPanel (backend failure classification)
    │   └── workflow/        — WorkflowProgress, AlertBanner, QualityPanel,
    │                          ExperimentTable, BudgetBar
    ├── types/               — events.ts, rpc.ts (generated type surface)
    └── styles/              — globals.css (dark/light theme CSS variables)

electron/tests/smoke/
├── diagnostic-window.spec.ts — Playwright _electron: forced backend failure
└── happy-path.spec.ts        — Playwright _electron: full stack boot

scripts/
├── build_backend.py         — PyInstaller → dist/ds-agent-backend/ + build/
├── build_all.py             — tests → PyInstaller → Electron → installer
├── sign_backend.py          — Windows signtool / macOS codesign wrapper (P0-05)
├── check_av_clean.py        — VirusTotal scan (P0-05 CI optional)
└── clean_workspace.ps1      — Local cache / build-output pruning
```

---

## Key Documents

| Document | Purpose | When to Read |
|----------|---------|-------------|
| `Docs/ARCHITECTURE.md` | System overview, hook table, event protocol, component tree | Before any architectural change |
| `Docs/SECURITY.md` | Sandbox policy, forbidden operations, threat model | Before modifying tools or permissions |
| `Docs/QUALITY_SCORE.md` | DS workflow quality rubric | Before modifying skills or hooks |
| `Docs/HARNESS_ENGINEERING_IMPROVEMENT_PLAN.md` | Full-stack harness roadmap | When planning new features |
| `Docs/plans/PLAN_10~15/` | Historical runtime/operator implementation plans | For architectural context |
| `Docs/plans/PLAN_17/PLAN_17_ROADMAP_MASTER.md` | Capability roadmap (P0→P6) | When planning capability expansion |
| `Docs/plans/productization/00_INDEX.md` | Beta launch readiness index | Before beta-release work |
| `Docs/plans/productization/P_NEXT_STEPS_2026-04-15.md` | Latest productization audit + sprint log | For current sprint status |

---

## Conventions

- **Clean Architecture**: Dependencies point inward only. Domain has zero external imports. `core.py` imports only domain interfaces — zero infrastructure references.
- **Domain Interfaces**: 5 Protocol types in `domain/interfaces/` — `LLMProvider`, `AgentCallbacks`, `ToolRegistry`, `PricingPort`, `PostLearningPort`. Application depends on these, infrastructure implements.
- **Harness Engineering**: DS methodology enforced via hooks (code), not just documentation.
- **TDD**: Red-Green-Refactor. Tests before implementation.
- **Lint**: `ruff check . && ruff format --check .` — zero violations
- **Type Check**: `mypy src/ds_agent/` — **0 errors**
- **Test**: `pytest tests/unit tests/smoke` — **current baseline: 1382 passed**
- **Security**: Regex + AST code scanning, `Path.is_relative_to()` boundary check, `validate_assignment` config protection, one-time WebSocket token (SEC-01), sandbox preamble injection
- **Secrets**: KeyringSecretStorage with automatic chunking for payloads >1024 chars (Windows Credential Manager 2560-byte cap workaround). In-memory fallback with degraded-UX surface.
- **Tool Error Format**: All tools return `json.dumps({"error": ...})` on failure
- **Backend READY**: emit in FastAPI lifespan startup hook, not before `uvicorn.run()` (prevents `/health` race)

---

## Verification Commands

```bash
# Python
pytest tests/unit tests/smoke      # 1382 passed baseline
ruff check . && ruff format --check .
mypy src/ds_agent/

# Electron
cd electron
npm run typecheck
npm run build
npm run test:e2e:smoke             # diagnostic-window (backend failure path)
npm run test:e2e:happy             # happy-path (full stack boot) — requires built backend

# Full pipeline including installer
python scripts/build_all.py
```

---

## Packaging (verified 2026-04-15)

- `dist/ds-agent-backend/ds-agent-api.exe` — 43.5 MB PyInstaller single binary
- `electron/release/DS Agent-Setup-0.1.0-win.exe` — 179 MB NSIS installer (per-user, UAC-free)
- Unsigned local build — SmartScreen "more info → run anyway" required on first launch until EV cert lands (P0-05)

---

## Forbidden

- Do NOT import outer layers from domain entities
- Do NOT import infrastructure (providers, memory, self_improve) from `agent/core.py` — use domain interfaces
- Do NOT use `str(path).startswith(str(base))` for path validation — use `Path.is_relative_to()`
- Do NOT use `setattr` on config without `validate_assignment=True` and path whitelist
- Do NOT execute code outside ProcessSandbox in production
- Do NOT return plain-text errors from tools — use `json.dumps({"error": ...})`
- Do NOT store API keys in frontend localStorage
- Do NOT commit `.env` files or credentials
- Do NOT add `# type: ignore[attr-defined]` — fix the type instead
- Do NOT emit `READY:port:token` before the listening socket binds — use FastAPI lifespan startup
- Do NOT write secrets >1024 chars directly via `keyring.set_password` — use `KeyringSecretStorage.store()` so chunking kicks in
