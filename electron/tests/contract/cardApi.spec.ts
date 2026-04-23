import assert from 'node:assert/strict';
import { setCardPinned } from '../../src/renderer/infrastructure/api/cardApi';

async function run(): Promise<void> {
  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;
  const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];

  Object.defineProperty(globalThis, 'window', {
    value: {
      location: {
        search: '?port=19999',
      },
    },
    configurable: true,
  });

  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    fetchCalls.push({ input, init });
    return {
      ok: true,
      json: async () => ({
        card: {
          cardId: 'card-1',
          resultId: 'result-1',
          type: 'insight',
          createdAt: 1_713_650_000,
          source: {
            messageId: 'msg-1',
            runId: 'run-1',
          },
          pinned: true,
          archived: false,
        },
      }),
    } as Response;
  }) as typeof fetch;

  try {
    const response = await setCardPinned('card/1', true);

    assert.equal(fetchCalls.length, 1);
    assert.equal(fetchCalls[0]?.input, 'http://127.0.0.1:19999/api/cards/card%2F1/pin');
    assert.equal(fetchCalls[0]?.init?.method, 'POST');
    assert.equal(fetchCalls[0]?.init?.headers instanceof Object, true);
    assert.equal(fetchCalls[0]?.init?.body, JSON.stringify({ pinned: true }));
    assert.equal(response.card.cardId, 'card-1');
    assert.equal(response.card.pinned, true);
  } finally {
    if (typeof originalWindow === 'undefined') {
      delete (globalThis as { window?: Window }).window;
    } else {
      Object.defineProperty(globalThis, 'window', {
        value: originalWindow,
        configurable: true,
      });
    }
    globalThis.fetch = originalFetch;
  }

  console.log('[contract] PASS card-api (5 cases)');
}

void run().catch((error) => {
  console.error(error);
  process.exit(1);
});
