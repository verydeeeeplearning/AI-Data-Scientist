"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const eventSchemaRegistry_1 = require("../../src/renderer/infrastructure/ws/eventSchemaRegistry");
const eventEnvelope_1 = require("../../src/renderer/infrastructure/ws/eventEnvelope");
const samplePayloadSchema = {
    type: 'sample.event',
    version: '1.0',
    validate(payload) {
        if (typeof payload !== 'object' || payload === null)
            return false;
        const p = payload;
        return typeof p.goal === 'string' && typeof p.budget === 'number';
    },
};
function run() {
    // === registerEventSchema and getEventSchema round-trip ===
    {
        (0, eventSchemaRegistry_1.registerEventSchema)(samplePayloadSchema);
        const fetched = (0, eventSchemaRegistry_1.getEventSchema)('sample.event');
        strict_1.default.ok(fetched);
        strict_1.default.equal(fetched.type, 'sample.event');
    }
    // === knownEventTypes lists registered events ===
    {
        const types = (0, eventSchemaRegistry_1.knownEventTypes)();
        strict_1.default.ok(types.includes('sample.event'));
    }
    // === validateEventPayload accepts valid payload ===
    {
        const ok = (0, eventSchemaRegistry_1.validateEventPayload)('sample.event', { goal: 'churn', budget: 10 });
        strict_1.default.equal(ok.ok, true);
        if (ok.ok) {
            strict_1.default.equal(ok.payload.goal, 'churn');
        }
    }
    // === validateEventPayload rejects invalid payload ===
    {
        const result = (0, eventSchemaRegistry_1.validateEventPayload)('sample.event', { goal: 1, budget: 'no' });
        strict_1.default.equal(result.ok, false);
    }
    // === validateEventPayload returns 'unknown-type' for unregistered ===
    {
        const result = (0, eventSchemaRegistry_1.validateEventPayload)('never.registered', { x: 1 });
        strict_1.default.equal(result.ok, false);
        if (!result.ok) {
            strict_1.default.equal(result.reason, 'unknown-type');
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
            strict_1.default.ok(eventSchemaRegistry_1.EVENT_SCHEMA_REGISTRY.has(t), `expected schema registry to pre-seed ${t}`);
        }
    }
    // === full envelope+payload validation pipeline (golden path) ===
    {
        const envelope = (0, eventEnvelope_1.parseEnvelope)({
            type: 'mission.context.updated',
            version: '1.0',
            ts: 1,
            payload: {
                goal: 'churn prediction',
                stage: { current: 4, total: 7, label: 'modeling' },
                budget: { limit: 10, spent: 2.4, currency: 'USD' },
            },
        });
        const result = (0, eventSchemaRegistry_1.validateEventPayload)(envelope.type, envelope.payload);
        strict_1.default.equal(result.ok, true);
    }
    // === unknown-type validation does NOT crash (graceful, per ADR-0007) ===
    {
        // Should not throw — caller decides whether to log + skip.
        const result = (0, eventSchemaRegistry_1.validateEventPayload)('totally.future.event', { anything: true });
        strict_1.default.equal(result.ok, false);
    }
    console.log('[contract] PASS event-schema-registry (8 cases)');
}
run();
