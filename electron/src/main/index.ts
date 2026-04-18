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
import {
  captureMainException,
  initializeMainObservability,
  shutdownMainObservability,
} from './observability';
import { startPythonBackend, stopPythonBackend } from './python-backend';
import { createDiagnosticWindow, createMainWindow } from './window';

initializeMainObservability();

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
