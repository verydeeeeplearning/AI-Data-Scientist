import assert from 'node:assert/strict';

import { resolveGovernanceLanding } from '../../src/renderer/application/navigation/resolveGovernanceLanding';

function run(): void {
  {
    const landing = resolveGovernanceLanding({ subPath: undefined });
    assert.equal(landing.sectionId, 'review');
    assert.equal(landing.sectionPath, '/governance/review');
    assert.equal(landing.detail, null);
  }

  {
    const landing = resolveGovernanceLanding({ subPath: 'verifier/result-42' });
    assert.equal(landing.sectionId, 'review');
    assert.equal(landing.sectionPath, '/governance/review');
    assert.equal(landing.detail?.kind, 'verifier');
    assert.equal(landing.detail?.id, 'result-42');
  }

  {
    const landing = resolveGovernanceLanding({ subPath: 'lineage/run-9/result-42' });
    assert.equal(landing.sectionId, 'review');
    assert.equal(landing.detail?.kind, 'lineage');
    assert.equal(landing.detail?.id, 'run-9/result-42');
  }

  {
    const landing = resolveGovernanceLanding({ subPath: 'fallback-log' });
    assert.equal(landing.sectionId, 'review');
    assert.equal(landing.detail?.kind, 'fallback-log');
    assert.equal(landing.detail?.id, null);
  }

  {
    const landing = resolveGovernanceLanding({ subPath: 'approvals/appr-7' });
    assert.equal(landing.sectionId, 'approvals');
    assert.equal(landing.sectionPath, '/governance/approvals');
    assert.equal(landing.detail?.kind, 'approval');
    assert.equal(landing.detail?.id, 'appr-7');
  }

  {
    const landing = resolveGovernanceLanding({ subPath: 'policies/runtime-profile' });
    assert.equal(landing.sectionId, 'policy');
    assert.equal(landing.sectionPath, '/governance/policy');
    assert.equal(landing.detail?.kind, 'policy');
    assert.equal(landing.detail?.id, 'runtime-profile');
  }

  {
    const landing = resolveGovernanceLanding({ subPath: 'certification/mission-alpha' });
    assert.equal(landing.sectionId, 'certification');
    assert.equal(landing.detail?.kind, 'certification');
    assert.equal(landing.detail?.id, 'mission-alpha');
  }

  {
    const landing = resolveGovernanceLanding({ subPath: 'unknown/route' });
    assert.equal(landing.sectionId, 'review');
    assert.equal(landing.detail, null);
  }

  console.log('[contract] PASS resolve-governance-landing (8 cases)');
}

run();
