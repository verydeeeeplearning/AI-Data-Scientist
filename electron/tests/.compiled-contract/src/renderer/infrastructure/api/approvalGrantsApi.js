"use strict";
/**
 * HTTP adapter for approval grants (W2-F).
 *
 * Implements the application-layer ports defined in
 * `application/approval/approvalGrantsPort.ts` against the backend routes
 * exposed by `src/ds_agent/api/routes/approval_grants.py`.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.revokeApprovalGrant = exports.fetchApprovalGrants = void 0;
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
function parseGrant(raw) {
    const scope = raw.scope === 'workspace' ? 'workspace' : 'session';
    const status = raw.status === 'expired' || raw.status === 'revoked'
        ? raw.status
        : 'active';
    const affected = Array.isArray(raw.affectedScopes)
        ? raw.affectedScopes.filter((entry) => typeof entry === 'string')
        : [];
    return {
        grantId: String(raw.grantId ?? ''),
        approvalId: String(raw.approvalId ?? ''),
        scope,
        riskCode: String(raw.riskCode ?? ''),
        kind: String(raw.kind ?? 'generic'),
        sessionId: String(raw.sessionId ?? ''),
        workspaceId: typeof raw.workspaceId === 'string' ? raw.workspaceId : null,
        actor: typeof raw.actor === 'string' ? raw.actor : null,
        source: typeof raw.source === 'string' ? raw.source : null,
        affectedScopes: affected,
        createdAt: typeof raw.createdAt === 'number' ? raw.createdAt : 0,
        expiresAt: typeof raw.expiresAt === 'number' ? raw.expiresAt : null,
        revokedAt: typeof raw.revokedAt === 'number' ? raw.revokedAt : null,
        status,
    };
}
const fetchApprovalGrants = async (options) => {
    const params = new URLSearchParams();
    if (options?.sessionId)
        params.set('sessionId', options.sessionId);
    if (options?.workspaceId)
        params.set('workspaceId', options.workspaceId);
    if (options?.includeInactive)
        params.set('includeInactive', 'true');
    const url = `${getBackendBaseUrl()}/api/approval/grants${params.toString() ? `?${params.toString()}` : ''}`;
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) {
        let payload = null;
        try {
            payload = await response.json();
        }
        catch {
            // Non-JSON body is acceptable here.
        }
        throw new Error(extractErrorMessage(payload, `Approval grant request failed with status ${response.status}`));
    }
    const payload = (await response.json());
    if (!Array.isArray(payload.grants)) {
        return [];
    }
    return payload.grants
        .filter((entry) => typeof entry === 'object' && entry !== null)
        .map(parseGrant);
};
exports.fetchApprovalGrants = fetchApprovalGrants;
const revokeApprovalGrant = async (grantId) => {
    const encoded = encodeURIComponent(grantId);
    const response = await fetch(`${getBackendBaseUrl()}/api/approval/grants/${encoded}/revoke`, {
        method: 'POST',
    });
    if (!response.ok) {
        let payload = null;
        try {
            payload = await response.json();
        }
        catch {
            // Ignore.
        }
        throw new Error(extractErrorMessage(payload, `Revoke request failed with status ${response.status}`));
    }
    const payload = (await response.json());
    if (!payload.grant) {
        throw new Error('Revoke response missing grant payload');
    }
    return parseGrant(payload.grant);
};
exports.revokeApprovalGrant = revokeApprovalGrant;
