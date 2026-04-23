/**
 * Electron main process for the DS Agent desktop app.
 *
 * 1. Start the Python backend
 * 2. Wait for READY + /health
 * 3. Open the main window or a startup diagnostic window
 * 4. Clean up the backend on exit
 */

import { app } from 'electron';
import { initAutoUpdater, shutdownAutoUpdater } from './auto-updater';
import { recordDiagnosticLog } from './diagnostics-collector';
import { registerMainIpcHandlers } from './ipc';
import { emitDeepLinkToRenderer } from './ipc/deepLink';
import {
  captureMainException,
  initializeMainObservability,
  shutdownMainObservability,
} from './observability';
import { startPythonBackend, stopPythonBackend } from './python-backend';
import { createDiagnosticWindow, createMainWindow, getMainWindow } from './window';

initializeMainObservability();

const e2eUserDataDir = process.env.DS_AGENT_E2E_USER_DATA_DIR;
if (e2eUserDataDir && e2eUserDataDir.trim().length > 0) {
  app.setPath('userData', e2eUserDataDir);
}

const DEEP_LINK_SCHEME = 'ds-agent';
const DEEP_LINK_PROTOCOL_PREFIX = `${DEEP_LINK_SCHEME}://`;

function extractDeepLinkFromArgv(argv: readonly string[]): string | null {
  for (let index = argv.length - 1; index >= 0; index -= 1) {
    const arg = argv[index];
    if (typeof arg === 'string' && arg.startsWith(DEEP_LINK_PROTOCOL_PREFIX)) {
      return arg;
    }
  }
  return null;
}

let pendingDeepLinkUri: string | null = extractDeepLinkFromArgv(process.argv.slice(1));

function deliverDeepLink(rawUri: string): void {
  const win = getMainWindow();
  if (!win) {
    pendingDeepLinkUri = rawUri;
    return;
  }
  if (win.isMinimized()) {
    win.restore();
  }
  win.focus();
  emitDeepLinkToRenderer(rawUri);
}

const singleInstanceLockAcquired = app.requestSingleInstanceLock();
if (!singleInstanceLockAcquired) {
  app.quit();
} else {
  app.on('second-instance', (_event, argv) => {
    const uri = extractDeepLinkFromArgv(argv);
    if (uri) {
      deliverDeepLink(uri);
    } else {
      const win = getMainWindow();
      if (win) {
        if (win.isMinimized()) {
          win.restore();
        }
        win.focus();
      }
    }
  });
}

app.on('open-url', (event, url) => {
  event.preventDefault();
  if (typeof url === 'string' && url.startsWith(DEEP_LINK_PROTOCOL_PREFIX)) {
    deliverDeepLink(url);
  }
});

app.whenReady().then(async () => {
  registerMainIpcHandlers();
  recordDiagnosticLog('info', 'main', 'Electron app is ready.');
  console.log('[main] Starting Python backend...');
  recordDiagnosticLog('info', 'main', 'Starting Python backend.');
  const result = await startPythonBackend();

  if (!result.ok) {
    console.error('[main] Failed to start backend:', result.reason, result.diagnostics);
    recordDiagnosticLog('error', 'main', 'Backend startup failed.', {
      reason: result.reason,
      diagnostics: result.diagnostics,
    });
    captureMainException(new Error(`Backend startup failed: ${result.reason}`), {
      reason: result.reason,
      diagnostics: result.diagnostics,
    });
    createDiagnosticWindow(result);
    return;
  }

  console.log(`[main] Backend ready on port ${result.port}`);
  recordDiagnosticLog('info', 'main', 'Backend startup succeeded.', {
    port: result.port,
    diagnostics: result.diagnostics,
  });
  createMainWindow(result.port, result.token);
  if (
    process.env.DS_AGENT_E2E_DISABLE_PROTOCOL_REGISTRATION !== '1' &&
    !app.isDefaultProtocolClient(DEEP_LINK_SCHEME)
  ) {
    app.setAsDefaultProtocolClient(DEEP_LINK_SCHEME);
  }
  if (pendingDeepLinkUri) {
    const queued = pendingDeepLinkUri;
    pendingDeepLinkUri = null;
    deliverDeepLink(queued);
  }
  initAutoUpdater();
});

app.on('window-all-closed', () => {
  stopPythonBackend();
  shutdownAutoUpdater();
  shutdownMainObservability();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopPythonBackend();
  shutdownAutoUpdater();
  shutdownMainObservability();
});
