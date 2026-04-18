# C15 Diagnostic Path Trace

**Agent**: C15 Packaging & Diagnostic Tester
**Run**: 2026-04-17
**Scope**: Verify that a failed backend startup deterministically routes the user to the diagnostic window (P0-03).

---

## 1. Entry points exercised

| Step | File | Symbol | Confirmed |
|------|------|--------|-----------|
| main ready | `electron/src/main/index.ts` | `app.whenReady().then(...)` | Playwright launched, `[main] Electron app is ready.` emitted |
| backend spawn | `electron/src/main/python-backend.ts` | `startPythonBackend()` | Env override `DS_AGENT_BACKEND_COMMAND` consumed (lines 216-225) |
| preflight | same file | `preflightCheck()` | Detected missing binary via `fs.existsSync(commandSpec.binaryPath)` |
| classify | same file | returns `{ reason: BINARY_NOT_FOUND }` | See enum line 31 |
| route | `electron/src/main/index.ts:41` | `createDiagnosticWindow(result)` | Invoked (main window never opened) |
| window | `electron/src/main/window.ts:46` | `createDiagnosticWindow()` | Loads renderer with `screen: 'diagnostic', startup: JSON.stringify(result)` |
| renderer | `electron/src/renderer/App.tsx:197-203` | `getScreen() === 'diagnostic'` → `<DiagnosticPanel />` | Assertion via `h1` text match |
| panel | `electron/src/renderer/components/diagnostic/DiagnosticPanel.tsx:72` | `REASON_COPY[BINARY_NOT_FOUND].title` | Rendered: **"Backend binary was not found"** |

---

## 2. Live Playwright evidence

### Path 5 — forced diagnostic (bad binary)

```
$ cd electron && npm run test:e2e:smoke
> vite build ...
> tsc -p tsconfig.main.json
> tsc -p tsconfig.test.json
> node tests/.compiled/smoke/diagnostic-window.spec.js
[smoke] PASS — diagnostic title: Backend binary was not found
```

Env under test:
- `DS_AGENT_BACKEND_COMMAND` = `<repo>/this-binary-does-not-exist`
- `DS_AGENT_SENTRY_DSN` = `` (blank — P0-07 Sentry disabled per spec)
- `DS_AGENT_E2E_USE_BUILT_RENDERER` = `1` (loads `dist/renderer/index.html`
  instead of Vite dev server)

### Path 4 — happy path guard

```
$ cd electron && npm run test:e2e:happy
> ...
[smoke] PASS — main UI hero rendered: DS Agent
```

The happy-path spec explicitly asserts `Diagnostic window appeared instead
of main UI` was NOT triggered (electron/tests/smoke/happy-path.spec.ts:70-75).
This verifies the non-diagnostic branch is taken when the backend spawns
successfully.

---

## 3. Failure reason taxonomy coverage (static)

From `electron/src/main/python-backend.ts:31-39`:

| Reason enum | UI title (DiagnosticPanel.tsx) | Classifier source |
|-------------|-------------------------------|-------------------|
| BINARY_NOT_FOUND | "Backend binary was not found" | preflightCheck + classifySpawnError (ENOENT) |
| BINARY_PERMISSION_DENIED | (rendered via REASON_COPY) | classifyStderr (permission denied / EACCES) |
| PORT_IN_USE | "Preferred startup port was unavailable" | classifyStderr (address already in use) |
| PYTHON_ERROR | "Backend crashed during startup" | classifyStderr (generic non-zero exit) |
| TIMEOUT / startup_timeout | "Backend startup timed out" | 30-second READY watchdog (STARTUP_TIMEOUT_MS) |
| ANTIVIRUS_BLOCKED | "Access blocked" | classifyStderr (access is denied / blocked) |
| CRASH_LOOP | "Multiple startup attempts failed" | After MAX_RESTARTS=3 retries |
| HEALTH_CHECK_FAILED | "Backend health check failed" | READY emitted but /health didn't respond 200 |

All 8 reasons map to unique renderer copy in `DiagnosticPanel.tsx`
(lines 70-114). Only BINARY_NOT_FOUND is exercised live; the others are
reachable via the same `createDiagnosticWindow` pathway and have
corresponding `recordDiagnosticLog('error', ...)` calls.

---

## 4. Security guard rails verified

- `sanitizeText()` in python-backend.ts:532 redacts `READY:<port>:<token>`
  to `READY:<port>:***REDACTED***` before any `recordDiagnosticLog` call
  on stdout chunks.
- Diagnostic window uses `contextIsolation: true`, `sandbox: true`,
  `nodeIntegration: false` (window.ts:54-58).
- The startup payload is passed via URL query `startup=<JSON>` which
  originates from the trusted main process — not user input.

---

## 5. Environment fallbacks explicitly declared

| Area | Blocked by | Fallback used here | Confidence |
|------|-----------|-------------------|------------|
| Code signing (NSIS install test) | P0-05 external credentials | Signed-install path NOT attempted. electron-builder config static-verified only. | Medium — cannot guarantee unsigned Win Defender friction. |
| Sentry DSN live | P0-07 external DSN | `DS_AGENT_SENTRY_DSN=""` forced during E2E; observability init short-circuits. | High — matches production no-DSN branch. |
| Auto-updater live feed injection | Requires packaged + signed app | Static audit of auto-updater.ts wiring + electron-builder.yml publish config. dev-app-update.yml template provided. | Medium — schema+IPC verified, network+install untested. |

---

## 6. Pass verdict (not self-pass — orchestrator decides)

Evidence supports the claim that the diagnostic-window routing is wired
correctly and terminates on the right renderer copy for the
`BINARY_NOT_FOUND` case. The other 7 failure reasons are reachable via
the identical dispatch and render via `REASON_COPY` table lookup. No
silent-failure branches were observed in the Electron main process;
every non-`ok` result records a diagnostic log and routes to
`createDiagnosticWindow`.
