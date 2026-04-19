import assert from 'node:assert/strict';

import {
  parseEnvelope,
  isEnvelope,
  ENVELOPE_VERSION,
  ENVELOPE_MAJOR,
  WsEnvelopeError,
  type WsEventEnvelope,
} from '../../src/renderer/infrastructure/ws/eventEnvelope';

function run(): void {
  // === parseEnvelope accepts a well-formed envelope ===
  {
    const raw = {
      type: 'mission.context.updated',
      version: '1.0',
      ts: 1_700_000_000_000,
      payload: { goal: 'churn prediction' },
    };
    const result: WsEventEnvelope = parseEnvelope(raw);
    assert.equal(result.type, 'mission.context.updated');
    assert.equal(result.version, '1.0');
    assert.equal(result.ts, 1_700_000_000_000);
    assert.deepEqual(result.payload, { goal: 'churn prediction' });
  }

  // === parseEnvelope accepts optional source + correlationId ===
  {
    const raw = {
      type: 'card.created',
      version: '1.1',
      ts: 1_700_000_000_001,
      source: 'agent-runner',
      correlationId: 'req-123',
      payload: { id: 'card-1' },
    };
    const result = parseEnvelope(raw);
    assert.equal(result.source, 'agent-runner');
    assert.equal(result.correlationId, 'req-123');
  }

  // === parseEnvelope rejects when required fields missing ===
  {
    assert.throws(() => parseEnvelope({}), WsEnvelopeError);
    assert.throws(() => parseEnvelope({ type: 'x' }), WsEnvelopeError);
    assert.throws(() => parseEnvelope({ type: 'x', version: '1.0' }), WsEnvelopeError);
    assert.throws(
      () => parseEnvelope({ type: 'x', version: '1.0', ts: 0 }),
      WsEnvelopeError,
    );
  }

  // === parseEnvelope rejects type with wrong shape ===
  {
    assert.throws(
      () => parseEnvelope({ type: 123, version: '1.0', ts: 0, payload: {} }),
      WsEnvelopeError,
    );
    assert.throws(
      () => parseEnvelope({ type: '', version: '1.0', ts: 0, payload: {} }),
      WsEnvelopeError,
    );
  }

  // === parseEnvelope rejects malformed version ===
  {
    assert.throws(
      () => parseEnvelope({ type: 'x', version: 'not-a-version', ts: 0, payload: {} }),
      WsEnvelopeError,
    );
    assert.throws(
      () => parseEnvelope({ type: 'x', version: 1.0, ts: 0, payload: {} }),
      WsEnvelopeError,
    );
  }

  // === parseEnvelope rejects major version mismatch ===
  {
    const future = { type: 'x', version: '99.0', ts: 0, payload: {} };
    let caught: unknown;
    try {
      parseEnvelope(future);
    } catch (err) {
      caught = err;
    }
    assert.ok(caught instanceof WsEnvelopeError);
    assert.equal((caught as WsEnvelopeError).code, 'major-mismatch');
  }

  // === parseEnvelope accepts minor version difference (forward-compat) ===
  {
    const newerMinor = {
      type: 'card.created',
      version: `${ENVELOPE_MAJOR}.99`,
      ts: 1,
      payload: { id: 'card-1' },
    };
    const result = parseEnvelope(newerMinor);
    assert.equal(result.version, `${ENVELOPE_MAJOR}.99`);
  }

  // === isEnvelope is a type guard that does not throw ===
  {
    assert.equal(isEnvelope({ type: 'x', version: '1.0', ts: 1, payload: {} }), true);
    assert.equal(isEnvelope({}), false);
    assert.equal(isEnvelope(null), false);
    assert.equal(isEnvelope(undefined), false);
    assert.equal(isEnvelope('string'), false);
  }

  // === ENVELOPE_VERSION is current semver ===
  {
    assert.match(ENVELOPE_VERSION, /^\d+\.\d+$/);
    assert.equal(typeof ENVELOPE_MAJOR, 'number');
  }

  // === Round-trip: envelope JSON.stringify -> JSON.parse -> parseEnvelope ===
  {
    const original: WsEventEnvelope = {
      type: 'reasoning.emitted',
      version: ENVELOPE_VERSION,
      ts: Date.now(),
      source: 'agent-runner',
      correlationId: 'corr-42',
      payload: { hypothesis: 'data leak', action: 'inspect' },
    };
    const json = JSON.stringify(original);
    const decoded = parseEnvelope(JSON.parse(json));
    assert.deepEqual(decoded, original);
  }

  console.log('[contract] PASS ws-envelope (10 cases)');
}

run();
