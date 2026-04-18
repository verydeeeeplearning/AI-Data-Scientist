/**
 * Auto-update runtime integration (P1-14).
 *
 * Uses electron-updater to check a GitHub Releases feed, stream progress to
 * the renderer, and restart on user confirmation. In dev (electron binary
 * from node_modules) the updater is disabled — the packaged app has its own
 * version metadata.
 *
 * Flow:
 *  1. init() wires handlers + schedules periodic checks.
 *  2. autoUpdater emits events → forwarded to renderer as `updater:*` IPC.
 *  3. Renderer asks us to `checkForUpdates`, `downloadUpdate`, or
 *     `quitAndInstall` via IPC handlers registered here.
 */

import { app, BrowserWindow, ipcMain } from 'electron';
import log from 'electron-log';
import { autoUpdater, type ProgressInfo, type UpdateInfo } from 'electron-updater';
import { recordDiagnosticLog } from './diagnostics-collector';

const CHECK_DELAY_MS = 5 * 60 * 1000; // first check 5 min after launch
const CHECK_INTERVAL_MS = 4 * 60 * 60 * 1000; // then every 4 hours
const RETRY_AFTER_FAILURE_MS = 24 * 60 * 60 * 1000;

let initialised = false;
let checkTimer: NodeJS.Timeout | null = null;
let retryTimer: NodeJS.Timeout | null = null;

function broadcast(event: string, payload: Record<string, unknown>): void {
  for (const window of BrowserWindow.getAllWindows()) {
    if (!window.isDestroyed()) {
      window.webContents.send(event, payload);
    }
  }
}

function scheduleRecurring(): void {
  if (checkTimer) clearTimeout(checkTimer);
  checkTimer = setTimeout(() => {
    void autoUpdater.checkForUpdates().catch((error) => {
      log.warn('[updater] recurring check failed', error);
    });
    setInterval(() => {
      void autoUpdater.checkForUpdates().catch((error) => {
        log.warn('[updater] recurring check failed', error);
      });
    }, CHECK_INTERVAL_MS);
  }, CHECK_DELAY_MS);
}

function scheduleRetry(): void {
  if (retryTimer) clearTimeout(retryTimer);
  retryTimer = setTimeout(() => {
    void autoUpdater.checkForUpdates().catch((error) => {
      log.warn('[updater] retry check failed', error);
    });
  }, RETRY_AFTER_FAILURE_MS);
}

function serializeUpdateInfo(info: UpdateInfo): Record<string, unknown> {
  return {
    version: info.version,
    releaseDate: info.releaseDate,
    releaseName: info.releaseName ?? null,
    releaseNotes: typeof info.releaseNotes === 'string' ? info.releaseNotes : null,
  };
}

function resolveChannel(): 'stable' | 'beta' | 'internal' {
  const raw = (process.env.DS_AGENT_UPDATE_CHANNEL ?? '').trim().toLowerCase();
  if (raw === 'beta' || raw === 'internal') return raw;
  return 'stable';
}

export function initAutoUpdater(): void {
  if (initialised) return;
  initialised = true;

  if (!app.isPackaged) {
    log.info('[updater] dev build detected — auto-update disabled.');
    return;
  }

  log.transports.file.level = 'info';
  autoUpdater.logger = log;
  autoUpdater.autoDownload = false; // User confirms before consuming bandwidth.
  autoUpdater.autoInstallOnAppQuit = true;
  autoUpdater.channel = resolveChannel();

  autoUpdater.on('checking-for-update', () => {
    broadcast('updater:checking', {});
  });

  autoUpdater.on('update-available', (info: UpdateInfo) => {
    recordDiagnosticLog('info', 'updater', 'Update available.', { version: info.version });
    broadcast('updater:update-available', serializeUpdateInfo(info));
  });

  autoUpdater.on('update-not-available', (info: UpdateInfo) => {
    broadcast('updater:update-not-available', serializeUpdateInfo(info));
  });

  autoUpdater.on('download-progress', (progress: ProgressInfo) => {
    broadcast('updater:download-progress', {
      percent: Math.round(progress.percent),
      bytesPerSecond: progress.bytesPerSecond,
      transferred: progress.transferred,
      total: progress.total,
    });
  });

  autoUpdater.on('update-downloaded', (info: UpdateInfo) => {
    recordDiagnosticLog('info', 'updater', 'Update downloaded.', { version: info.version });
    broadcast('updater:update-ready', serializeUpdateInfo(info));
  });

  autoUpdater.on('error', (error: Error) => {
    recordDiagnosticLog('error', 'updater', 'Auto-update error.', {
      message: error.message,
      stack: error.stack ?? null,
    });
    broadcast('updater:error', {
      message: error.message ?? 'Update failed.',
    });
    scheduleRetry();
  });

  ipcMain.removeHandler('updater:check');
  ipcMain.removeHandler('updater:download');
  ipcMain.removeHandler('updater:install');
  ipcMain.removeHandler('updater:getState');

  ipcMain.handle('updater:check', async () => {
    try {
      const result = await autoUpdater.checkForUpdates();
      return {
        ok: true,
        updateAvailable: Boolean(result?.updateInfo && result.updateInfo.version !== app.getVersion()),
        version: result?.updateInfo?.version ?? null,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Update check failed.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle('updater:download', async () => {
    try {
      await autoUpdater.downloadUpdate();
      return { ok: true };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Download failed.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle('updater:install', () => {
    setImmediate(() => autoUpdater.quitAndInstall(false, true));
    return { ok: true };
  });

  ipcMain.handle('updater:getState', () => ({
    channel: autoUpdater.channel,
    currentVersion: app.getVersion(),
    isPackaged: app.isPackaged,
  }));

  scheduleRecurring();
  recordDiagnosticLog('info', 'updater', 'Auto-updater initialised.', {
    channel: autoUpdater.channel,
    currentVersion: app.getVersion(),
  });
}

export function shutdownAutoUpdater(): void {
  if (checkTimer) {
    clearTimeout(checkTimer);
    checkTimer = null;
  }
  if (retryTimer) {
    clearTimeout(retryTimer);
    retryTimer = null;
  }
}
