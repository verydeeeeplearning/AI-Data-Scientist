import assert from 'node:assert/strict';

import {
  flushQueuedMobileApprovals,
  selectPendingApprovals,
  submitMobileApproval,
  toMobileApprovalView,
  type RpcPort,
} from '../../src/mobile/approvals/approvalAdapter';
import type { ApprovalRequest } from '../../src/renderer/stores/workflowStore';
import type { IndexedDbOutbox, OutboxItem } from '../../src/mobile/outbox/indexedDbOutbox';

interface RpcCall {
  method: string;
  params?: Record<string, unknown>;
}

function makeRpc(
  responder: (call: RpcCall) => Record<string, unknown> | Promise<Record<string, unknown>>,
): { rpc: RpcPort; calls: RpcCall[] } {
  const calls: RpcCall[] = [];
  const rpc: RpcPort = async (method, params) => {
    calls.push({ method, params });
    return responder({ method, params });
  };
  return { rpc, calls };
}

function makeApproval(overrides: Partial<ApprovalRequest> = {}): ApprovalRequest {
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

function makeOutbox(initial: OutboxItem[] = []): IndexedDbOutbox & { items: OutboxItem[] } {
  const items = [...initial];
  return {
    items,
    async enqueue(item) {
      const next: OutboxItem = {
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
      if (index < 0) return 0;
      const next = items[index].attemptCount + 1;
      items[index] = { ...items[index], attemptCount: next };
      return next;
    },
  };
}

interface TestCase {
  name: string;
  fn: () => void | Promise<void>;
}

const tests: TestCase[] = [];
function test(name: string, fn: () => void | Promise<void>): void {
  tests.push({ name, fn });
}

test('selectPendingApprovals filters and sorts newest-first', () => {
  const approvals: ApprovalRequest[] = [
    makeApproval({ approvalId: 'a', createdAt: 1, status: 'pending' }),
    makeApproval({ approvalId: 'b', createdAt: 5, status: 'pending' }),
    makeApproval({ approvalId: 'c', createdAt: 9, status: 'approved' }),
    makeApproval({ approvalId: 'd', createdAt: 3, status: 'pending' }),
  ];
  const out = selectPendingApprovals(approvals);
  assert.deepEqual(
    out.map((item) => item.approvalId),
    ['b', 'd', 'a'],
  );
});

test('toMobileApprovalView extracts metadata fields when present', () => {
  const view = toMobileApprovalView(
    makeApproval({
      metadata: {
        proposalType: 'delete_table',
        targetId: 'workspace://x/y',
        risk: 'high',
      },
      kind: 'semantic_proposal',
      options: ['confirm'],
      default: 'confirm',
    }),
  );
  assert.equal(view.proposalType, 'delete_table');
  assert.equal(view.targetId, 'workspace://x/y');
  assert.equal(view.risk, 'high');
  // High risk and destructive proposal both demand confirmation.
  assert.equal(view.requiresConfirmation, true);
  assert.deepEqual([...view.options], ['confirm']);
  assert.equal(view.defaultResponse, 'confirm');
});

test('toMobileApprovalView degrades gracefully on missing metadata', () => {
  const view = toMobileApprovalView(makeApproval({ metadata: {} }));
  assert.equal(view.proposalType, null);
  assert.equal(view.targetId, null);
  assert.equal(view.risk, null);
  assert.equal(view.requiresConfirmation, false);
});

test('toMobileApprovalView ignores invalid risk values', () => {
  const view = toMobileApprovalView(
    makeApproval({ metadata: { risk: 'critical' } }),
  );
  assert.equal(view.risk, null);
});

test('toMobileApprovalView marks sandbox/grant kinds as confirmation-required', () => {
  for (const kind of ['sandbox_violation', 'grant', 'mutation']) {
    const view = toMobileApprovalView(makeApproval({ kind }));
    assert.equal(view.requiresConfirmation, true, `kind ${kind} should require confirmation`);
  }
});

test('submitMobileApproval forwards to approval.resolve with the right shape', async () => {
  const { rpc, calls } = makeRpc(() => ({ ok: true }));
  const out = await submitMobileApproval(rpc, {
    approvalId: 'apr-7',
    decision: 'approved',
    response: 'looks good',
  });
  assert.equal(out.ok, true);
  assert.equal(out.queued, false);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].method, 'approval.resolve');
  assert.deepEqual(calls[0].params, {
    approvalId: 'apr-7',
    decision: 'approved',
    response: 'looks good',
    actor: 'mobile',
  });
});

test('submitMobileApproval defaults actor=mobile and omits null response', async () => {
  const { rpc, calls } = makeRpc(() => ({ ok: true }));
  await submitMobileApproval(rpc, {
    approvalId: 'apr-8',
    decision: 'rejected',
  });
  assert.equal(calls[0].params?.actor, 'mobile');
  assert.equal(calls[0].params?.response, undefined);
});

test('submitMobileApproval rejects empty approvalId without calling rpc', async () => {
  const { rpc, calls } = makeRpc(() => ({}));
  const out = await submitMobileApproval(rpc, {
    approvalId: '',
    decision: 'approved',
  });
  assert.equal(out.ok, false);
  assert.equal(out.queued, false);
  assert.equal(calls.length, 0);
});

test('submitMobileApproval surfaces RPC errors as ok=false with message', async () => {
  const { rpc } = makeRpc(() => {
    throw new Error('validation failed');
  });
  const out = await submitMobileApproval(rpc, {
    approvalId: 'apr-9',
    decision: 'approved',
  });
  assert.equal(out.ok, false);
  assert.equal(out.queued, false);
  assert.equal(out.error, 'validation failed');
});

test('submitMobileApproval queues immediately when navigator reports offline', async () => {
  const { rpc, calls } = makeRpc(() => ({ ok: true }));
  const outbox = makeOutbox();
  let syncRequested = 0;

  const out = await submitMobileApproval(
    rpc,
    {
      approvalId: 'apr-offline',
      decision: 'approved',
    },
    {
      navigatorOnline: false,
      outbox,
      requestBackgroundSync: async () => {
        syncRequested += 1;
        return true;
      },
      now: () => 123,
    },
  );

  assert.equal(out.ok, true);
  assert.equal(out.queued, true);
  assert.equal(calls.length, 0);
  assert.equal(syncRequested, 1);
  assert.equal(outbox.items.length, 1);
  assert.equal(outbox.items[0].payload.approvalId, 'apr-offline');
});

test('submitMobileApproval queues network-like RPC failures', async () => {
  const { rpc, calls } = makeRpc(() => {
    throw new Error('backend offline');
  });
  const outbox = makeOutbox();

  const out = await submitMobileApproval(
    rpc,
    {
      approvalId: 'apr-network',
      decision: 'rejected',
    },
    {
      outbox,
      requestBackgroundSync: async () => true,
      now: () => 456,
    },
  );

  assert.equal(out.ok, true);
  assert.equal(out.queued, true);
  assert.equal(calls.length, 1);
  assert.equal(outbox.items.length, 1);
  assert.equal(outbox.items[0].payload.decision, 'rejected');
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

  const result = await flushQueuedMobileApprovals(rpc, { outbox });

  assert.equal(result.sentCount, 2);
  assert.equal(result.failedCount, 0);
  assert.equal(result.remainingCount, 0);
  assert.equal(calls.length, 2);
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

  const result = await flushQueuedMobileApprovals(rpc, { outbox });

  assert.equal(result.sentCount, 0);
  assert.equal(result.failedCount, 1);
  assert.equal(result.remainingCount, 1);
  assert.equal(outbox.items[0].attemptCount, 1);
});

let passed = 0;
let failed = 0;

(async () => {
  for (const current of tests) {
    try {
      await current.fn();
      console.log(`  ok  ${current.name}`);
      passed += 1;
    } catch (error) {
      console.error(`  FAIL ${current.name}`);
      console.error(`    ${(error as Error).message}`);
      failed += 1;
    }
  }
  console.log(
    `\nmobileApprovalFlow.spec - ${passed}/${passed + failed} passed${failed ? ` (${failed} failed)` : ''}`,
  );
  if (failed > 0) {
    process.exit(1);
  }
})();
