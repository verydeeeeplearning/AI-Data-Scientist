"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.__test = void 0;
exports.parseMobileBootstrapParams = parseMobileBootstrapParams;
exports.describeMobileConnection = describeMobileConnection;
exports.MobileRuntimeProvider = MobileRuntimeProvider;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const useAgent_1 = require("../renderer/hooks/useAgent");
const useRuntime_1 = require("../renderer/hooks/useRuntime");
const WsProvider_1 = require("../renderer/hooks/WsProvider");
const useWorkflow_1 = require("../renderer/hooks/useWorkflow");
const approvalAdapter_1 = require("./approvals/approvalAdapter");
const DEFAULT_BACKEND_PORT = 18790;
function parseMobileBootstrapParams(search, defaultPort = DEFAULT_BACKEND_PORT) {
    const params = new URLSearchParams(search);
    const parsedPort = Number.parseInt(params.get('port') ?? '', 10);
    const port = Number.isFinite(parsedPort) && parsedPort > 0 ? parsedPort : defaultPort;
    const token = params.get('token')?.trim() || undefined;
    return { port, token };
}
function describeMobileConnection(status, reason) {
    if (status === 'connected') {
        return {
            tone: 'success',
            labelKey: 'status.connected',
            detailKey: 'connection.detail.live',
        };
    }
    if (status === 'connecting') {
        return {
            tone: 'warning',
            labelKey: 'status.connecting',
            detailKey: reason === 'reconnecting'
                ? 'connection.detail.reconnecting'
                : 'connection.detail.waiting',
        };
    }
    return {
        tone: 'danger',
        labelKey: 'status.disconnected',
        detailKey: reason === 'network_error'
            ? 'connection.detail.network'
            : reason === 'backend_crashed'
                ? 'connection.detail.backend'
                : 'connection.detail.waiting',
    };
}
function MobileRuntimeBootstrap({ children, }) {
    const { status, rpc, on } = (0, WsProvider_1.useWs)();
    (0, useAgent_1.useAgent)();
    (0, useRuntime_1.useRuntime)(on, rpc, status === 'connected');
    (0, useWorkflow_1.useWorkflow)(on, rpc, status === 'connected');
    (0, react_1.useEffect)(() => {
        if (status !== 'connected') {
            return;
        }
        void (0, approvalAdapter_1.flushQueuedMobileApprovals)(rpc).catch(() => undefined);
    }, [rpc, status]);
    (0, react_1.useEffect)(() => {
        if (typeof window === 'undefined') {
            return;
        }
        const handleOnline = () => {
            if (status !== 'connected') {
                return;
            }
            void (0, approvalAdapter_1.flushQueuedMobileApprovals)(rpc).catch(() => undefined);
        };
        const handleServiceWorkerMessage = (event) => {
            const payload = event.data;
            if (!payload || typeof payload !== 'object') {
                return;
            }
            if (payload.type !== 'ds-agent-outbox-flush') {
                return;
            }
            if (status !== 'connected') {
                return;
            }
            void (0, approvalAdapter_1.flushQueuedMobileApprovals)(rpc).catch(() => undefined);
        };
        window.addEventListener('online', handleOnline);
        navigator.serviceWorker?.addEventListener('message', handleServiceWorkerMessage);
        return () => {
            window.removeEventListener('online', handleOnline);
            navigator.serviceWorker?.removeEventListener('message', handleServiceWorkerMessage);
        };
    }, [rpc, status]);
    return (0, jsx_runtime_1.jsx)(react_1.Fragment, { children: children });
}
function MobileRuntimeProvider({ children, search, }) {
    const params = parseMobileBootstrapParams(search ?? (typeof window === 'undefined' ? '' : window.location.search));
    return ((0, jsx_runtime_1.jsx)(WsProvider_1.WsProvider, { port: params.port, token: params.token, children: (0, jsx_runtime_1.jsx)(MobileRuntimeBootstrap, { children: children }) }));
}
exports.__test = {
    describeMobileConnection,
    parseMobileBootstrapParams,
};
