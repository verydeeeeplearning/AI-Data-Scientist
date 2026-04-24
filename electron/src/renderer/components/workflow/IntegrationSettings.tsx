import { useEffect } from 'react';
import { useIntegrationHealth } from '../../hooks/useIntegrationHealth';
import type { ConnectorHealthView } from '../../hooks/useIntegrationHealth';
import { useI18n } from '../../stores/i18nStore';

const STATUS_STYLES: Record<string, string> = {
  healthy: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
  unhealthy: 'bg-rose-500/15 text-rose-300 border-rose-500/40',
};

function ConnectorCard({ connector }: { connector: ConnectorHealthView }) {
  const { t } = useI18n();
  const statusKey = connector.healthy ? 'healthy' : 'unhealthy';
  return (
    <div
      className={`rounded-xl border px-3 py-2 ${STATUS_STYLES[statusKey]}`}
      data-testid={`connector-${connector.system}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide">{connector.system}</span>
        <span className="text-[10px]">
          {connector.healthy
            ? t('workspace.workflow.integrations.status.connected')
            : t('workspace.workflow.integrations.status.unavailable')}
        </span>
      </div>
      <p className="mt-1 text-[11px] opacity-70">{connector.message}</p>
      {connector.latency_ms !== null && (
        <p className="mt-0.5 text-[10px] opacity-50">{connector.latency_ms.toFixed(1)} ms</p>
      )}
    </div>
  );
}

export function IntegrationSettings() {
  const { t } = useI18n();
  const { connectors, allHealthy, loading, error, refresh } = useIntegrationHealth();

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <section
      className="mx-3 rounded-2xl border border-ds-border bg-ds-bg px-4 py-4"
      data-testid="integration-settings"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ds-text">
            {t('workspace.workflow.integrations.title')}
          </h3>
          {allHealthy !== null && (
            <p className="mt-1 text-[11px] text-ds-muted">
              {allHealthy
                ? t('workspace.workflow.integrations.allHealthy')
                : t('workspace.workflow.integrations.needsAttention')}
            </p>
          )}
        </div>
        <button
          onClick={() => void refresh()}
          disabled={loading}
          className="rounded-lg border border-ds-border px-3 py-1.5 text-[11px] text-ds-muted hover:border-ds-accent hover:text-ds-text disabled:opacity-40"
          data-testid="integration-health-check-btn"
        >
          {loading
            ? t('workspace.workflow.integrations.checking')
            : t('workspace.workflow.integrations.healthCheck')}
        </button>
      </div>

      {error && (
        <div className="mt-3 rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
          {error}
        </div>
      )}

      {connectors.length > 0 && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {connectors.map((c) => (
            <ConnectorCard key={c.system} connector={c} />
          ))}
        </div>
      )}

      {!loading && connectors.length === 0 && !error && (
        <p className="mt-3 text-xs text-ds-muted">
          {t('workspace.workflow.integrations.empty', {
            action: t('workspace.workflow.integrations.healthCheck'),
          })}
        </p>
      )}
    </section>
  );
}
