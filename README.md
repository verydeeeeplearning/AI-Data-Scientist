# DS Agent - AI Data Scientist

DS Agent is a local-first autonomous data science agent. It combines a Python
backend, a tool-driven agent loop, persistent runtime state, and an Electron
desktop interface for running data analysis workflows from data intake through
modeling, review, and artifact delivery.

The central runtime model is simple: the LLM proposes tool calls, the backend
executes them through registered tools and safety hooks, and the agent repeats
until the task is complete or budget and policy controls stop it.

## Repository At A Glance

- `src/ds_agent/` contains the Python backend, domain model, agent runtime,
  tools, providers, memory stores, API routes, CLI, and gateway surfaces.
- `electron/` contains the Electron 31 desktop app, React 18 renderer, Vite
  builds, Tailwind styles, Zustand stores, Storybook, contract tests, and
  Playwright smoke tests.
- `scripts/` contains quality gates, PyInstaller packaging, release packaging,
  smoke runners, signing helpers, and parity harness scripts.
- `tests/` contains Python unit, contract, integration, e2e, and packaged
  backend smoke tests.
- `assets/`, `config/`, and `electron/resources/` contain export themes,
  local config assets, sample datasets, and packaging resources.

## Core Architecture

### Agent Runtime

- `ds_agent.agent.core.DSAgent` is the main async loop. It builds prompts,
  sends messages to the provider, dispatches tool calls, records runtime
  events, checkpoints state, and persists transcript data.
- `ds_agent.agent.factory.create_agent()` is the shared wiring point for CLI,
  WebSocket, Telegram/gateway, and desktop paths. It connects tools, hooks,
  skills, memory, approvals, task contracts, verifier support, and sandbox
  policy in one place.
- Hooks enforce data science and governance behavior in code. Current hook
  groups include permissions, audit, budget, workflow tracking, leakage checks,
  baseline and overfitting guards, semantic trust, PII redaction, lineage,
  claim traceability, drift detection, self-debug, and verifier integration.
- Tools self-register through `@tool` into `ToolRegistry`. Dispatch validates
  JSON-schema arguments, enforces per-tool timeouts, and returns JSON-formatted
  errors.

### Backend API

- FastAPI entrypoint: `python -m ds_agent.api.app --port 18790`
- Default host and port: `127.0.0.1:18790`
- Health endpoint: `GET /health`
- Status endpoint: `GET /api/status`
- WebSocket endpoint: `/ws`
- WebSocket auth uses a one-time token. If `DS_AGENT_WS_TOKEN` is not set, the
  backend generates one at startup.
- Electron waits for `READY:<port>:<token>` on stdout, then verifies `/health`
  before opening the main window.

API route groups currently cover status, config, files, workspace upload,
onboarding, integrations, mission context, task contracts, work objects, cards,
trust metadata, export, support bundles, usage, certification, access logs,
approval grants, admin, and web push.

### Providers

`ProviderRouter` parses model strings and routes calls to the correct provider.
Supported routing prefixes include:

- `anthropic/...`
- `openai/...`
- `codex/...`
- `gemini/...`
- `ollama/...`
- `vllm/...`
- `sglang/...`

Unknown model strings fall through to LiteLLM when that extra is installed.
Provider fallback chains are configured through the runtime config.

### Desktop App

The desktop app is an Electron shell around the Python backend.

- Main process: starts the backend, handles diagnostics, IPC, deep links,
  auto-update wiring, safe storage, and shutdown.
- Preload: exposes a narrow `electronAPI` bridge with context isolation enabled
  and Node integration disabled in the renderer.
- Renderer: React, TypeScript, TailwindCSS, Zustand, WebSocket RPC, command
  palette, onboarding, settings, workspace upload, runtime panels, governance
  views, artifact workspace, and floating chat.
- Navigation areas: Artifacts, Runs, Governance, and Admin. Mission context and
  chat live in the top strip and floating chat surface.
- Mobile bundle: `electron/src/mobile` has a separate Vite build for the mobile
  companion surface and service worker.

## Key Capabilities

- Data science toolchain: data loading, profiling, EDA, feature engineering,
  modeling, evaluation, reporting, deployment helpers, A/B testing, drift,
  schema, SQL, semantic query, and distributed execution helpers.
- Workspace UX: file upload, schema preview, file explorer, plot gallery,
  project panel, experiments, portfolio, evidence workspace, and export flows.
- Runtime operations: sessions, runs, tasks, checkpoints, recurring goals,
  alerts, policy evaluation, approval grants, delivery settings, digests, and
  startup recovery.
- Governance: task contracts, review artifacts, verifier results, trust
  metadata, certification, lineage, result cards, policy panels, and access
  logs.
- Memory and learning: session history, experiment logs, domain knowledge,
  semantic packs, learned patterns, learning inbox, promotion review, and
  rollback support.
- Secrets: API keys and OAuth payloads are stored through the secret storage
  layer. OS keyring is preferred, with chunking for large token payloads and an
  in-memory degraded fallback when keyring is unavailable.
- Sandbox: agent-authored Python runs through `ProcessSandbox`; packaged
  PyInstaller builds use the backend binary's `--mode exec SCRIPT` path for
  sandbox subprocess execution.

## Prerequisites

- Python 3.11 or newer
- Node.js 18 or newer
- npm for the Electron workspace

Optional provider SDKs and gateway dependencies are installed through Python
extras.

## Install

From the repository root:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[all]"
```

More targeted installs:

```bash
python -m pip install -e ".[cli]"
python -m pip install -e ".[gateway]"
python -m pip install -e ".[providers]"
python -m pip install -e ".[dev]"
```

Electron dependencies:

```bash
cd electron
npm install
```

## Configuration

Default config path:

```text
~/.ds-agent/config.yaml
```

Set `DS_AGENT_CONFIG_PATH` to load a different config file.

Important defaults from the config schema:

- Config schema version: `4`
- Default model: `anthropic/claude-sonnet-4-6`
- Default budget: `10.0` USD
- Default workspace: `~/.ds-agent/workspace`
- Default mode: `auto`
- Default response language: `ko`

Common environment overrides:

```bash
export DS_AGENT_MODEL=anthropic/claude-sonnet-4-6
export DS_AGENT_MAX_BUDGET_USD=10.0
export DS_AGENT_BUDGET_WARNING_THRESHOLD_PCT=80
export DS_AGENT_MODE=auto
export DS_AGENT_MAX_ITERATIONS=100
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
```

Other supported runtime overrides include `DS_AGENT_GEMINI_CLIENT_SECRET`,
`DS_AGENT_TELEGRAM_BOT_TOKEN`, `DS_AGENT_SENTRY_DSN`,
`DS_AGENT_ERROR_REPORTING_ENABLED`, and `DS_AGENT_TELEMETRY_ENABLED`.

Interactive setup:

```bash
ds-agent init
```

## Run

Interactive CLI:

```bash
ds-agent
```

One-shot CLI:

```bash
ds-agent "Analyze data.csv. The target column is churn."
```

Backend API:

```bash
python -m ds_agent.api.app --port 18790
```

Daemon entrypoint:

```bash
ds-agent-daemon
```

Useful CLI subcommands include `contract`, `integration`, `portfolio`,
`learning`, `work`, `delivery`, `mode`, `certification`, `verdict`,
`web-push`, `semantic`, `eval`, `open`, and `share`.

## Electron Development

Install Python dependencies first from the repository root, then start Electron:

```bash
cd electron
npm run dev
```

Development behavior:

- The renderer runs on Vite at `http://localhost:5173`.
- The main process starts `python -m ds_agent.api.app --port <port>`.
- `DS_AGENT_BACKEND_COMMAND` and `DS_AGENT_BACKEND_ARGS` can override the
  backend command.
- `DS_AGENT_E2E_USE_BUILT_RENDERER=1` forces Electron to load the built
  renderer instead of the Vite dev server.
- `DS_AGENT_E2E_EXISTING_BACKEND_PORT` lets tests or local rigs reuse an
  already-running backend.

Build commands:

```bash
cd electron
npm run typecheck
npm run build
npm run build:mobile
```

## Packaging

Build the PyInstaller backend:

```bash
python scripts/build_backend.py --clean
```

The backend binary is produced under `dist/ds-agent-backend/` and copied to
`build/ds-agent-backend/` for Electron packaging.

Package the desktop app:

```bash
cd electron
npm run dist:win
npm run dist:mac
npm run dist:linux
```

Or run the full pipeline:

```bash
python scripts/build_all.py --platform win
```

`electron-builder` packages the PyInstaller backend as an extra resource.
Release targets are Windows NSIS, macOS DMG, and Linux AppImage. The desktop app
also registers the `ds-agent://` deep-link scheme.

## Verification

Python quality gate:

```bash
python scripts/check_backend_quality_gate.py
```

Python test and static checks:

```bash
python -m pytest tests
ruff check .
ruff format --check .
mypy src/ds_agent/
```

Packaged backend smoke tests:

```bash
python scripts/build_backend.py --clean
python -m pytest tests/smoke -v -m smoke
```

Electron checks:

```bash
cd electron
npm run typecheck
npm run build
npm run test:contract
npm run test:e2e:smoke
npm run test:e2e:happy
```

Notes:

- `npm run test:e2e:happy` expects a built backend binary. Run
  `python scripts/build_backend.py --clean` first if it is missing.
- `tests/smoke` skips locally when the packaged backend binary is absent unless
  a smoke runner builds it first.
- Some integration and provider tests require external credentials or local
  services.

## Project Structure

```text
src/ds_agent/
  agent/             Agent loop, hooks, factory, prompts, budget, context
  api/               FastAPI app, WebSocket RPC, HTTP routes
  application/       Use cases, services, DTOs, ports
  channels/          Channel plugin registry and bundled channel support
  cli/               Rich TUI, slash commands, setup and operator commands
  config/            Pydantic config schema and YAML/env loader
  domain/            Entities, value objects, domain interfaces, errors
  evaluation/        Evaluation domain, application services, CLI, stores
  gateway/           Daemon, session manager, Telegram runner and supervisor
  infrastructure/    Persistence, secrets, auth, sandbox, connectors, exports
  memory/            Session, experiment, project, domain, semantic stores
  presentation/      Presentation mappers for delivery and review surfaces
  providers/         Anthropic, OpenAI, Codex, Gemini, LiteLLM, Ollama routing
  runtime/           Sessions, runs, policies, approvals, alerts, delivery
  self_improve/      Learning, pattern extraction, promotion, post-project flow
  skills/            Builtin, shared, custom, mission, and domain skill packs
  tools/             Registered DS, governance, semantic, file, SQL tools

electron/
  src/main/          Electron main process, backend spawn, diagnostics, IPC
  src/preload/       Secure contextBridge API
  src/renderer/      React desktop renderer
  src/mobile/        Mobile companion bundle and service worker
  tests/             Contract, smoke, and e2e tests
  scripts/           Frontend lint, audit, i18n, and test runners
```

## Engineering Constraints

- Domain code must not import infrastructure or outer layers.
- Application code must not depend directly on infrastructure implementations
  unless an existing boundary explicitly allows it.
- Use `Path.is_relative_to()` for path boundary checks.
- Do not store API keys or OAuth tokens in frontend local storage.
- Production code execution must go through the sandbox path.
- Tool failures should return JSON error payloads, not plain-text exceptions.
- Config mutation is path-whitelisted and assignment-validated.
- Large secret payloads should go through `KeyringSecretStorage.store()` so
  chunking is applied when needed.

## License

MIT
