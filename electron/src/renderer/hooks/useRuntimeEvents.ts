/**
 * Runtime timeline hook for alert/recovery/operator-visible events.
 */

import { useCallback, useEffect } from 'react';
import {
  useRuntimeEventStore,
  type RuntimeEventEntry,
} from '../stores/runtimeEventStore';

type OnFn = (event: string, handler: (payload: Record<string, unknown>) => void) => () => void;
type RpcFn = (method: string, params?: Record<string, unknown>) => Promise<Record<string, unknown>>;

function normalizeEvent(payload: unknown): RuntimeEventEntry | null {
  if (!payload || typeof payload !== 'object') {
    return null;
  }

  const raw = payload as Record<string, unknown>;
  const eventId = typeof raw.eventId === 'string' ? raw.eventId : '';
  if (!eventId) {
    return null;
  }

  const severity = typeof raw.severity === 'string'
    ? raw.severity
    : 'info';

  return {
    eventId,
    category: typeof raw.category === 'string' ? raw.category : 'runtime',
    kind: typeof raw.kind === 'string' ? raw.kind : 'runtime.event',
    severity: severity as RuntimeEventEntry['severity'],
    message: typeof raw.message === 'string' ? raw.message : '',
    sessionId: typeof raw.sessionId === 'string' ? raw.sessionId : null,
    runId: typeof raw.runId === 'string' ? raw.runId : null,
    surface: typeof raw.surface === 'string' ? raw.surface : 'daemon',
    source: typeof raw.source === 'string' ? raw.source : 'runtime',
    metadata:
      raw.metadata && typeof raw.metadata === 'object'
        ? (raw.metadata as Record<string, unknown>)
        : {},
    createdAt: typeof raw.createdAt === 'number' ? raw.createdAt : Date.now() / 1000,
  };
}

function approvalTimelineEvent(
  payload: Record<string, unknown>,
  kind: 'approval.requested' | 'approval.resolved',
): RuntimeEventEntry | null {
  const approvalId = typeof payload.approvalId === 'string' ? payload.approvalId : '';
  if (!approvalId) {
    return null;
  }

  const status = typeof payload.status === 'string' ? payload.status : 'pending';
  const eventId = `${kind}:${approvalId}:${status}`;
  const message = kind === 'approval.requested'
    ? `Approval requested: ${typeof payload.question === 'string' ? payload.question : 'Operator input required.'}`
    : `Approval ${status}: ${typeof payload.response === 'string' && payload.response ? payload.response : 'response captured'}.`;

  return {
    eventId,
    category: 'approval',
    kind,
    severity: kind === 'approval.requested' ? 'warning' : 'success',
    message,
    sessionId: typeof payload.sessionId === 'string' ? payload.sessionId : null,
    runId: typeof payload.runId === 'string' ? payload.runId : null,
    surface: typeof payload.surface === 'string' ? payload.surface : 'ws',
    source: 'approval_bus',
    metadata: payload,
    createdAt: Date.now() / 1000,
  };
}

export async function fetchRuntimeEvents(rpc: RpcFn): Promise<RuntimeEventEntry[]> {
  const result = await rpc('runtime.events.list', { limit: 60 });
  if (!Array.isArray(result.events)) {
    return [];
  }
  return result.events
    .map(normalizeEvent)
    .filter((event): event is RuntimeEventEntry => event !== null);
}

export function useRuntimeEvents(on: OnFn, rpc: RpcFn, connected: boolean) {
  const setEvents = useRuntimeEventStore((s) => s.setEvents);
  const upsertEvent = useRuntimeEventStore((s) => s.upsertEvent);
  const resetEvents = useRuntimeEventStore((s) => s.resetEvents);

  const refreshEvents = useCallback(async () => {
    setEvents(await fetchRuntimeEvents(rpc));
  }, [rpc, setEvents]);

  useEffect(() => {
    if (!connected) {
      resetEvents();
      return;
    }

    let cancelled = false;
    const guardedRefresh = async () => {
      try {
        await refreshEvents();
      } catch (err) {
        if (!cancelled) {
          console.warn('[useRuntimeEvents] refresh failed:', err);
        }
      }
    };

    void guardedRefresh();
    const timer = window.setInterval(() => {
      void guardedRefresh();
    }, 4000);

    const unsubs = [
      on('runtime.alert', (payload) => {
        const event = normalizeEvent(payload);
        if (event) {
          upsertEvent(event);
        }
      }),
      on('approval.requested', (payload) => {
        const event = approvalTimelineEvent(payload, 'approval.requested');
        if (event) {
          upsertEvent(event);
        }
      }),
      on('approval.resolved', (payload) => {
        const event = approvalTimelineEvent(payload, 'approval.resolved');
        if (event) {
          upsertEvent(event);
        }
      }),
    ];

    return () => {
      cancelled = true;
      window.clearInterval(timer);
      unsubs.forEach((unsub) => unsub());
    };
  }, [connected, on, refreshEvents, resetEvents, upsertEvent]);
}
