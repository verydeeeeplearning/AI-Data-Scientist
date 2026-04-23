"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const approvalAdapter_1 = require("../../src/mobile/approvals/approvalAdapter");
function makeRpc(responder) {
    const calls = [];
    const rpc = async (method, params) => {
        calls.push({ method, params });
        return responder({ method, params });
    };
    return { rpc, calls };
}
function makeApproval(overrides = {}) {
    return {
        approvalId: overrides.approvalId ?? 'apr-1',
        sessionId: overrides.sessionId ?? 'sess-1',
        runId: overrides.runId ?? null,
        surface: overrides.surface ?? 'electron',
        question: overrides.question ?? 'Run feature engineering?',
        kind: overrides.kind ?? 'plan_step',
        metadata: overrides.metadata ?? {},
        options: overrides.options ?? [],
        default: overrides.default ?? null,
        status: overrides.status ?? 'pending',
        response: overrides.response ?? null,
        source: overrides.source ?? null,
        actor: overrides.actor ?? null,
        createdAt: overrides.createdAt ?? 1000,
        updatedAt: overrides.updatedAt ?? 1000,
        resolvedAt: overrides.resolvedAt ?? null,
    };
}
function makeOutbox(initial = []) {
    const items = [...initial];
    return {
        items,
        async enqueue(item) {
            const next = {
                id: item.id ?? `queued-${items.length + 1}`,
                kind: item.kind,
                payload: item.payload,
                enqueuedAt: item.enqueuedAt,
                attemptCount: item.attemptCount,
            };
            items.push(next);
            return next.id;
        },
        async dequeue(id) {
            const index = items.findIndex((item) => item.id === id);
            if (index >= 0) {
                items.splice(index, 1);
            }
        },
        async list() {
            return [...items].sort((left, right) => left.enqueuedAt - right.enqueuedAt);
        },
        async clear() {
            items.length = 0;
        },
        async incrementAttemptCount(id) {
            const index = items.findIndex((item) => item.id === id);
            if (index < 0)
                return 0;
            const next = items[index].attemptCount + 1;
            items[index] = { ...items[index], attemptCount: next };
            return next;
        },
    };
}
const tests = [];
function test(name, fn) {
    tests.push({ name, fn });
}
test('selectPendingApprovals filters and sorts newest-first', () => {
    const approvals = [
        makeApproval({ approvalId: 'a', createdAt: 1, status: 'pending' }),
        makeApproval({ approvalId: 'b', createdAt: 5, status: 'pending' }),
        makeApproval({ approvalId: 'c', createdAt: 9, status: 'approved' }),
        makeApproval({ approvalId: 'd', createdAt: 3, status: 'pending' }),
    ];
    const out = (0, approvalAdapter_1.selectPendingApprovals)(approvals);
    strict_1.default.deepEqual(out.map((item) => item.approvalId), ['b', 'd', 'a']);
});
test('toMobileApprovalView extracts metadata fields when present', () => {
    const view = (0, approvalAdapter_1.toMobileApprovalView)(makeApproval({
        metadata: {
            proposalType: 'delete_table',
            targetId: 'workspace://x/y',
            risk: 'high',
        },
        kind: 'semantic_proposal',
        options: ['confirm'],
        default: 'confirm',
    }));
    strict_1.default.equal(view.proposalType, 'delete_table');
    strict_1.default.equal(view.targetId, 'workspace://x/y');
    strict_1.default.equal(view.risk, 'high');
    // High risk and destructive proposal both demand confirmation.
    strict_1.default.equal(view.requiresConfirmation, true);
    strict_1.default.deepEqual([...view.options], ['confirm']);
    strict_1.default.equal(view.defaultResponse, 'confirm');
});
test('toMobileApprovalView degrades gracefully on missing metadata', () => {
    const view = (0, approvalAdapter_1.toMobileApprovalView)(makeApproval({ metadata: {} }));
    strict_1.default.equal(view.proposalType, null);
    strict_1.default.equal(view.targetId, null);
    strict_1.default.equal(view.risk, null);
    strict_1.default.equal(view.requiresConfirmation, false);
});
test('toMobileApprovalView ignores invalid risk values', () => {
    const view = (0, approvalAdapter_1.toMobileApprovalView)(makeApproval({ metadata: { risk: 'critical' } }));
    strict_1.default.equal(view.risk, null);
});
test('toMobileApprovalView marks sandbox/grant kinds as confirmation-required', () => {
    for (const kind of ['sandbox_violation', 'grant', 'mutation']) {
        const view = (0, approvalAdapter_1.toMobileApprovalView)(makeApproval({ kind }));
        strict_1.default.equal(view.requiresConfirmation, true, `kind ${kind} should require confirmation`);
    }
});
test('submitMobileApproval forwards to approval.resolve with the right shape', async () => {
    const { rpc, calls } = makeRpc(() => ({ ok: true }));
    const out = await (0, approvalAdapter_1.submitMobileApproval)(rpc, {
        approvalId: 'apr-7',
        decision: 'approved',
        response: 'looks good',
    });
    strict_1.default.equal(out.ok, true);
    strict_1.default.equal(out.queued, false);
    strict_1.default.equal(calls.length, 1);
    strict_1.default.equal(calls[0].method, 'approval.resolve');
    strict_1.default.deepEqual(calls[0].params, {
        approvalId: 'apr-7',
        decision: 'approved',
        response: 'looks good',
        actor: 'mobile',
    });
});
test('submitMobileApproval defaults actor=mobile and omits null response', async () => {
    const { rpc, calls } = makeRpc(() => ({ ok: true }));
    await (0, approvalAdapter_1.submitMobileApproval)(rpc, {
        approvalId: 'apr-8',
        decision: 'rejected',
    });
    strict_1.default.equal(calls[0].params?.actor, 'mobile');
    strict_1.default.equal(calls[0].params?.response, undefined);
});
test('submitMobileApproval rejects empty approvalId without calling rpc', async () => {
    const { rpc, calls } = makeRpc(() => ({}));
    const out = await (0, approvalAdapter_1.submitMobileApproval)(rpc, {
        approvalId: '',
        decision: 'approved',
    });
    strict_1.default.equal(out.ok, false);
    strict_1.default.equal(out.queued, false);
    strict_1.default.equal(calls.length, 0);
});
test('submitMobileApproval surfaces RPC errors as ok=false with message', async () => {
    const { rpc } = makeRpc(() => {
        throw new Error('validation failed');
    });
    const out = await (0, approvalAdapter_1.submitMobileApproval)(rpc, {
        approvalId: 'apr-9',
        decision: 'approved',
    });
    strict_1.default.equal(out.ok, false);
    strict_1.default.equal(out.queued, false);
    strict_1.default.equal(out.error, 'validation failed');
});
test('submitMobileApproval queues immediately when navigator reports offline', async () => {
    const { rpc, calls } = makeRpc(() => ({ ok: true }));
    const outbox = makeOutbox();
    let syncRequested = 0;
    const out = await (0, approvalAdapter_1.submitMobileApproval)(rpc, {
        approvalId: 'apr-offline',
        decision: 'approved',
    }, {
        navigatorOnline: false,
        outbox,
        requestBackgroundSync: async () => {
            syncRequested += 1;
            return true;
        },
        now: () => 123,
    });
    strict_1.default.equal(out.ok, true);
    strict_1.default.equal(out.queued, true);
    strict_1.default.equal(calls.length, 0);
    strict_1.default.equal(syncRequested, 1);
    strict_1.default.equal(outbox.items.length, 1);
    strict_1.default.equal(outbox.items[0].payload.approvalId, 'apr-offline');
});
test('submitMobileApproval queues network-like RPC failures', async () => {
    const { rpc, calls } = makeRpc(() => {
        throw new Error('backend offline');
    });
    const outbox = makeOutbox();
    const out = await (0, approvalAdapter_1.submitMobileApproval)(rpc, {
        approvalId: 'apr-network',
        decision: 'rejected',
    }, {
        outbox,
        requestBackgroundSync: async () => true,
        now: () => 456,
    });
    strict_1.default.equal(out.ok, true);
    strict_1.default.equal(out.queued, true);
    strict_1.default.equal(calls.length, 1);
    strict_1.default.equal(outbox.items.length, 1);
    strict_1.default.equal(outbox.items[0].payload.decision, 'rejected');
});
test('flushQueuedMobileApprovals replays queued items and dequeues successes', async () => {
    const outbox = makeOutbox([
        {
            id: 'queued-1',
            kind: 'approval',
            payload: {
                approvalId: 'apr-1',
                decision: 'approved',
                actor: 'mobile',
            },
            enqueuedAt: 1,
            attemptCount: 0,
        },
        {
            id: 'queued-2',
            kind: 'approval',
            payload: {
                approvalId: 'apr-2',
                decision: 'rejected',
                actor: 'mobile',
            },
            enqueuedAt: 2,
            attemptCount: 0,
        },
    ]);
    const { rpc, calls } = makeRpc(() => ({ ok: true }));
    const result = await (0, approvalAdapter_1.flushQueuedMobileApprovals)(rpc, { outbox });
    strict_1.default.equal(result.sentCount, 2);
    strict_1.default.equal(result.failedCount, 0);
    strict_1.default.equal(result.remainingCount, 0);
    strict_1.default.equal(calls.length, 2);
});
test('flushQueuedMobileApprovals keeps failed items and increments attempt count', async () => {
    const outbox = makeOutbox([
        {
            id: 'queued-1',
            kind: 'approval',
            payload: {
                approvalId: 'apr-1',
                decision: 'approved',
                actor: 'mobile',
            },
            enqueuedAt: 1,
            attemptCount: 0,
        },
    ]);
    const { rpc } = makeRpc(() => {
        throw new Error('network disconnected');
    });
    const result = await (0, approvalAdapter_1.flushQueuedMobileApprovals)(rpc, { outbox });
    strict_1.default.equal(result.sentCount, 0);
    strict_1.default.equal(result.failedCount, 1);
    strict_1.default.equal(result.remainingCount, 1);
    strict_1.default.equal(outbox.items[0].attemptCount, 1);
});
let passed = 0;
let failed = 0;
(async () => {
    for (const current of tests) {
        try {
            await current.fn();
            console.log(`  ok  ${current.name}`);
            passed += 1;
        }
        catch (error) {
            console.error(`  FAIL ${current.name}`);
            console.error(`    ${error.message}`);
            failed += 1;
        }
    }
    console.log(`\nmobileApprovalFlow.spec - ${passed}/${passed + failed} passed${failed ? ` (${failed} failed)` : ''}`);
    if (failed > 0) {
        process.exit(1);
    }
})();
