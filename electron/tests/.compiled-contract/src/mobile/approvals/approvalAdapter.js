"use strict";
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
Object.defineProperty(exports, "__esModule", { value: true });
exports.toMobileApprovalView = toMobileApprovalView;
exports.selectPendingApprovals = selectPendingApprovals;
exports.submitMobileApproval = submitMobileApproval;
exports.flushQueuedMobileApprovals = flushQueuedMobileApprovals;
exports.getQueuedApprovalCount = getQueuedApprovalCount;
exports.buildApprovalResolvePayload = buildApprovalResolvePayload;
const indexedDbOutbox_1 = require("../outbox/indexedDbOutbox");
const mobileError_1 = require("../errors/mobileError");
const RISK_VALUES = ['low', 'medium', 'high'];
function pickString(meta, key) {
    if (!meta) {
        return null;
    }
    const raw = meta[key];
    return typeof raw === 'string' && raw.length > 0 ? raw : null;
}
function pickRisk(meta) {
    const raw = pickString(meta, 'risk');
    if (raw && RISK_VALUES.includes(raw)) {
        return raw;
    }
    return null;
}
/**
 * Build the mobile-facing view for a single pending approval.
 *
 * Tolerates missing fields — every desktop-side field is optional in
 * the mobile presenter so a partial event still renders.
 */
function toMobileApprovalView(approval) {
    const risk = pickRisk(approval.metadata);
    const proposalType = pickString(approval.metadata, 'proposalType');
    const targetId = pickString(approval.metadata, 'targetId');
    // Confirmation is required for material approvals: high risk, anything
    // marked destructive in the proposal type, or sandbox/grant kinds.
    const destructiveKind = approval.kind === 'sandbox_violation' ||
        approval.kind === 'grant' ||
        approval.kind === 'mutation';
    const destructiveProposal = proposalType !== null &&
        /(delete|drop|destroy|overwrite|publish|deploy)/i.test(proposalType);
    const requiresConfirmation = risk === 'high' || destructiveKind || destructiveProposal;
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
function selectPendingApprovals(approvals) {
    return [...approvals]
        .filter((item) => item.status === 'pending')
        .sort((a, b) => b.createdAt - a.createdAt);
}
/**
 * Submit an approval decision through the supplied RPC port.
 *
 * Reuses the existing `approval.resolve` channel — see
 * `renderer/components/workflow/ApprovalPanel.tsx` for the desktop caller.
 * Approval business logic lives in the backend `application/` layer; this
 * function is a pure transport adapter.
 */
async function submitMobileApproval(rpc, params, options = {}) {
    if (!params.approvalId) {
        return {
            ok: false,
            queued: false,
            error: 'missing approvalId',
            errorCode: 'approval_missing_id',
            debugDetail: 'missing approvalId',
        };
    }
    if (params.decision !== 'approved' && params.decision !== 'rejected') {
        return {
            ok: false,
            queued: false,
            error: 'invalid decision',
            errorCode: 'approval_invalid_decision',
            debugDetail: 'invalid decision',
        };
    }
    const outbox = options.outbox ?? indexedDbOutbox_1.indexedDbOutbox;
    const requestBackgroundSync = options.requestBackgroundSync ?? indexedDbOutbox_1.registerOutboxBackgroundSync;
    const navigatorOnline = options.navigatorOnline ?? readNavigatorOnline();
    const payload = buildApprovalResolvePayload(params);
    if (!navigatorOnline) {
        try {
            const queuedId = await enqueueApproval(outbox, payload, options.now);
            await requestBackgroundSync();
            return { ok: true, queued: true, queuedId };
        }
        catch (error) {
            const errorCode = (0, mobileError_1.resolveApprovalErrorCode)(error);
            const debugDetail = (0, mobileError_1.getMobileErrorDebugDetail)(error);
            return {
                ok: false,
                queued: false,
                error: debugDetail,
                errorCode,
                debugDetail,
            };
        }
    }
    try {
        await rpc('approval.resolve', payload);
        return { ok: true, queued: false };
    }
    catch (err) {
        if (isQueueableApprovalError(err)) {
            try {
                const queuedId = await enqueueApproval(outbox, payload, options.now);
                await requestBackgroundSync();
                return {
                    ok: true,
                    queued: true,
                    queuedId,
                };
            }
            catch (queueError) {
                const errorCode = (0, mobileError_1.resolveApprovalErrorCode)(queueError);
                const debugDetail = (0, mobileError_1.getMobileErrorDebugDetail)(queueError);
                return {
                    ok: false,
                    queued: false,
                    error: debugDetail,
                    errorCode,
                    debugDetail,
                };
            }
        }
        const errorCode = (0, mobileError_1.resolveApprovalErrorCode)(err);
        const debugDetail = (0, mobileError_1.getMobileErrorDebugDetail)(err);
        return {
            ok: false,
            queued: false,
            error: debugDetail,
            errorCode,
            debugDetail,
        };
    }
}
async function flushQueuedMobileApprovals(rpc, options = {}) {
    const outbox = options.outbox ?? indexedDbOutbox_1.indexedDbOutbox;
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
        }
        catch (err) {
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
async function getQueuedApprovalCount(outbox = indexedDbOutbox_1.indexedDbOutbox) {
    const items = await outbox.list();
    return items.filter((item) => item.kind === 'approval').length;
}
function buildApprovalResolvePayload(params) {
    return {
        approvalId: params.approvalId,
        decision: params.decision,
        response: params.response ?? undefined,
        actor: params.actor ?? 'mobile',
    };
}
function readNavigatorOnline() {
    if (typeof navigator === 'undefined') {
        return true;
    }
    return navigator.onLine !== false;
}
function isQueueableApprovalError(error) {
    return (0, mobileError_1.resolveApprovalErrorCode)(error) === 'approval_transport_unavailable';
}
async function enqueueApproval(outbox, payload, now) {
    return outbox.enqueue({
        kind: 'approval',
        payload,
        enqueuedAt: now ? now() : Date.now(),
        attemptCount: 0,
    });
}
