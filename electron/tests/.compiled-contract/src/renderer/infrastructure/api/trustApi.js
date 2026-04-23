"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.fetchTrustByResultId = fetchTrustByResultId;
const trustMapper_1 = require("../../application/trust/trustMapper");
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
async function fetchTrustByResultId(resultId) {
    const encodedResultId = encodeURIComponent(resultId);
    const response = await fetch(`${getBackendBaseUrl()}/api/trust/${encodedResultId}`, {
        cache: 'no-store',
    });
    if (!response.ok) {
        let payload = null;
        try {
            payload = await response.json();
        }
        catch {
            // Ignore non-JSON error bodies.
        }
        throw new Error(extractErrorMessage(payload, `Trust request failed with status ${response.status}`));
    }
    const payload = await response.json();
    return (0, trustMapper_1.mapTrustPayload)(resultId, payload);
}
