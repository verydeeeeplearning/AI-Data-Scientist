/**
 * Runtime hook that polls operator-console state from backend RPCs.
 */

import { useCallback, useEffect } from 'react';
import {
  useRuntimeStore,
  type RuntimeRunEntry,
  type RuntimeSessionEntry,
  type RuntimeStatusSnapshot,
  type RuntimeTaskEntry,
} from '../stores/runtimeStore';

type OnFn = (event: string, handler: (payload: Record<string, unknown>) => void) => () => void;
type RpcFn = (method: string, params?: Record<string, unknown>) => Promise<Record<string, unknown>>;

export function useRuntime(on: OnFn, rpc: RpcFn, connected: boolean) {
  const setStatus = useRuntimeStore((s) => s.setStatus);
  const setSessions = useRuntimeStore((s) => s.setSessions);
  const setRuns = useRuntimeStore((s) => s.setRuns);
  const setTasks = useRuntimeStore((s) => s.setTasks);
  const markUpdated = useRuntimeStore((s) => s.markUpdated);
  const resetRuntime = useRuntimeStore((s) => s.resetRuntime);

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
    if (!connected) {
      resetRuntime();
      return;
    }

    let cancelled = false;
    const guardedRefresh = async () => {
      try {
        await refreshRuntime();
      } catch (err) {
        if (!cancelled) {
          console.warn('[useRuntime] refresh failed:', err);
        }
      }
    };

    void guardedRefresh();
    const timer = window.setInterval(() => {
      void guardedRefresh();
    }, 3000);

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
      cancelled = true;
      window.clearInterval(timer);
      unsubs.forEach((unsub) => unsub());
    };
  }, [connected, on, refreshRuntime, resetRuntime]);
}
