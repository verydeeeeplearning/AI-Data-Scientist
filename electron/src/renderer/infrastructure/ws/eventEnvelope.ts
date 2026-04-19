export const ENVELOPE_VERSION = '1.0';
export const ENVELOPE_MAJOR = 1;

export interface WsEventEnvelope<TPayload = unknown> {
  type: string;
  version: string;
  ts: number;
  source?: string;
  correlationId?: string;
  payload: TPayload;
}

export type WsEnvelopeErrorCode =
  | 'missing-field'
  | 'wrong-type'
  | 'malformed-version'
  | 'major-mismatch';

export class WsEnvelopeError extends Error {
  readonly code: WsEnvelopeErrorCode;
  constructor(code: WsEnvelopeErrorCode, message: string) {
    super(message);
    this.code = code;
    this.name = 'WsEnvelopeError';
  }
}

const VERSION_RE = /^(\d+)\.(\d+)$/;

function parseVersion(v: unknown): { major: number; minor: number } {
  if (typeof v !== 'string') {
    throw new WsEnvelopeError('wrong-type', `version must be a string, got ${typeof v}`);
  }
  const m = v.match(VERSION_RE);
  if (!m) {
    throw new WsEnvelopeError('malformed-version', `version "${v}" must match major.minor`);
  }
  return { major: Number(m[1]), minor: Number(m[2]) };
}

export function parseEnvelope<T = unknown>(raw: unknown): WsEventEnvelope<T> {
  if (typeof raw !== 'object' || raw === null) {
    throw new WsEnvelopeError('wrong-type', 'envelope must be an object');
  }
  const r = raw as Record<string, unknown>;

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
  if (major !== ENVELOPE_MAJOR) {
    throw new WsEnvelopeError(
      'major-mismatch',
      `envelope major version ${major} mismatches server major ${ENVELOPE_MAJOR}`,
    );
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

  const env: WsEventEnvelope<T> = {
    type: r.type,
    version: r.version as string,
    ts: r.ts,
    payload: r.payload as T,
  };

  if (typeof r.source === 'string') {
    env.source = r.source;
  }
  if (typeof r.correlationId === 'string') {
    env.correlationId = r.correlationId;
  }
  return env;
}

export function isEnvelope(raw: unknown): raw is WsEventEnvelope {
  try {
    parseEnvelope(raw);
    return true;
  } catch {
    return false;
  }
}

export function wrapEvent<T>(
  type: string,
  payload: T,
  options: { source?: string; correlationId?: string; ts?: number } = {},
): WsEventEnvelope<T> {
  const env: WsEventEnvelope<T> = {
    type,
    version: ENVELOPE_VERSION,
    ts: options.ts ?? Date.now(),
    payload,
  };
  if (options.source) env.source = options.source;
  if (options.correlationId) env.correlationId = options.correlationId;
  return env;
}
