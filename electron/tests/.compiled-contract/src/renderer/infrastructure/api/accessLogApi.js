"use strict";
/**
 * HTTP adapter for the owner access-log surface.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.fetchAccessLogs = fetchAccessLogs;
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
function parseEntry(raw) {
    const metadata = raw.metadata && typeof raw.metadata === 'object' && !Array.isArray(raw.metadata)
        ? raw.metadata
        : {};
    return {
        entryId: String(raw.entryId ?? raw.entry_id ?? ''),
        resourceType: String(raw.resourceType ?? raw.resource_type ?? ''),
        resourceId: String(raw.resourceId ?? raw.resource_id ?? ''),
        action: String(raw.action ?? ''),
        actorRef: String(raw.actorRef ?? raw.actor_ref ?? ''),
        allowed: Boolean(raw.allowed),
        role: typeof raw.role === 'string' && raw.role.trim()
            ? raw.role
            : null,
        reason: typeof raw.reason === 'string' && raw.reason.trim()
            ? raw.reason
            : null,
        metadata,
        createdAt: typeof raw.createdAt === 'number'
            ? raw.createdAt
            : typeof raw.created_at === 'number'
                ? raw.created_at
                : 0,
    };
}
async function fetchAccessLogs(options = {}) {
    const params = new URLSearchParams();
    params.set('operatorId', options.operatorId?.trim() || 'local-user');
    if (options.resourceType?.trim())
        params.set('resourceType', options.resourceType.trim());
    if (typeof options.since === 'number' && Number.isFinite(options.since)) {
        params.set('since', String(options.since));
    }
    if (typeof options.until === 'number' && Number.isFinite(options.until)) {
        params.set('until', String(options.until));
    }
    if (typeof options.limit === 'number' && Number.isFinite(options.limit)) {
        params.set('limit', String(options.limit));
    }
    const response = await fetch(`${getBackendBaseUrl()}/api/access-log?${params.toString()}`, {
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
        throw new Error(extractErrorMessage(payload, `Access log request failed with status ${response.status}`));
    }
    const payload = (await response.json());
    if (!Array.isArray(payload.entries)) {
        return [];
    }
    return payload.entries
        .filter((entry) => typeof entry === 'object' && entry !== null)
        .map(parseEntry);
}
