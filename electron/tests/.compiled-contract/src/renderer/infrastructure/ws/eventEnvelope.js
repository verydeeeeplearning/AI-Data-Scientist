"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.WsEnvelopeError = exports.ENVELOPE_MAJOR = exports.ENVELOPE_VERSION = void 0;
exports.parseEnvelope = parseEnvelope;
exports.isEnvelope = isEnvelope;
exports.wrapEvent = wrapEvent;
exports.ENVELOPE_VERSION = '1.0';
exports.ENVELOPE_MAJOR = 1;
class WsEnvelopeError extends Error {
    constructor(code, message) {
        super(message);
        this.code = code;
        this.name = 'WsEnvelopeError';
    }
}
exports.WsEnvelopeError = WsEnvelopeError;
const VERSION_RE = /^(\d+)\.(\d+)$/;
function parseVersion(v) {
    if (typeof v !== 'string') {
        throw new WsEnvelopeError('wrong-type', `version must be a string, got ${typeof v}`);
    }
    const m = v.match(VERSION_RE);
    if (!m) {
        throw new WsEnvelopeError('malformed-version', `version "${v}" must match major.minor`);
    }
    return { major: Number(m[1]), minor: Number(m[2]) };
}
function parseEnvelope(raw) {
    if (typeof raw !== 'object' || raw === null) {
        throw new WsEnvelopeError('wrong-type', 'envelope must be an object');
    }
    const r = raw;
    if (!('type' in r)) {
        throw new WsEnvelopeError('missing-field', 'envelope.type is required');
    }
    if (typeof r.type !== 'string' || r.type.length === 0) {
        throw new WsEnvelopeError('wrong-type', 'envelope.type must be a non-empty string');
    }
    if (!('version' in r)) {
        throw new WsEnvelopeError('missing-field', 'envelope.version is required');
    }
    const { major } = parseVersion(r.version);
    if (major !== exports.ENVELOPE_MAJOR) {
        throw new WsEnvelopeError('major-mismatch', `envelope major version ${major} mismatches server major ${exports.ENVELOPE_MAJOR}`);
    }
    if (!('ts' in r)) {
        throw new WsEnvelopeError('missing-field', 'envelope.ts is required');
    }
    if (typeof r.ts !== 'number' || !Number.isFinite(r.ts)) {
        throw new WsEnvelopeError('wrong-type', 'envelope.ts must be a finite number');
    }
    if (!('payload' in r)) {
        throw new WsEnvelopeError('missing-field', 'envelope.payload is required');
    }
    const env = {
        type: r.type,
        version: r.version,
        ts: r.ts,
        payload: r.payload,
    };
    if (typeof r.source === 'string') {
        env.source = r.source;
    }
    if (typeof r.correlationId === 'string') {
        env.correlationId = r.correlationId;
    }
    return env;
}
function isEnvelope(raw) {
    try {
        parseEnvelope(raw);
        return true;
    }
    catch {
        return false;
    }
}
function wrapEvent(type, payload, options = {}) {
    const env = {
        type,
        version: exports.ENVELOPE_VERSION,
        ts: options.ts ?? Date.now(),
        payload,
    };
    if (options.source)
        env.source = options.source;
    if (options.correlationId)
        env.correlationId = options.correlationId;
    return env;
}
