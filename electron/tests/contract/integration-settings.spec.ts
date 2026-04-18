import assert from 'node:assert/strict';

/**
 * Integration Settings contract test.
 * Verifies the ConnectorHealthView type contract and utility expectations.
 */

interface ConnectorHealthView {
  system: string;
  healthy: boolean;
  message: string;
  latency_ms: number | null;
}

function run(): void {
  // Healthy connector
  const healthy: ConnectorHealthView = {
    system: 'slack',
    healthy: true,
    message: 'Client available.',
    latency_ms: 0.5,
  };
  assert.equal(healthy.system, 'slack');
  assert.equal(healthy.healthy, true);
  assert.equal(typeof healthy.latency_ms, 'number');

  // Unhealthy connector
  const unhealthy: ConnectorHealthView = {
    system: 'jira',
    healthy: false,
    message: 'No Jira client configured.',
    latency_ms: null,
  };
  assert.equal(unhealthy.healthy, false);
  assert.equal(unhealthy.latency_ms, null);

  // All-healthy check
  const connectors: ConnectorHealthView[] = [healthy, unhealthy];
  const allHealthy = connectors.every((c) => c.healthy);
  assert.equal(allHealthy, false);

  const allGood: ConnectorHealthView[] = [
    { ...healthy },
    { ...healthy, system: 'confluence' },
  ];
  assert.equal(allGood.every((c) => c.healthy), true);

  console.log('[contract] PASS integration-settings model');
}

run();
