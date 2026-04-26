/**
 * Runtime hook that polls operator-console state from backend RPCs.
 */

import { useCallback, useEffect, useRef } from 'react';
import {
  useRuntimeStore,
  type RuntimeRunEntry,
  type RuntimeSessionEntry,
  type RuntimeStatusSnapshot,
  type RuntimeTaskEntry,
} from '../stores/runtimeStore';
import { useVisiblePolling } from './useVisiblePolling';

type OnFn = (event: string, handler: (payload: Record<string, unknown>) => void) => () => void;
type RpcFn = (method: string, params?: Record<string, unknown>) => Promise<Record<string, unknown>>;

export function useRuntime(on: OnFn, rpc: RpcFn, connected: boolean) {
  const setStatus = useRuntimeStore((s) => s.setStatus);
  const setSessions = useRuntimeStore((s) => s.setSessions);
  const setRuns = useRuntimeStore((s) => s.setRuns);
  const setTasks = useRuntimeStore((s) => s.setTasks);
  const markUpdated = useRuntimeStore((s) => s.markUpdated);
  const resetRuntime = useRuntimeStore((s) => s.resetRuntime);
  const refreshGenerationRef = useRef(0);

  const refreshRuntime = useCallback(async () => {
    const [statusResult, sessionsResult, runsResult, tasksResult] = await Promise.all([
      rpc('status.get'),
      rpc('session.list', { limit: 12 }),
      rpc('run.list', { limit: 12 }),
      rpc('task.list', { limit: 12 }),
    ]);

    setStatus((statusResult as unknown as RuntimeStatusSnapshot) ?? null);
    setSessions((sessionsResult.sessions as RuntimeSessionEntry[]) ?? []);
    setRuns((runsResult.runs as RuntimeRunEntry[]) ?? []);
    setTasks((tasksResult.tasks as RuntimeTaskEntry[]) ?? []);
    markUpdated();
  }, [markUpdated, rpc, setRuns, setSessions, setStatus, setTasks]);

  useEffect(() => {
    refreshGenerationRef.current += 1;
    if (!connected) {
      resetRuntime();
    }

    return () => {
      refreshGenerationRef.current += 1;
    };
  }, [connected, refreshRuntime, resetRuntime]);

  const guardedRefresh = useCallback(async () => {
    const generation = refreshGenerationRef.current;
    try {
      await refreshRuntime();
    } catch (err) {
      if (refreshGenerationRef.current === generation) {
        console.warn('[useRuntime] refresh failed:', err);
      }
    }
  }, [refreshRuntime]);

  useVisiblePolling(() => {
    void guardedRefresh();
  }, { intervalMs: 3000, enabled: connected });

  useEffect(() => {
    if (!connected) {
      return;
    }

    const unsubs = [
      on('stream.done', () => {
        void guardedRefresh();
      }),
      on('approval.requested', () => {
        void guardedRefresh();
      }),
      on('approval.resolved', () => {
        void guardedRefresh();
      }),
      on('workspace.changed', () => {
        void guardedRefresh();
      }),
      on('runtime.alert', () => {
        void guardedRefresh();
      }),
    ];

    return () => {
      unsubs.forEach((unsub) => unsub());
    };
  }, [connected, guardedRefresh, on]);
}
