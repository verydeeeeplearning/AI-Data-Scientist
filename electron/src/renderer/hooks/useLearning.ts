import { useCallback, useState } from 'react';
import type {
  LearningGovernanceStatusView,
  LearningInboxView,
  LearningItemDetailView,
} from '../types/learning';
import {
  normalizeLearningGovernanceStatus,
  normalizeLearningInboxItem,
  normalizeLearningItemDetail,
} from '../types/learning';
import { useWs } from './WsProvider';

type LearningRpc = (
  method: string,
  params?: Record<string, unknown>,
) => Promise<Record<string, unknown>>;

export type {
  FailureTaxonomyCandidateSummary,
  HarnessWarningReviewSummary,
  LearningGovernanceBacklogView,
  LearningGovernanceHistoryView,
  LearningGovernanceReportView,
  LearningGovernanceStandingOrderView,
  LearningGovernanceStatusView,
  LearningInboxView,
  LearningItemDetailView,
  LearningItemView,
} from '../types/learning';
export {
  extractFailureTaxonomyCandidateSummary,
  extractHarnessWarningReviewSummary,
  isHarnessWarningLearningItem,
  normalizeLearningGovernanceStatus,
  normalizeLearningInboxItem,
  normalizeLearningItemDetail,
} from '../types/learning';

export interface LearningCandidatePromotionResult {
  candidateId: string;
  status: string;
  promoted: boolean;
  candidateScore: number;
  baselineScore: number | null;
  deltaScore: number | null;
  deltaThreshold: number;
  passedTasks: number;
  totalTasks: number;
  summary: string;
  promotedPath: string | null;
  pendingPath: string;
}

export const EMPTY_LEARNING_INBOX: LearningInboxView = { items: [], total: 0 };
export const EMPTY_LEARNING_GOVERNANCE_STATUS: LearningGovernanceStatusView = {
  reviewEnabled: false,
  standingOrder: null,
  backlog: {
    activeWarningItems: 0,
    activeWarningRecurrences: 0,
    promotionCandidateItems: 0,
    promotionCandidateClasses: [],
    warningTypes: [],
    surfaces: [],
    lastGcAt: null,
  },
  latestCompletedRun: null,
  latestReport: null,
  recentHistory: [],
};

export function readLearningGovernanceEnabled(payload: unknown): boolean {
  if (!payload || typeof payload !== 'object') {
    return false;
  }
  const featureFlags = (payload as { featureFlags?: unknown }).featureFlags;
  if (!featureFlags || typeof featureFlags !== 'object') {
    return false;
  }

  const rawValue = (featureFlags as { selfImproveGovernanceV1?: unknown }).selfImproveGovernanceV1;
  if (typeof rawValue === 'boolean') {
    return rawValue;
  }
  if (typeof rawValue === 'string') {
    return ['1', 'true', 'yes'].includes(rawValue.trim().toLowerCase());
  }
  return false;
}

export function createLearningClient(rpc: LearningRpc) {
  let enabledPromise: Promise<boolean> | null = null;

  const getEnabled = async (): Promise<boolean> => {
    if (enabledPromise === null) {
      enabledPromise = rpc('config.get').then((result) => readLearningGovernanceEnabled(result));
    }
    return enabledPromise;
  };

  return {
    getEnabled,
    async fetchStatus() {
      const enabled = await getEnabled();
      const result = await rpc('learning.status', { historyLimit: 5 });
      return {
        enabled,
        status: normalizeLearningGovernanceStatus({
          ...result,
          reviewEnabled:
            (result as { reviewEnabled?: unknown }).reviewEnabled ?? enabled,
        }),
      };
    },
    async fetchInbox(status = 'proposed', itemType = 'all') {
      const enabled = await getEnabled();
      const result = await rpc('learning.inbox', { status, itemType, limit: 30 });
      const rawItems = Array.isArray(result.items) ? result.items : [];
      const items = rawItems
        .map((raw) => normalizeLearningInboxItem(raw))
        .filter((item): item is NonNullable<typeof item> => item !== null);
      const total = typeof result.total === 'number' ? result.total : items.length;
      return {
        enabled,
        inbox: { items, total } satisfies LearningInboxView,
      };
    },
    async fetchItemDetail(item: LearningInboxView['items'][number]) {
      const enabled = await getEnabled();
      const result = await rpc('learning.getItem', { itemId: item.item_id });
      return {
        enabled,
        item: normalizeLearningItemDetail(item, result) as LearningItemDetailView,
      };
    },
    async reviewItem(itemId: string, decision: string, comment = '') {
      if (!(await getEnabled())) {
        return false;
      }
      await rpc('learning.review', { itemId, decision, comment });
      return true;
    },
    async finalizeCandidatePromotion(params: {
      candidateId: string;
      candidateScore: number;
      passedTasks: number;
      totalTasks: number;
      baselineScore?: number;
      deltaThreshold?: number;
    }) {
      if (!(await getEnabled())) {
        return null;
      }
      const result = await rpc('learning.finalizePromotion', params);
      return result as unknown as LearningCandidatePromotionResult;
    },
  };
}

export function useLearning() {
  const { rpc } = useWs();
  const [enabled, setEnabled] = useState(false);
  const [inbox, setInbox] = useState<LearningInboxView>(EMPTY_LEARNING_INBOX);
  const [status, setStatus] = useState<LearningGovernanceStatusView>(
    EMPTY_LEARNING_GOVERNANCE_STATUS,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshInbox = useCallback(
    async (status = 'proposed', itemType = 'all') => {
      setLoading(true);
      setError(null);
      try {
        const client = createLearningClient(rpc);
        const nextStatus = await client.fetchStatus();
        const result = await client.fetchInbox(status, itemType);
        setEnabled(result.enabled);
        setStatus(nextStatus.status);
        setInbox(result.inbox);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    },
    [rpc],
  );

  const fetchItemDetail = useCallback(
    async (item: LearningInboxView['items'][number]) => {
      const client = createLearningClient(rpc);
      const result = await client.fetchItemDetail(item);
      setEnabled(result.enabled);
      return result.item;
    },
    [rpc],
  );

  const reviewItem = useCallback(
    async (itemId: string, decision: string, comment = '') => {
      const client = createLearningClient(rpc);
      const nextEnabled = await client.reviewItem(itemId, decision, comment);
      setEnabled(nextEnabled);
      if (!nextEnabled) {
        return;
      }
      await refreshInbox();
    },
    [rpc, refreshInbox],
  );

  const finalizeCandidatePromotion = useCallback(
    async (params: {
      candidateId: string;
      candidateScore: number;
      passedTasks: number;
      totalTasks: number;
      baselineScore?: number;
      deltaThreshold?: number;
    }) => {
      const client = createLearningClient(rpc);
      const result = await client.finalizeCandidatePromotion(params);
      setEnabled(Boolean(result));
      if (!result) {
        return null;
      }
      await refreshInbox();
      return result;
    },
    [rpc, refreshInbox],
  );

  return {
    enabled,
    status,
    inbox,
    loading,
    error,
    refreshInbox,
    fetchItemDetail,
    reviewItem,
    finalizeCandidatePromotion,
  };
}
