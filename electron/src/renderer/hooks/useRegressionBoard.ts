import { useCallback, useEffect, useState } from 'react';
import { useWs } from './WsProvider';
import type { RegressionBoardView, RegressionFrozenBaselineView } from '../types/evaluation';

interface RegressionBoardRpcResponse {
  board?: RegressionBoardView;
}

interface FreezeRegressionBaselineRpcResponse {
  baseline?: RegressionFrozenBaselineView;
  board?: RegressionBoardView;
}

export function useRegressionBoard() {
  const { status, rpc, on } = useWs();
  const [board, setBoard] = useState<RegressionBoardView | null>(null);
  const [selectedMode, setSelectedMode] = useState<string | null>(null);
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [freezeLoading, setFreezeLoading] = useState(false);
  const [freezeError, setFreezeError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = (await rpc('eval.regressionBoard', {
        mode: selectedMode ?? undefined,
        domain: selectedDomain ?? undefined,
      })) as RegressionBoardRpcResponse;
      const nextBoard = response.board ?? null;
      setBoard(nextBoard);
      if (nextBoard && selectedDomain && !nextBoard.availableDomains.includes(selectedDomain)) {
        setSelectedDomain(null);
      }
    } catch (err) {
      setBoard(null);
      setError(err instanceof Error ? err.message : 'Regression board unavailable.');
    } finally {
      setLoading(false);
    }
  }, [rpc, selectedDomain, selectedMode]);

  const freezeBaseline = useCallback(
    async (commitSha: string) => {
      setFreezeLoading(true);
      setFreezeError(null);
      try {
        const response = (await rpc('eval.freezeRegressionBaseline', {
          commitSha,
          mode: selectedMode ?? undefined,
          domain: selectedDomain ?? undefined,
          recentWindow: board?.recentWindow ?? 3,
          baselineWindowDays: board?.baselineWindowDays ?? 14,
        })) as FreezeRegressionBaselineRpcResponse;
        if (response.board) {
          setBoard(response.board);
        }
      } catch (err) {
        setFreezeError(err instanceof Error ? err.message : 'Failed to freeze baseline.');
      } finally {
        setFreezeLoading(false);
      }
    },
    [board?.baselineWindowDays, board?.recentWindow, rpc, selectedDomain, selectedMode]
  );

  useEffect(() => {
    if (status === 'connected') {
      void refresh();
      return;
    }
    setBoard(null);
    setLoading(false);
    setError(null);
    setFreezeLoading(false);
    setFreezeError(null);
  }, [refresh, status]);

  useEffect(() => on('stream.done', () => {
    void refresh();
  }), [on, refresh]);

  useEffect(() => on('approval.resolved', () => {
    void refresh();
  }), [on, refresh]);

  useEffect(() => on('runtime.alert', (payload) => {
    const kind = typeof payload.kind === 'string' ? payload.kind : '';
    if (kind.startsWith('regression_alert.') || kind === 'regression_alert.baseline_frozen') {
      void refresh();
    }
  }), [on, refresh]);

  return {
    board,
    selectedMode,
    setSelectedMode,
    selectedDomain,
    setSelectedDomain,
    loading,
    error,
    freezeLoading,
    freezeError,
    refresh,
    freezeBaseline,
  };
}
