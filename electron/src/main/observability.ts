import fs from 'fs';
import os from 'os';
import path from 'path';
import { app } from 'electron';
import * as MainSentry from '@sentry/electron/main';
import { recordDiagnosticLog } from './diagnostics-collector';

export interface RendererObservabilityBootstrap {
  sentryConfigured: boolean;
  errorReportingEnabled: boolean;
  telemetryEnabled: boolean;
}

interface MainObservabilityState extends RendererObservabilityBootstrap {
  initialized: boolean;
  sentryDsn: string | null;
  sentryEnvironment: string;
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

const state: MainObservabilityState = {
  initialized: false,
  sentryDsn: null,
  sentryEnvironment: 'production',
  sentryConfigured: false,
  errorReportingEnabled: false,
  telemetryEnabled: false,
};

let listenersInstalled = false;

export function initializeMainObservability(): RendererObservabilityBootstrap {
  applyMainObservability(loadInitialSettings());
  installElectronCrashHooks();
  return getRendererObservabilityBootstrap();
}

export function updateMainObservability(
  update: Partial<RendererObservabilityBootstrap>
): RendererObservabilityBootstrap {
  state.errorReportingEnabled = update.errorReportingEnabled ?? state.errorReportingEnabled;
  state.telemetryEnabled = update.telemetryEnabled ?? state.telemetryEnabled;
  if (!state.initialized && state.sentryConfigured) {
    applyMainObservability({
      sentryDsn: state.sentryDsn,
      sentryEnvironment: state.sentryEnvironment,
      errorReportingEnabled: state.errorReportingEnabled,
      telemetryEnabled: state.telemetryEnabled,
    });
  }
  return getRendererObservabilityBootstrap();
}

export function shutdownMainObservability(timeoutMs = 2000): void {
  if (!state.initialized) {
    return;
  }
  void MainSentry.flush(timeoutMs).finally(() => {
    void MainSentry.close(timeoutMs);
  });
}

export function captureMainException(
  error: unknown,
  context?: Record<string, unknown>,
  message?: string
): void {
  if (!state.sentryConfigured || !state.initialized) {
    return;
  }
  const normalized = normalizeError(error, message);
  MainSentry.withScope((scope) => {
    if (context) {
      scope.setExtras(sanitizeUnknown(context) as Record<string, unknown>);
    }
    MainSentry.captureException(normalized);
  });
}

export function getRendererObservabilityQuery(): Record<string, string> {
  return {
    sentry: state.sentryConfigured ? '1' : '0',
    errorReporting: state.errorReportingEnabled ? '1' : '0',
    telemetry: state.telemetryEnabled ? '1' : '0',
  };
}

export function getRendererObservabilityBootstrap(): RendererObservabilityBootstrap {
  return {
    sentryConfigured: state.sentryConfigured,
    errorReportingEnabled: state.errorReportingEnabled,
    telemetryEnabled: state.telemetryEnabled,
  };
}

function applyMainObservability(settings: {
  sentryDsn: string | null;
  sentryEnvironment: string;
  errorReportingEnabled: boolean;
  telemetryEnabled: boolean;
}): void {
  state.sentryDsn = settings.sentryDsn;
  state.sentryEnvironment = settings.sentryEnvironment;
  state.sentryConfigured = Boolean(settings.sentryDsn);
  state.errorReportingEnabled = settings.errorReportingEnabled;
  state.telemetryEnabled = settings.telemetryEnabled;

  if (!state.sentryConfigured || state.initialized || !settings.sentryDsn) {
    return;
  }

  MainSentry.init({
    dsn: settings.sentryDsn,
    environment: settings.sentryEnvironment,
    sendDefaultPii: false,
    tracesSampleRate: 1.0,
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
  recordDiagnosticLog('info', 'observability', 'Electron main crash reporting initialized.', {
    environment: settings.sentryEnvironment,
    telemetryEnabled: settings.telemetryEnabled,
    errorReportingEnabled: settings.errorReportingEnabled,
  });
}

function installElectronCrashHooks(): void {
  if (listenersInstalled) {
    return;
  }
  listenersInstalled = true;

  app.on('render-process-gone', (_event, _contents, details) => {
    captureMainException(
      new Error(`Renderer process exited: ${details.reason}`),
      {
        reason: details.reason,
        exitCode: details.exitCode,
      },
      'Renderer process terminated unexpectedly.'
    );
  });
}

function loadInitialSettings(): {
  sentryDsn: string | null;
  sentryEnvironment: string;
  errorReportingEnabled: boolean;
  telemetryEnabled: boolean;
} {
  const fromFile = readPersistedSettings();
  const envDsn = readStringEnv('DS_AGENT_SENTRY_DSN');
  const envEnvironment = readStringEnv('DS_AGENT_SENTRY_ENVIRONMENT');
  const envErrorReporting = readBooleanEnv('DS_AGENT_ERROR_REPORTING_ENABLED');
  const envTelemetry = readBooleanEnv('DS_AGENT_TELEMETRY_ENABLED');

  return {
    sentryDsn: envDsn ?? fromFile.sentryDsn ?? null,
    sentryEnvironment: envEnvironment ?? fromFile.sentryEnvironment ?? 'production',
    errorReportingEnabled: envErrorReporting ?? fromFile.errorReportingEnabled ?? false,
    telemetryEnabled: envTelemetry ?? fromFile.telemetryEnabled ?? false,
  };
}

function readPersistedSettings(): Partial<{
  sentryDsn: string | null;
  sentryEnvironment: string;
  errorReportingEnabled: boolean;
  telemetryEnabled: boolean;
}> {
  const configPath = resolveConfigPath();
  try {
    const raw = fs.readFileSync(configPath, 'utf-8');
    return extractObservabilitySettings(raw);
  } catch {
    return {};
  }
}

function resolveConfigPath(): string {
  const override = process.env.DS_AGENT_CONFIG_PATH?.trim();
  if (override) {
    return override;
  }
  return path.join(os.homedir(), '.ds-agent', 'config.yaml');
}

function extractObservabilitySettings(
  raw: string
): Partial<{
  sentryDsn: string | null;
  sentryEnvironment: string;
  errorReportingEnabled: boolean;
  telemetryEnabled: boolean;
}> {
  let inObservabilitySection = false;
  const result: Partial<{
    sentryDsn: string | null;
    sentryEnvironment: string;
    errorReportingEnabled: boolean;
    telemetryEnabled: boolean;
  }> = {};

  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (/^[A-Za-z0-9_]+\s*:\s*$/.test(trimmed) && !line.startsWith(' ')) {
      inObservabilitySection = trimmed === 'observability:';
      continue;
    }
    if (!inObservabilitySection) {
      continue;
    }
    const match = line.match(/^\s+([A-Za-z_]+):\s*(.*)$/);
    if (!match) {
      continue;
    }
    const key = match[1];
    const scalar = parseYamlScalar(match[2]);
    if (key === 'sentry_dsn') {
      result.sentryDsn = typeof scalar === 'string' ? scalar : null;
    } else if (key === 'sentry_environment' && typeof scalar === 'string') {
      result.sentryEnvironment = scalar;
    } else if (key === 'error_reporting_enabled' && typeof scalar === 'boolean') {
      result.errorReportingEnabled = scalar;
    } else if (key === 'telemetry_enabled' && typeof scalar === 'boolean') {
      result.telemetryEnabled = scalar;
    }
  }

  return result;
}

function parseYamlScalar(raw: string): string | boolean | null {
  const withoutComment = raw.replace(/\s+#.*$/, '').trim();
  if (!withoutComment || withoutComment === 'null' || withoutComment === '~') {
    return null;
  }
  if (withoutComment === 'true') {
    return true;
  }
  if (withoutComment === 'false') {
    return false;
  }
  return withoutComment.replace(/^['"]|['"]$/g, '');
}

function readStringEnv(name: string): string | null {
  const value = process.env[name]?.trim();
  return value ? value : null;
}

function readBooleanEnv(name: string): boolean | undefined {
  const value = process.env[name];
  if (!value) {
    return undefined;
  }
  return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase());
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

function normalizeError(error: unknown, fallbackMessage?: string): Error {
  if (error instanceof Error) {
    return error;
  }
  return new Error(fallbackMessage ?? String(error));
}
