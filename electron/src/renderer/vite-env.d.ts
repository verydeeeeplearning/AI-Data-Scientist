/// <reference types="vite/client" />

import type {
  CertificationStatusView,
  CertificationSubmissionView,
} from './types/certification';
import type {
  WorkObjectDetailView,
  WorkObjectListItemView,
} from './types/workObject';
import type {
  AssumptionVerificationResultView,
  TaskContractCreatePayload,
  TaskContractCreateResultView,
  TaskContractIpcErrorResult,
  DeliveryBuildResultView,
  DeliveryDispatchResultView,
  DeliveryLogQueryResultView,
  DeliveryRenderResultView,
  RenderedArtifactPreviewView,
  ShadowComparisonView,
  TaskContractListItem,
  TaskContractView,
} from './types/taskContract';
import type { ArtifactPreviewView } from './types/artifactPreview';

interface ElectronAPI {
  deleteApiKey: (
    provider: string
  ) => Promise<{ ok: boolean; deleted?: boolean; error?: string }>;
  getMaskedApiKeys: () => Promise<{
    available: boolean;
    persistent: boolean;
    backend: 'safeStorage' | 'unavailable';
    maskedKeys: Record<string, string>;
    error?: string;
  }>;
  getSecretVaultStatus: () => Promise<{
    available: boolean;
    persistent: boolean;
    backend: 'safeStorage' | 'unavailable';
    error?: string;
  }>;
  platform: string;
  minimize: () => void;
  maximize: () => void;
  close: () => void;
  openFileDialog: () => Promise<string | null>;
  saveDiagnosticBundle: (
    defaultName: string,
    payload: Record<string, unknown> | null
  ) => Promise<{ canceled: boolean; path: string | null }>;
  exportSupportBundle: (
    defaultName?: string
  ) => Promise<{ canceled: boolean; path: string | null; error?: string }>;
  updateObservability: (params: {
    errorReportingEnabled: boolean;
    telemetryEnabled: boolean;
  }) => Promise<{
    sentryConfigured: boolean;
    errorReportingEnabled: boolean;
    telemetryEnabled: boolean;
  }>;
  revealPath: (targetPath: string) => Promise<{ ok: boolean; error?: string }>;
  previewArtifactFile: (targetPath: string) => Promise<
    | { ok: true; preview: ArtifactPreviewView }
    | { ok: false; error: string }
  >;
  setApiKey: (
    provider: string,
    key: string
  ) => Promise<{ ok: boolean; error?: string }>;
  loadSampleForUseCase: (useCaseId: string) => Promise<
    | {
        ok: true;
        sample: {
          useCaseId: string;
          filename: string;
          label: string;
          description: string;
          mimeType: string;
          data: string;
        };
      }
    | { ok: false; error: string }
  >;
  finishArtifactExport: (params: {
    stagedPath: string;
    suggestedFilename: string;
    format: string;
    needsPdfRender: boolean;
  }) => Promise<{
    canceled: boolean;
    path: string | null;
    error?: string;
  }>;
  certification: {
    list: () => Promise<
      | { ok: true; missions: CertificationStatusView[] }
      | { ok: false; error: string }
    >;
    status: (params: { missionName: string }) => Promise<
      | { ok: true; mission: CertificationStatusView }
      | { ok: false; error: string }
    >;
    submit: (params: {
      missionName: string;
      targetLevel: string;
      approvedBy?: string[];
      evidenceRef?: string;
    }) => Promise<
      | { ok: true; result: CertificationSubmissionView }
      | { ok: false; error: string }
    >;
  };
  workObject: {
    list: (params?: {
      sessionId?: string;
      taskContractId?: string;
      phase?: string[];
      limit?: number;
    }) => Promise<
      | { ok: true; workObjects: WorkObjectListItemView[] }
      | { ok: false; error: string }
    >;
    get: (params: {
      workObjectId: string;
      timelineLimit?: number;
    }) => Promise<
      | { ok: true; detail: WorkObjectDetailView }
      | { ok: false; error: string }
    >;
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
    }) => Promise<
      | { ok: true; result: unknown }
      | { ok: false; error: string }
    >;
    advance: (params: {
      workObjectId: string;
      toPhase: string;
      runId?: string;
    }) => Promise<
      | { ok: true; result: unknown }
      | { ok: false; error: string }
    >;
    close: (params: {
      workObjectId: string;
      reason: string;
    }) => Promise<
      | { ok: true; result: unknown }
      | { ok: false; error: string }
    >;
  };
  taskContract: {
    list: (params?: {
      sessionId?: string;
      status?: string[];
      limit?: number;
    }) => Promise<
      | { ok: true; contracts: TaskContractListItem[] }
      | TaskContractIpcErrorResult
    >;
    active: (params: {
      sessionId: string;
      include?: string[];
    }) => Promise<
      | { ok: true; contract: TaskContractView | null }
      | TaskContractIpcErrorResult
    >;
    get: (params: {
      taskId: string;
      include?: string[];
    }) => Promise<
      | { ok: true; contract: TaskContractView }
      | TaskContractIpcErrorResult
    >;
    create: (params: TaskContractCreatePayload) => Promise<
      | { ok: true; result: TaskContractCreateResultView }
      | TaskContractIpcErrorResult
    >;
    update: (params: {
      taskId: string;
      expectedVersion: number;
      patch?: Record<string, unknown>;
      transitionTo?: string;
      reason?: string;
    }) => Promise<
      | { ok: true; result: { task_id: string; status: string; new_version: number } }
      | TaskContractIpcErrorResult
    >;
    close: (params: {
      taskId: string;
      expectedVersion: number;
      closingNote: string;
    }) => Promise<
      | {
          ok: true;
          result: {
            task_id: string;
            status: string;
            new_version: number;
            dod_summary: string[];
          };
        }
      | TaskContractIpcErrorResult
    >;
    verifyAssumption: (params: {
      taskId: string;
      entryId: string;
      expectedVersion: number;
      verificationNote?: string;
    }) => Promise<
      | { ok: true; result: AssumptionVerificationResultView }
      | TaskContractIpcErrorResult
    >;
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
    }) => Promise<
      | { ok: true; result: DeliveryBuildResultView }
      | TaskContractIpcErrorResult
    >;
    renderArtifact: (params: {
      taskId: string;
      artifactId: string;
      analysis: Record<string, unknown> | string;
      outputDir?: string;
      audienceProfile?: string;
      providerBacked?: boolean;
      model?: string;
    }) => Promise<
      | { ok: true; result: DeliveryRenderResultView }
      | TaskContractIpcErrorResult
    >;
    previewRenderedArtifact: (params: {
      renderedUri: string;
      format: string;
    }) => Promise<
      | { ok: true; preview: RenderedArtifactPreviewView }
      | { ok: false; error: string }
    >;
    dispatchDelivery: (params: {
      taskId: string;
      artifactIds?: string[];
      channels?: string[];
      dryRun?: boolean;
      approveManualReview?: boolean;
    }) => Promise<
      | { ok: true; result: DeliveryDispatchResultView }
      | TaskContractIpcErrorResult
    >;
    listDeliveryLog: (params: {
      taskId: string;
      packId?: string;
      artifactIds?: string[];
      channels?: string[];
      limit?: number;
    }) => Promise<
      | { ok: true; result: DeliveryLogQueryResultView }
      | TaskContractIpcErrorResult
    >;
    listShadowComparisons: (params: {
      taskId: string;
      verdictId?: string;
      mismatchesOnly?: boolean;
      limit?: number;
    }) => Promise<
      | { ok: true; comparisons: ShadowComparisonView[] }
      | TaskContractIpcErrorResult
    >;
    getShadowComparison: (params: {
      taskId: string;
      comparisonId: string;
    }) => Promise<
      | { ok: true; comparison: ShadowComparisonView }
      | TaskContractIpcErrorResult
    >;
  };
  updater: {
    check: () => Promise<
      | { ok: true; updateAvailable: boolean; version: string | null }
      | { ok: false; error: string }
    >;
    download: () => Promise<{ ok: true } | { ok: false; error: string }>;
    install: () => Promise<{ ok: true }>;
    getState: () => Promise<{
      channel: 'stable' | 'beta' | 'internal' | string;
      currentVersion: string;
      isPackaged: boolean;
    }>;
    on: (
      event:
        | 'checking'
        | 'update-available'
        | 'update-not-available'
        | 'download-progress'
        | 'update-ready'
        | 'error',
      handler: (payload: Record<string, unknown>) => void
    ) => () => void;
  };
  deepLink: {
    onDeepLink: (handler: (uri: string) => void) => () => void;
  };
  webPush?: {
    getPublicKey: () => Promise<{
      ok: boolean;
      publicKey?: string;
      reason?: string;
    }>;
    getSubject: () => Promise<{
      ok: boolean;
      subject?: string | null;
      source?: 'config' | 'env' | null;
      reason?: string;
    }>;
    setSubject: (payload: {
      subject: string;
    }) => Promise<{
      ok: boolean;
      subject?: string | null;
      source?: 'config' | 'env' | null;
      error?: string;
    }>;
    registerSubscription: (payload: {
      endpoint: string;
      p256dhKey: string;
      authKey: string;
    }) => Promise<{ ok: boolean; error?: string }>;
    unregisterSubscription: (payload: { endpoint: string }) => Promise<{
      ok: boolean;
      error?: string;
    }>;
  };
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

export {};
