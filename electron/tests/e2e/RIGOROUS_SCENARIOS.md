# Electron E2E Rigorous Scenario Matrix

This matrix is for real Electron app verification with Playwright `_electron`.
Default scenarios avoid live LLM/network dependency and use the packaged backend
binary plus seeded local workspaces.

## Default Gate

Run from the repository root:

```powershell
.\scripts\run_electron_e2e_rigorous.ps1
```

The runner builds the backend unless `-SkipBackendBuild` is supplied, builds the
Electron renderer/main process, compiles E2E TypeScript, runs the actual Electron
flows, and writes screenshots/logs under `.manual_verification/electron-e2e/`.

Useful narrower runs:

```powershell
.\scripts\run_electron_e2e_rigorous.ps1 -Quick
.\scripts\run_electron_e2e_rigorous.ps1 -SkipBackendBuild -SkipElectronBuild -Quick
.\scripts\run_electron_e2e_rigorous.ps1 -IncludeA11y -IncludeOnboarding
```

If the automation host blocks Node `child_process.spawn` but still allows
PowerShell to start executables directly, use the CDP fallback:

```powershell
.\scripts\run_electron_e2e_direct_cdp.ps1
```

That fallback starts the packaged backend and Electron directly from
PowerShell, passes `DS_AGENT_E2E_EXISTING_BACKEND_PORT` into Electron so the
main process does not spawn the backend, then connects to the running Electron
window through Chrome DevTools Protocol to capture the visual survey.

Known local blocker: if Windows shows an `electron.exe - Application Error`
dialog and `electron.stderr.log` contains `platform_channel.cc` or
`network_sandbox.cc` with `Access is denied (0x5)`, stop the run. In that
state Chromium's Windows sandbox/AppContainer setup is failing before the
renderer can be driven. This is below Playwright and below application code.
Run the suite from a non-sandboxed elevated terminal, or fix the host policy
that blocks Chromium AppContainer/cache ACL setup, then retry the same command.

## Scenario Coverage

| Area | Scenario | Evidence | Automated Assertions |
| --- | --- | --- | --- |
| Startup | Backend failure routes to diagnostic window | failure diagnostic HTML/screenshot on failure | `binary_not_found` classification is rendered |
| Startup | Packaged backend READY -> `/health` -> WebSocket -> main UI | console log plus failure artifacts | main DS Agent UI renders, no diagnostic panel |
| Visual survey | Empty chat, files/upload sidebar, workflow, runtime, review, experiments, settings | `01-*` through `08-*` screenshots | target surface selectors are visible before capture |
| Onboarding | First-run onboarding creates contract-first Mission Brief | smoke log/artifacts | onboarding can complete and active draft contract exists |
| Task contract | Edit -> agree -> start -> review -> close | smoke log/artifacts | status badge reaches each lifecycle state and DoD summary appears |
| Governance | Delegation/rollback/rejection paths | smoke log/artifacts | seeded governance state is actionable without live LLM |
| Workflow ops | Work object phase advance/close and integration health | named screenshots | seeded Slack/Jira events, phase transition, connector cards |
| Autonomy | Runtime authority overlay and Policy Studio action matrix | named screenshots | freeze overlay, contract preset, matrix override persistence |
| Decision OS | Review overview, shared-skill artifact, run diff, promotion gate, post-deploy status | named screenshots | seeded runs/models/monitors load and promotion request records |
| Accessibility | Onboarding, chat, settings, sidebar, runtime, workspace axe scans | stdout report | no critical/serious WCAG 2.1 A/AA violations |
| Palette | Design token / color surface smoke | stdout report | palette expectations pass |

## Manual Visual Review Checklist

Use the `visual-surface-survey` screenshots first because they are intentionally
captured for human review.

- Chat: empty state is centered, textarea is enabled, status bar does not overlap
  content, no diagnostic or disconnect overlay is visible.
- Files/upload: import dropzone is discoverable, format badges are readable,
  file explorer empty state is not visually confused with an error.
- Workflow: Mission Brief, Work Object, Integration Settings, Approval, Quality,
  and Budget panels are separated clearly and scannable in the sidebar.
- Runtime: authority/policy/certification/session panels are readable at the
  default window size; warning/freeze copy is not clipped.
- Decision OS: overview cards, run diff controls, promotion entry point, and
  post-deploy controls are visible without horizontal overflow.
- Experiments: metrics and experiment surfaces have meaningful empty/seeded
  states and do not collapse into blank panels.
- Settings: dialog has a clear title, close control, keyboard Escape behavior,
  readable auth/API-key sections, and no background focus leakage.

## Optional Live-LLM Scenario

Only run this when real provider credentials and network access are intentionally
available. It is excluded from the default gate because it is slower, flaky, and
cost-bearing.

1. Start the same Electron app with a real configured provider.
2. Upload a small CSV fixture.
3. Send a scoped DS request: "Profile this dataset, identify target leakage
   risks, build a baseline, and produce a concise report."
4. Verify tool activity, sandbox approval/violation surfaces when relevant,
   generated artifacts, result cards, and final answer language.
