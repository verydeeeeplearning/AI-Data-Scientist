import { useCallback, useState } from 'react';
import { useWs } from './WsProvider';

export interface PortfolioEntryView {
  entry_id: string;
  task_contract_id: string;
  quadrant: string;
  priority: string;
  sla_deadline: string | null;
  parent_run_id: string | null;
  wait_condition_id: string | null;
  monitoring_metric_ref: string | null;
  tags: string[];
  updated_at: string;
}

export interface PortfolioSlotView {
  active: number;
  max: number;
  available: number;
}

export interface PortfolioOverview {
  active: PortfolioEntryView[];
  waiting: PortfolioEntryView[];
  monitoring: PortfolioEntryView[];
  candidates: PortfolioEntryView[];
  slots: PortfolioSlotView;
  error?: string;
}

const EMPTY_OVERVIEW: PortfolioOverview = {
  active: [],
  waiting: [],
  monitoring: [],
  candidates: [],
  slots: { active: 0, max: 3, available: 3 },
};

export function usePortfolio() {
  const { rpc } = useWs();
  const [overview, setOverview] = useState<PortfolioOverview>(EMPTY_OVERVIEW);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await rpc('portfolio.overview', { limit: 20 });
      setOverview(result as unknown as PortfolioOverview);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [rpc]);

  const pause = useCallback(
    async (entryId: string, waitKind: string, waitSpec: object, reason: string) => {
      await rpc('portfolio.pause', { entryId, waitKind, waitSpec, reason });
      await refresh();
    },
    [rpc, refresh],
  );

  const resume = useCallback(
    async (entryId: string, runId: string, reason: string) => {
      await rpc('portfolio.resume', { entryId, runId, reason });
      await refresh();
    },
    [rpc, refresh],
  );

  const setSla = useCallback(
    async (entryId: string, priority: string, deadline?: string) => {
      await rpc('portfolio.setSla', { entryId, priority, deadline: deadline || '' });
      await refresh();
    },
    [rpc, refresh],
  );

  return { overview, loading, error, refresh, pause, resume, setSla };
}
