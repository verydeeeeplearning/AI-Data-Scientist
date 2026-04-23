import assert from 'node:assert/strict';

import { buildShareUrl } from '../../src/renderer/application/sharing/buildShareUrl';

function run(): void {
  // run resource builds correct path
  assert.equal(buildShareUrl({ resourceType: 'run', resourceId: 'run-42' }).url, '/runs/run-42');

  // artifact / session / mission cover all 4 resource types
  assert.equal(
    buildShareUrl({ resourceType: 'artifact', resourceId: 'art-abc' }).url,
    '/artifacts/art-abc',
  );
  assert.equal(buildShareUrl({ resourceType: 'session', resourceId: 's-1' }).url, '/sessions/s-1');
  assert.equal(buildShareUrl({ resourceType: 'mission', resourceId: 'm-9' }).url, '/missions/m-9');

  // baseUrl prefix is prepended
  assert.equal(
    buildShareUrl({
      resourceType: 'run',
      resourceId: 'run-1',
      baseUrl: 'https://ds-agent.local',
    }).url,
    'https://ds-agent.local/runs/run-1',
  );

  // baseUrl trailing slash is normalized
  assert.equal(
    buildShareUrl({
      resourceType: 'run',
      resourceId: 'run-1',
      baseUrl: 'https://ds-agent.local/',
    }).url,
    'https://ds-agent.local/runs/run-1',
  );

  // resourceId whitespace is trimmed
  const trimmed = buildShareUrl({ resourceType: 'run', resourceId: '  run-77  ' });
  assert.equal(trimmed.resourceId, 'run-77');
  assert.ok(trimmed.url.endsWith('/runs/run-77'));

  // empty resourceId throws
  assert.throws(
    () => buildShareUrl({ resourceType: 'run', resourceId: '   ' }),
    /resourceId is required/,
  );

  // resourceId with special chars is encoded
  const encoded = buildShareUrl({ resourceType: 'run', resourceId: 'run/with/slash' });
  assert.ok(encoded.url.includes('run%2Fwith%2Fslash'));

  console.log('[contract] PASS build-share-url (10 cases)');
}

run();
