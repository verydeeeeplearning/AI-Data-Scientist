# DS Agent — AI Data Scientist

Autonomous AI agent that performs end-to-end data science workflows: data loading, profiling, EDA, feature engineering, modeling, evaluation, and reporting. The LLM decides what to do — no rigid pipelines, no hardcoded phases.

```
You> 이 데이터셋 분석해줘. 타겟은 churn 컬럼이야.
DS Agent> 데이터를 로드하고 프로파일링하겠습니다...
  ▶ data_loader ✓ 1.2s
  ▶ data_profiler ✓ 2.3s
  ▶ run_eda ✓ 5.1s
  ▶ feature_engineering ✓ 3.4s
  ▶ train_model ✓ 8.7s
  ▶ evaluate_model ✓ 1.1s

| Model     | F1   | AUC  | Accuracy |
|-----------|------|------|----------|
| LightGBM  | 0.81 | 0.87 | 0.84     |
| XGBoost   | 0.79 | 0.85 | 0.82     |

최고 성능 모델은 LightGBM입니다. Feature importance 상위 3개는...
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Interface Layer                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ CLI (TUI) │  │ Telegram │  │ Electron Desktop │  │
│  └─────┬────┘  └────┬─────┘  └────────┬─────────┘  │
│        └────────────┼─────────────────┘              │
│                     ▼                                │
│  ┌─────────────────────────────────────────────┐    │
│  │  Agent Core (single while loop)              │    │
│  │  LLM → tool_calls → execute → loop          │    │
│  ├─────────────────────────────────────────────┤    │
│  │  Tool Registry (self-registering @tool)      │    │
│  ├─────────────────────────────────────────────┤    │
│  │  Skills: 8 builtin + 6 shared (Markdown)     │    │
│  ├─────────────────────────────────────────────┤    │
│  │  Memory (Session + Experiment + Domain KB +  │    │
│  │          Code Registry + Project Store)      │    │
│  ├─────────────────────────────────────────────┤    │
│  │  Runtime Orchestration (approvals, digests,  │    │
│  │   delivery policy, sensor hub, recovery)     │    │
│  ├─────────────────────────────────────────────┤    │
│  │  Self-Improvement (pattern + skill learning) │    │
│  └─────────────────────────────────────────────┘    │
│                     ▼                                │
│  ┌─────────────────────────────────────────────┐    │
│  │  Provider Router                             │    │
│  │  Anthropic │ OpenAI │ Codex │ Gemini │ Groq  │    │
│  │  Ollama │ vLLM │ SGLang │ LiteLLM (100+)    │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

**Core principle:** The LLM is the orchestrator. No state machines, no phase gates. The agent loop runs `LLM → tool_calls → execute → repeat` until the task is done or the budget is exhausted.

## Features

- **Tool suite** (`src/ds_agent/tools/`) — code execution, data loading, profiling, EDA, feature engineering, modeling, evaluation, reporting, deployment, A/B testing, drift detection, schema tools, SQL tools, integration connectors, network sandbox, file ops, governance, distributed, memory, skill, sampling, DS error translation
- **Skills** — 8 builtin methodology files (`scoping`, `data-profiling`, `eda`, `feature-engineering`, `modeling`, `evaluation`, `reporting`, `deployment`) + 6 shared skills (`backtesting`, `causal-assumption-check`, `hypothesis-ranking`, `resource-aware-planning`, `retrain-vs-rollback`, `uncertainty-quantification`)
- **Multi-provider LLM** — Anthropic, OpenAI, Codex (ChatGPT OAuth), Gemini (Google OAuth), Groq, Mistral, Ollama, vLLM, SGLang, 100+ via LiteLLM
- **5-layer memory** — Immediate context, Session DB (SQLite+FTS5), Domain KB, Skills, Project Store (+ Code Registry for learned patterns)
- **Runtime operations** — Approval bus, policy engine, sensor hub, startup recovery, operator preferences, delivery rate limiter, digest builder, operator alert store, outcome delivery
- **Self-improvement** — pattern learning, domain KB extraction, skill generation from completed projects, independent cross-model evaluator
- **3-tier interface** — CLI (interactive TUI), Telegram bot, Electron desktop app
- **Telegram operator UX** — subscriptions, ack/mute/digest, inline callback actions, `/menu`, bot command registration, operator audit
- **Thread-aware session isolation** — Telegram topic-aware identity, recovery routing, session labels across runtime APIs and Electron panels
- **Delivery policy automation** — quiet hours, digest cadence/timezone, effective delivery settings, suggested next actions, repeated blocked-state escalation
- **3 operating modes** — `auto`, `supervised`, `step-by-step`
- **Budget control** — iteration / token / cost / wall-time limits with warning thresholds

## Current Implementation Snapshot (2026-04-15)

### Agent core & runtime
- **PLAN_10~12** Autonomous runtime, Electron frontend parity, Telegram operator parity — **Complete**
- **PLAN_13** Telegram operator UX hardening — **Complete** (subscriptions, ack/mute/digest, inline actions, `/menu`, audit)
- **PLAN_14** Thread-aware session isolation — **Complete** across runtime stores, Telegram routing, WebSocket payloads, Electron runtime views
- **PLAN_15** Notification delivery policy automation — **Complete** (quiet hours, digest cadence/timezone, suggested next actions, escalation)
- **PLAN_17** Capability roadmap active (P0 foundation, P1 data autonomy, P2 runtime autonomy, P3 enterprise, P4 artifact, P5 operations, P6 advanced) — see `Docs/plans/PLAN_17/`

### Productization (베타 출시 준비 — `Docs/plans/productization/`)
| ID | Area | Status |
|----|------|--------|
| P0-01 | Code execution sandbox (preamble + UI) | ✅ Complete (approval modal + violation toast shipped) |
| P0-02 | Secure credential storage | ✅ Complete — keyring + chunking for >2560-byte payloads (Codex OAuth); multi-platform real-device verification pending |
| P0-03 | Startup diagnostics & recovery | ✅ Complete — diagnostic window with root-cause classification |
| P0-04 | Config migration framework | ✅ Complete — schema v4 (observability defaults); 7-step authoring convention documented |
| P0-05 | Code signing & distribution | ⏸ CI pipeline ready — blocked on Windows EV + Apple Developer ID procurement |
| P0-06 | Packaged QA & smoke tests | ✅ Backend smoke (5/5) + Electron diagnostic-window E2E + happy-path E2E; signed-installer E2E gated on P0-05 |
| P0-07 | Observability & crash reporting | ✅ Sentry SDK integrated (backend + Electron) + DSA-* error catalog + onboarding telemetry consent; DSN procurement gated |
| P1-08 | Use-case onboarding wizard | ✅ Complete |
| P1-09 | Provider / Model abstraction UX | ✅ Complete |
| P1-10 | Data import UX — Postgres connector | ✅ Complete for Postgres GA (BigQuery/Snowflake UI polish: post-beta) |
| P1-11 | Cost governance & usage | ✅ Complete |
| P1-12 | Artifact export & reporting | ✅ Complete — PDF/docx/xlsx/ipynb + Korean content round-trip (48 tests) |
| P1-13 | i18n (Korean) & accessibility | ✅ Complete — ARIA audit across 7 modal/overlay components |
| P1-14 | Auto-update & release | ⏸ `electron-updater` wired — activation blocked on P0-05 |

### Latest bug fixes (pre-beta hardening)
- **Backend READY race** — `print("READY:port:token")` previously fired before the listening socket bound, racing Electron's `/health` probe. Moved emission into the FastAPI lifespan startup hook so `/health` is guaranteed to respond (`src/ds_agent/api/app.py`)
- **Windows credential size limit** — Codex CLI's ChatGPT OAuth bundle (~4.3 KB) exceeded the 2560-byte Windows Credential Manager cap, triggering `CredWrite error 1783`. `KeyringSecretStorage` now transparently chunks values over 1024 chars across `key__part0`, `key__part1`, ... with an `__ds_chunked__:N` header written last for crash safety (`src/ds_agent/infrastructure/secrets/secret_storage.py`)
- **Sandbox UI** — `sandbox.violation` event + blocking approval modal (Esc=reject, textarea rationale) + non-blocking violation toast (8s TTL, max 3 visible) wired into the renderer
- **Electron E2E hooks** — `DS_AGENT_BACKEND_COMMAND` (backend command override) + `DS_AGENT_E2E_USE_BUILT_RENDERER=1` (bypass Vite dev server) env hooks for deterministic smoke testing

### Verification baseline
| Check | Command | Result |
|-------|---------|--------|
| Backend baseline gate | `python scripts/check_backend_quality_gate.py` | Import contracts + architecture + DS semantic contracts |
| Unit + smoke | `pytest tests/unit tests/smoke` | **1382 passed** |
| Backend smoke | `pytest tests/smoke` | **5 passed** (packaged binary boots, /health, /ws) |
| Electron typecheck | `cd electron && npm run typecheck` | Clean |
| Diagnostic-window E2E | `cd electron && npm run test:e2e:smoke` | **PASS** (backend failure → diagnostic UI) |
| Happy-path E2E | `cd electron && npm run test:e2e:happy` | **PASS** (backend boot → /health → WS handshake → main UI hero) |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for Electron desktop app)

### Install

```bash
git clone https://github.com/your-org/ds-agent.git
cd ds-agent

pip install -e ".[all]"            # everything
pip install -e ".[cli]"            # CLI only
pip install -e ".[gateway]"        # FastAPI backend
pip install -e ".[providers]"      # All LLM providers
```

### Configure

```bash
# Option 1: environment variables
export ANTHROPIC_API_KEY=sk-ant-...
# or
export OPENAI_API_KEY=sk-...

# Option 2: interactive setup
ds-agent init
```

### Run

```bash
ds-agent                                      # Interactive CLI
ds-agent "Analyze data.csv, target is churn"  # One-shot
python -m ds_agent.api.app --port 18790       # API server (Electron backend)
```

## Electron Desktop App

Full-featured desktop application with chat UI, inline plots, file explorer, drag-and-drop upload, and a runtime operator console.

```bash
cd electron
npm install
npm run dev        # Development (Vite + Electron)
npm run build      # Production build (renderer + main)
npm run dist:win   # Windows NSIS installer
npm run dist:mac   # macOS DMG
npm run dist:linux # Linux AppImage
```

**Features:**
- Chat with Markdown, syntax highlighting, inline tables
- Tool activity stream (live execution status)
- Runtime console: sessions, runs, approvals, thread-aware labels
- Sandbox approval modal + violation toast (P0-01 Phase 3)
- Onboarding wizard (OAuth login, API key, local LLM)
- Sidebar: file explorer, plot gallery (click for full-size), model/mode selectors
- Settings panel (Ctrl+,), diagnostic panel on backend failure, update notification
- Dark/Light theme, Korean/English i18n
- ARIA: `role=dialog`, `aria-modal`, `aria-live` wired across 7 modal/overlay components

**Build for distribution:**

```bash
# Step by step
python scripts/build_backend.py    # PyInstaller → build/ds-agent-backend/
cd electron && npm run dist:win    # Windows NSIS installer
# Or everything at once
python scripts/build_all.py
```

Output lands in `electron/release/`. Unsigned builds show a SmartScreen warning on Windows and a Gatekeeper notarization prompt on macOS until EV / Developer ID certificates are wired in via `CSC_LINK` / `APPLE_ID` env vars (P0-05).

### Packaging verified (local dev build)

- `dist/ds-agent-backend/ds-agent-api.exe` — 43.5 MB PyInstaller single binary (spawned by the main process via `spawn()`)
- `electron/release/DS Agent-Setup-0.1.0-win.exe` — 179 MB NSIS installer (per-user install, desktop + start-menu shortcuts, UAC-free)

## Project Structure

```
src/ds_agent/
├── agent/              # Core loop, hooks, permissions, prompt builder, budget tracker
├── domain/             # Entities, value objects, domain interfaces (Clean Architecture inner)
├── application/        # Use cases, DTOs, application ports
├── infrastructure/
│   ├── auth/           # OAuth service, PKCE, callback server, token store
│   ├── secrets/        # KeyringSecretStorage (chunked), config/connector secret managers
│   ├── sandbox/        # Preamble generator for LLM-authored code
│   ├── observability/  # Sentry backend, redaction filter
│   ├── persistence/    # Stores for sessions, projects, registries
│   ├── migration/      # Schema migration runner + registry
│   └── ...             # artifact, distributed, external, support
├── providers/          # Anthropic, OpenAI, Codex OAuth, Gemini OAuth, LiteLLM, Ollama,
│                       # local discovery, pricing table, router
├── tools/              # Self-registering @tool decorator; data/ML/ops/governance tools
├── skills/             # 8 builtin + 6 shared Markdown skills; hub for discovery
├── memory/             # session_db, experiment_log, experiment_compare, code_registry,
│                       # domain_kb, project_store, unified_store
├── runtime/            # 28 orchestration modules: approval_store, coordinator, policy_engine,
│                       # sensor_hub, digest_builder, delivery_policy_store, delivery_rate_limiter,
│                       # event_classifier, operator_alert_state_store, operator_preferences_store,
│                       # run_registry, session_registry, startup_recovery, task_ledger, ...
├── self_improve/       # Post-project learning, pattern extractor, skill generator,
│                       # independent evaluator, learning adapter
├── config/             # Pydantic schema (v4), YAML/env loader
├── cli/                # Rich TUI, slash commands, onboarding wizard
├── api/                # FastAPI app (lifespan READY emit), WebSocket RPC, HTTP routes
│   └── routes/         # admin, config, files, status, support, usage
├── channels/           # Channel plugin system (Telegram, ...)
└── gateway/            # Session manager, Telegram runner

electron/
├── src/main/           # Electron main process (backend spawn, diagnostic window, IPC)
├── src/preload/        # Secure IPC bridge (exposes secret vault, policies, updater)
├── src/renderer/       # React 18 + TypeScript + Tailwind + Zustand
│   ├── components/
│   │   ├── chat/       # ChatPanel, ChatMessage, ChatInput, ToolActivity
│   │   ├── sidebar/    # FileExplorer, FileUpload, PlotGallery, ModelSelector
│   │   ├── layout/     # MainPanel, StatusBar, SplashScreen, DisconnectOverlay
│   │   ├── runtime/    # SessionsPanel, RunsPanel, RunDetailDrawer, approvals
│   │   ├── sandbox/    # SandboxApprovalModal, SandboxViolationToast (P0-01 Phase 3)
│   │   ├── settings/   # SettingsPanel, OnboardingWizard, ConnectorWizard (P1-10)
│   │   ├── diagnostic/ # DiagnosticPanel (backend failure classification)
│   │   └── workflow/   # WorkflowProgress, AlertBanner, QualityPanel, BudgetBar
│   └── stores/         # chatStore, agentStore, filesStore, configStore, i18nStore, workflowStore
└── tests/
    └── smoke/          # Playwright _electron specs (diagnostic-window, happy-path)

scripts/
├── build_backend.py    # PyInstaller → build/ds-agent-backend/
├── build_all.py        # Full pipeline: tests → PyInstaller → Electron → installer
├── sign_backend.py     # Windows signtool / macOS codesign wrapper (P0-05)
├── check_av_clean.py   # VirusTotal auto-scan (P0-05, CI optional)
└── clean_workspace.ps1 # Local cache / build-output pruning

tests/                  # 1382 tests passing (unit + smoke); 140+ test files
├── unit/               # Domain, Application, Infrastructure unit tests
├── integration/        # Tools, Skills, Memory, Telegram, Runtime wiring
├── smoke/              # PyInstaller binary health, /health, /api/status, WS
└── e2e/                # Full DS workflow simulation
```

## LLM Providers

| Provider | Type | Model Examples | Setup |
|----------|------|----------------|-------|
| Anthropic | API Key | `claude-sonnet-4-6`, `claude-opus-4-6`, `claude-haiku-4-5` | `ANTHROPIC_API_KEY` |
| OpenAI | API Key | `gpt-4.1`, `o3-mini` | `OPENAI_API_KEY` |
| Codex | OAuth | `codex/gpt-4.1`, `codex/o4-mini` | `codex login` (ChatGPT account) |
| Gemini | OAuth / Key | `gemini/gemini-2.5-pro` | Google login or `GEMINI_API_KEY` |
| Groq | API Key | `groq/llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| Ollama | Local | `ollama/qwen2.5:32b` | `ollama serve` |
| vLLM | Local | `vllm/meta-llama/Llama-3.1-8B` | vLLM server running |
| LiteLLM | Any | `openrouter/...`, `together/...` | Various API keys |

```python
# Model string format: provider/model-name
# Provider auto-detected from model name when prefix is omitted
"claude-sonnet-4-6"              # → Anthropic
"gpt-4.1"                        # → OpenAI
"codex/gpt-4.1"                  # → Codex OAuth
"ollama/qwen2.5:32b"             # → Ollama local
"groq/llama-3.3-70b-versatile"   # → LiteLLM
```

## WebSocket Protocol

The Electron app communicates with the Python backend via WebSocket (OpenClaw pattern) over a token-authenticated `/ws` endpoint:

```typescript
// Client → Server: RPC Request
{ type: "req", id: "r1", method: "chat.send", params: { message: "..." } }

// Server → Client: RPC Response
{ type: "res", id: "r1", ok: true, payload: { sessionId: "abc" } }

// Server → Client: Streaming Events
{ type: "event", event: "stream.delta", payload: { token: "Hello" } }
{ type: "event", event: "tool.start", payload: { name: "data_loader" } }
{ type: "event", event: "tool.end", payload: { name: "data_loader", success: true } }
{ type: "event", event: "stream.done", payload: { content: "...", cost: 0.05 } }
{ type: "event", event: "sandbox.violation", payload: { kind: "filesystem", blocked: true, ... } }
```

**Token auth (SEC-01)**: backend generates a one-time `DS_AGENT_WS_TOKEN` at launch; the Electron main process forwards it to the renderer via the `token` query param; `/ws` rejects any connection missing the expected token with close code `1008`.

**Representative RPC methods**: `chat.send`, `chat.abort`, `chat.history`, `run.start`, `run.wait`, `run.list`, `session.list`, `task.list`, `runtime.events.list`, `approval.list`, `approval.resolve`, `policy.get`, `policy.upsertRecurringGoal`, `config.get`, `config.set`, `files.list`, `files.upload`, `provider.list`, `provider.models`, `project.list`, `project.create`, `connector.create`, `connector.test`, `connector.list`, `secret.set`, `secret.delete`, `support.exportBundle`.

## Development

```bash
pip install -e ".[dev]"

# Tests
pytest                              # 1382 passed (unit + smoke baseline)
pytest tests/unit/                  # Unit only
pytest tests/smoke/                 # Packaged-binary smoke (requires built backend)
pytest -x                           # Stop on first failure

# Lint + type
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/ds_agent/

# Electron
cd electron
npm run typecheck                   # Main + renderer TS
npm run build                       # Vite + tsc
npm run test:e2e:smoke              # Diagnostic-window E2E
npm run test:e2e:happy              # Happy-path E2E (requires built backend)
```

## Workspace Cleanup

Cleanup script prunes local caches and temporary workdirs without touching source, docs, `openclaw/`, or datasets.

```powershell
# Preview cleanup candidates only
powershell -ExecutionPolicy Bypass -File .\scripts\clean_workspace.ps1

# Remove cache/temp targets
powershell -ExecutionPolicy Bypass -File .\scripts\clean_workspace.ps1 -Apply

# Also remove build outputs
powershell -ExecutionPolicy Bypass -File .\scripts\clean_workspace.ps1 -Apply -IncludeBuildArtifacts

# Cold rebuild (remove dependency installs and virtualenv too)
powershell -ExecutionPolicy Bypass -File .\scripts\clean_workspace.ps1 -Apply -IncludeDependencies -IncludeVirtualEnv
```

## Tests

Current verification snapshot:

- `python scripts/check_backend_quality_gate.py` → backend baseline gate (import contracts + architecture + DS semantic contracts)
- `pytest tests/unit tests/smoke` → **1382 passed**
- Packaged-binary smoke suite: 5/5 (backend boot, `/health`, `/api/status`, WS connect)
- Electron E2E: 2/2 (diagnostic-window failure path + happy-path)
- Coverage target: `78%+`
- Known pre-existing drift: `tests/integration/test_runtime_wiring.py::test_all_25_hooks_registered` expects 25 hooks, actual 26 (unrelated to recent changes)

## License

MIT
