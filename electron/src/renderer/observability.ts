import * as RendererSentry from '@sentry/electron/renderer';

export interface RendererObservabilityBootstrap {
  sentryConfigured: boolean;
  errorReportingEnabled: boolean;
  telemetryEnabled: boolean;
}

const REDACTED = '***REDACTED***';
const SECRET_FIELD_TOKENS = ['key', 'token', 'secret', 'password', 'authorization', 'cookie'];
const SECRET_PATTERNS = [
  /READY:(\d+):[^\s]+/g,
  /sk-ant-[A-Za-z0-9\-_]+/g,
  /sk-[A-Za-z0-9\-_]{20,}/g,
  /ya29\.[A-Za-z0-9\-_]+/g,
  /1\/\/[A-Za-z0-9\-_]+/g,
  /\b\d{8,}:[A-Za-z0-9\-_]{20,}\b/g,
];

const state: RendererObservabilityBootstrap & { initialized: boolean } = {
  initialized: false,
  sentryConfigured: false,
  errorReportingEnabled: false,
  telemetryEnabled: false,
};

export function bootstrapRendererObservabilityFromQuery(): RendererObservabilityBootstrap {
  const params = new URLSearchParams(window.location.search);
  return configureRendererObservability({
    sentryConfigured: params.get('sentry') === '1',
    errorReportingEnabled: params.get('errorReporting') === '1',
    telemetryEnabled: params.get('telemetry') === '1',
  });
}

export function configureRendererObservability(
  update: Partial<RendererObservabilityBootstrap>
): RendererObservabilityBootstrap {
  state.sentryConfigured = update.sentryConfigured ?? state.sentryConfigured;
  state.errorReportingEnabled = update.errorReportingEnabled ?? state.errorReportingEnabled;
  state.telemetryEnabled = update.telemetryEnabled ?? state.telemetryEnabled;

  if (state.sentryConfigured && !state.initialized) {
    RendererSentry.init({
      beforeSend(event) {
        if (!state.errorReportingEnabled) {
          return null;
        }
        return sanitizeUnknown(event);
      },
      beforeSendTransaction(event) {
        if (!state.telemetryEnabled) {
          return null;
        }
        return sanitizeUnknown(event);
      },
    });
    state.initialized = true;
  }

  return {
    sentryConfigured: state.sentryConfigured,
    errorReportingEnabled: state.errorReportingEnabled,
    telemetryEnabled: state.telemetryEnabled,
  };
}

export function captureRendererException(
  error: unknown,
  context?: Record<string, unknown>
): void {
  if (!state.initialized || !state.sentryConfigured) {
    return;
  }
  RendererSentry.withScope((scope) => {
    if (context) {
      scope.setExtras(sanitizeUnknown(context) as Record<string, unknown>);
    }
    RendererSentry.captureException(normalizeError(error));
  });
}

function sanitizeUnknown<T>(value: T): T {
  if (typeof value === 'string') {
    return sanitizeText(value) as T;
  }
  if (Array.isArray(value)) {
    return value.map((entry) => sanitizeUnknown(entry)) as T;
  }
  if (value && typeof value === 'object') {
    const result: Record<string, unknown> = {};
    for (const [key, entry] of Object.entries(value as Record<string, unknown>)) {
      if (SECRET_FIELD_TOKENS.some((token) => key.toLowerCase().includes(token))) {
        result[key] = REDACTED;
        continue;
      }
      result[key] = sanitizeUnknown(entry);
    }
    return result as T;
  }
  return value;
}

function sanitizeText(value: string): string {
  let sanitized = value;
  for (const pattern of SECRET_PATTERNS) {
    sanitized = sanitized.replace(pattern, (match) => {
      if (match.startsWith('READY:')) {
        const port = match.split(':')[1] ?? 'unknown';
        return `READY:${port}:${REDACTED}`;
      }
      return REDACTED;
    });
  }
  return sanitized;
}

function normalizeError(error: unknown): Error {
  if (error instanceof Error) {
    return error;
  }
  return new Error(String(error));
}
