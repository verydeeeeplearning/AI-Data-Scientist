"use strict";
/**
 * WebSocket connection hook for RPC + event streaming.
 *
 * Tracks both connection state and a renderer-friendly disconnect reason so
 * the UI can distinguish reconnect attempts from probable backend crashes.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.useWebSocket = useWebSocket;
const react_1 = require("react");
const eventEnvelope_1 = require("../infrastructure/ws/eventEnvelope");
const eventSchemaRegistry_1 = require("../infrastructure/ws/eventSchemaRegistry");
const i18nStore_1 = require("../stores/i18nStore");
const RECONNECT_DELAY_MS = 2000;
const HEALTHCHECK_TIMEOUT_MS = 1500;
const DEFAULT_RPC_TIMEOUT_MS = 30000;
const HEARTBEAT_INTERVAL_MS = 25000;
const HEARTBEAT_TIMEOUT_MS = 10000;
function isRecord(value) {
    return typeof value === 'object' && value !== null;
}
function normalizeEventEnvelope(msg) {
    const envelopeCandidate = {
        type: msg.event,
        version: msg.version,
        ts: msg.ts,
    };
    if ('payload' in msg) {
        envelopeCandidate.payload = msg.payload;
    }
    if (msg.source !== undefined) {
        envelopeCandidate.source = msg.source;
    }
    if (msg.correlationId !== undefined) {
        envelopeCandidate.correlationId = msg.correlationId;
    }
    return (0, eventEnvelope_1.parseEnvelope)(envelopeCandidate);
}
async function classifyDisconnectReason(port) {
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
        return 'network_error';
    }
    const healthy = await probeBackendHealth(port);
    return healthy ? 'ws_closed' : 'backend_crashed';
}
async function probeBackendHealth(port, attempts = 2) {
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
async function fetchBackendHealth(port) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), HEALTHCHECK_TIMEOUT_MS);
    try {
        const response = await fetch(`http://127.0.0.1:${port}/health`, {
            cache: 'no-store',
            signal: controller.signal,
        });
        return response.ok;
    }
    catch {
        return false;
    }
    finally {
        window.clearTimeout(timeout);
    }
}
function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
}
function wsMessage(key, vars) {
    return (0, i18nStore_1.translateKey)(key, vars);
}
function useWebSocket(port, token) {
    const wsRef = (0, react_1.useRef)(null);
    const [status, setStatus] = (0, react_1.useState)('disconnected');
    const [disconnectReason, setDisconnectReason] = (0, react_1.useState)('unknown');
    const [lastConnectedAt, setLastConnectedAt] = (0, react_1.useState)(null);
    const [reconnectEpoch, setReconnectEpoch] = (0, react_1.useState)(0);
    const pendingRef = (0, react_1.useRef)(new Map());
    const listenersRef = (0, react_1.useRef)(new Map());
    const reconnectTimer = (0, react_1.useRef)();
    const heartbeatTimerRef = (0, react_1.useRef)(null);
    const heartbeatInFlightRef = (0, react_1.useRef)(false);
    const disposedRef = (0, react_1.useRef)(false);
    const manualCloseRef = (0, react_1.useRef)(false);
    const everConnectedRef = (0, react_1.useRef)(false);
    const disconnectEpochRef = (0, react_1.useRef)(0);
    const idCounterRef = (0, react_1.useRef)(0);
    const rejectPending = (0, react_1.useCallback)((message) => {
        for (const [id, pending] of pendingRef.current.entries()) {
            clearTimeout(pending.timer);
            pending.reject(new Error(message));
            pendingRef.current.delete(id);
        }
    }, []);
    const nextId = (0, react_1.useCallback)(() => {
        idCounterRef.current += 1;
        return `r${idCounterRef.current}-${Date.now().toString(36)}`;
    }, []);
    const rpc = (0, react_1.useCallback)((method, params, options) => {
        return new Promise((resolve, reject) => {
            const ws = wsRef.current;
            if (!ws || ws.readyState !== WebSocket.OPEN) {
                reject(new Error(wsMessage('common.webSocket.notConnected')));
                return;
            }
            const id = nextId();
            const req = { type: 'req', id, method, params };
            const timeoutMs = options?.timeoutMs ?? DEFAULT_RPC_TIMEOUT_MS;
            const timer = setTimeout(() => {
                if (pendingRef.current.has(id)) {
                    clearTimeout(timer);
                    pendingRef.current.delete(id);
                    reject(new Error(wsMessage('common.webSocket.timeout', { method })));
                }
            }, timeoutMs);
            pendingRef.current.set(id, { resolve, reject, timer });
            try {
                ws.send(JSON.stringify(req));
            }
            catch (error) {
                clearTimeout(timer);
                pendingRef.current.delete(id);
                reject(error instanceof Error
                    ? error
                    : new Error(wsMessage('common.webSocket.sendFailed')));
            }
        });
    }, [nextId]);
    const clearHeartbeat = (0, react_1.useCallback)(() => {
        if (heartbeatTimerRef.current !== null) {
            clearInterval(heartbeatTimerRef.current);
            heartbeatTimerRef.current = null;
        }
        heartbeatInFlightRef.current = false;
    }, []);
    const startHeartbeat = (0, react_1.useCallback)((ws) => {
        clearHeartbeat();
        heartbeatTimerRef.current = setInterval(() => {
            if (disposedRef.current || wsRef.current !== ws || ws.readyState !== WebSocket.OPEN) {
                clearHeartbeat();
                return;
            }
            if (heartbeatInFlightRef.current) {
                console.warn('[ws] heartbeat still pending, forcing reconnect');
                ws.close();
                return;
            }
            heartbeatInFlightRef.current = true;
            rpc('ping', undefined, { timeoutMs: HEARTBEAT_TIMEOUT_MS })
                .catch((error) => {
                if (disposedRef.current || wsRef.current !== ws || ws.readyState !== WebSocket.OPEN) {
                    return;
                }
                console.warn('[ws] heartbeat missed, forcing reconnect:', error);
                ws.close();
            })
                .finally(() => {
                if (wsRef.current === ws) {
                    heartbeatInFlightRef.current = false;
                }
            });
        }, HEARTBEAT_INTERVAL_MS);
    }, [clearHeartbeat, rpc]);
    const connect = (0, react_1.useCallback)(() => {
        if (disposedRef.current)
            return;
        if (wsRef.current?.readyState === WebSocket.OPEN
            || wsRef.current?.readyState === WebSocket.CONNECTING) {
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
            if (wsRef.current !== ws)
                return;
            console.log('[ws] connected');
            manualCloseRef.current = false;
            everConnectedRef.current = true;
            setStatus('connected');
            setDisconnectReason('unknown');
            setLastConnectedAt(Date.now());
            setReconnectEpoch((epoch) => epoch + 1);
            startHeartbeat(ws);
        };
        ws.onmessage = (ev) => {
            try {
                const msg = JSON.parse(ev.data);
                if (msg.type === 'res') {
                    const pending = pendingRef.current.get(msg.id);
                    if (pending) {
                        clearTimeout(pending.timer);
                        pendingRef.current.delete(msg.id);
                        if (msg.ok) {
                            pending.resolve(msg.payload ?? {});
                        }
                        else {
                            pending.reject(new Error(msg.error?.message ?? wsMessage('common.webSocket.rpcError')));
                        }
                    }
                }
                else if (msg.type === 'event') {
                    try {
                        const envelope = normalizeEventEnvelope(msg);
                        let payload;
                        if ((0, eventSchemaRegistry_1.getEventSchema)(envelope.type)) {
                            const validation = (0, eventSchemaRegistry_1.validateEventPayload)(envelope.type, envelope.payload);
                            if (!validation.ok) {
                                console.warn('[ws] dropped invalid event payload:', {
                                    event: envelope.type,
                                    reason: validation.reason,
                                    payload: envelope.payload,
                                });
                                return;
                            }
                            payload = validation.payload;
                        }
                        else {
                            if (!isRecord(envelope.payload)) {
                                console.warn('[ws] dropped non-object event payload:', {
                                    event: envelope.type,
                                    payload: envelope.payload,
                                });
                                return;
                            }
                            payload = envelope.payload;
                        }
                        const handlers = listenersRef.current.get(envelope.type);
                        if (handlers) {
                            for (const handler of [...handlers]) {
                                handler(payload);
                            }
                        }
                    }
                    catch (error) {
                        if (error instanceof eventEnvelope_1.WsEnvelopeError) {
                            console.warn('[ws] dropped malformed event envelope:', error.code, error.message);
                            return;
                        }
                        console.warn('[ws] event dispatch failed:', error);
                    }
                }
            }
            catch (error) {
                console.error('[ws] parse error:', error);
            }
        };
        ws.onclose = () => {
            if (wsRef.current !== ws)
                return;
            console.log('[ws] disconnected');
            clearHeartbeat();
            wsRef.current = null;
            rejectPending(wsMessage('common.webSocket.disconnected'));
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
            reconnectTimer.current = setTimeout(() => {
                if (disposedRef.current) {
                    return;
                }
                connect();
            }, RECONNECT_DELAY_MS);
        };
        ws.onerror = (error) => {
            if (wsRef.current !== ws)
                return;
            console.error('[ws] error:', error);
            if (typeof navigator !== 'undefined' && navigator.onLine === false) {
                setDisconnectReason('network_error');
            }
        };
        wsRef.current = ws;
    }, [clearHeartbeat, port, rejectPending, startHeartbeat, token]);
    (0, react_1.useEffect)(() => {
        disposedRef.current = false;
        connect();
        return () => {
            disposedRef.current = true;
            clearTimeout(reconnectTimer.current);
            clearHeartbeat();
            rejectPending(wsMessage('common.webSocket.closed'));
            if (wsRef.current) {
                manualCloseRef.current = true;
                wsRef.current.close();
                wsRef.current = null;
            }
        };
    }, [clearHeartbeat, connect, rejectPending]);
    const on = (0, react_1.useCallback)((event, handler) => {
        if (!listenersRef.current.has(event)) {
            listenersRef.current.set(event, new Set());
        }
        listenersRef.current.get(event).add(handler);
        return () => {
            listenersRef.current.get(event)?.delete(handler);
        };
    }, []);
    return { status, disconnectReason, rpc, on, lastConnectedAt, reconnectEpoch };
}
