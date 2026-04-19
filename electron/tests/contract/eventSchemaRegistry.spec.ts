import assert from 'node:assert/strict';

import {
  registerEventSchema,
  getEventSchema,
  knownEventTypes,
  validateEventPayload,
  EVENT_SCHEMA_REGISTRY,
  type EventSchema,
} from '../../src/renderer/infrastructure/ws/eventSchemaRegistry';
import { parseEnvelope } from '../../src/renderer/infrastructure/ws/eventEnvelope';

interface SamplePayload {
  goal: string;
  budget: number;
}

const samplePayloadSchema: EventSchema<SamplePayload> = {
  type: 'sample.event',
  version: '1.0',
  validate(payload): payload is SamplePayload {
    if (typeof payload !== 'object' || payload === null) return false;
    const p = payload as Record<string, unknown>;
    return typeof p.goal === 'string' && typeof p.budget === 'number';
  },
};

function run(): void {
  // === registerEventSchema and getEventSchema round-trip ===
  {
    registerEventSchema(samplePayloadSchema);
    const fetched = getEventSchema('sample.event');
    assert.ok(fetched);
    assert.equal(fetched.type, 'sample.event');
  }

  // === knownEventTypes lists registered events ===
  {
    const types = knownEventTypes();
    assert.ok(types.includes('sample.event'));
  }

  // === validateEventPayload accepts valid payload ===
  {
    const ok = validateEventPayload<SamplePayload>('sample.event', { goal: 'churn', budget: 10 });
    assert.equal(ok.ok, true);
    if (ok.ok) {
      assert.equal(ok.payload.goal, 'churn');
    }
  }

  // === validateEventPayload rejects invalid payload ===
  {
    const result = validateEventPayload('sample.event', { goal: 1, budget: 'no' });
    assert.equal(result.ok, false);
  }

  // === validateEventPayload returns 'unknown-type' for unregistered ===
  {
    const result = validateEventPayload('never.registered', { x: 1 });
    assert.equal(result.ok, false);
    if (!result.ok) {
      assert.equal(result.reason, 'unknown-type');
    }
  }

  // === EVENT_SCHEMA_REGISTRY pre-seeds known DS Agent events ===
  {
    const expected = [
      'mission.context.updated',
      'card.created',
      'card.updated',
      'card.pinned',
      'plan.created',
      'plan.updated',
      'plan.replanned',
      'reasoning.emitted',
    ];
    for (const t of expected) {
      assert.ok(
        EVENT_SCHEMA_REGISTRY.has(t),
        `expected schema registry to pre-seed ${t}`,
      );
    }
  }

  // === full envelope+payload validation pipeline (golden path) ===
  {
    const envelope = parseEnvelope({
      type: 'mission.context.updated',
      version: '1.0',
      ts: 1,
      payload: {
        goal: 'churn prediction',
        stage: { current: 4, total: 7, label: 'modeling' },
        budget: { limit: 10, spent: 2.4, currency: 'USD' },
      },
    });
    const result = validateEventPayload(envelope.type, envelope.payload);
    assert.equal(result.ok, true);
  }

  // === unknown-type validation does NOT crash (graceful, per ADR-0007) ===
  {
    // Should not throw — caller decides whether to log + skip.
    const result = validateEventPayload('totally.future.event', { anything: true });
    assert.equal(result.ok, false);
  }

  console.log('[contract] PASS event-schema-registry (8 cases)');
}

run();
