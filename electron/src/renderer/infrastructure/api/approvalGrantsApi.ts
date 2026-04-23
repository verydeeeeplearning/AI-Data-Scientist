/**
 * HTTP adapter for approval grants (W2-F).
 *
 * Implements the application-layer ports defined in
 * `application/approval/approvalGrantsPort.ts` against the backend routes
 * exposed by `src/ds_agent/api/routes/approval_grants.py`.
 */

import type {
  ApprovalGrantSummary,
  ListApprovalGrantsOptions,
  ListApprovalGrantsPort,
  RevokeApprovalGrantPort,
} from '../../application/approval/approvalGrantsPort';

function getBackendBaseUrl(): string {
  const params = new URLSearchParams(window.location.search);
  const rawPort = params.get('port');
  const port = rawPort ? Number.parseInt(rawPort, 10) : 18790;
  return `http://127.0.0.1:${Number.isFinite(port) ? port : 18790}`;
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') {
    return fallback;
  }
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  return fallback;
}

function parseGrant(raw: Record<string, unknown>): ApprovalGrantSummary {
  const scope = raw.scope === 'workspace' ? 'workspace' : 'session';
  const status =
    raw.status === 'expired' || raw.status === 'revoked'
      ? (raw.status as 'expired' | 'revoked')
      : 'active';
  const affected = Array.isArray(raw.affectedScopes)
    ? raw.affectedScopes.filter((entry): entry is string => typeof entry === 'string')
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

export const fetchApprovalGrants: ListApprovalGrantsPort = async (
  options?: ListApprovalGrantsOptions,
): Promise<ApprovalGrantSummary[]> => {
  const params = new URLSearchParams();
  if (options?.sessionId) params.set('sessionId', options.sessionId);
  if (options?.workspaceId) params.set('workspaceId', options.workspaceId);
  if (options?.includeInactive) params.set('includeInactive', 'true');
  const url = `${getBackendBaseUrl()}/api/approval/grants${params.toString() ? `?${params.toString()}` : ''}`;
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // Non-JSON body is acceptable here.
    }
    throw new Error(
      extractErrorMessage(payload, `Approval grant request failed with status ${response.status}`),
    );
  }
  const payload = (await response.json()) as { grants?: unknown[] };
  if (!Array.isArray(payload.grants)) {
    return [];
  }
  return payload.grants
    .filter((entry): entry is Record<string, unknown> => typeof entry === 'object' && entry !== null)
    .map(parseGrant);
};

export const revokeApprovalGrant: RevokeApprovalGrantPort = async (
  grantId: string,
): Promise<ApprovalGrantSummary> => {
  const encoded = encodeURIComponent(grantId);
  const response = await fetch(`${getBackendBaseUrl()}/api/approval/grants/${encoded}/revoke`, {
    method: 'POST',
  });
  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // Ignore.
    }
    throw new Error(
      extractErrorMessage(payload, `Revoke request failed with status ${response.status}`),
    );
  }
  const payload = (await response.json()) as { grant?: Record<string, unknown> };
  if (!payload.grant) {
    throw new Error('Revoke response missing grant payload');
  }
  return parseGrant(payload.grant);
};
