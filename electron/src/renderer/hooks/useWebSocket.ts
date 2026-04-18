/**
 * WebSocket connection hook for RPC + event streaming.
 *
 * Tracks both connection state and a renderer-friendly disconnect reason so
 * the UI can distinguish reconnect attempts from probable backend crashes.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected';
export type DisconnectReason =
  | 'unknown'
  | 'ws_closed'
  | 'backend_crashed'
  | 'network_error'
  | 'reconnecting';

interface WsRequest {
  type: 'req';
  id: string;
  method: string;
  params?: Record<string, unknown>;
}

interface WsResponse {
  type: 'res';
  id: string;
  ok: boolean;
  payload?: Record<string, unknown>;
  error?: { code: string; message: string };
}

interface WsEvent {
  type: 'event';
  event: string;
  payload?: Record<string, unknown>;
  ts?: number;
}

type WsMessage = WsResponse | WsEvent;
type EventHandler = (payload: Record<string, unknown>) => void;

const RECONNECT_DELAY_MS = 2000;
const HEALTHCHECK_TIMEOUT_MS = 1500;

let idCounter = 0;

function nextId(): string {
  return `r${++idCounter}-${Date.now().toString(36)}`;
}

async function classifyDisconnectReason(port: number): Promise<DisconnectReason> {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    return 'network_error';
  }

  const healthy = await probeBackendHealth(port);
  return healthy ? 'ws_closed' : 'backend_crashed';
}

async function probeBackendHealth(port: number, attempts = 2): Promise<boolean> {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (await fetchBackendHealth(port)) {
      return true;
    }
    if (attempt < attempts - 1) {
      await sleep(300);
    }
  }
  return false;
}

async function fetchBackendHealth(port: number): Promise<boolean> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), HEALTHCHECK_TIMEOUT_MS);

  try {
    const response = await fetch(`http://127.0.0.1:${port}/health`, {
      cache: 'no-store',
      signal: controller.signal,
    });
    return response.ok;
  } catch {
    return false;
  } finally {
    window.clearTimeout(timeout);
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function useWebSocket(port: number, token?: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [disconnectReason, setDisconnectReason] = useState<DisconnectReason>('unknown');
  const pendingRef = useRef<Map<string, {
    resolve: (v: Record<string, unknown>) => void;
    reject: (e: Error) => void;
    timer: ReturnType<typeof setTimeout>;
  }>>(new Map());
  const listenersRef = useRef<Map<string, Set<EventHandler>>>(new Map());
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const disposedRef = useRef(false);
  const manualCloseRef = useRef(false);
  const everConnectedRef = useRef(false);
  const disconnectEpochRef = useRef(0);

  const rejectPending = useCallback((message: string) => {
    for (const [id, pending] of pendingRef.current.entries()) {
      clearTimeout(pending.timer);
      pending.reject(new Error(message));
      pendingRef.current.delete(id);
    }
  }, []);

  const connect = useCallback(() => {
    if (disposedRef.current) return;
    if (
      wsRef.current?.readyState === WebSocket.OPEN
      || wsRef.current?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    clearTimeout(reconnectTimer.current);
    setStatus('connecting');
    setDisconnectReason(everConnectedRef.current ? 'reconnecting' : 'unknown');

    const url = token
      ? `ws://127.0.0.1:${port}/ws?token=${encodeURIComponent(token)}`
      : `ws://127.0.0.1:${port}/ws`;
    const ws = new WebSocket(url);

    ws.onopen = () => {
      if (wsRef.current !== ws) return;
      console.log('[ws] connected');
      manualCloseRef.current = false;
      everConnectedRef.current = true;
      setStatus('connected');
      setDisconnectReason('unknown');
    };

    ws.onmessage = (ev) => {
      try {
        const msg: WsMessage = JSON.parse(ev.data);

        if (msg.type === 'res') {
          const pending = pendingRef.current.get(msg.id);
          if (pending) {
            clearTimeout(pending.timer);
            pendingRef.current.delete(msg.id);
            if (msg.ok) {
              pending.resolve(msg.payload ?? {});
            } else {
              pending.reject(new Error(msg.error?.message ?? 'RPC error'));
            }
          }
        } else if (msg.type === 'event') {
          const handlers = listenersRef.current.get(msg.event);
          if (handlers) {
            for (const handler of handlers) {
              handler(msg.payload ?? {});
            }
          }
        }
      } catch (error) {
        console.error('[ws] parse error:', error);
      }
    };

    ws.onclose = () => {
      if (wsRef.current !== ws) return;
      console.log('[ws] disconnected');
      wsRef.current = null;
      rejectPending('WebSocket disconnected');

      if (disposedRef.current || manualCloseRef.current) {
        setStatus('disconnected');
        return;
      }

      const epoch = ++disconnectEpochRef.current;
      setStatus('connecting');
      setDisconnectReason('reconnecting');

      void classifyDisconnectReason(port)
        .then((reason) => {
          if (disposedRef.current || disconnectEpochRef.current !== epoch) {
            return;
          }
          setDisconnectReason(reason);
        })
        .catch((error) => {
          console.warn('[ws] disconnect classification failed:', error);
        });

      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
    };

    ws.onerror = (error) => {
      if (wsRef.current !== ws) return;
      console.error('[ws] error:', error);
      if (typeof navigator !== 'undefined' && navigator.onLine === false) {
        setDisconnectReason('network_error');
      }
    };

    wsRef.current = ws;
  }, [port, token, rejectPending]);

  useEffect(() => {
    disposedRef.current = false;
    connect();
    return () => {
      disposedRef.current = true;
      clearTimeout(reconnectTimer.current);
      rejectPending('WebSocket closed');
      if (wsRef.current) {
        manualCloseRef.current = true;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect, rejectPending]);

  const rpc = useCallback(
    (method: string, params?: Record<string, unknown>): Promise<Record<string, unknown>> => {
      return new Promise((resolve, reject) => {
        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) {
          reject(new Error('WebSocket not connected'));
          return;
        }

        const id = nextId();
        const req: WsRequest = { type: 'req', id, method, params };

        const timer = setTimeout(() => {
          if (pendingRef.current.has(id)) {
            clearTimeout(timer);
            pendingRef.current.delete(id);
            reject(new Error(`RPC timeout: ${method}`));
          }
        }, 30_000);

        pendingRef.current.set(id, { resolve, reject, timer });
        try {
          ws.send(JSON.stringify(req));
        } catch (error) {
          clearTimeout(timer);
          pendingRef.current.delete(id);
          reject(error instanceof Error ? error : new Error('WebSocket send failed'));
        }
      });
    },
    []
  );

  const on = useCallback((event: string, handler: EventHandler) => {
    if (!listenersRef.current.has(event)) {
      listenersRef.current.set(event, new Set());
    }
    listenersRef.current.get(event)!.add(handler);

    return () => {
      listenersRef.current.get(event)?.delete(handler);
    };
  }, []);

  return { status, disconnectReason, rpc, on };
}
