import assert from 'node:assert/strict';

import { fetchTrustByResultId } from '../../src/renderer/infrastructure/api/trustApi';

async function run(): Promise<void> {
  const originalFetch = globalThis.fetch;
  const originalWindow = (globalThis as { window?: unknown }).window;

  try {
    (globalThis as { window: { location: { search: string } } }).window = {
      location: { search: '?port=18888' },
    };

    let requestedUrl: string | null = null;
    let requestedInit: RequestInit | undefined;

    globalThis.fetch = (async (input: URL | RequestInfo, init?: RequestInit) => {
      requestedUrl = typeof input === 'string' ? input : input.toString();
      requestedInit = init;
      return {
        ok: true,
        json: async () => ({
          resultId: 'result/with/slash',
          badges: [{ kind: 'verifier', status: 'pass', verifierId: 'vf-1' }],
        }),
      } as Response;
    }) as typeof fetch;

    const trust = await fetchTrustByResultId('result/with/slash');

    assert.equal(
      requestedUrl,
      'http://127.0.0.1:18888/api/trust/result%2Fwith%2Fslash',
    );
    assert.deepEqual(requestedInit, { cache: 'no-store' });
    assert.equal(trust.badges[0]?.kind, 'verifier');
    assert.equal(trust.badges[0]?.href, '/governance/verifier/vf-1');

    globalThis.fetch = (async () =>
      ({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'trust metadata not found' }),
      }) as Response) as typeof fetch;

    await assert.rejects(fetchTrustByResultId('missing-result'), /trust metadata not found/);

    console.log('[contract] PASS trust-api (2 cases)');
  } finally {
    globalThis.fetch = originalFetch;
    if (typeof originalWindow === 'undefined') {
      delete (globalThis as { window?: unknown }).window;
    } else {
      (globalThis as { window?: unknown }).window = originalWindow;
    }
  }
}

void run().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
