"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.subscribeToMissionContextUpdates = subscribeToMissionContextUpdates;
function isMissionContextUpdate(payload) {
    if (typeof payload !== 'object' || payload === null) {
        return false;
    }
    const candidate = payload;
    return (candidate.sessionId === undefined
        || candidate.sessionId === null
        || typeof candidate.sessionId === 'string');
}
function getScopedSessionId(payload) {
    if (typeof payload.sessionId !== 'string') {
        return null;
    }
    const normalized = payload.sessionId.trim();
    return normalized ? normalized : null;
}
function toMissionContextPatch(payload) {
    const { sessionId: _sessionId, delta: _delta, ...patch } = payload;
    return patch;
}
function subscribeToMissionContextUpdates(on, sessionId, handler) {
    return on('mission.context.updated', (payload) => {
        if (!isMissionContextUpdate(payload)) {
            return;
        }
        const payloadSessionId = getScopedSessionId(payload);
        if (payloadSessionId && payloadSessionId !== sessionId) {
            return;
        }
        handler(toMissionContextPatch(payload));
    });
}
