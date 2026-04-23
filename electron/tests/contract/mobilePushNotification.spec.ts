import assert from 'node:assert/strict';

import {
  normalizePushNotification,
  resolveNotificationClickTarget,
} from '../../src/mobile/sw/pushPayload';

function run(): void {
  const normalized = normalizePushNotification({
    title: 'Approve run',
    body: 'A queued action needs review',
    data: {
      deepLink: 'ds-agent://run/r-1',
      category: 'approval',
    },
  });
  assert.equal(normalized.title, 'Approve run');
  assert.equal(normalized.body, 'A queued action needs review');
  assert.equal(normalized.deepLink, 'ds-agent://run/r-1');
  assert.equal(normalized.tag, 'ds-agent-approval');

  const fallback = normalizePushNotification(null);
  assert.equal(fallback.title, 'DS Agent');
  assert.equal(fallback.body, '');
  assert.equal(fallback.deepLink, null);

  assert.equal(
    resolveNotificationClickTarget({ deepLink: 'ds-agent://workspace/ws-1' }),
    'ds-agent://workspace/ws-1',
  );
  assert.equal(resolveNotificationClickTarget({}, './'), './');

  console.log('[contract] PASS mobile-push-notification (4 cases)');
}

run();
