/**
 * Mobile approval adapter.
 *
 * Pure functions that translate between the renderer-shared `ApprovalRequest`
 * shape (defined in `renderer/stores/workflowStore`) and the mobile UI, and
 * submit decisions through the same WebSocket RPC port the desktop uses.
 *
 * Business logic for approvals lives in `application/`. This module is only
 * an adapter — it does NOT implement approve/reject semantics, nor does it
 * decide who is allowed to act. It composes the shared `approval.resolve`
 * RPC the renderer already calls.
 */

import type { ApprovalRequest } from '../../renderer/stores/workflowStore';
import {
  indexedDbOutbox,
  registerOutboxBackgroundSync,
  type IndexedDbOutbox,
  type OutboxItem,
} from '../outbox/indexedDbOutbox';

export type RpcPort = (
  method: string,
  params?: Record<string, unknown>,
) => Promise<Record<string, unknown>>;

export type ApprovalDecision = 'approved' | 'rejected';

export interface MobileApprovalView {
  readonly approvalId: string;
  readonly question: string;
  readonly kind: string;
  readonly options: readonly string[];
  readonly defaultResponse: string | null;
  readonly sessionId: string;
  readonly runId: string | null;
  readonly risk: 'low' | 'medium' | 'high' | null;
  readonly proposalType: string | null;
  readonly targetId: string | null;
  readonly requiresConfirmation: boolean;
  readonly createdAt: number;
}

const RISK_VALUES: readonly string[] = ['low', 'medium', 'high'];

function pickString(meta: Record<string, unknown> | undefined, key: string): string | null {
  if (!meta) {
    return null;
  }
  const raw = meta[key];
  return typeof raw === 'string' && raw.length > 0 ? raw : null;
}

function pickRisk(
  meta: Record<string, unknown> | undefined,
): 'low' | 'medium' | 'high' | null {
  const raw = pickString(meta, 'risk');
  if (raw && RISK_VALUES.includes(raw)) {
    return raw as 'low' | 'medium' | 'high';
  }
  return null;
}

/**
 * Build the mobile-facing view for a single pending approval.
 *
 * Tolerates missing fields — every desktop-side field is optional in
 * the mobile presenter so a partial event still renders.
 */
export function toMobileApprovalView(
  approval: ApprovalRequest,
): MobileApprovalView {
  const risk = pickRisk(approval.metadata);
  const proposalType = pickString(approval.metadata, 'proposalType');
  const targetId = pickString(approval.metadata, 'targetId');

  // Confirmation is required for material approvals: high risk, anything
  // marked destructive in the proposal type, or sandbox/grant kinds.
  const destructiveKind =
    approval.kind === 'sandbox_violation' ||
    approval.kind === 'grant' ||
    approval.kind === 'mutation';
  const destructiveProposal =
    proposalType !== null &&
    /(delete|drop|destroy|overwrite|publish|deploy)/i.test(proposalType);

  const requiresConfirmation =
    risk === 'high' || destructiveKind || destructiveProposal;

  return {
    approvalId: approval.approvalId,
    question: approval.question,
    kind: approval.kind,
    options: [...approval.options],
    defaultResponse: approval.default ?? null,
    sessionId: approval.sessionId,
    runId: approval.runId ?? null,
    risk,
    proposalType,
    targetId,
    requiresConfirmation,
    createdAt: approval.createdAt,
  };
}

/**
 * Filter to the pending subset, newest-first, suitable for a mobile inbox.
 */
export function selectPendingApprovals(
  approvals: readonly ApprovalRequest[],
): readonly ApprovalRequest[] {
  return [...approvals]
    .filter((item) => item.status === 'pending')
    .sort((a, b) => b.createdAt - a.createdAt);
}

export interface SubmitApprovalParams {
  readonly approvalId: string;
  readonly decision: ApprovalDecision;
  readonly response?: string | null;
  readonly actor?: string;
}

export interface SubmitApprovalResult {
  readonly ok: boolean;
  readonly queued: boolean;
  readonly queuedId?: string;
  readonly error?: string;
}

export interface SubmitApprovalOptions {
  readonly outbox?: IndexedDbOutbox;
  readonly navigatorOnline?: boolean;
  readonly requestBackgroundSync?: () => Promise<boolean>;
  readonly now?: () => number;
}

export interface FlushApprovalOutboxOptions {
  readonly outbox?: IndexedDbOutbox;
}

export interface FlushApprovalOutboxResult {
  readonly sentCount: number;
  readonly failedCount: number;
  readonly remainingCount: number;
}

/**
 * Submit an approval decision through the supplied RPC port.
 *
 * Reuses the existing `approval.resolve` channel — see
 * `renderer/components/workflow/ApprovalPanel.tsx` for the desktop caller.
 * Approval business logic lives in the backend `application/` layer; this
 * function is a pure transport adapter.
 */
export async function submitMobileApproval(
  rpc: RpcPort,
  params: SubmitApprovalParams,
  options: SubmitApprovalOptions = {},
): Promise<SubmitApprovalResult> {
  if (!params.approvalId) {
    return { ok: false, queued: false, error: 'missing approvalId' };
  }
  if (params.decision !== 'approved' && params.decision !== 'rejected') {
    return { ok: false, queued: false, error: 'invalid decision' };
  }

  const outbox = options.outbox ?? indexedDbOutbox;
  const requestBackgroundSync = options.requestBackgroundSync ?? registerOutboxBackgroundSync;
  const navigatorOnline = options.navigatorOnline ?? readNavigatorOnline();
  const payload = buildApprovalResolvePayload(params);

  if (!navigatorOnline) {
    const queuedId = await enqueueApproval(outbox, payload, options.now);
    await requestBackgroundSync();
    return { ok: true, queued: true, queuedId };
  }
  try {
    await rpc('approval.resolve', payload);
    return { ok: true, queued: false };
  } catch (err) {
    if (isQueueableApprovalError(err)) {
      const queuedId = await enqueueApproval(outbox, payload, options.now);
      await requestBackgroundSync();
      return {
        ok: true,
        queued: true,
        queuedId,
      };
    }
    return {
      ok: false,
      queued: false,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

export async function flushQueuedMobileApprovals(
  rpc: RpcPort,
  options: FlushApprovalOutboxOptions = {},
): Promise<FlushApprovalOutboxResult> {
  const outbox = options.outbox ?? indexedDbOutbox;
  const items = await outbox.list();
  let sentCount = 0;
  let failedCount = 0;

  for (const item of items) {
    if (item.kind !== 'approval') {
      continue;
    }
    try {
      await rpc('approval.resolve', item.payload);
      await outbox.dequeue(item.id);
      sentCount += 1;
    } catch (err) {
      failedCount += 1;
      await outbox.incrementAttemptCount(item.id);
      if (isQueueableApprovalError(err)) {
        break;
      }
    }
  }

  const remainingCount = (await outbox.list()).length;
  return {
    sentCount,
    failedCount,
    remainingCount,
  };
}

export async function getQueuedApprovalCount(
  outbox: IndexedDbOutbox = indexedDbOutbox,
): Promise<number> {
  const items = await outbox.list();
  return items.filter((item) => item.kind === 'approval').length;
}

export function buildApprovalResolvePayload(
  params: SubmitApprovalParams,
): Record<string, unknown> {
  return {
    approvalId: params.approvalId,
    decision: params.decision,
    response: params.response ?? undefined,
    actor: params.actor ?? 'mobile',
  };
}

function readNavigatorOnline(): boolean {
  if (typeof navigator === 'undefined') {
    return true;
  }
  return navigator.onLine !== false;
}

function isQueueableApprovalError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return /(offline|network|socket|websocket|disconnected|failed to fetch|backend is not connected)/i
    .test(message);
}

async function enqueueApproval(
  outbox: IndexedDbOutbox,
  payload: Record<string, unknown>,
  now: SubmitApprovalOptions['now'],
): Promise<string> {
  return outbox.enqueue({
    kind: 'approval',
    payload,
    enqueuedAt: now ? now() : Date.now(),
    attemptCount: 0,
  } satisfies Omit<OutboxItem, 'id'>);
}
