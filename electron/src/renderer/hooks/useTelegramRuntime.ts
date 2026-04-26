import { useEffect } from 'react';

import { useTelegramStore } from '../stores/telegramStore';
import type { RpcFn } from '../components/settings/types';

type EventSubscriber = (
  event: string,
  handler: (payload: Record<string, unknown>) => void,
) => () => void;

export function useTelegramRuntime(
  on: EventSubscriber,
  rpc: RpcFn,
  connected: boolean,
): void {
  const applyStatusEvent = useTelegramStore((state) => state.applyStatusEvent);
  const applyPairedEvent = useTelegramStore((state) => state.applyPairedEvent);
  const refreshStatus = useTelegramStore((state) => state.refreshStatus);

  useEffect(() => {
    if (!connected) {
      return;
    }
    let cancelled = false;
    void refreshStatus(rpc).catch((error) => {
      if (!cancelled) {
        console.warn('[useTelegramRuntime] telegram.status failed:', error);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [connected, refreshStatus, rpc]);

  useEffect(() => {
    const unsubs = [
      on('telegram.statusChanged', (payload) => {
        applyStatusEvent(payload);
      }),
      on('telegram.paired', (payload) => {
        applyPairedEvent(payload);
      }),
    ];
    return () => {
      for (const unsubscribe of unsubs) {
        unsubscribe();
      }
    };
  }, [applyPairedEvent, applyStatusEvent, on]);
}
