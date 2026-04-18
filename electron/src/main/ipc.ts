/**
 * Electron IPC registration for renderer-only desktop capabilities.
 */

import fs from 'fs/promises';
import http from 'http';
import path from 'path';
import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron';
import type { OpenDialogOptions, SaveDialogOptions } from 'electron';
import { pathToFileURL } from 'url';
import { buildSupportBundle, recordDiagnosticLog } from './diagnostics-collector';
import { updateMainObservability } from './observability';
import { getBackendConnection, restartPythonBackend } from './python-backend';
import { loadSampleForUseCase } from './sample-data';
import {
  deleteProviderApiKey,
  getMaskedProviderApiKeys,
  getSecretVaultStatus,
  setProviderApiKey,
} from './secret-vault';
import {
  getMainWindow,
  navigateMainWindowToBackend,
  navigateMainWindowToDiagnostic,
} from './window';
import { loadRenderedArtifactPreview } from './task-contract-preview';

interface ExportDiagnosticBundleParams {
  defaultName?: string;
  payload?: Record<string, unknown> | null;
}

interface SetApiKeyParams {
  provider?: string;
  key?: string;
}

interface DeleteApiKeyParams {
  provider?: string;
}

interface LoadSampleParams {
  useCaseId?: string;
}

interface ExportSupportBundleParams {
  defaultName?: string;
}

interface FinishArtifactExportParams {
  stagedPath?: string;
  suggestedFilename?: string;
  format?: string;
  needsPdfRender?: boolean;
}

interface UpdateObservabilityParams {
  errorReportingEnabled?: boolean;
  telemetryEnabled?: boolean;
}

interface TaskContractListParams {
  sessionId?: string;
  status?: string[];
  limit?: number;
}

interface WorkObjectListParams {
  sessionId?: string;
  taskContractId?: string;
  phase?: string[];
  limit?: number;
}

interface WorkObjectGetParams {
  workObjectId?: string;
  timelineLimit?: number;
}

interface WorkObjectIntakeParams {
  taskContractId?: string;
  title?: string;
  requestSource?: string;
  requestorId?: string;
  requestorDisplay?: string;
  originalText?: string;
  channel?: string;
  ownerAgent?: string;
  tags?: string[];
}

interface WorkObjectAdvanceParams {
  workObjectId?: string;
  toPhase?: string;
  runId?: string;
}

interface WorkObjectCloseParams {
  workObjectId?: string;
  reason?: string;
}

interface TaskContractActiveParams {
  sessionId?: string;
  include?: string[];
}

interface TaskContractGetParams {
  taskId?: string;
  include?: string[];
}

interface TaskContractUpdateParams {
  taskId?: string;
  expectedVersion?: number;
  patch?: Record<string, unknown>;
  transitionTo?: string;
  reason?: string;
}

interface TaskContractCloseParams {
  taskId?: string;
  expectedVersion?: number;
  closingNote?: string;
}

interface TaskContractVerifyAssumptionParams {
  taskId?: string;
  entryId?: string;
  expectedVersion?: number;
  verificationNote?: string;
}

interface TaskContractBuildDeliveryPackParams {
  taskId?: string;
  audiences?: string[];
  followUpActions?: string[];
  sourceAnalysisId?: string;
  confidence?: number;
  signedBy?: string;
  signature?: string;
  globalContext?: Record<string, string>;
  tenant?: string;
}

interface TaskContractRenderArtifactParams {
  taskId?: string;
  artifactId?: string;
  analysis?: Record<string, unknown> | string;
  outputDir?: string;
  audienceProfile?: string;
  providerBacked?: boolean;
  model?: string;
}

interface TaskContractPreviewRenderedArtifactParams {
  renderedUri?: string;
  format?: string;
}

interface TaskContractDispatchDeliveryParams {
  taskId?: string;
  artifactIds?: string[];
  channels?: string[];
  dryRun?: boolean;
  approveManualReview?: boolean;
}

interface TaskContractListDeliveryLogParams {
  taskId?: string;
  packId?: string;
  artifactIds?: string[];
  channels?: string[];
  limit?: number;
}

interface TaskContractListShadowComparisonsParams {
  taskId?: string;
  verdictId?: string;
  mismatchesOnly?: boolean;
  limit?: number;
}

interface TaskContractGetShadowComparisonParams {
  taskId?: string;
  comparisonId?: string;
}

interface PreviewLocalArtifactParams {
  targetPath?: string;
}

const EXPORT_FORMAT_FILTERS: Record<string, { name: string; extensions: string[] }> = {
  pdf: { name: 'PDF', extensions: ['pdf'] },
  docx: { name: 'Word Document', extensions: ['docx'] },
  html: { name: 'HTML', extensions: ['html'] },
  xlsx: { name: 'Excel Workbook', extensions: ['xlsx'] },
  ipynb: { name: 'Jupyter Notebook', extensions: ['ipynb'] },
};

export function registerMainIpcHandlers(): void {
  ipcMain.removeHandler('dialog:openFile');
  ipcMain.removeHandler('diagnostic:export');
  ipcMain.removeHandler('support:exportBundle');
  ipcMain.removeHandler('shell:revealPath');
  ipcMain.removeHandler('artifact:previewLocalFile');
  ipcMain.removeHandler('secrets:getMaskedApiKeys');
  ipcMain.removeHandler('secrets:getStatus');
  ipcMain.removeHandler('secrets:setApiKey');
  ipcMain.removeHandler('secrets:deleteApiKey');
  ipcMain.removeHandler('certification:list');
  ipcMain.removeHandler('certification:status');
  ipcMain.removeHandler('certification:submit');
  ipcMain.removeHandler('workObject:list');
  ipcMain.removeHandler('workObject:get');
  ipcMain.removeHandler('observability:update');
  ipcMain.removeHandler('samples:loadForUseCase');
  ipcMain.removeHandler('export:finish');
  ipcMain.removeHandler('taskContract:list');
  ipcMain.removeHandler('taskContract:active');
  ipcMain.removeHandler('taskContract:get');
  ipcMain.removeHandler('taskContract:update');
  ipcMain.removeHandler('taskContract:close');
  ipcMain.removeHandler('taskContract:verifyAssumption');
  ipcMain.removeHandler('taskContract:buildDeliveryPack');
  ipcMain.removeHandler('taskContract:renderArtifact');
  ipcMain.removeHandler('taskContract:previewRenderedArtifact');
  ipcMain.removeHandler('taskContract:dispatchDelivery');
  ipcMain.removeHandler('taskContract:listDeliveryLog');
  ipcMain.removeHandler('taskContract:listShadowComparisons');
  ipcMain.removeHandler('taskContract:getShadowComparison');
  ipcMain.removeAllListeners('window:minimize');
  ipcMain.removeAllListeners('window:maximize');
  ipcMain.removeAllListeners('window:close');

  ipcMain.on('window:minimize', () => {
    getMainWindow()?.minimize();
  });

  ipcMain.on('window:maximize', () => {
    const window = getMainWindow();
    if (!window) return;
    if (window.isMaximized()) {
      window.unmaximize();
      return;
    }
    window.maximize();
  });

  ipcMain.on('window:close', () => {
    getMainWindow()?.close();
  });

  ipcMain.handle('dialog:openFile', async () => {
    const options: OpenDialogOptions = {
      properties: ['openFile'],
    };
    const owner = getMainWindow();
    const result = owner
      ? await dialog.showOpenDialog(owner, options)
      : await dialog.showOpenDialog(options);

    if (result.canceled || result.filePaths.length === 0) {
      return null;
    }
    return result.filePaths[0];
  });

  ipcMain.handle(
    'diagnostic:export',
    async (_event, params: ExportDiagnosticBundleParams = {}) => {
      const defaultName = sanitizeFilename(
        params.defaultName || `ds-agent-support-bundle-${new Date().toISOString()}.json`
      );
      const supportBundle = await buildSupportBundle(params.payload ?? null);
      const content = JSON.stringify(supportBundle, null, 2);

      const owner = getMainWindow();
      const options: SaveDialogOptions = {
        title: 'Export Support Bundle',
        defaultPath: path.join(app.getPath('documents'), defaultName),
        filters: [
          { name: 'JSON', extensions: ['json'] },
          { name: 'Text', extensions: ['txt'] },
        ],
      };
      const result = owner
        ? await dialog.showSaveDialog(owner, options)
        : await dialog.showSaveDialog(options);

      if (result.canceled || !result.filePath) {
        return { canceled: true, path: null };
      }

      await fs.writeFile(result.filePath, content, 'utf-8');
      recordDiagnosticLog('info', 'ipc', 'Support bundle exported.', {
        filePath: result.filePath,
      });
      return { canceled: false, path: result.filePath };
    }
  );

  ipcMain.handle(
    'support:exportBundle',
    async (_event, params: ExportSupportBundleParams = {}) => {
      const connection = getBackendConnection();
      if (!connection) {
        return {
          canceled: false,
          path: null,
          error: 'Backend is not connected.',
        };
      }

      const defaultName = sanitizeFilename(
        params.defaultName || `ds-agent-support-${new Date().toISOString()}.zip`
      );
      const owner = getMainWindow();
      const options: SaveDialogOptions = {
        title: 'Export Support Bundle',
        defaultPath: path.join(app.getPath('documents'), defaultName),
        filters: [{ name: 'ZIP', extensions: ['zip'] }],
      };
      const result = owner
        ? await dialog.showSaveDialog(owner, options)
        : await dialog.showSaveDialog(options);

      if (result.canceled || !result.filePath) {
        return { canceled: true, path: null };
      }

      try {
        const response = await postBackendJson<{ path: string }>(
          connection.port,
          '/api/support/bundle',
          { outputPath: result.filePath }
        );
        recordDiagnosticLog('info', 'ipc', 'Support ZIP bundle exported.', {
          filePath: response.path,
        });
        return { canceled: false, path: response.path };
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Support bundle export failed.';
        recordDiagnosticLog('error', 'ipc', 'Support ZIP bundle export failed.', {
          error: message,
        });
        return { canceled: false, path: null, error: message };
      }
    }
  );

  ipcMain.handle('shell:revealPath', async (_event, rawPath: string) => {
    const targetPath = typeof rawPath === 'string' ? rawPath.trim() : '';
    if (!targetPath) {
      return { ok: false, error: 'Path is required.' };
    }

    const normalized = path.normalize(targetPath);
    try {
      await fs.access(normalized);
      shell.showItemInFolder(normalized);
      return { ok: true };
    } catch {
      const parent = path.dirname(normalized);
      try {
        await fs.access(parent);
        const error = await shell.openPath(parent);
        if (error) {
          return { ok: false, error };
        }
        return { ok: true };
      } catch {
        return { ok: false, error: `Unable to reveal path: ${normalized}` };
      }
    }
  });

  ipcMain.handle('artifact:previewLocalFile', async (_event, params: PreviewLocalArtifactParams = {}) => {
    const targetPath =
      typeof params.targetPath === 'string' ? params.targetPath.trim() : '';
    if (!targetPath) {
      return { ok: false, error: 'targetPath is required.' };
    }

    try {
      const preview = await previewLocalArtifactFile(targetPath);
      return { ok: true, preview };
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to preview local artifact.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle('secrets:getMaskedApiKeys', async () => {
    return getMaskedProviderApiKeys();
  });

  ipcMain.handle('secrets:getStatus', async () => {
    return getSecretVaultStatus();
  });

  ipcMain.handle('secrets:setApiKey', async (_event, params: SetApiKeyParams = {}) => {
    const provider = typeof params.provider === 'string' ? params.provider.trim().toLowerCase() : '';
    const key = typeof params.key === 'string' ? params.key.trim() : '';

    if (!provider || !key) {
      return { ok: false, error: 'Provider and key are required.' };
    }

    try {
      await setProviderApiKey(provider, key);
      const before = getBackendConnection();
      const restartResult = await restartPythonBackend();

      if (!restartResult.ok) {
        navigateMainWindowToDiagnostic(restartResult);
        return {
          ok: false,
          error: `Backend restart failed: ${restartResult.reason}`,
        };
      }

      if (
        !before
        || before.port !== restartResult.port
        || before.token !== restartResult.token
      ) {
        navigateMainWindowToBackend(restartResult.port, restartResult.token);
      }

      return { ok: true };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to save API key.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle('secrets:deleteApiKey', async (_event, params: DeleteApiKeyParams = {}) => {
    const provider = typeof params.provider === 'string' ? params.provider.trim().toLowerCase() : '';
    if (!provider) {
      return { ok: false, error: 'Provider is required.' };
    }

    try {
      const deleted = await deleteProviderApiKey(provider);
      const before = getBackendConnection();
      const restartResult = await restartPythonBackend();

      if (!restartResult.ok) {
        navigateMainWindowToDiagnostic(restartResult);
        return {
          ok: false,
          error: `Backend restart failed: ${restartResult.reason}`,
        };
      }

      if (
        !before
        || before.port !== restartResult.port
        || before.token !== restartResult.token
      ) {
        navigateMainWindowToBackend(restartResult.port, restartResult.token);
      }

      return { ok: true, deleted };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to delete API key.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle('observability:update', async (_event, params: UpdateObservabilityParams = {}) => {
    return updateMainObservability({
      errorReportingEnabled: params.errorReportingEnabled,
      telemetryEnabled: params.telemetryEnabled,
    });
  });

  ipcMain.handle('export:finish', async (_event, params: FinishArtifactExportParams = {}) => {
    const stagedPath = typeof params.stagedPath === 'string' ? params.stagedPath.trim() : '';
    const suggestedFilename =
      typeof params.suggestedFilename === 'string' ? params.suggestedFilename.trim() : '';
    const format = typeof params.format === 'string' ? params.format.trim().toLowerCase() : '';
    const needsPdfRender = params.needsPdfRender === true;

    if (!stagedPath || !suggestedFilename || !format) {
      return { canceled: false, path: null, error: 'Invalid export parameters.' };
    }

    try {
      await fs.access(stagedPath);
    } catch {
      return { canceled: false, path: null, error: `Staged export missing: ${stagedPath}` };
    }

    const owner = getMainWindow();
    const filter = EXPORT_FORMAT_FILTERS[format] ?? { name: format.toUpperCase(), extensions: [format] };
    const saveOptions: SaveDialogOptions = {
      title: 'Export',
      defaultPath: path.join(app.getPath('documents'), sanitizeFilename(suggestedFilename)),
      filters: [filter],
    };
    const dialogResult = owner
      ? await dialog.showSaveDialog(owner, saveOptions)
      : await dialog.showSaveDialog(saveOptions);

    if (dialogResult.canceled || !dialogResult.filePath) {
      await cleanupStagedExport(stagedPath);
      return { canceled: true, path: null };
    }

    try {
      if (needsPdfRender) {
        await renderHtmlToPdf(stagedPath, dialogResult.filePath);
      } else {
        await fs.copyFile(stagedPath, dialogResult.filePath);
      }
      recordDiagnosticLog('info', 'ipc', 'Artifact export completed.', {
        format,
        filePath: dialogResult.filePath,
      });
      return { canceled: false, path: dialogResult.filePath };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Export failed.';
      recordDiagnosticLog('error', 'ipc', 'Artifact export failed.', { error: message, format });
      return { canceled: false, path: null, error: message };
    } finally {
      await cleanupStagedExport(stagedPath);
    }
  });

  ipcMain.handle('samples:loadForUseCase', async (_event, params: LoadSampleParams = {}) => {
    const useCaseId =
      typeof params.useCaseId === 'string' && params.useCaseId.trim()
        ? params.useCaseId.trim()
        : 'general';
    try {
      const payload = await loadSampleForUseCase(useCaseId);
      return { ok: true, sample: payload };
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to load sample dataset.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle('certification:list', async () => {
    const connection = getBackendConnection();
    if (!connection) {
      return { ok: false, error: 'Backend is not connected.' };
    }

    try {
      const response = await getBackendJson<{ missions: unknown[] }>(
        connection.port,
        '/api/certification'
      );
      return { ok: true, missions: response.missions };
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to load certification missions.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle(
    'certification:status',
    async (_event, params: { missionName?: string } = {}) => {
      const connection = getBackendConnection();
      const missionName =
        typeof params.missionName === 'string' ? params.missionName.trim() : '';
      if (!connection) {
        return { ok: false, error: 'Backend is not connected.' };
      }
      if (!missionName) {
        return { ok: false, error: 'missionName is required.' };
      }

      try {
        const response = await getBackendJson<{ mission: unknown }>(
          connection.port,
          `/api/certification/${encodeURIComponent(missionName)}`
        );
        return { ok: true, mission: response.mission };
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Failed to load certification status.';
        return { ok: false, error: message };
      }
    }
  );

  ipcMain.handle(
    'certification:submit',
    async (
      _event,
      params: {
        missionName?: string;
        targetLevel?: string;
        approvedBy?: string[];
        evidenceRef?: string;
      } = {}
    ) => {
      const connection = getBackendConnection();
      const missionName =
        typeof params.missionName === 'string' ? params.missionName.trim() : '';
      const targetLevel =
        typeof params.targetLevel === 'string' ? params.targetLevel.trim() : '';
      if (!connection) {
        return { ok: false, error: 'Backend is not connected.' };
      }
      if (!missionName || !targetLevel) {
        return { ok: false, error: 'missionName and targetLevel are required.' };
      }

      try {
        const response = await postBackendJson<{ result: unknown }>(
          connection.port,
          `/api/certification/${encodeURIComponent(missionName)}/submit`,
          {
            targetLevel,
            approvedBy: Array.isArray(params.approvedBy) ? params.approvedBy : [],
            evidenceRef:
              typeof params.evidenceRef === 'string' && params.evidenceRef.trim()
                ? params.evidenceRef.trim()
                : undefined,
          }
        );
        return { ok: true, result: response.result };
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Failed to submit certification.';
        return { ok: false, error: message };
      }
    }
  );

  ipcMain.handle('workObject:list', async (_event, params: WorkObjectListParams = {}) => {
    const connection = getBackendConnection();
    if (!connection) {
      return { ok: false, error: 'Backend is not connected.' };
    }

    try {
      const query = new URLSearchParams();
      if (typeof params.sessionId === 'string' && params.sessionId.trim()) {
        query.set('sessionId', params.sessionId.trim());
      }
      if (typeof params.taskContractId === 'string' && params.taskContractId.trim()) {
        query.set('taskContractId', params.taskContractId.trim());
      }
      if (Array.isArray(params.phase)) {
        for (const item of params.phase) {
          if (typeof item === 'string' && item.trim()) {
            query.append('phase', item.trim());
          }
        }
      }
      if (typeof params.limit === 'number' && Number.isFinite(params.limit)) {
        query.set('limit', String(params.limit));
      }
      const suffix = query.toString() ? `?${query.toString()}` : '';
      const response = await getBackendJson<{ work_objects: unknown[] }>(
        connection.port,
        `/api/work-objects${suffix}`
      );
      return { ok: true, workObjects: response.work_objects };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load work objects.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle('workObject:get', async (_event, params: WorkObjectGetParams = {}) => {
    const connection = getBackendConnection();
    const workObjectId =
      typeof params.workObjectId === 'string' ? params.workObjectId.trim() : '';
    if (!connection) {
      return { ok: false, error: 'Backend is not connected.' };
    }
    if (!workObjectId) {
      return { ok: false, error: 'workObjectId is required.' };
    }

    try {
      const query = new URLSearchParams();
      if (typeof params.timelineLimit === 'number' && Number.isFinite(params.timelineLimit)) {
        query.set('timelineLimit', String(params.timelineLimit));
      }
      const suffix = query.toString() ? `?${query.toString()}` : '';
      const response = await getBackendJson<{ work_object: unknown; timeline: unknown[] }>(
        connection.port,
        `/api/work-objects/${encodeURIComponent(workObjectId)}${suffix}`
      );
      return { ok: true, detail: response };
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to load the work object.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle('workObject:intake', async (_event, params: WorkObjectIntakeParams = {}) => {
    const connection = getBackendConnection();
    if (!connection) {
      return { ok: false, error: 'Backend is not connected.' };
    }
    const title = typeof params.title === 'string' ? params.title.trim() : '';
    if (!title) {
      return { ok: false, error: 'title is required.' };
    }

    try {
      const body: Record<string, unknown> = {
        title,
        taskContractId: typeof params.taskContractId === 'string' ? params.taskContractId.trim() : '',
        requestSource: typeof params.requestSource === 'string' ? params.requestSource.trim() : 'electron',
        requestorId: typeof params.requestorId === 'string' ? params.requestorId.trim() : 'operator',
        requestorDisplay: typeof params.requestorDisplay === 'string' ? params.requestorDisplay.trim() : 'Operator',
        originalText: typeof params.originalText === 'string' ? params.originalText.trim() : title,
      };
      if (typeof params.channel === 'string' && params.channel.trim()) {
        body.channel = params.channel.trim();
      }
      if (typeof params.ownerAgent === 'string' && params.ownerAgent.trim()) {
        body.ownerAgent = params.ownerAgent.trim();
      }
      if (Array.isArray(params.tags)) {
        body.tags = params.tags;
      }
      const response = await postBackendJson<{ result: unknown }>(
        connection.port,
        '/api/work-objects/intake',
        body,
      );
      return { ok: true, result: response.result };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to create work object.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle('workObject:advance', async (_event, params: WorkObjectAdvanceParams = {}) => {
    const connection = getBackendConnection();
    if (!connection) {
      return { ok: false, error: 'Backend is not connected.' };
    }
    const workObjectId = typeof params.workObjectId === 'string' ? params.workObjectId.trim() : '';
    const toPhase = typeof params.toPhase === 'string' ? params.toPhase.trim() : '';
    if (!workObjectId) {
      return { ok: false, error: 'workObjectId is required.' };
    }
    if (!toPhase) {
      return { ok: false, error: 'toPhase is required.' };
    }

    try {
      const body: Record<string, unknown> = { toPhase };
      if (typeof params.runId === 'string' && params.runId.trim()) {
        body.runId = params.runId.trim();
      }
      const response = await postBackendJson<{ result: unknown }>(
        connection.port,
        `/api/work-objects/${encodeURIComponent(workObjectId)}/phase`,
        body,
      );
      return { ok: true, result: response.result };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to advance work object phase.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle('workObject:close', async (_event, params: WorkObjectCloseParams = {}) => {
    const connection = getBackendConnection();
    if (!connection) {
      return { ok: false, error: 'Backend is not connected.' };
    }
    const workObjectId = typeof params.workObjectId === 'string' ? params.workObjectId.trim() : '';
    const reason = typeof params.reason === 'string' ? params.reason.trim() : '';
    if (!workObjectId) {
      return { ok: false, error: 'workObjectId is required.' };
    }
    if (!reason) {
      return { ok: false, error: 'reason is required.' };
    }

    try {
      const response = await postBackendJson<{ result: unknown }>(
        connection.port,
        `/api/work-objects/${encodeURIComponent(workObjectId)}/close`,
        { reason },
      );
      return { ok: true, result: response.result };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to close work object.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle('taskContract:list', async (_event, params: TaskContractListParams = {}) => {
    const connection = getBackendConnection();
    if (!connection) {
      return { ok: false, error: 'Backend is not connected.' };
    }

    try {
      const query = new URLSearchParams();
      if (typeof params.sessionId === 'string' && params.sessionId.trim()) {
        query.set('sessionId', params.sessionId.trim());
      }
      if (Array.isArray(params.status)) {
        for (const item of params.status) {
          if (typeof item === 'string' && item.trim()) {
            query.append('status', item.trim());
          }
        }
      }
      if (typeof params.limit === 'number' && Number.isFinite(params.limit)) {
        query.set('limit', String(params.limit));
      }
      const suffix = query.toString() ? `?${query.toString()}` : '';
      const response = await getBackendJson<{ contracts: unknown[] }>(
        connection.port,
        `/api/task-contracts${suffix}`
      );
      return { ok: true, contracts: response.contracts };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to list task contracts.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle('taskContract:active', async (_event, params: TaskContractActiveParams = {}) => {
    const connection = getBackendConnection();
    const sessionId = typeof params.sessionId === 'string' ? params.sessionId.trim() : '';
    if (!connection) {
      return { ok: false, error: 'Backend is not connected.' };
    }
    if (!sessionId) {
      return { ok: false, error: 'sessionId is required.' };
    }

    try {
      const query = new URLSearchParams({ sessionId });
      if (Array.isArray(params.include)) {
        for (const item of params.include) {
          if (typeof item === 'string' && item.trim()) {
            query.append('include', item.trim());
          }
        }
      }
      const response = await getBackendJson<{ contract: unknown | null }>(
        connection.port,
        `/api/task-contracts/active?${query.toString()}`
      );
      return { ok: true, contract: response.contract };
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to load the active task contract.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle('taskContract:get', async (_event, params: TaskContractGetParams = {}) => {
    const connection = getBackendConnection();
    const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
    if (!connection) {
      return { ok: false, error: 'Backend is not connected.' };
    }
    if (!taskId) {
      return { ok: false, error: 'taskId is required.' };
    }

    try {
      const query = new URLSearchParams();
      if (Array.isArray(params.include)) {
        for (const item of params.include) {
          if (typeof item === 'string' && item.trim()) {
            query.append('include', item.trim());
          }
        }
      }
      const suffix = query.toString() ? `?${query.toString()}` : '';
      const response = await getBackendJson<{ contract: unknown }>(
        connection.port,
        `/api/task-contracts/${encodeURIComponent(taskId)}${suffix}`
      );
      return { ok: true, contract: response.contract };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load the task contract.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle('taskContract:update', async (_event, params: TaskContractUpdateParams = {}) => {
    const connection = getBackendConnection();
    const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
    if (!connection) {
      return { ok: false, error: 'Backend is not connected.' };
    }
    if (!taskId || typeof params.expectedVersion !== 'number') {
      return { ok: false, error: 'taskId and expectedVersion are required.' };
    }

    try {
      const response = await postBackendJson<{ result: unknown }>(
        connection.port,
        `/api/task-contracts/${encodeURIComponent(taskId)}/update`,
        {
          expectedVersion: params.expectedVersion,
          patch: params.patch ?? {},
          transitionTo: params.transitionTo,
          reason: params.reason,
        }
      );
      return { ok: true, result: response.result };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to update the task contract.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle('taskContract:close', async (_event, params: TaskContractCloseParams = {}) => {
    const connection = getBackendConnection();
    const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
    const closingNote =
      typeof params.closingNote === 'string' ? params.closingNote.trim() : '';
    if (!connection) {
      return { ok: false, error: 'Backend is not connected.' };
    }
    if (!taskId || typeof params.expectedVersion !== 'number' || !closingNote) {
      return { ok: false, error: 'taskId, expectedVersion, and closingNote are required.' };
    }

    try {
      const response = await postBackendJson<{ result: unknown }>(
        connection.port,
        `/api/task-contracts/${encodeURIComponent(taskId)}/close`,
        {
          expectedVersion: params.expectedVersion,
          closingNote,
        }
      );
      return { ok: true, result: response.result };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to close the task contract.';
      return { ok: false, error: message };
    }
  });

  ipcMain.handle(
    'taskContract:verifyAssumption',
    async (_event, params: TaskContractVerifyAssumptionParams = {}) => {
      const connection = getBackendConnection();
      const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
      const entryId = typeof params.entryId === 'string' ? params.entryId.trim() : '';
      if (!connection) {
        return { ok: false, error: 'Backend is not connected.' };
      }
      if (!taskId || !entryId || typeof params.expectedVersion !== 'number') {
        return { ok: false, error: 'taskId, entryId, and expectedVersion are required.' };
      }

      try {
        const response = await postBackendJson<{ result: unknown }>(
          connection.port,
          `/api/task-contracts/${encodeURIComponent(taskId)}/assumptions/${encodeURIComponent(entryId)}/verify`,
          {
            expectedVersion: params.expectedVersion,
            verificationNote: params.verificationNote,
          }
        );
        return { ok: true, result: response.result };
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Failed to verify the assumption.';
        return { ok: false, error: message };
      }
    }
  );

  ipcMain.handle(
    'taskContract:buildDeliveryPack',
    async (_event, params: TaskContractBuildDeliveryPackParams = {}) => {
      const connection = getBackendConnection();
      const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
      if (!connection) {
        return { ok: false, error: 'Backend is not connected.' };
      }
      if (!taskId) {
        return { ok: false, error: 'taskId is required.' };
      }

      try {
        const response = await postBackendJson<{ result: unknown }>(
          connection.port,
          `/api/task-contracts/${encodeURIComponent(taskId)}/delivery-pack/build`,
          {
            audiences: Array.isArray(params.audiences) ? params.audiences : [],
            followUpActions: Array.isArray(params.followUpActions) ? params.followUpActions : [],
            sourceAnalysisId:
              typeof params.sourceAnalysisId === 'string' && params.sourceAnalysisId.trim()
                ? params.sourceAnalysisId.trim()
                : undefined,
            confidence: typeof params.confidence === 'number' ? params.confidence : undefined,
            signedBy:
              typeof params.signedBy === 'string' && params.signedBy.trim()
                ? params.signedBy.trim()
                : undefined,
              signature:
                typeof params.signature === 'string' && params.signature.trim()
                  ? params.signature.trim()
                  : undefined,
              globalContext: params.globalContext ?? {},
              tenant:
                typeof params.tenant === 'string' && params.tenant.trim()
                  ? params.tenant.trim()
                  : undefined,
            }
          );
        return { ok: true, result: response.result };
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Failed to build the delivery pack.';
        return { ok: false, error: message };
      }
    }
  );

  ipcMain.handle(
    'taskContract:renderArtifact',
    async (_event, params: TaskContractRenderArtifactParams = {}) => {
      const connection = getBackendConnection();
      const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
      const artifactId = typeof params.artifactId === 'string' ? params.artifactId.trim() : '';
      if (!connection) {
        return { ok: false, error: 'Backend is not connected.' };
      }
      if (!taskId || !artifactId || params.analysis === undefined) {
        return { ok: false, error: 'taskId, artifactId, and analysis are required.' };
      }

      const outputDir =
        typeof params.outputDir === 'string' && params.outputDir.trim()
          ? params.outputDir.trim()
          : defaultDeliveryOutputDir(taskId);

      try {
        const response = await postBackendJson<{ result: unknown }>(
          connection.port,
          `/api/task-contracts/${encodeURIComponent(taskId)}/delivery-artifacts/${encodeURIComponent(
            artifactId
          )}/render`,
          {
            analysis: params.analysis,
            outputDir,
            audienceProfile:
              typeof params.audienceProfile === 'string' && params.audienceProfile.trim()
                ? params.audienceProfile.trim()
                : undefined,
            providerBacked: params.providerBacked === true,
            model:
              typeof params.model === 'string' && params.model.trim()
                ? params.model.trim()
                : undefined,
          }
        );
        return { ok: true, result: response.result };
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Failed to render the delivery artifact.';
        return { ok: false, error: message };
      }
    }
  );

  ipcMain.handle(
    'taskContract:previewRenderedArtifact',
    async (_event, params: TaskContractPreviewRenderedArtifactParams = {}) => {
      const renderedUri =
        typeof params.renderedUri === 'string' ? params.renderedUri.trim() : '';
      const format = typeof params.format === 'string' ? params.format.trim() : '';
      if (!renderedUri || !format) {
        return { ok: false, error: 'renderedUri and format are required.' };
      }

      try {
        const preview = await loadRenderedArtifactPreview({
          renderedUri,
          format,
        });
        return { ok: true, preview };
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Failed to load rendered artifact preview.';
        return { ok: false, error: message };
      }
    }
  );

  ipcMain.handle(
    'taskContract:dispatchDelivery',
    async (_event, params: TaskContractDispatchDeliveryParams = {}) => {
      const connection = getBackendConnection();
      const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
      if (!connection) {
        return { ok: false, error: 'Backend is not connected.' };
      }
      if (!taskId) {
        return { ok: false, error: 'taskId is required.' };
      }

      try {
        const response = await postBackendJson<{ result: unknown }>(
          connection.port,
          `/api/task-contracts/${encodeURIComponent(taskId)}/delivery/dispatch`,
          {
            artifactIds: Array.isArray(params.artifactIds) ? params.artifactIds : [],
            channels: Array.isArray(params.channels) ? params.channels : [],
            dryRun: params.dryRun === true,
            approveManualReview: params.approveManualReview === true,
          }
        );
        return { ok: true, result: response.result };
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Failed to dispatch the delivery pack.';
        return { ok: false, error: message };
      }
    }
  );

  ipcMain.handle(
    'taskContract:listDeliveryLog',
    async (_event, params: TaskContractListDeliveryLogParams = {}) => {
      const connection = getBackendConnection();
      const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
      if (!connection) {
        return { ok: false, error: 'Backend is not connected.' };
      }
      if (!taskId) {
        return { ok: false, error: 'taskId is required.' };
      }

      try {
        const query = new URLSearchParams();
        if (typeof params.packId === 'string' && params.packId.trim()) {
          query.set('packId', params.packId.trim());
        }
        if (Array.isArray(params.artifactIds)) {
          for (const item of params.artifactIds) {
            if (typeof item === 'string' && item.trim()) {
              query.append('artifactId', item.trim());
            }
          }
        }
        if (Array.isArray(params.channels)) {
          for (const item of params.channels) {
            if (typeof item === 'string' && item.trim()) {
              query.append('channel', item.trim());
            }
          }
        }
        if (typeof params.limit === 'number' && Number.isFinite(params.limit)) {
          query.set('limit', String(params.limit));
        }
        const suffix = query.toString() ? `?${query.toString()}` : '';
        const response = await getBackendJson<{ result: unknown }>(
          connection.port,
          `/api/task-contracts/${encodeURIComponent(taskId)}/delivery/log${suffix}`
        );
        return { ok: true, result: response.result };
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Failed to load delivery log records.';
        return { ok: false, error: message };
      }
    }
  );

  ipcMain.handle(
    'taskContract:listShadowComparisons',
    async (_event, params: TaskContractListShadowComparisonsParams = {}) => {
      const connection = getBackendConnection();
      const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
      if (!connection) {
        return { ok: false, error: 'Backend is not connected.' };
      }
      if (!taskId) {
        return { ok: false, error: 'taskId is required.' };
      }

      try {
        const query = new URLSearchParams();
        if (typeof params.verdictId === 'string' && params.verdictId.trim()) {
          query.set('verdictId', params.verdictId.trim());
        }
        if (params.mismatchesOnly === true) {
          query.set('mismatchesOnly', 'true');
        }
        if (typeof params.limit === 'number' && Number.isFinite(params.limit)) {
          query.set('limit', String(params.limit));
        }
        const suffix = query.toString() ? `?${query.toString()}` : '';
        const response = await getBackendJson<{ comparisons: unknown[] }>(
          connection.port,
          `/api/task-contracts/${encodeURIComponent(taskId)}/shadow-comparisons${suffix}`
        );
        return { ok: true, comparisons: response.comparisons };
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Failed to load shadow comparison records.';
        return { ok: false, error: message };
      }
    }
  );

  ipcMain.handle(
    'taskContract:getShadowComparison',
    async (_event, params: TaskContractGetShadowComparisonParams = {}) => {
      const connection = getBackendConnection();
      const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
      const comparisonId =
        typeof params.comparisonId === 'string' ? params.comparisonId.trim() : '';
      if (!connection) {
        return { ok: false, error: 'Backend is not connected.' };
      }
      if (!taskId || !comparisonId) {
        return { ok: false, error: 'taskId and comparisonId are required.' };
      }

      try {
        const response = await getBackendJson<{ comparison: unknown }>(
          connection.port,
          `/api/task-contracts/${encodeURIComponent(taskId)}/shadow-comparisons/${encodeURIComponent(
            comparisonId
          )}`
        );
        return { ok: true, comparison: response.comparison };
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Failed to load the shadow comparison.';
        return { ok: false, error: message };
      }
    }
  );
}

function sanitizeFilename(name: string): string {
  return name.replace(/[<>:"/\\|?*\x00-\x1f]/g, '-');
}

async function previewLocalArtifactFile(targetPath: string): Promise<Record<string, unknown>> {
  const normalized = path.normalize(targetPath);

  try {
    const stat = await fs.stat(normalized);
    if (!stat.isFile()) {
      return {
        kind: 'binary',
        path: normalized,
        name: path.basename(normalized),
        size: 0,
        modifiedAt: stat.mtime.toISOString(),
        message: 'Inline preview is only available for files.',
      };
    }

    const base = {
      path: normalized,
      name: path.basename(normalized),
      size: stat.size,
      modifiedAt: stat.mtime.toISOString(),
    };
    const ext = path.extname(normalized).toLowerCase();

    if (ext === '.md' || ext === '.markdown' || ext === '.txt') {
      const raw = await fs.readFile(normalized, 'utf-8');
      const { value, truncated } = truncatePreviewText(raw, 12_000);
      return {
        ...base,
        kind: 'markdown',
        content: value,
        truncated,
        headings: extractMarkdownHeadings(value),
      };
    }

    if (ext === '.ipynb') {
      const raw = await fs.readFile(normalized, 'utf-8');
      const parsed = JSON.parse(raw) as {
        cells?: Array<{
          cell_type?: string;
          source?: string[] | string;
          execution_count?: number | null;
        }>;
      };
      const cells = Array.isArray(parsed.cells) ? parsed.cells : [];
      let markdownCells = 0;
      let codeCells = 0;

      const cellPreviews = cells.slice(0, 6).map((cell) => {
        const kind = cell.cell_type === 'code' ? 'code' : 'markdown';
        if (kind === 'code') {
          codeCells += 1;
        } else {
          markdownCells += 1;
        }
        const source = Array.isArray(cell.source) ? cell.source.join('') : cell.source ?? '';
        const { value } = truncatePreviewText(source, 600);
        return {
          kind,
          excerpt: value.trim() || '(empty cell)',
          executionCount: cell.execution_count ?? null,
        };
      });

      for (const cell of cells.slice(6)) {
        if (cell.cell_type === 'code') {
          codeCells += 1;
        } else {
          markdownCells += 1;
        }
      }

      return {
        ...base,
        kind: 'notebook',
        totalCells: cells.length,
        markdownCells,
        codeCells,
        truncated: cells.length > 6,
        cellPreviews,
      };
    }

    if (ext === '.pdf') {
      return {
        ...base,
        kind: 'pdf',
        message: 'Inline PDF preview is not wired into the delivery workspace yet.',
      };
    }

    if (ext === '.pptx') {
      return {
        ...base,
        kind: 'pptx',
        message: 'Inline slide thumbnails are not available yet. Reveal the file to inspect it in PowerPoint.',
      };
    }

    return {
      ...base,
      kind: 'binary',
      message: `Inline preview is not available for ${ext || 'this file type'}.`,
    };
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return {
        kind: 'missing',
        path: normalized,
        message: `Rendered artifact is missing: ${normalized}`,
      };
    }
    throw error;
  }
}

function defaultDeliveryOutputDir(taskId: string): string {
  return path.join(
    app.getPath('documents'),
    'DS Agent',
    'Stakeholder Artifacts',
    sanitizeFilename(taskId),
  );
}

function truncatePreviewText(value: string, maxChars: number): { value: string; truncated: boolean } {
  if (value.length <= maxChars) {
    return { value, truncated: false };
  }
  return {
    value: `${value.slice(0, maxChars)}\n\n...`,
    truncated: true,
  };
}

function extractMarkdownHeadings(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.startsWith('#'))
    .map((line) => line.replace(/^#+\s*/, ''))
    .filter(Boolean)
    .slice(0, 8);
}

async function cleanupStagedExport(stagedPath: string): Promise<void> {
  try {
    await fs.rm(path.dirname(stagedPath), { recursive: true, force: true });
  } catch {
    // Staged files live under .ds-agent/exports/<uuid>/; cleanup is best-effort.
  }
}

async function renderHtmlToPdf(htmlPath: string, outputPath: string): Promise<void> {
  const pdfWindow = new BrowserWindow({
    show: false,
    webPreferences: {
      offscreen: true,
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  try {
    await pdfWindow.loadURL(pathToFileURL(htmlPath).toString());
    // Give webfonts a tick to settle before printing.
    await new Promise((resolve) => setTimeout(resolve, 200));
    const pdfBuffer = await pdfWindow.webContents.printToPDF({
      printBackground: true,
      pageSize: 'A4',
      margins: { top: 0.8, bottom: 0.8, left: 1, right: 1 },
    });
    await fs.writeFile(outputPath, pdfBuffer);
  } finally {
    pdfWindow.destroy();
  }
}

function getBackendJson<T>(port: number, requestPath: string): Promise<T> {
  return requestBackendJson<T>(port, requestPath, 'GET');
}

function postBackendJson<T>(
  port: number,
  requestPath: string,
  payload: Record<string, unknown>
): Promise<T> {
  return requestBackendJson<T>(port, requestPath, 'POST', payload);
}

function requestBackendJson<T>(
  port: number,
  requestPath: string,
  method: 'GET' | 'POST',
  payload?: Record<string, unknown>
): Promise<T> {
  return new Promise((resolve, reject) => {
    const body = payload ? JSON.stringify(payload) : '';
    const request = http.request(
      {
        host: '127.0.0.1',
        port,
        path: requestPath,
        method,
        headers: {
          ...(payload
            ? {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(body),
              }
            : {}),
        },
      },
      (response) => {
        const chunks: Buffer[] = [];
        response.on('data', (chunk: Buffer) => chunks.push(chunk));
        response.on('end', () => {
          const raw = Buffer.concat(chunks).toString('utf-8');
          const statusCode = response.statusCode ?? 500;
          let parsed: unknown = null;
          try {
            parsed = raw ? JSON.parse(raw) : null;
          } catch {
            parsed = null;
          }
          if (statusCode >= 400) {
            const detail = (
              parsed
              && typeof parsed === 'object'
              && 'detail' in parsed
              && typeof parsed.detail === 'string'
            )
              ? parsed.detail
              : raw || `Backend request failed (${statusCode})`;
            reject(new Error(detail));
            return;
          }
          if (parsed === null) {
            reject(new Error('Backend returned an empty response.'));
            return;
          }
          resolve(parsed as T);
        });
      }
    );
    request.on('error', reject);
    if (payload) {
      request.write(body);
    }
    request.end();
  });
}
