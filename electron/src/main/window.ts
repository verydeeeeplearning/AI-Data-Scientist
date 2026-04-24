/**
 * BrowserWindow management.
 */

import { BrowserWindow, app } from 'electron';
import path from 'path';
import { getRendererObservabilityQuery } from './observability';
import type { BackendStartResult } from './python-backend';

let mainWindow: BrowserWindow | null = null;

function shouldDisableRendererSandboxForE2E(): boolean {
  return process.env.DS_AGENT_E2E_DISABLE_CHROMIUM_SANDBOX === '1';
}

export function createMainWindow(backendPort: number, wsToken: string = ''): BrowserWindow {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    title: 'DS Agent',
    backgroundColor: '#0f1117',
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: !shouldDisableRendererSandboxForE2E(),
    },
  });

  // Pass backend port and WS token to renderer via query params (SEC-01)
  const query: Record<string, string> = {
    port: String(backendPort),
    ...getRendererObservabilityQuery(),
  };
  if (wsToken) query.token = wsToken;
  if (process.env.DS_AGENT_E2E_SKIP_ONBOARDING === '1') {
    query.e2e_skip_onboarding = '1';
  }
  if (process.env.DS_AGENT_E2E_FORCE_LEGACY_IA === '1') {
    query.e2e_force_legacy_ia = '1';
  }
  loadRenderer(mainWindow, query);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  return mainWindow;
}

export function createDiagnosticWindow(result: Extract<BackendStartResult, { ok: false }>): BrowserWindow {
  mainWindow = new BrowserWindow({
    width: 860,
    height: 700,
    minWidth: 720,
    minHeight: 560,
    title: 'DS Agent Diagnostics',
    backgroundColor: '#0f1117',
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: !shouldDisableRendererSandboxForE2E(),
    },
  });

  loadRenderer(mainWindow, {
    screen: 'diagnostic',
    startup: JSON.stringify(result),
    ...getRendererObservabilityQuery(),
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  return mainWindow;
}

export function getMainWindow(): BrowserWindow | null {
  return mainWindow;
}

export function navigateMainWindowToBackend(backendPort: number, wsToken: string = ''): void {
  if (!mainWindow || mainWindow.isDestroyed()) {
    createMainWindow(backendPort, wsToken);
    return;
  }

  const query: Record<string, string> = {
    port: String(backendPort),
    ...getRendererObservabilityQuery(),
  };
  if (wsToken) query.token = wsToken;
  if (process.env.DS_AGENT_E2E_SKIP_ONBOARDING === '1') {
    query.e2e_skip_onboarding = '1';
  }
  if (process.env.DS_AGENT_E2E_FORCE_LEGACY_IA === '1') {
    query.e2e_force_legacy_ia = '1';
  }
  loadRenderer(mainWindow, query);
}

export function navigateMainWindowToDiagnostic(
  result: Extract<BackendStartResult, { ok: false }>
): void {
  if (!mainWindow || mainWindow.isDestroyed()) {
    createDiagnosticWindow(result);
    return;
  }

  loadRenderer(mainWindow, {
    screen: 'diagnostic',
    startup: JSON.stringify(result),
    ...getRendererObservabilityQuery(),
  });
}

function loadRenderer(window: BrowserWindow, query: Record<string, string>): void {
  // E2E hook: when set, load the built renderer regardless of `app.isPackaged`.
  // Lets smoke tests run against `npm run build` output without spinning up Vite.
  const useBuilt = app.isPackaged || process.env.DS_AGENT_E2E_USE_BUILT_RENDERER === '1';

  if (useBuilt) {
    window.loadFile(path.join(__dirname, '../renderer/index.html'), { query });
    return;
  }

  const params = new URLSearchParams(query).toString();
  window.loadURL(`http://localhost:5173?${params}`);
  window.webContents.openDevTools({ mode: 'right' });
}
