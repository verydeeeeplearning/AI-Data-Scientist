import { create } from 'zustand';

export interface UsageModelSummary {
  model: string;
  provider: string;
  costUsd: number;
  runCount: number;
}

export interface UsageRunSummary {
  runId?: string | null;
  sessionId?: string | null;
  provider: string;
  model?: string | null;
  costUsd: number;
  cacheSavingsUsd: number;
  recordedAt: number;
}

export interface UsageSummary {
  actorId: string;
  monthlyCostUsd: number;
  monthlyBudgetUsd: number | null;
  budgetUsedPct: number;
  cacheSavingsUsd: number;
  sessionCostUsd: number;
  todayCostUsd: number;
  remainingBudgetUsd: number | null;
  monthRunCount: number;
  warningLevel: string;
  warningThresholdPct: number;
  limitExceeded: boolean;
  byModel: UsageModelSummary[];
  recentRuns: UsageRunSummary[];
}

interface UsageState {
  summary: UsageSummary | null;
  loading: boolean;
  lastUpdatedAt: number | null;
  setSummary: (summary: UsageSummary) => void;
  setLoading: (loading: boolean) => void;
  resetUsage: () => void;
}

export const useUsageStore = create<UsageState>((set) => ({
  summary: null,
  loading: false,
  lastUpdatedAt: null,

  setSummary: (summary) => set({ summary, lastUpdatedAt: Date.now() }),
  setLoading: (loading) => set({ loading }),
  resetUsage: () => set({ summary: null, loading: false, lastUpdatedAt: null }),
}));
