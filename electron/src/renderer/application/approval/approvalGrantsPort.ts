/**
 * Application-layer ports for approval grants (W2-F).
 *
 * The settings UI consumes these ports; the composition root binds them to
 * the HTTP adapter in `infrastructure/api/approvalGrantsApi.ts`. Components
 * never import from infrastructure directly, satisfying the Clean Arch
 * dependency rule enforced by `lint:arch`.
 */

export type ApprovalGrantScope = 'session' | 'workspace';
export type ApprovalGrantStatus = 'active' | 'expired' | 'revoked';

export interface ApprovalGrantSummary {
  grantId: string;
  approvalId: string;
  scope: ApprovalGrantScope;
  riskCode: string;
  kind: string;
  sessionId: string;
  workspaceId: string | null;
  actor: string | null;
  source: string | null;
  affectedScopes: readonly string[];
  createdAt: number;
  expiresAt: number | null;
  revokedAt: number | null;
  status: ApprovalGrantStatus;
}

export interface ListApprovalGrantsOptions {
  sessionId?: string;
  workspaceId?: string;
  includeInactive?: boolean;
}

export type ListApprovalGrantsPort = (
  options?: ListApprovalGrantsOptions,
) => Promise<ApprovalGrantSummary[]>;

export type RevokeApprovalGrantPort = (
  grantId: string,
) => Promise<ApprovalGrantSummary>;
