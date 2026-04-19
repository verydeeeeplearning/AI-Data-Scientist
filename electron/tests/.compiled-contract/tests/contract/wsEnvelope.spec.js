"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const eventEnvelope_1 = require("../../src/renderer/infrastructure/ws/eventEnvelope");
function run() {
    // === parseEnvelope accepts a well-formed envelope ===
    {
        const raw = {
            type: 'mission.context.updated',
            version: '1.0',
            ts: 1700000000000,
            payload: { goal: 'churn prediction' },
        };
        const result = (0, eventEnvelope_1.parseEnvelope)(raw);
        strict_1.default.equal(result.type, 'mission.context.updated');
        strict_1.default.equal(result.version, '1.0');
        strict_1.default.equal(result.ts, 1700000000000);
        strict_1.default.deepEqual(result.payload, { goal: 'churn prediction' });
    }
    // === parseEnvelope accepts optional source + correlationId ===
    {
        const raw = {
            type: 'card.created',
            version: '1.1',
            ts: 1700000000001,
            source: 'agent-runner',
            correlationId: 'req-123',
            payload: { id: 'card-1' },
        };
        const result = (0, eventEnvelope_1.parseEnvelope)(raw);
        strict_1.default.equal(result.source, 'agent-runner');
        strict_1.default.equal(result.correlationId, 'req-123');
    }
    // === parseEnvelope rejects when required fields missing ===
    {
        strict_1.default.throws(() => (0, eventEnvelope_1.parseEnvelope)({}), eventEnvelope_1.WsEnvelopeError);
        strict_1.default.throws(() => (0, eventEnvelope_1.parseEnvelope)({ type: 'x' }), eventEnvelope_1.WsEnvelopeError);
        strict_1.default.throws(() => (0, eventEnvelope_1.parseEnvelope)({ type: 'x', version: '1.0' }), eventEnvelope_1.WsEnvelopeError);
        strict_1.default.throws(() => (0, eventEnvelope_1.parseEnvelope)({ type: 'x', version: '1.0', ts: 0 }), eventEnvelope_1.WsEnvelopeError);
    }
    // === parseEnvelope rejects type with wrong shape ===
    {
        strict_1.default.throws(() => (0, eventEnvelope_1.parseEnvelope)({ type: 123, version: '1.0', ts: 0, payload: {} }), eventEnvelope_1.WsEnvelopeError);
        strict_1.default.throws(() => (0, eventEnvelope_1.parseEnvelope)({ type: '', version: '1.0', ts: 0, payload: {} }), eventEnvelope_1.WsEnvelopeError);
    }
    // === parseEnvelope rejects malformed version ===
    {
        strict_1.default.throws(() => (0, eventEnvelope_1.parseEnvelope)({ type: 'x', version: 'not-a-version', ts: 0, payload: {} }), eventEnvelope_1.WsEnvelopeError);
        strict_1.default.throws(() => (0, eventEnvelope_1.parseEnvelope)({ type: 'x', version: 1.0, ts: 0, payload: {} }), eventEnvelope_1.WsEnvelopeError);
    }
    // === parseEnvelope rejects major version mismatch ===
    {
        const future = { type: 'x', version: '99.0', ts: 0, payload: {} };
        let caught;
        try {
            (0, eventEnvelope_1.parseEnvelope)(future);
        }
        catch (err) {
            caught = err;
        }
        strict_1.default.ok(caught instanceof eventEnvelope_1.WsEnvelopeError);
        strict_1.default.equal(caught.code, 'major-mismatch');
    }
    // === parseEnvelope accepts minor version difference (forward-compat) ===
    {
        const newerMinor = {
            type: 'card.created',
            version: `${eventEnvelope_1.ENVELOPE_MAJOR}.99`,
            ts: 1,
            payload: { id: 'card-1' },
        };
        const result = (0, eventEnvelope_1.parseEnvelope)(newerMinor);
        strict_1.default.equal(result.version, `${eventEnvelope_1.ENVELOPE_MAJOR}.99`);
    }
    // === isEnvelope is a type guard that does not throw ===
    {
        strict_1.default.equal((0, eventEnvelope_1.isEnvelope)({ type: 'x', version: '1.0', ts: 1, payload: {} }), true);
        strict_1.default.equal((0, eventEnvelope_1.isEnvelope)({}), false);
        strict_1.default.equal((0, eventEnvelope_1.isEnvelope)(null), false);
        strict_1.default.equal((0, eventEnvelope_1.isEnvelope)(undefined), false);
        strict_1.default.equal((0, eventEnvelope_1.isEnvelope)('string'), false);
    }
    // === ENVELOPE_VERSION is current semver ===
    {
        strict_1.default.match(eventEnvelope_1.ENVELOPE_VERSION, /^\d+\.\d+$/);
        strict_1.default.equal(typeof eventEnvelope_1.ENVELOPE_MAJOR, 'number');
    }
    // === Round-trip: envelope JSON.stringify -> JSON.parse -> parseEnvelope ===
    {
        const original = {
            type: 'reasoning.emitted',
            version: eventEnvelope_1.ENVELOPE_VERSION,
            ts: Date.now(),
            source: 'agent-runner',
            correlationId: 'corr-42',
            payload: { hypothesis: 'data leak', action: 'inspect' },
        };
        const json = JSON.stringify(original);
        const decoded = (0, eventEnvelope_1.parseEnvelope)(JSON.parse(json));
        strict_1.default.deepEqual(decoded, original);
    }
    console.log('[contract] PASS ws-envelope (10 cases)');
}
run();
