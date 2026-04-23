import assert from 'node:assert/strict';

import { MOBILE_TABS, type MobileTab } from '../../src/mobile/router';

function run(): void {
  // Tab registry is exactly 5 entries, ordered.
  // Approvals is inserted between artifacts and settings so it lives in the
  // action zone of the bottom nav, not adjacent to settings overflow.
  assert.equal(MOBILE_TABS.length, 5);
  assert.deepEqual(
    [...MOBILE_TABS],
    ['mission', 'runs', 'artifacts', 'approvals', 'settings'],
  );

  // All 5 documented tabs are present.
  const valid = new Set<MobileTab>([
    'mission',
    'runs',
    'artifacts',
    'approvals',
    'settings',
  ]);
  for (const tab of MOBILE_TABS) {
    assert.ok(valid.has(tab), `unexpected tab: ${tab}`);
  }

  console.log('[contract] PASS mobile-shell-routing (5 cases)');
}

run();
