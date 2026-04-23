"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.WsProvider = WsProvider;
exports.useWs = useWs;
const jsx_runtime_1 = require("react/jsx-runtime");
/**
 * WsProvider — single WebSocket instance shared via React Context.
 *
 * WIRE-07 fix: useChat and useAgent previously each called useWebSocket(port),
 * creating two independent connections. Now they share one via useWs().
 */
const react_1 = require("react");
const useWebSocket_1 = require("./useWebSocket");
const WsContext = (0, react_1.createContext)(null);
function WsProvider({ port, token, children, }) {
    const ws = (0, useWebSocket_1.useWebSocket)(port, token);
    return (0, jsx_runtime_1.jsx)(WsContext.Provider, { value: ws, children: children });
}
function useWs() {
    const ctx = (0, react_1.useContext)(WsContext);
    if (!ctx) {
        throw new Error('useWs must be used within a WsProvider');
    }
    return ctx;
}
