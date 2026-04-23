"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
require("fake-indexeddb/auto");
const strict_1 = __importDefault(require("node:assert/strict"));
const indexedDbOutbox_1 = require("../../src/mobile/outbox/indexedDbOutbox");
const tests = [];
function test(name, fn) {
    tests.push({ name, fn });
}
async function freshOutbox() {
    const outbox = (0, indexedDbOutbox_1.createIndexedDbOutbox)();
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
    strict_1.default.deepEqual(items.map((item) => item.payload.approvalId), ['a', 'b']);
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
    strict_1.default.equal(items.length, 0);
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
    strict_1.default.notEqual(first, second);
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
    strict_1.default.deepEqual(await outbox.list(), []);
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
    strict_1.default.equal(count, 1);
    strict_1.default.equal(items[0].attemptCount, 1);
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
    strict_1.default.equal(items.length, 2);
    strict_1.default.notEqual(items[0].id, items[1].id);
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
    console.log(`\nindexedDbOutbox.spec - ${passed}/${passed + failed} passed${failed ? ` (${failed} failed)` : ''}`);
    if (failed > 0) {
        process.exit(1);
    }
})();
