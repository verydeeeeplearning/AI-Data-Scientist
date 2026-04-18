import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Activity, ShieldCheck } from 'lucide-react';
import { configureRendererObservability } from '../../observability';
import type { RpcFn } from './types';

type SaveTarget = 'error' | 'telemetry' | null;

export function PrivacySettings({ rpc }: { rpc: RpcFn }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<SaveTarget>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [sentryConfigured, setSentryConfigured] = useState(false);
  const [errorReportingEnabled, setErrorReportingEnabled] = useState(false);
  const [telemetryEnabled, setTelemetryEnabled] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void rpc('config.get')
      .then((result) => {
        if (cancelled) {
          return;
        }
        const config = (result.config ?? {}) as Record<string, unknown>;
        const observability =
          config.observability && typeof config.observability === 'object'
            ? (config.observability as Record<string, unknown>)
            : {};
        const hasSentryDsn =
          typeof observability.sentry_dsn === 'string' && observability.sentry_dsn.trim().length > 0;
        const nextErrorReporting = Boolean(observability.error_reporting_enabled);
        const nextTelemetry = Boolean(observability.telemetry_enabled);

        setSentryConfigured(hasSentryDsn);
        setErrorReportingEnabled(nextErrorReporting);
        setTelemetryEnabled(nextTelemetry);
        configureRendererObservability({
          sentryConfigured: hasSentryDsn,
          errorReportingEnabled: nextErrorReporting,
          telemetryEnabled: nextTelemetry,
        });
      })
      .catch((error) => {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : String(error));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [rpc]);

  const syncDesktopObservability = async (
    nextErrorReporting: boolean,
    nextTelemetry: boolean,
    nextSentryConfigured: boolean = sentryConfigured
  ) => {
    configureRendererObservability({
      sentryConfigured: nextSentryConfigured,
      errorReportingEnabled: nextErrorReporting,
      telemetryEnabled: nextTelemetry,
    });
    if (window.electronAPI?.updateObservability) {
      await window.electronAPI.updateObservability({
        errorReportingEnabled: nextErrorReporting,
        telemetryEnabled: nextTelemetry,
      });
    }
  };

  const persistToggle = async (target: Exclude<SaveTarget, null>, nextValue: boolean) => {
    const prevErrorReporting = errorReportingEnabled;
    const prevTelemetry = telemetryEnabled;
    const nextErrorReporting = target === 'error' ? nextValue : errorReportingEnabled;
    const nextTelemetry = target === 'telemetry' ? nextValue : telemetryEnabled;

    setSaving(target);
    setErrorMessage(null);
    setErrorReportingEnabled(nextErrorReporting);
    setTelemetryEnabled(nextTelemetry);

    try {
      await rpc('config.set', {
        path:
          target === 'error'
            ? 'observability.error_reporting_enabled'
            : 'observability.telemetry_enabled',
        value: nextValue,
      });
      await syncDesktopObservability(nextErrorReporting, nextTelemetry);
    } catch (error) {
      setErrorReportingEnabled(prevErrorReporting);
      setTelemetryEnabled(prevTelemetry);
      await syncDesktopObservability(prevErrorReporting, prevTelemetry);
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-ds-border bg-ds-bg p-3 text-[11px] text-ds-muted">
        Crash reports and performance telemetry are off by default. API keys, OAuth tokens, and
        backend handshake secrets are redacted before anything is sent.
      </div>

      {!sentryConfigured && (
        <div className="rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-[11px] text-amber-200">
          Remote crash reporting is not configured for this build yet. Your preference will still be
          saved and applied automatically once a Sentry DSN is configured.
        </div>
      )}

      {errorMessage && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-[11px] text-red-200">
          {errorMessage}
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <ToggleCard
          icon={<ShieldCheck size={14} />}
          title="Anonymous Crash Reports"
          description="Send redacted renderer/main/backend exceptions so repeated failures can be fixed faster."
          enabled={errorReportingEnabled}
          loading={saving === 'error' || loading}
          onToggle={(value) => void persistToggle('error', value)}
        />
        <ToggleCard
          icon={<Activity size={14} />}
          title="Anonymous Performance Telemetry"
          description="Share low-rate transaction traces to diagnose slow startup, RPC, and UI bottlenecks."
          enabled={telemetryEnabled}
          loading={saving === 'telemetry' || loading}
          onToggle={(value) => void persistToggle('telemetry', value)}
        />
      </div>
    </div>
  );
}

function ToggleCard({
  icon,
  title,
  description,
  enabled,
  loading,
  onToggle,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  enabled: boolean;
  loading: boolean;
  onToggle: (value: boolean) => void;
}) {
  return (
    <div className="rounded-lg border border-ds-border bg-ds-bg p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs font-medium text-ds-text">
            <span className="text-ds-accent">{icon}</span>
            {title}
          </div>
          <p className="mt-2 text-[11px] leading-5 text-ds-muted">{description}</p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          disabled={loading}
          onClick={() => onToggle(!enabled)}
          className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${
            enabled ? 'bg-ds-accent' : 'bg-ds-border'
          } ${loading ? 'opacity-50' : ''}`}
        >
          <span
            className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${
              enabled ? 'translate-x-5' : 'translate-x-1'
            }`}
          />
        </button>
      </div>
      <div className="mt-3 text-[10px] uppercase tracking-wider text-ds-muted">
        {loading ? 'Saving...' : enabled ? 'Enabled' : 'Disabled'}
      </div>
    </div>
  );
}
