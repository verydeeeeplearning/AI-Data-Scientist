/**
 * Preload script — secure IPC bridge between main and renderer.
 *
 * Exposes minimal API to the renderer via contextBridge.
 * The renderer communicates with Python backend directly via WebSocket,
 * so this preload only handles Electron-specific features.
 */

import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  // Platform info
  platform: process.platform,

  // Window controls (for custom title bar if needed)
  minimize: () => ipcRenderer.send('window:minimize'),
  maximize: () => ipcRenderer.send('window:maximize'),
  close: () => ipcRenderer.send('window:close'),

  // File dialog
  openFileDialog: () => ipcRenderer.invoke('dialog:openFile'),

  // Diagnostic bundle export
  saveDiagnosticBundle: (defaultName: string, payload: Record<string, unknown> | null) => ipcRenderer.invoke(
    'diagnostic:export',
    { defaultName, payload }
  ),
  exportSupportBundle: (defaultName?: string) => ipcRenderer.invoke(
    'support:exportBundle',
    { defaultName }
  ),
  updateObservability: (params: {
    errorReportingEnabled: boolean;
    telemetryEnabled: boolean;
  }) => ipcRenderer.invoke('observability:update', params),

  // Shell helpers
  revealPath: (targetPath: string) => ipcRenderer.invoke('shell:revealPath', targetPath),
  previewArtifactFile: (targetPath: string) => ipcRenderer.invoke('artifact:previewLocalFile', { targetPath }),

  // Desktop secret vault
  getMaskedApiKeys: () => ipcRenderer.invoke('secrets:getMaskedApiKeys'),
  getSecretVaultStatus: () => ipcRenderer.invoke('secrets:getStatus'),
  setApiKey: (provider: string, key: string) => ipcRenderer.invoke('secrets:setApiKey', { provider, key }),
  deleteApiKey: (provider: string) => ipcRenderer.invoke('secrets:deleteApiKey', { provider }),

  // Onboarding sample datasets (P1-08 Phase 3)
  loadSampleForUseCase: (useCaseId: string) =>
    ipcRenderer.invoke('samples:loadForUseCase', { useCaseId }),

  // Artifact export save dialog (P1-12)
  finishArtifactExport: (params: {
    stagedPath: string;
    suggestedFilename: string;
    format: string;
    needsPdfRender: boolean;
  }) => ipcRenderer.invoke('export:finish', params),

  certification: {
    list: () => ipcRenderer.invoke('certification:list'),
    status: (params: { missionName: string }) => ipcRenderer.invoke('certification:status', params),
    submit: (params: {
      missionName: string;
      targetLevel: string;
      approvedBy?: string[];
      evidenceRef?: string;
    }) => ipcRenderer.invoke('certification:submit', params),
  },

  workObject: {
    list: (params?: {
      sessionId?: string;
      taskContractId?: string;
      phase?: string[];
      limit?: number;
    }) => ipcRenderer.invoke('workObject:list', params ?? {}),
    get: (params: {
      workObjectId: string;
      timelineLimit?: number;
    }) => ipcRenderer.invoke('workObject:get', params),
    intake: (params: {
      taskContractId?: string;
      title: string;
      requestSource?: string;
      requestorId?: string;
      requestorDisplay?: string;
      originalText?: string;
      channel?: string;
      ownerAgent?: string;
      tags?: string[];
    }) => ipcRenderer.invoke('workObject:intake', params),
    advance: (params: {
      workObjectId: string;
      toPhase: string;
      runId?: string;
    }) => ipcRenderer.invoke('workObject:advance', params),
    close: (params: {
      workObjectId: string;
      reason: string;
    }) => ipcRenderer.invoke('workObject:close', params),
  },

  taskContract: {
    list: (params?: { sessionId?: string; status?: string[]; limit?: number }) =>
      ipcRenderer.invoke('taskContract:list', params ?? {}),
    active: (params: { sessionId: string; include?: string[] }) =>
      ipcRenderer.invoke('taskContract:active', params),
    get: (params: { taskId: string; include?: string[] }) =>
      ipcRenderer.invoke('taskContract:get', params),
    update: (params: {
      taskId: string;
      expectedVersion: number;
      patch?: Record<string, unknown>;
      transitionTo?: string;
      reason?: string;
    }) => ipcRenderer.invoke('taskContract:update', params),
    close: (params: {
      taskId: string;
      expectedVersion: number;
      closingNote: string;
    }) => ipcRenderer.invoke('taskContract:close', params),
    verifyAssumption: (params: {
      taskId: string;
      entryId: string;
      expectedVersion: number;
      verificationNote?: string;
    }) => ipcRenderer.invoke('taskContract:verifyAssumption', params),
    buildDeliveryPack: (params: {
      taskId: string;
      audiences?: string[];
      followUpActions?: string[];
      sourceAnalysisId?: string;
      confidence?: number;
      signedBy?: string;
      signature?: string;
      globalContext?: Record<string, string>;
      tenant?: string;
    }) => ipcRenderer.invoke('taskContract:buildDeliveryPack', params),
    renderArtifact: (params: {
      taskId: string;
      artifactId: string;
      analysis: Record<string, unknown> | string;
      outputDir?: string;
      audienceProfile?: string;
      providerBacked?: boolean;
      model?: string;
    }) => ipcRenderer.invoke('taskContract:renderArtifact', params),
    previewRenderedArtifact: (params: {
      renderedUri: string;
      format: string;
    }) => ipcRenderer.invoke('taskContract:previewRenderedArtifact', params),
    dispatchDelivery: (params: {
      taskId: string;
      artifactIds?: string[];
      channels?: string[];
      dryRun?: boolean;
      approveManualReview?: boolean;
    }) => ipcRenderer.invoke('taskContract:dispatchDelivery', params),
    listDeliveryLog: (params: {
      taskId: string;
      packId?: string;
      artifactIds?: string[];
      channels?: string[];
      limit?: number;
    }) => ipcRenderer.invoke('taskContract:listDeliveryLog', params),
    listShadowComparisons: (params: {
      taskId: string;
      verdictId?: string;
      mismatchesOnly?: boolean;
      limit?: number;
    }) => ipcRenderer.invoke('taskContract:listShadowComparisons', params),
    getShadowComparison: (params: {
      taskId: string;
      comparisonId: string;
    }) => ipcRenderer.invoke('taskContract:getShadowComparison', params),
  },

  // Auto-updater (P1-14)
  updater: {
    check: () => ipcRenderer.invoke('updater:check'),
    download: () => ipcRenderer.invoke('updater:download'),
    install: () => ipcRenderer.invoke('updater:install'),
    getState: () => ipcRenderer.invoke('updater:getState'),
    on: (event: string, handler: (payload: Record<string, unknown>) => void) => {
      const listener = (_evt: unknown, payload: Record<string, unknown>) => handler(payload);
      ipcRenderer.on(`updater:${event}`, listener);
      return () => ipcRenderer.off(`updater:${event}`, listener);
    },
  },
});
