import assert from 'node:assert/strict';

import { __test } from '../../src/mobile/runtime';

function run(): void {
  const defaults = __test.parseMobileBootstrapParams('');
  assert.equal(defaults.port, 18_790);
  assert.equal(defaults.token, undefined);

  const parsed = __test.parseMobileBootstrapParams('?port=19001&token=abc123');
  assert.equal(parsed.port, 19_001);
  assert.equal(parsed.token, 'abc123');

  const invalidPort = __test.parseMobileBootstrapParams('?port=oops');
  assert.equal(invalidPort.port, 18_790);

  const connected = __test.describeMobileConnection('connected', 'unknown');
  assert.equal(connected.tone, 'success');
  assert.equal(connected.labelKey, 'status.connected');

  const reconnecting = __test.describeMobileConnection('connecting', 'reconnecting');
  assert.equal(reconnecting.detailKey, 'connection.detail.reconnecting');

  const crashed = __test.describeMobileConnection('disconnected', 'backend_crashed');
  assert.equal(crashed.tone, 'danger');
  assert.equal(crashed.detailKey, 'connection.detail.backend');

  console.log('[contract] PASS mobile-bootstrap (9 cases)');
}

run();
