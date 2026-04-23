import assert from 'node:assert/strict';

import { resolveAccessRole, type ViewerRole } from '../../src/renderer/hooks/useAccessRole';

function run(): void {
  // sole-user mode → owner (default product behavior)
  assert.equal(resolveAccessRole(undefined, true), 'owner');

  // forceRole=viewer overrides sole-user (testing UI viewer state)
  assert.equal(resolveAccessRole('viewer', true), 'viewer');

  // explicit owner forceRole preserved
  assert.equal(resolveAccessRole('owner', false), 'owner');

  // non-sole-user defaults to owner today (future v2 will resolve from auth context)
  assert.equal(resolveAccessRole(undefined, false), 'owner');

  // ViewerRole literal type sanity
  const owner: ViewerRole = 'owner';
  const viewer: ViewerRole = 'viewer';
  assert.equal(owner === 'owner', true);
  assert.equal(viewer === 'viewer', true);

  console.log('[contract] PASS use-access-role (6 cases)');
}

run();
