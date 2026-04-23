import assert from 'node:assert/strict';

import { resolveCanMutate } from '../../src/renderer/hooks/useCanMutate';

function run(): void {
  const ownerOutcome = resolveCanMutate('owner');
  assert.equal(ownerOutcome.role, 'owner');
  assert.equal(ownerOutcome.canMutate, true);
  assert.equal(ownerOutcome.reason, undefined);

  const viewerOutcome = resolveCanMutate('viewer');
  assert.equal(viewerOutcome.role, 'viewer');
  assert.equal(viewerOutcome.canMutate, false);
  assert.equal(viewerOutcome.reason, 'share.banner.readOnlyTooltip');

  // reason is a stable i18n key, not a translated literal — call sites bind
  // it to tooltips on disabled controls.
  assert.equal(typeof viewerOutcome.reason, 'string');
  assert.equal(viewerOutcome.reason!.startsWith('share.'), true);

  console.log('[contract] PASS use-can-mutate (7 cases)');
}

run();
