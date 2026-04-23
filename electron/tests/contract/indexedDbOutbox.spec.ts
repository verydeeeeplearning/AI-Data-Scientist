import 'fake-indexeddb/auto';

import assert from 'node:assert/strict';

import { createIndexedDbOutbox } from '../../src/mobile/outbox/indexedDbOutbox';

interface TestCase {
  name: string;
  fn: () => void | Promise<void>;
}

const tests: TestCase[] = [];
function test(name: string, fn: () => void | Promise<void>): void {
  tests.push({ name, fn });
}

async function freshOutbox() {
  const outbox = createIndexedDbOutbox();
  await outbox.clear();
  return outbox;
}

test('enqueue + list returns items in time order', async () => {
  const outbox = await freshOutbox();
  await outbox.enqueue({
    kind: 'approval',
    payload: { approvalId: 'b' },
    enqueuedAt: 20,
    attemptCount: 0,
  });
  await outbox.enqueue({
    kind: 'approval',
    payload: { approvalId: 'a' },
    enqueuedAt: 10,
    attemptCount: 0,
  });

  const items = await outbox.list();
  assert.deepEqual(
    items.map((item) => item.payload.approvalId),
    ['a', 'b'],
  );
});

test('dequeue removes an item', async () => {
  const outbox = await freshOutbox();
  const id = await outbox.enqueue({
    kind: 'approval',
    payload: { approvalId: 'apr-1' },
    enqueuedAt: 1,
    attemptCount: 0,
  });

  await outbox.dequeue(id);
  const items = await outbox.list();
  assert.equal(items.length, 0);
});

test('enqueue generates unique ids by default', async () => {
  const outbox = await freshOutbox();
  const first = await outbox.enqueue({
    kind: 'approval',
    payload: { approvalId: 'apr-1' },
    enqueuedAt: 1,
    attemptCount: 0,
  });
  const second = await outbox.enqueue({
    kind: 'approval',
    payload: { approvalId: 'apr-2' },
    enqueuedAt: 2,
    attemptCount: 0,
  });

  assert.notEqual(first, second);
});

test('clear empties the outbox', async () => {
  const outbox = await freshOutbox();
  await outbox.enqueue({
    kind: 'approval',
    payload: { approvalId: 'apr-1' },
    enqueuedAt: 1,
    attemptCount: 0,
  });
  await outbox.clear();
  assert.deepEqual(await outbox.list(), []);
});

test('incrementAttemptCount updates the stored item', async () => {
  const outbox = await freshOutbox();
  const id = await outbox.enqueue({
    kind: 'approval',
    payload: { approvalId: 'apr-1' },
    enqueuedAt: 1,
    attemptCount: 0,
  });

  const count = await outbox.incrementAttemptCount(id);
  const items = await outbox.list();
  assert.equal(count, 1);
  assert.equal(items[0].attemptCount, 1);
});

test('duplicate payloads are stored as distinct queue entries', async () => {
  const outbox = await freshOutbox();
  await outbox.enqueue({
    kind: 'approval',
    payload: { approvalId: 'apr-1', decision: 'approved' },
    enqueuedAt: 1,
    attemptCount: 0,
  });
  await outbox.enqueue({
    kind: 'approval',
    payload: { approvalId: 'apr-1', decision: 'approved' },
    enqueuedAt: 2,
    attemptCount: 0,
  });

  const items = await outbox.list();
  assert.equal(items.length, 2);
  assert.notEqual(items[0].id, items[1].id);
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
    `\nindexedDbOutbox.spec - ${passed}/${passed + failed} passed${failed ? ` (${failed} failed)` : ''}`,
  );

  if (failed > 0) {
    process.exit(1);
  }
})();
