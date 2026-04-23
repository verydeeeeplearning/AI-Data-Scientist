import assert from 'node:assert/strict';

import { mapTrustPayload } from '../../src/renderer/application/trust/trustMapper';

function run(): void {
  {
    const trust = mapTrustPayload('result-42', {
      resultId: 'result-42',
      badges: [
        {
          kind: 'verifier',
          status: 'pass',
          detail: 'Schema verified',
          target: { kind: 'verifier', id: 'vf-1' },
        },
        {
          kind: 'approval',
          status: 'pending',
          approvalId: 'approval-9',
        },
      ],
    });

    assert.equal(trust.resultId, 'result-42');
    assert.equal(trust.badges.length, 2);
    assert.equal(trust.badges[0]?.kind, 'verifier');
    assert.equal(trust.badges[0]?.status, 'pass');
    assert.equal(trust.badges[0]?.href, '/governance/verifier/vf-1');
    assert.equal(trust.badges[0]?.detail, 'Schema verified');
    assert.equal(trust.badges[1]?.kind, 'approval');
    assert.equal(trust.badges[1]?.status, 'pending');
    assert.equal(trust.badges[1]?.href, '/governance/approval/approval-9');
  }

  {
    const trust = mapTrustPayload('result-derived', {
      verifierStatus: 'warning',
      verifierId: 'vf-2',
      approvalStatus: 'queued',
      approvalId: 'approval-4',
      policyStatus: 'blocked',
      policyId: 'policy-3',
    });

    assert.deepEqual(
      trust.badges.map((badge) => badge.kind),
      ['verifier', 'approval', 'policy'],
    );
    assert.deepEqual(
      trust.badges.map((badge) => badge.status),
      ['warn', 'pending', 'fail'],
    );
    assert.deepEqual(
      trust.badges.map((badge) => badge.href),
      [
        '/governance/verifier/vf-2',
        '/governance/approval/approval-4',
        '/governance/policy/policy-3',
      ],
    );
  }

  console.log('[contract] PASS trust-mapper (2 cases)');
}

run();
