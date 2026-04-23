import assert from 'node:assert/strict';

import { createTrustStore } from '../../src/renderer/application/trust/trustStore';
import type { TrustMetadata } from '../../src/renderer/application/trust/trustTypes';

function buildTrust(resultId: string): TrustMetadata {
  return {
    resultId,
    badges: [
      {
        key: 'verifier',
        kind: 'verifier',
        label: 'Verifier',
        status: 'pass',
        detail: 'Verified',
        href: '/governance/verifier/verifier-1',
        target: {
          path: '/governance/verifier/verifier-1',
          sectionId: 'review',
          detailKind: 'verifier',
          detailId: 'verifier-1',
        },
      },
    ],
    fetchedAt: Date.now(),
    updatedAt: null,
  };
}

async function run(): Promise<void> {
  {
    let calls = 0;
    const store = createTrustStore(async (resultId) => {
      calls += 1;
      return buildTrust(resultId);
    });

    const first = store.getState().ensure('result-1');
    const second = store.getState().ensure('result-1');

    assert.equal(store.getState().entries['result-1']?.state, 'loading');

    const [trust, dedupedTrust] = await Promise.all([first, second]);
    assert.equal(trust?.resultId, 'result-1');
    assert.equal(dedupedTrust?.resultId, 'result-1');
    assert.equal(calls, 1);

    const cached = await store.getState().ensure('result-1');
    assert.equal(cached, trust);
    assert.equal(calls, 1);
    assert.equal(store.getState().entries['result-1']?.state, 'loaded');
  }

  {
    let shouldReject = true;
    const store = createTrustStore(async (resultId) => {
      if (shouldReject) {
        shouldReject = false;
        throw new Error('backend unavailable');
      }
      return buildTrust(resultId);
    });

    await assert.rejects(store.getState().ensure('result-2'), /backend unavailable/);
    assert.equal(store.getState().entries['result-2']?.state, 'error');
    assert.equal(store.getState().entries['result-2']?.error, 'backend unavailable');

    const trust = await store.getState().ensure('result-2', { force: true });
    assert.equal(trust?.resultId, 'result-2');
    assert.equal(store.getState().entries['result-2']?.state, 'loaded');
  }

  console.log('[contract] PASS trust-store (2 cases)');
}

void run().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
