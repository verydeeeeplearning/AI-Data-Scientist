import { useCallback, useEffect, useRef } from 'react';

import { useWs } from './WsProvider';
import { useVisiblePolling } from './useVisiblePolling';
import { useChatStore } from '../stores/chatStore';
import { useConfigStore } from '../stores/configStore';
import { useUsageStore, type UsageSummary } from '../stores/usageStore';

function normalizeUsageSummary(payload: Record<string, unknown>): UsageSummary {
  return {
    actorId: String(payload.actorId ?? 'local-user'),
    monthlyCostUsd: Number(payload.monthlyCostUsd ?? 0),
    monthlyBudgetUsd: payload.monthlyBudgetUsd == null ? null : Number(payload.monthlyBudgetUsd),
    budgetUsedPct: Number(payload.budgetUsedPct ?? 0),
    cacheSavingsUsd: Number(payload.cacheSavingsUsd ?? 0),
    sessionCostUsd: Number(payload.sessionCostUsd ?? 0),
    todayCostUsd: Number(payload.todayCostUsd ?? 0),
    remainingBudgetUsd: payload.remainingBudgetUsd == null ? null : Number(payload.remainingBudgetUsd),
    monthRunCount: Number(payload.monthRunCount ?? 0),
    warningLevel: String(payload.warningLevel ?? 'ok'),
    warningThresholdPct: Number(payload.warningThresholdPct ?? 80),
    limitExceeded: Boolean(payload.limitExceeded),
    byModel: Array.isArray(payload.byModel) ? payload.byModel as UsageSummary['byModel'] : [],
    recentRuns: Array.isArray(payload.recentRuns) ? payload.recentRuns as UsageSummary['recentRuns'] : [],
  };
}

export function useUsageSummary(connected: boolean) {
  const { rpc, on } = useWs();
  const sessionId = useChatStore((s) => s.sessionId);
  const setSummary = useUsageStore((s) => s.setSummary);
  const setLoading = useUsageStore((s) => s.setLoading);
  const resetUsage = useUsageStore((s) => s.resetUsage);
  const setMaxBudget = useConfigStore((s) => s.setMaxBudget);
  const setBudgetWarningThresholdPct = useConfigStore((s) => s.setBudgetWarningThresholdPct);
  const refreshGenerationRef = useRef(0);

  const refreshUsage = useCallback(async () => {
    setLoading(true);
    try {
      const result = await rpc('usage.summary', sessionId ? { sessionId } : {});
      const summary = normalizeUsageSummary(result);
      setSummary(summary);
      setMaxBudget(summary.monthlyBudgetUsd ?? 0);
      setBudgetWarningThresholdPct(summary.warningThresholdPct);
    } finally {
      setLoading(false);
    }
  }, [rpc, sessionId, setBudgetWarningThresholdPct, setLoading, setMaxBudget, setSummary]);

  useEffect(() => {
    refreshGenerationRef.current += 1;
    if (!connected) {
      resetUsage();
    }

    return () => {
      refreshGenerationRef.current += 1;
    };
  }, [connected, refreshUsage, resetUsage]);

  const guardedRefresh = useCallback(async () => {
    const generation = refreshGenerationRef.current;
    try {
      await refreshUsage();
    } catch (error) {
      if (refreshGenerationRef.current === generation) {
        console.warn('[useUsageSummary] refresh failed:', error);
      }
    }
  }, [refreshUsage]);

  useVisiblePolling(() => {
    void guardedRefresh();
  }, { intervalMs: 15_000, enabled: connected });

  useEffect(() => {
    if (!connected) {
      return;
    }

    const unsubs = [
      on('stream.done', () => {
        void guardedRefresh();
      }),
      on('usage.summary', (payload) => {
        const summary = normalizeUsageSummary(payload);
        setSummary(summary);
        setMaxBudget(summary.monthlyBudgetUsd ?? 0);
        setBudgetWarningThresholdPct(summary.warningThresholdPct);
      }),
    ];

    return () => {
      unsubs.forEach((unsub) => unsub());
    };
  }, [connected, guardedRefresh, on, setBudgetWarningThresholdPct, setMaxBudget, setSummary]);
}
