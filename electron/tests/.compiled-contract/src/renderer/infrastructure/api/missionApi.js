"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.fetchCurrentMissionContext = fetchCurrentMissionContext;
exports.requestAgentPause = requestAgentPause;
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
async function fetchCurrentMissionContext(sessionId) {
    const query = new URLSearchParams({ sessionId });
    const response = await fetch(`${getBackendBaseUrl()}/api/mission/current?${query.toString()}`, {
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
        throw new Error(extractErrorMessage(payload, `Mission context request failed with status ${response.status}`));
    }
    const payload = (await response.json());
    return payload.mission;
}
async function requestAgentPause(input) {
    const response = await fetch(`${getBackendBaseUrl()}/api/mission/pause`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            sessionId: input.sessionId,
            reason: input.reason,
        }),
    });
    if (!response.ok) {
        let payload = null;
        try {
            payload = await response.json();
        }
        catch {
            // Ignore non-JSON error bodies.
        }
        throw new Error(extractErrorMessage(payload, `Mission pause request failed with status ${response.status}`));
    }
    const payload = (await response.json());
    return {
        paused: payload.paused,
        previousStatus: payload.previousStatus,
    };
}
