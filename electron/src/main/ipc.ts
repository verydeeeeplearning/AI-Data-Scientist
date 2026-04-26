/**
 * Electron IPC registration for renderer-only desktop capabilities.
 */

import fs from 'fs/promises';
import http from 'http';
import path from 'path';
import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron';
import type { OpenDialogOptions, SaveDialogOptions } from 'electron';
import { pathToFileURL } from 'url';
import { buildSupportBundle, recordDiagnosticLog, resolveWorkspaceDir } from './diagnostics-collector';
import { updateMainObservability } from './observability';
import { getBackendConnection, restartPythonBackend } from './python-backend';
import { loadSampleForUseCase } from './sample-data';
import {
  clearConfigSecret,
  deleteProviderApiKey,
  getMaskedProviderApiKeys,
  getSecretVaultStatus,
  setConfigSecret,
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

interface SetConfigSecretParams {
  path?: string;
  value?: string;
}

interface ClearConfigSecretParams {
  path?: string;
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

interface TaskContractGoalBriefParams {
  business_question?: string;
  ds_problem_statement?: string;
  comparison_baseline?: string;
  decision_to_make?: string;
  hypothesis?: string | null;
  expected_effort?: string;
}

interface TaskContractDeliverableParams {
  type?: string;
  audience?: string;
  format?: string;
  count?: number | null;
}

interface TaskContractCreateParams {
  session_id?: string;
  contract_type?: string;
  business_goal?: string;
  goal_brief?: TaskContractGoalBriefParams;
  required_deliverables?: TaskContractDeliverableParams[];
  allowed_data_sources?: Record<string, unknown>[];
  forbidden_data_patterns?: string[];
  budget?: Record<string, unknown>;
  autonomy?: Record<string, unknown>;
  decision_owner?: string | null;
  decision_deadline?: string | null;
  definition_of_done?: Record<string, unknown> | null;
  authority?: string | null;
  audience?: string | null;
  mission?: string | null;
  created_by?: string;
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

interface WebPushRegisterParams {
  endpoint?: string;
  p256dhKey?: string;
  authKey?: string;
}

interface WebPushUnregisterParams {
  endpoint?: string;
}

interface WebPushSubjectPayload {
  subject?: string;
}

interface BackendErrorDetail {
  message?: string;
  error_code?: string | null;
  metadata?: Record<string, unknown>;
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
  ipcMain.removeHandler('secrets:setConfigSecret');
  ipcMain.removeHandler('secrets:clearConfigSecret');
  ipcMain.removeHandler('certification:list');
  ipcMain.removeHandler('certification:submit');
  ipcMain.removeHandler('workObject:list');
  ipcMain.removeHandler('workObject:get');
  ipcMain.removeHandler('observability:update');
  ipcMain.removeHandler('samples:loadForUseCase');
  ipcMain.removeHandler('export:finish');
  ipcMain.removeHandler('taskContract:list');
  ipcMain.removeHandler('taskContract:active');
  ipcMain.removeHandler('taskContract:get');
  ipcMain.removeHandler('taskContract:create');
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
  ipcMain.removeHandler('webPush:getPublicKey');
  ipcMain.removeHandler('webPush:getSubject');
  ipcMain.removeHandler('webPush:setSubject');
  ipcMain.removeHandler('webPush:registerSubscription');
  ipcMain.removeHandler('webPush:unregisterSubscription');
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
        return buildDialogIpcErrorResult('Backend is not connected.', 'backend_offline');
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
        return buildDialogIpcErrorResult(
          'Support bundle export failed.',
          'support_bundle_export_failed',
        );
      }
    }
  );

  ipcMain.handle('shell:revealPath', async (_event, rawPath: string) => {
    const targetPath = typeof rawPath === 'string' ? rawPath.trim() : '';
    if (!targetPath) {
      return buildIpcErrorResult('Path is required.', 'path_required');
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
          return buildIpcErrorResult(
            'Unable to reveal the requested path.',
            'reveal_path_failed',
          );
        }
        return { ok: true };
      } catch {
        return buildIpcErrorResult(
          'Unable to reveal the requested path.',
          'reveal_path_failed',
        );
      }
    }
  });

  ipcMain.handle('artifact:previewLocalFile', async (_event, params: PreviewLocalArtifactParams = {}) => {
    const targetPath =
      typeof params.targetPath === 'string' ? params.targetPath.trim() : '';
    if (!targetPath) {
      return buildIpcErrorResult('targetPath is required.', 'target_path_required');
    }

    try {
      const preview = await previewLocalArtifactFile(targetPath);
      return { ok: true, preview };
    } catch (error) {
      return buildIpcErrorResult(
        'Failed to preview local artifact.',
        'artifact_preview_failed',
      );
    }
  });

  ipcMain.handle('secrets:getMaskedApiKeys', async () => {
    return getMaskedProviderApiKeys();
  });

  ipcMain.handle('secrets:getStatus', async () => {
    return getSecretVaultStatus();
  });

  ipcMain.handle(
    'secrets:setConfigSecret',
    async (_event, params: SetConfigSecretParams = {}) => {
      const secretPath = typeof params.path === 'string' ? params.path.trim() : '';
      const value = typeof params.value === 'string' ? params.value.trim() : '';

      if (!secretPath || !value) {
        return buildIpcErrorResult(
          'Config secret path and value are required.',
          'config_secret_path_and_value_required',
        );
      }

      try {
        await setConfigSecret(secretPath, value);
        return { ok: true };
      } catch (error) {
        return buildIpcErrorResult(
          'Failed to save config secret.',
          'config_secret_save_failed',
        );
      }
    }
  );

  ipcMain.handle(
    'secrets:clearConfigSecret',
    async (_event, params: ClearConfigSecretParams = {}) => {
      const secretPath = typeof params.path === 'string' ? params.path.trim() : '';
      if (!secretPath) {
        return buildIpcErrorResult(
          'Config secret path is required.',
          'config_secret_path_required',
        );
      }

      try {
        const deleted = await clearConfigSecret(secretPath);
        return { ok: true, deleted };
      } catch (error) {
        return buildIpcErrorResult(
          'Failed to clear config secret.',
          'config_secret_clear_failed',
        );
      }
    }
  );

  ipcMain.handle('secrets:setApiKey', async (_event, params: SetApiKeyParams = {}) => {
    const provider = typeof params.provider === 'string' ? params.provider.trim().toLowerCase() : '';
    const key = typeof params.key === 'string' ? params.key.trim() : '';

    if (!provider || !key) {
      return buildIpcErrorResult(
        'Provider and key are required.',
        'provider_and_key_required',
      );
    }

    try {
      await setProviderApiKey(provider, key);
      const before = getBackendConnection();
      const restartResult = await restartPythonBackend();

      if (!restartResult.ok) {
        navigateMainWindowToDiagnostic(restartResult);
        return buildIpcErrorResult(
          'Failed to restart the local backend after saving the API key.',
          'backend_restart_failed',
        );
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
      return buildIpcErrorResult('Failed to save API key.', 'api_key_save_failed');
    }
  });

  ipcMain.handle('secrets:deleteApiKey', async (_event, params: DeleteApiKeyParams = {}) => {
    const provider = typeof params.provider === 'string' ? params.provider.trim().toLowerCase() : '';
    if (!provider) {
      return buildIpcErrorResult('Provider is required.', 'provider_required');
    }

    try {
      const deleted = await deleteProviderApiKey(provider);
      const before = getBackendConnection();
      const restartResult = await restartPythonBackend();

      if (!restartResult.ok) {
        navigateMainWindowToDiagnostic(restartResult);
        return buildIpcErrorResult(
          'Failed to restart the local backend after deleting the API key.',
          'backend_restart_failed',
        );
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
      return buildIpcErrorResult('Failed to delete API key.', 'api_key_delete_failed');
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
      return buildDialogIpcErrorResult(
        'Invalid export parameters.',
        'artifact_export_invalid_params',
      );
    }

    // Containment check: reject any stagedPath that does not resolve to within
    // the known backend staging root (<workspace>/.ds-agent/exports/).  This
    // prevents a compromised renderer from crafting an arbitrary path and using
    // the IPC to read sensitive files (path traversal / absolute-path attack).
    if (!isStagedPathConfined(stagedPath)) {
      recordDiagnosticLog('error', 'ipc', 'export:finish rejected: staged path outside staging root.', {
        stagedPath,
      });
      return buildDialogIpcErrorResult(
        'area.files.export.error.untrustedPath',
        'artifact_export_untrusted_path',
      );
    }

    try {
      await fs.access(stagedPath);
    } catch {
      return buildDialogIpcErrorResult(
        'Prepared export file is missing.',
        'artifact_export_staged_missing',
      );
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
      return buildDialogIpcErrorResult('Export failed.', 'artifact_export_failed');
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
      return buildIpcErrorResult('Failed to load sample dataset.', 'sample_load_failed');
    }
  });

  ipcMain.handle('certification:list', async () => {
    const connection = getBackendConnection();
    if (!connection) {
      return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
    }

    try {
      const response = await getBackendJson<{ missions: unknown[] }>(
        connection.port,
        '/api/certification'
      );
      return { ok: true, missions: response.missions };
    } catch (error) {
      return buildIpcErrorResult(
        'Failed to load certification missions.',
        'certification_list_failed',
      );
    }
  });

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
        return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
      }
      if (!missionName || !targetLevel) {
        return buildIpcErrorResult(
          'missionName and targetLevel are required.',
          'certification_submit_params_required',
        );
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
        return buildIpcErrorResult(
          'Failed to submit certification.',
          'certification_submit_failed',
        );
      }
    }
  );

  ipcMain.handle('workObject:list', async (_event, params: WorkObjectListParams = {}) => {
    const connection = getBackendConnection();
    if (!connection) {
      return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
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
      return buildIpcErrorResult('Failed to load work objects.', 'work_object_list_failed');
    }
  });

  ipcMain.handle('workObject:get', async (_event, params: WorkObjectGetParams = {}) => {
    const connection = getBackendConnection();
    const workObjectId =
      typeof params.workObjectId === 'string' ? params.workObjectId.trim() : '';
    if (!connection) {
      return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
    }
    if (!workObjectId) {
      return buildIpcErrorResult('workObjectId is required.', 'work_object_id_required');
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
      return buildIpcErrorResult('Failed to load the work object.', 'work_object_get_failed');
    }
  });

  ipcMain.handle('workObject:intake', async (_event, params: WorkObjectIntakeParams = {}) => {
    const connection = getBackendConnection();
    if (!connection) {
      return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
    }
    const title = typeof params.title === 'string' ? params.title.trim() : '';
    if (!title) {
      return buildIpcErrorResult('title is required.', 'title_required');
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
      return buildIpcErrorResult('Failed to create work object.', 'work_object_intake_failed');
    }
  });

  ipcMain.handle('workObject:advance', async (_event, params: WorkObjectAdvanceParams = {}) => {
    const connection = getBackendConnection();
    if (!connection) {
      return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
    }
    const workObjectId = typeof params.workObjectId === 'string' ? params.workObjectId.trim() : '';
    const toPhase = typeof params.toPhase === 'string' ? params.toPhase.trim() : '';
    if (!workObjectId) {
      return buildIpcErrorResult('workObjectId is required.', 'work_object_id_required');
    }
    if (!toPhase) {
      return buildIpcErrorResult('toPhase is required.', 'to_phase_required');
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
      return buildIpcErrorResult(
        'Failed to advance work object phase.',
        'work_object_advance_failed',
      );
    }
  });

  ipcMain.handle('workObject:close', async (_event, params: WorkObjectCloseParams = {}) => {
    const connection = getBackendConnection();
    if (!connection) {
      return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
    }
    const workObjectId = typeof params.workObjectId === 'string' ? params.workObjectId.trim() : '';
    const reason = typeof params.reason === 'string' ? params.reason.trim() : '';
    if (!workObjectId) {
      return buildIpcErrorResult('workObjectId is required.', 'work_object_id_required');
    }
    if (!reason) {
      return buildIpcErrorResult('reason is required.', 'reason_required');
    }

    try {
      const response = await postBackendJson<{ result: unknown }>(
        connection.port,
        `/api/work-objects/${encodeURIComponent(workObjectId)}/close`,
        { reason },
      );
      return { ok: true, result: response.result };
    } catch (error) {
      return buildIpcErrorResult('Failed to close work object.', 'work_object_close_failed');
    }
  });

  ipcMain.handle('taskContract:list', async (_event, params: TaskContractListParams = {}) => {
    const connection = getBackendConnection();
    if (!connection) {
      return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
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
      return buildTaskContractIpcError(error, 'Failed to list task contracts.', 'task_contract_list_failed');
    }
  });

  ipcMain.handle('taskContract:active', async (_event, params: TaskContractActiveParams = {}) => {
    const connection = getBackendConnection();
    const sessionId = typeof params.sessionId === 'string' ? params.sessionId.trim() : '';
    if (!connection) {
      return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
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
      return buildTaskContractIpcError(
        error,
        'Failed to load the active task contract.',
        'task_contract_active_failed',
      );
    }
  });

  ipcMain.handle('taskContract:get', async (_event, params: TaskContractGetParams = {}) => {
    const connection = getBackendConnection();
    const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
    if (!connection) {
      return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
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
      return buildTaskContractIpcError(error, 'Failed to load the task contract.', 'task_contract_get_failed');
    }
  });

  ipcMain.handle('taskContract:create', async (_event, params: TaskContractCreateParams = {}) => {
    const connection = getBackendConnection();
    const sessionId = typeof params.session_id === 'string' ? params.session_id.trim() : '';
    const contractType =
      typeof params.contract_type === 'string' ? params.contract_type.trim() : '';
    const businessGoal =
      typeof params.business_goal === 'string' ? params.business_goal.trim() : '';
    const goalBrief =
      params.goal_brief && typeof params.goal_brief === 'object' ? params.goal_brief : null;
    const requiredDeliverables = Array.isArray(params.required_deliverables)
      ? params.required_deliverables
      : [];

    if (!connection) {
      return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
    }
    if (!sessionId || !contractType || !businessGoal || !goalBrief || requiredDeliverables.length === 0) {
      return {
        ok: false,
        error: 'session_id, contract_type, business_goal, goal_brief, and required_deliverables are required.',
      };
    }

    try {
      const response = await postBackendJson<{ result: unknown }>(
        connection.port,
        '/api/task-contracts',
        {
          session_id: sessionId,
          contract_type: contractType,
          business_goal: businessGoal,
          goal_brief: goalBrief,
          required_deliverables: requiredDeliverables,
          allowed_data_sources: Array.isArray(params.allowed_data_sources)
            ? params.allowed_data_sources
            : [],
          forbidden_data_patterns: Array.isArray(params.forbidden_data_patterns)
            ? params.forbidden_data_patterns
            : [],
          budget:
            params.budget && typeof params.budget === 'object'
              ? params.budget
              : {},
          autonomy:
            params.autonomy && typeof params.autonomy === 'object'
              ? params.autonomy
              : {},
          decision_owner:
            typeof params.decision_owner === 'string' ? params.decision_owner.trim() : params.decision_owner,
          decision_deadline:
            typeof params.decision_deadline === 'string' ? params.decision_deadline.trim() : params.decision_deadline,
          definition_of_done:
            params.definition_of_done && typeof params.definition_of_done === 'object'
              ? params.definition_of_done
              : params.definition_of_done ?? undefined,
          authority:
            typeof params.authority === 'string' ? params.authority.trim() : params.authority,
          audience:
            typeof params.audience === 'string' ? params.audience.trim() : params.audience,
          mission:
            typeof params.mission === 'string' ? params.mission.trim() : params.mission,
          created_by:
            typeof params.created_by === 'string' ? params.created_by.trim() : params.created_by,
        }
      );
      return { ok: true, result: response.result };
    } catch (error) {
      return buildTaskContractIpcError(
        error,
        'Failed to create the task contract.',
        'task_contract_create_failed',
      );
    }
  });

  ipcMain.handle('taskContract:update', async (_event, params: TaskContractUpdateParams = {}) => {
    const connection = getBackendConnection();
    const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
    if (!connection) {
      return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
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
      return buildTaskContractIpcError(
        error,
        'Failed to update the task contract.',
        'task_contract_update_failed',
      );
    }
  });

  ipcMain.handle('taskContract:close', async (_event, params: TaskContractCloseParams = {}) => {
    const connection = getBackendConnection();
    const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
    const closingNote =
      typeof params.closingNote === 'string' ? params.closingNote.trim() : '';
    if (!connection) {
      return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
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
      return buildTaskContractIpcError(
        error,
        'Failed to close the task contract.',
        'task_contract_close_failed',
      );
    }
  });

  ipcMain.handle(
    'taskContract:verifyAssumption',
    async (_event, params: TaskContractVerifyAssumptionParams = {}) => {
      const connection = getBackendConnection();
      const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
      const entryId = typeof params.entryId === 'string' ? params.entryId.trim() : '';
      if (!connection) {
        return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
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
        return buildTaskContractIpcError(
          error,
          'Failed to verify the assumption.',
          'task_contract_verify_failed',
        );
      }
    }
  );

  ipcMain.handle(
    'taskContract:buildDeliveryPack',
    async (_event, params: TaskContractBuildDeliveryPackParams = {}) => {
      const connection = getBackendConnection();
      const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
      if (!connection) {
        return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
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
        return buildTaskContractIpcError(
          error,
          'Failed to build the delivery pack.',
          'task_contract_build_delivery_failed',
        );
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
        return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
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
        return buildTaskContractIpcError(
          error,
          'Failed to render the delivery artifact.',
          'task_contract_render_failed',
        );
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
        return buildIpcErrorResult(
          'renderedUri and format are required.',
          'rendered_artifact_preview_params_required',
        );
      }

      try {
        const preview = await loadRenderedArtifactPreview({
          renderedUri,
          format,
        });
        return { ok: true, preview };
      } catch (error) {
        return buildIpcErrorResult(
          'Failed to load rendered artifact preview.',
          'task_contract_preview_failed',
        );
      }
    }
  );

  ipcMain.handle(
    'taskContract:dispatchDelivery',
    async (_event, params: TaskContractDispatchDeliveryParams = {}) => {
      const connection = getBackendConnection();
      const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
      if (!connection) {
        return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
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
        return buildTaskContractIpcError(
          error,
          'Failed to dispatch the delivery pack.',
          'task_contract_dispatch_failed',
        );
      }
    }
  );

  ipcMain.handle(
    'taskContract:listDeliveryLog',
    async (_event, params: TaskContractListDeliveryLogParams = {}) => {
      const connection = getBackendConnection();
      const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
      if (!connection) {
        return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
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
        return buildTaskContractIpcError(
          error,
          'Failed to load delivery log records.',
          'task_contract_delivery_log_failed',
        );
      }
    }
  );

  ipcMain.handle(
    'taskContract:listShadowComparisons',
    async (_event, params: TaskContractListShadowComparisonsParams = {}) => {
      const connection = getBackendConnection();
      const taskId = typeof params.taskId === 'string' ? params.taskId.trim() : '';
      if (!connection) {
        return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
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
        return buildTaskContractIpcError(
          error,
          'Failed to load shadow comparison records.',
          'task_contract_shadow_list_failed',
        );
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
        return buildIpcErrorResult('Backend is not connected.', 'backend_offline');
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
        return buildTaskContractIpcError(
          error,
          'Failed to load the shadow comparison.',
          'task_contract_shadow_get_failed',
        );
      }
    }
  );

  // ------------------------------------------------------------------
  // Mobile web push (Wave 4 PLAN_06b)
  //
  // Backend RPCs are mounted under /api/web-push/* by the gateway. The
  // public key endpoint is unauthenticated by design (it's literally a
  // public key) so the renderer can request it before a user gesture.
  // ------------------------------------------------------------------

  ipcMain.handle('webPush:getPublicKey', async () => {
    const connection = getBackendConnection();
    if (!connection) {
      return { ok: false, reason: 'backend_offline' };
    }
    try {
      const response = await getBackendJson<{ publicKey: string | null; reason?: string }>(
        connection.port,
        '/api/web-push/public-key',
      );
      if (!response.publicKey) {
        return { ok: false, reason: response.reason ?? 'vapid_keys_missing' };
      }
      return { ok: true, publicKey: response.publicKey };
    } catch (error) {
      return { ok: false, reason: 'public_key_fetch_failed' };
    }
  });

  ipcMain.handle('webPush:getSubject', async () => {
    const connection = getBackendConnection();
    if (!connection) {
      return { ok: false, reason: 'backend_offline' };
    }
    try {
      const response = await getBackendJson<{
        subject: string | null;
        source: 'config' | 'env' | null;
      }>(connection.port, '/api/web-push/subject');
      return {
        ok: true,
        subject: response.subject ?? null,
        source: response.source ?? null,
      };
    } catch (error) {
      return { ok: false, reason: 'subject_fetch_failed' };
    }
  });

  ipcMain.handle('webPush:setSubject', async (_event, params: WebPushSubjectPayload = {}) => {
    const connection = getBackendConnection();
    if (!connection) {
      return { ok: false, error: 'Backend is not connected.', reason: 'backend_offline' };
    }
    const subject = typeof params.subject === 'string' ? params.subject.trim() : '';
    if (!subject) {
      return { ok: false, error: 'subject is required.', reason: 'subject_required' };
    }
    try {
      const response = await postBackendJson<{
        ok: boolean;
        subject?: string | null;
        source?: 'config' | 'env' | null;
      }>(connection.port, '/api/web-push/subject', { subject });
      return {
        ok: response.ok === true,
        subject: response.subject ?? subject,
        source: response.source ?? 'config',
      };
    } catch (error) {
      return { ok: false, error: 'Failed to save subject.', reason: 'subject_save_failed' };
    }
  });

  ipcMain.handle(
    'webPush:registerSubscription',
    async (_event, params: WebPushRegisterParams = {}) => {
      const connection = getBackendConnection();
      if (!connection) {
        return { ok: false, error: 'Backend is not connected.', reason: 'backend_offline' };
      }
      const endpoint = typeof params.endpoint === 'string' ? params.endpoint.trim() : '';
      const p256dhKey = typeof params.p256dhKey === 'string' ? params.p256dhKey.trim() : '';
      const authKey = typeof params.authKey === 'string' ? params.authKey.trim() : '';
      if (!endpoint || !p256dhKey || !authKey) {
        return {
          ok: false,
          error: 'endpoint, p256dhKey, and authKey are required.',
          reason: 'subscription_payload_required',
        };
      }
      try {
        await postBackendJson<{ ok: boolean }>(
          connection.port,
          '/api/web-push/subscriptions',
          { endpoint, p256dhKey, authKey },
        );
        return { ok: true };
      } catch (error) {
        return {
          ok: false,
          error: 'Failed to register subscription.',
          reason: 'subscription_register_failed',
        };
      }
    },
  );

  ipcMain.handle(
    'webPush:unregisterSubscription',
    async (_event, params: WebPushUnregisterParams = {}) => {
      const connection = getBackendConnection();
      if (!connection) {
        return { ok: false, error: 'Backend is not connected.', reason: 'backend_offline' };
      }
      const endpoint = typeof params.endpoint === 'string' ? params.endpoint.trim() : '';
      if (!endpoint) {
        return { ok: false, error: 'endpoint is required.', reason: 'endpoint_required' };
      }
      try {
        await postBackendJson<{ ok: boolean }>(
          connection.port,
          '/api/web-push/subscriptions/unregister',
          { endpoint },
        );
        return { ok: true };
      } catch (error) {
        return {
          ok: false,
          error: 'Failed to unregister subscription.',
          reason: 'subscription_unregister_failed',
        };
      }
    },
  );
}

/**
 * Derive the expected staging root from the backend workspace config.
 *
 * The backend always writes staged export files under:
 *   <workspace>/.ds-agent/exports/<uuid>/
 *
 * We resolve the workspace dir from the same config file the Python backend
 * reads, so this stays consistent across all deployment modes.
 */
function resolveStagingRoot(): string {
  const workspaceDir = resolveWorkspaceDir();
  return path.resolve(workspaceDir, '.ds-agent', 'exports');
}

/**
 * Return true iff `stagedPath` resolves to a location strictly inside the
 * backend export staging root.  Rejects path-traversal sequences and any
 * absolute path that lands outside the workspace subtree.
 */
function isStagedPathConfined(stagedPath: string): boolean {
  try {
    const resolved = path.resolve(stagedPath);
    const stagingRoot = resolveStagingRoot();
    // Must be a proper descendant of stagingRoot (not stagingRoot itself).
    return resolved.startsWith(stagingRoot + path.sep);
  } catch {
    return false;
  }
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

function buildTaskContractIpcError(
  error: unknown,
  fallbackMessage: string,
  errorCode: string,
): { ok: false; error: string; errorCode: string; errorDetail?: BackendErrorDetail } {
  const detail = getBackendErrorDetail(error);
  return detail
    ? { ok: false, error: fallbackMessage, errorCode, errorDetail: detail }
    : { ok: false, error: fallbackMessage, errorCode };
}

function buildIpcErrorResult(
  error: string,
  errorCode: string,
): { ok: false; error: string; errorCode: string } {
  return { ok: false, error, errorCode };
}

function buildDialogIpcErrorResult(
  error: string,
  errorCode: string,
): { canceled: false; path: null; error: string; errorCode: string } {
  return { canceled: false, path: null, error, errorCode };
}

function getBackendErrorDetail(error: unknown): BackendErrorDetail | undefined {
  if (!(error instanceof Error) || !('detail' in error)) {
    return undefined;
  }
  const detail = (error as Error & { detail?: unknown }).detail;
  return isBackendErrorDetail(detail) ? detail : undefined;
}

function isBackendErrorDetail(value: unknown): value is BackendErrorDetail {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
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
            )
              ? parsed.detail
              : null;
            if (isBackendErrorDetail(detail)) {
              const message =
                typeof detail.message === 'string' && detail.message.trim()
                  ? detail.message
                  : raw || `Backend request failed (${statusCode})`;
              const error = new Error(message) as Error & { detail?: BackendErrorDetail };
              error.detail = detail;
              reject(error);
              return;
            }
            reject(
              new Error(
                typeof detail === 'string'
                  ? detail
                  : raw || `Backend request failed (${statusCode})`
              )
            );
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
