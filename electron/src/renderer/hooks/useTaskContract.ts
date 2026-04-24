import { useCallback, useEffect, useRef, useState } from 'react';
import { useChatStore } from '../stores/chatStore';
import { translateKey } from '../stores/i18nStore';
import { resolveMainIpcErrorMessage } from '../utils/mainIpcErrors';
import { useWs } from './WsProvider';
import type {
  AssumptionVerificationResultView,
  DeliveryBuildResultView,
  DeliveryDispatchResultView,
  DeliveryLogQueryResultView,
  DeliveryRenderResultView,
  ReviewVerdictView,
  ShadowComparisonView,
  TaskContractCreatePayload,
  TaskContractCreateResultView,
  TaskContractErrorDetailView,
  TaskContractStatus,
  TaskContractView,
} from '../types/taskContract';

const INCLUDE = [
  'goal_brief',
  'metric_specs',
  'dataset_manifest',
  'assumption_log',
  'review_verdicts',
  'delivery_pack',
];

const CONTRACT_TOOL_NAMES = new Set([
  'create_task_contract',
  'update_task_contract',
  'add_assumption',
  'add_task_assumption',
  'verify_assumption',
  'record_review_verdict',
  'record_delivery_pack',
  'close_task_contract',
  'build_delivery_pack',
  'render_delivery_artifact',
  'dispatch_delivery',
  'list_delivery_log',
]);

const TERMINAL_TASK_CONTRACT_STATUSES = new Set<TaskContractStatus>([
  'closed',
  'abandoned',
]);

export function useTaskContract() {
  const { status, on } = useWs();
  const sessionId = useChatStore((s) => s.sessionId);
  const lastViewedTaskIdRef = useRef<string | null>(null);
  const [activeContract, setActiveContract] = useState<TaskContractView | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deliveryLog, setDeliveryLog] = useState<DeliveryLogQueryResultView | null>(null);
  const [deliveryLogLoading, setDeliveryLogLoading] = useState(false);
  const [deliveryLogError, setDeliveryLogError] = useState<string | null>(null);
  const [shadowComparison, setShadowComparison] = useState<ShadowComparisonView | null>(null);
  const [shadowComparisonLoading, setShadowComparisonLoading] = useState(false);
  const [shadowComparisonError, setShadowComparisonError] = useState<string | null>(null);

  const loadTaskContract = useCallback(async (taskId: string): Promise<TaskContractView | null> => {
    if (!window.electronAPI?.taskContract) {
      return null;
    }
    const result = await window.electronAPI.taskContract.get({
      taskId,
      include: INCLUDE,
    });
    if (!result.ok || !result.contract) {
      return null;
    }
    return result.contract;
  }, []);

  const refresh = useCallback(async () => {
    if (!sessionId || !window.electronAPI?.taskContract) {
      lastViewedTaskIdRef.current = null;
      setActiveContract(null);
      setDeliveryLog(null);
      setError(null);
      setDeliveryLogError(null);
      setShadowComparison(null);
      setShadowComparisonError(null);
      return;
    }

    setLoading(true);
    const result = await window.electronAPI.taskContract.active({
      sessionId,
      include: INCLUDE,
    });
    if (!result.ok) {
      setError(resolveMainIpcErrorMessage(result, 'common.mainIpc.taskContract.activeFailed'));
      setActiveContract(null);
      setDeliveryLog(null);
      setLoading(false);
      return;
    }
    if (result.contract) {
      lastViewedTaskIdRef.current = result.contract.contract.task_id;
      setActiveContract(result.contract);
      setError(null);
      setLoading(false);
      return;
    }

    const fallbackTaskId = lastViewedTaskIdRef.current;
    if (fallbackTaskId) {
      const fallbackContract = await loadTaskContract(fallbackTaskId);
      if (
        fallbackContract
        && fallbackContract.contract.session_id === sessionId
        && TERMINAL_TASK_CONTRACT_STATUSES.has(fallbackContract.contract.status)
      ) {
        setActiveContract(fallbackContract);
        setError(null);
        setLoading(false);
        return;
      }
      lastViewedTaskIdRef.current = null;
    }

    setActiveContract(null);
    setDeliveryLog(null);
    setError(null);
    setLoading(false);
  }, [loadTaskContract, sessionId]);

  const refreshDeliveryLog = useCallback(async (params?: {
    packId?: string;
    artifactIds?: string[];
    channels?: string[];
    limit?: number;
  }) => {
    if (!activeContract || !window.electronAPI?.taskContract) {
      setDeliveryLog(null);
      setDeliveryLogError(null);
      return null;
    }

    setDeliveryLogLoading(true);
    const result = await window.electronAPI.taskContract.listDeliveryLog({
      taskId: activeContract.contract.task_id,
      packId: params?.packId ?? activeContract.delivery_pack?.pack_id,
      artifactIds: params?.artifactIds,
      channels: params?.channels,
      limit: params?.limit,
    });
    if (!result.ok) {
      setDeliveryLogError(
        resolveMainIpcErrorMessage(result, 'common.mainIpc.taskContract.deliveryLogFailed'),
      );
      setDeliveryLogLoading(false);
      return null;
    }
    setDeliveryLog(result.result);
    setDeliveryLogError(null);
    setDeliveryLogLoading(false);
    return result.result;
  }, [activeContract]);

  const refreshShadowComparison = useCallback(async (params?: {
    comparisonId?: string;
  }) => {
    if (!activeContract || !window.electronAPI?.taskContract) {
      setShadowComparison(null);
      setShadowComparisonError(null);
      return null;
    }

    const latestVerdict = pickLatestReviewVerdict(activeContract.review_verdicts);
    const comparisonId =
      typeof params?.comparisonId === 'string' && params.comparisonId.trim()
        ? params.comparisonId.trim()
        : getShadowComparisonId(latestVerdict);
    if (!comparisonId) {
      setShadowComparison(null);
      setShadowComparisonError(null);
      setShadowComparisonLoading(false);
      return null;
    }

    setShadowComparisonLoading(true);
    const result = await window.electronAPI.taskContract.getShadowComparison({
      taskId: activeContract.contract.task_id,
      comparisonId,
    });
    if (!result.ok) {
      setShadowComparisonError(
        resolveMainIpcErrorMessage(result, 'common.mainIpc.taskContract.shadowGetFailed'),
      );
      setShadowComparisonLoading(false);
      return null;
    }
    setShadowComparison(result.comparison);
    setShadowComparisonError(null);
    setShadowComparisonLoading(false);
    return result.comparison;
  }, [activeContract]);

  const latestReviewVerdict = pickLatestReviewVerdict(activeContract?.review_verdicts ?? []);
  const activeShadowComparisonId = getShadowComparisonId(latestReviewVerdict);
  const activeShadowMismatchCount = getShadowMismatchCount(latestReviewVerdict);

  useEffect(() => {
    lastViewedTaskIdRef.current = null;
  }, [sessionId]);

  useEffect(() => {
    if (status === 'connected') {
      void refresh();
      return;
    }
    setActiveContract(null);
    setDeliveryLog(null);
    setError(null);
    setDeliveryLogError(null);
    setShadowComparison(null);
    setShadowComparisonError(null);
    setLoading(false);
    setDeliveryLogLoading(false);
    setShadowComparisonLoading(false);
  }, [refresh, status]);

  useEffect(() => on('stream.done', () => {
    void refresh();
  }), [on, refresh]);

  useEffect(() => on('tool.end', (payload) => {
    const name = typeof payload.name === 'string' ? payload.name : '';
    if (CONTRACT_TOOL_NAMES.has(name)) {
      void refresh();
    }
  }), [on, refresh]);

  useEffect(() => {
    if (!activeContract?.delivery_pack?.pack_id) {
      setDeliveryLog(null);
      setDeliveryLogError(null);
      setDeliveryLogLoading(false);
      return;
    }
    void refreshDeliveryLog({ packId: activeContract.delivery_pack.pack_id, limit: 20 });
  }, [activeContract?.delivery_pack?.pack_id, refreshDeliveryLog]);

  useEffect(() => {
    if (!activeContract?.contract.task_id || !activeShadowComparisonId || activeShadowMismatchCount < 1) {
      setShadowComparison(null);
      setShadowComparisonError(null);
      setShadowComparisonLoading(false);
      return;
    }
    void refreshShadowComparison({ comparisonId: activeShadowComparisonId });
  }, [
    activeContract?.contract.task_id,
    activeShadowComparisonId,
    activeShadowMismatchCount,
    refreshShadowComparison,
  ]);

  const transition = useCallback(async (transitionTo: TaskContractStatus, reason: string) => {
    if (!activeContract || !window.electronAPI?.taskContract) {
      throw new Error(translateKey('common.taskContract.noActive'));
    }
    const result = await window.electronAPI.taskContract.update({
      taskId: activeContract.contract.task_id,
      expectedVersion: activeContract.contract.version,
      patch: {},
      transitionTo,
      reason,
    });
    if (!result.ok) {
      throw buildTaskContractOperationError(
        resolveMainIpcErrorMessage(result, 'common.mainIpc.taskContract.updateFailed'),
        result.errorDetail,
      );
    }
    await refresh();
  }, [activeContract, refresh]);

  const createContract = useCallback(async (
    payload: TaskContractCreatePayload,
  ): Promise<TaskContractCreateResultView> => {
    if (!window.electronAPI?.taskContract) {
      throw new Error(translateKey('common.taskContract.ipcUnavailable'));
    }
    const result = await window.electronAPI.taskContract.create(payload);
    if (!result.ok) {
      throw buildTaskContractOperationError(
        resolveMainIpcErrorMessage(result, 'common.mainIpc.taskContract.createFailed'),
        result.errorDetail,
      );
    }
    lastViewedTaskIdRef.current = result.result.task_id;
    await refresh();
    return result.result;
  }, [refresh]);

  const savePatch = useCallback(async (patch: Record<string, unknown>, reason: string) => {
    if (!activeContract || !window.electronAPI?.taskContract) {
      throw new Error(translateKey('common.taskContract.noActive'));
    }
    const result = await window.electronAPI.taskContract.update({
      taskId: activeContract.contract.task_id,
      expectedVersion: activeContract.contract.version,
      patch,
      reason,
    });
    if (!result.ok) {
      throw buildTaskContractOperationError(
        resolveMainIpcErrorMessage(result, 'common.mainIpc.taskContract.updateFailed'),
        result.errorDetail,
      );
    }
    await refresh();
  }, [activeContract, refresh]);

  const closeContract = useCallback(async (closingNote: string) => {
    if (!activeContract || !window.electronAPI?.taskContract) {
      throw new Error(translateKey('common.taskContract.noActive'));
    }
    const result = await window.electronAPI.taskContract.close({
      taskId: activeContract.contract.task_id,
      expectedVersion: activeContract.contract.version,
      closingNote,
    });
    if (!result.ok) {
      throw buildTaskContractOperationError(
        resolveMainIpcErrorMessage(result, 'common.mainIpc.taskContract.closeFailed'),
        result.errorDetail,
      );
    }
    await refresh();
  }, [activeContract, refresh]);

  const verifyAssumption = useCallback(async (params: {
    entryId: string;
    verificationNote?: string;
  }): Promise<AssumptionVerificationResultView> => {
    if (!activeContract || !window.electronAPI?.taskContract) {
      throw new Error(translateKey('common.taskContract.noActive'));
    }

    const result = await window.electronAPI.taskContract.verifyAssumption({
      taskId: activeContract.contract.task_id,
      entryId: params.entryId,
      expectedVersion: activeContract.contract.version,
      verificationNote: params.verificationNote,
    });
    if (!result.ok) {
      throw buildTaskContractOperationError(
        resolveMainIpcErrorMessage(result, 'common.mainIpc.taskContract.verifyFailed'),
        result.errorDetail,
      );
    }
    await refresh();
    return result.result;
  }, [activeContract, refresh]);

  const buildDeliveryPack = useCallback(async (params: {
    audiences?: string[];
    followUpActions?: string[];
    sourceAnalysisId?: string;
    confidence?: number;
    signedBy?: string;
    signature?: string;
    globalContext?: Record<string, string>;
    tenant?: string;
  }): Promise<DeliveryBuildResultView> => {
    if (!activeContract || !window.electronAPI?.taskContract) {
      throw new Error(translateKey('common.taskContract.noActive'));
    }

    const result = await window.electronAPI.taskContract.buildDeliveryPack({
      taskId: activeContract.contract.task_id,
      ...params,
    });
    if (!result.ok) {
      throw buildTaskContractOperationError(
        resolveMainIpcErrorMessage(result, 'common.mainIpc.taskContract.buildDeliveryFailed'),
        result.errorDetail,
      );
    }
    await refresh();
    return result.result;
  }, [activeContract, refresh]);

  const renderArtifact = useCallback(async (params: {
    artifactId: string;
    analysis: Record<string, unknown> | string;
    outputDir?: string;
    audienceProfile?: string;
    providerBacked?: boolean;
    model?: string;
  }): Promise<DeliveryRenderResultView> => {
    if (!activeContract || !window.electronAPI?.taskContract) {
      throw new Error(translateKey('common.taskContract.noActive'));
    }

    const result = await window.electronAPI.taskContract.renderArtifact({
      taskId: activeContract.contract.task_id,
      artifactId: params.artifactId,
      analysis: params.analysis,
      outputDir: params.outputDir,
      audienceProfile: params.audienceProfile,
      providerBacked: params.providerBacked,
      model: params.model,
    });
    if (!result.ok) {
      throw buildTaskContractOperationError(
        resolveMainIpcErrorMessage(result, 'common.mainIpc.taskContract.renderFailed'),
        result.errorDetail,
      );
    }
    await refresh();
    return result.result;
  }, [activeContract, refresh]);

  const dispatchDelivery = useCallback(async (params: {
    artifactIds?: string[];
    channels?: string[];
    dryRun?: boolean;
    approveManualReview?: boolean;
  }): Promise<DeliveryDispatchResultView> => {
    if (!activeContract || !window.electronAPI?.taskContract) {
      throw new Error(translateKey('common.taskContract.noActive'));
    }

    const result = await window.electronAPI.taskContract.dispatchDelivery({
      taskId: activeContract.contract.task_id,
      artifactIds: params.artifactIds,
      channels: params.channels,
      dryRun: params.dryRun,
      approveManualReview: params.approveManualReview,
    });
    if (!result.ok) {
      throw buildTaskContractOperationError(
        resolveMainIpcErrorMessage(result, 'common.mainIpc.taskContract.dispatchFailed'),
        result.errorDetail,
      );
    }
    await refresh();
    return result.result;
  }, [activeContract, refresh]);

  return {
    sessionId,
    activeContract,
    loading,
    error,
    deliveryLog,
    deliveryLogLoading,
    deliveryLogError,
    shadowComparison,
    shadowComparisonLoading,
    shadowComparisonError,
    refresh,
    refreshDeliveryLog,
    refreshShadowComparison,
    transition,
    createContract,
    savePatch,
    closeContract,
    verifyAssumption,
    buildDeliveryPack,
    renderArtifact,
    dispatchDelivery,
  };
}

function pickLatestReviewVerdict(reviewVerdicts: ReviewVerdictView[]): ReviewVerdictView | null {
  if (reviewVerdicts.length === 0) return null;
  const orchestratorVerdicts = reviewVerdicts.filter((item) => item.category === 'orchestrator');
  const candidates = orchestratorVerdicts.length > 0 ? orchestratorVerdicts : reviewVerdicts;
  return candidates.reduce((latest, current) => {
    const currentKey = `${current.created_at}:${current.verdict_id}`;
    const latestKey = `${latest.created_at}:${latest.verdict_id}`;
    return currentKey > latestKey ? current : latest;
  });
}

function getShadowComparisonId(verdict: ReviewVerdictView | null): string | null {
  return typeof verdict?.metadata?.shadow_comparison_id === 'string'
    ? verdict.metadata.shadow_comparison_id
    : null;
}

function getShadowMismatchCount(verdict: ReviewVerdictView | null): number {
  return typeof verdict?.metadata?.shadow_mismatch_count === 'number'
    ? verdict.metadata.shadow_mismatch_count
    : 0;
}

function buildTaskContractOperationError(
  message: string,
  detail?: TaskContractErrorDetailView,
): Error {
  const error = new Error(message);
  if (detail) {
    Object.assign(error, { detail });
  }
  return error;
}
