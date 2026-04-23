"use strict";
/**
 * Backend URL utilities — single source of truth for backend base URL.
 *
 * 4.14 fix: Eliminates hardcoded 'http://127.0.0.1:18790' in renderer components.
 * The actual port is passed from the main process as a URL query parameter.
 * Falls back to 18790 only when running in browser dev mode without a port param.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.getBackendBase = getBackendBase;
function getBackendPort() {
    if (typeof window === 'undefined')
        return 18790;
    const params = new URLSearchParams(window.location.search);
    const port = params.get('port');
    return port ? parseInt(port, 10) : 18790;
}
/**
 * Returns the backend base URL including scheme, host, and port.
 * Example: 'http://127.0.0.1:18790'
 */
function getBackendBase() {
    return `http://127.0.0.1:${getBackendPort()}`;
}
