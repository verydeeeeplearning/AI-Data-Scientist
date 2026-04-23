"use strict";
/**
 * Backend adapter for the workspace export wizard.
 *
 * Wraps `POST /api/export/file` with the same backend port discovery used by
 * the trust/mission/cards adapters.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.exportWorkspaceFile = exportWorkspaceFile;
function getBackendBaseUrl() {
    const params = new URLSearchParams(window.location.search);
    const rawPort = params.get('port');
    const port = rawPort ? Number.parseInt(rawPort, 10) : 18790;
    return `http://127.0.0.1:${Number.isFinite(port) ? port : 18790}`;
}
function extractErrorMessage(payload, fallback) {
    if (!payload || typeof payload !== 'object') {
        return fallback;
    }
    const detail = payload.detail;
    if (typeof detail === 'string' && detail.trim()) {
        return detail;
    }
    return fallback;
}
async function exportWorkspaceFile(input) {
    const response = await fetch(`${getBackendBaseUrl()}/api/export/file`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            path: input.path,
            format: input.format,
            audience: input.audience,
        }),
    });
    if (!response.ok) {
        let payload = null;
        try {
            payload = await response.json();
        }
        catch {
            // Ignore non-JSON bodies.
        }
        throw new Error(extractErrorMessage(payload, `Export request failed with status ${response.status}`));
    }
    const payload = await response.json();
    return typeof payload === 'object' && payload !== null
        ? payload
        : {};
}
