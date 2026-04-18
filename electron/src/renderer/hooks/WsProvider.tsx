/**
 * WsProvider — single WebSocket instance shared via React Context.
 *
 * WIRE-07 fix: useChat and useAgent previously each called useWebSocket(port),
 * creating two independent connections. Now they share one via useWs().
 */

import { createContext, useContext, type ReactNode } from 'react';
import { useWebSocket } from './useWebSocket';

type WsValue = ReturnType<typeof useWebSocket>;

const WsContext = createContext<WsValue | null>(null);

export function WsProvider({
  port,
  token,
  children,
}: {
  port: number;
  token?: string;
  children: ReactNode;
}) {
  const ws = useWebSocket(port, token);
  return <WsContext.Provider value={ws}>{children}</WsContext.Provider>;
}

export function useWs(): WsValue {
  const ctx = useContext(WsContext);
  if (!ctx) {
    throw new Error('useWs must be used within a WsProvider');
  }
  return ctx;
}
