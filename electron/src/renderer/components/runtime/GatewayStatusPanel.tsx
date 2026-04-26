/**
 * Gateway/operator status panel for the runtime console.
 */

import { Activity, Bot, RefreshCcw, Server, ShieldAlert, Wifi, WifiOff } from 'lucide-react';
import { useMemo, useState, type ReactNode } from 'react';
import {
  Badge,
  Button,
  Card,
  Select,
} from '../../design-system/primitives';
import { useWs } from '../../hooks/WsProvider';
import { useI18n } from '../../stores/i18nStore';
import { useRuntimeEventStore } from '../../stores/runtimeEventStore';
import { useRuntimeStore } from '../../stores/runtimeStore';
import {
  translateRuntimeConnectionStatus,
  translateRuntimeMode,
  translateRuntimeOverlay,
  translateRuntimeProfile,
  translateRuntimeSeverity,
} from './runtimeI18n';
import { getBackendPort } from '../../utils/backendUrl';

type MetricItem = {
  readonly labelKey: string;
  readonly value: number;
  readonly icon: typeof Bot;
};

export function GatewayStatusPanel() {
  const { t } = useI18n();
  const { status: connectionStatus, rpc } = useWs();
  const runtimeStatus = useRuntimeStore((s) => s.status);
  const lastUpdatedAt = useRuntimeStore((s) => s.lastUpdatedAt);
  const runtimeEvents = useRuntimeEventStore((s) => s.events);
  const [busy, setBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const endpoint = useMemo(() => `ws://127.0.0.1:${getBackendPort()}/ws`, []);
  const autonomyEnabled = runtimeStatus?.autonomousRuntimeEnabled ?? false;
  const autonomyRunning = runtimeStatus?.autonomousRuntimeRunning ?? false;
  const automationProfile = runtimeStatus?.automationProfile ?? 'balanced';
  const authorityOverlay = runtimeStatus?.authorityOverlay ?? null;
  const overlaySelectValue = authorityOverlay ?? 'none';
  const effectiveAuthorityMode = runtimeStatus?.effectiveAuthorityMode ?? runtimeStatus?.mode ?? 'auto';
  const authorityOverlayStartedAt = runtimeStatus?.authorityOverlayStartedAt ?? null;
  const authorityOverlayExpiresAt = runtimeStatus?.authorityOverlayExpiresAt ?? null;
  const latestAlert = runtimeEvents[0] ?? null;
  const warningCount = runtimeEvents.filter((event) => (
    event.severity === 'warning' || event.severity === 'error'
  )).length;

  const toggleAutonomy = async () => {
    const confirmKey = autonomyEnabled
      ? 'run.runtime.gateway.autonomy.confirmDisable'
      : 'run.runtime.gateway.autonomy.confirmEnable';
    if (!window.confirm(t(confirmKey))) {
      return;
    }
    setBusy(true);
    setErrorMessage(null);
    try {
      await rpc('config.set', {
        path: 'gateway.autonomous_runtime_enabled',
        value: !autonomyEnabled,
      });
    } catch (err) {
      console.warn('[GatewayStatusPanel] autonomous toggle failed:', err);
      setErrorMessage(t('run.runtime.gateway.error.autonomyToggleFailed'));
    } finally {
      setBusy(false);
    }
  };

  const updateAutomationProfile = async (profile: 'manual' | 'balanced' | 'aggressive') => {
    setBusy(true);
    setErrorMessage(null);
    try {
      await rpc('config.set', {
        path: 'gateway.automation_profile',
        value: profile,
      });
    } catch (err) {
      console.warn('[GatewayStatusPanel] automation profile update failed:', err);
      setErrorMessage(t('run.runtime.gateway.error.automationProfileFailed'));
    } finally {
      setBusy(false);
    }
  };

  const updateAuthorityOverlay = async (overlay: 'none' | 'incident' | 'freeze') => {
    setBusy(true);
    setErrorMessage(null);
    try {
      await rpc('config.set', {
        path: 'gateway.authority_overlay',
        value: overlay === 'none' ? null : overlay,
      });
    } catch (err) {
      console.warn('[GatewayStatusPanel] authority overlay update failed:', err);
      setErrorMessage(t('run.runtime.gateway.error.authorityOverlayFailed'));
    } finally {
      setBusy(false);
    }
  };

  const profileOptions = [
    { value: 'manual', label: translateRuntimeProfile('manual', t) },
    { value: 'balanced', label: translateRuntimeProfile('balanced', t) },
    { value: 'aggressive', label: translateRuntimeProfile('aggressive', t) },
  ] as const;

  const overlayOptions = [
    { value: 'none', label: translateRuntimeOverlay('none', t) },
    { value: 'incident', label: translateRuntimeOverlay('incident', t) },
    { value: 'freeze', label: translateRuntimeOverlay('freeze', t) },
  ] as const;

  const metrics: MetricItem[] = [
    { labelKey: 'run.runtime.gateway.metric.sessions', value: runtimeStatus?.activeSessions ?? 0, icon: Bot },
    { labelKey: 'run.runtime.gateway.metric.runs', value: runtimeStatus?.activeRuns ?? 0, icon: Activity },
    { labelKey: 'run.runtime.gateway.metric.tasks', value: runtimeStatus?.activeTasks ?? 0, icon: Activity },
    { labelKey: 'run.runtime.gateway.metric.approvals', value: runtimeStatus?.pendingApprovals ?? 0, icon: ShieldAlert },
  ];

  return (
    <section className="px-3 py-2" aria-labelledby="gateway-status-title" aria-busy={busy}>
      <Card className="space-y-ds-4 border-ds-border bg-ds-bg/70 p-ds-3">
        <header className="flex items-center gap-ds-2 text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
          <Server size={12} aria-hidden="true" />
          <h2 id="gateway-status-title" className="text-inherit">
            {t('run.runtime.gateway.title')}
          </h2>
          <Badge
            compact
            tone={connectionStatus === 'connected' ? 'success' : 'danger'}
            className="ml-auto normal-case text-ds-text"
          >
            {translateRuntimeConnectionStatus(connectionStatus, t)}
          </Badge>
        </header>

        <div className="flex flex-wrap items-center justify-between gap-ds-3">
          <div className="flex min-w-0 items-center gap-ds-2 text-ds-xs text-ds-text">
            {connectionStatus === 'connected' ? (
              <Wifi size={14} className="text-ds-success" aria-hidden="true" />
            ) : (
              <WifiOff size={14} className="text-ds-error" aria-hidden="true" />
            )}
            <span className="truncate">
              {t('run.runtime.gateway.connectionLine', {
                status: translateRuntimeConnectionStatus(connectionStatus, t),
              })}
            </span>
          </div>
          <Button
            variant="secondary"
            size="sm"
            leadingIcon={<RefreshCcw size={12} aria-hidden="true" />}
            onClick={() => window.location.reload()}
            title={t('run.runtime.gateway.reconnectTitle')}
          >
            {t('run.runtime.gateway.reload')}
          </Button>
        </div>

        <Card className="border-ds-border/70 bg-ds-surface/60 p-ds-3 text-ds-xs text-ds-muted shadow-none">
          <div className="text-[10px] uppercase tracking-wider text-ds-muted">
            {t('run.runtime.gateway.endpoint')}
          </div>
          <div className="mt-ds-2 break-all font-mono text-[10px] text-ds-text">{endpoint}</div>
        </Card>

        <div className="grid grid-cols-2 gap-ds-2">
          {metrics.map((metric) => (
            <MetricCard key={metric.labelKey} t={t} {...metric} />
          ))}
        </div>

        <Card className="space-y-ds-3 border-ds-border/70 bg-ds-surface/60 p-ds-3 shadow-none">
          <div className="flex flex-wrap items-center justify-between gap-ds-2">
            <div className="text-ds-sm font-semibold text-ds-text">
              {t('run.runtime.gateway.autonomy.title')}
            </div>
            <Badge compact tone={resolveAutonomyTone(autonomyEnabled, autonomyRunning)}>
              {autonomyRunning
                ? t('run.runtime.gateway.autonomy.state.running')
                : autonomyEnabled
                  ? t('run.runtime.gateway.autonomy.state.enabled')
                  : t('run.runtime.gateway.autonomy.state.disabled')}
            </Badge>
          </div>

          {errorMessage ? (
            <p
              role="alert"
              className="text-ds-xs text-ds-error"
              data-testid="runtime-gateway-error"
            >
              {errorMessage}
            </p>
          ) : null}

          <div className="grid gap-ds-3 sm:grid-cols-2">
            <Select
              label={t('run.runtime.gateway.automationProfile')}
              value={automationProfile}
              onChange={(event) =>
                void updateAutomationProfile(
                  event.target.value as 'manual' | 'balanced' | 'aggressive',
                )
              }
              disabled={busy || connectionStatus !== 'connected'}
              options={profileOptions}
            />
            <Select
              id="runtime-authority-overlay"
              label={t('run.runtime.gateway.authorityOverlay')}
              value={overlaySelectValue}
              onChange={(event) =>
                void updateAuthorityOverlay(
                  event.target.value as 'none' | 'incident' | 'freeze',
                )
              }
              disabled={busy || connectionStatus !== 'connected'}
              options={overlayOptions}
              data-testid="runtime-authority-overlay"
            />
          </div>

          <div className="grid gap-ds-2 sm:grid-cols-2">
            <RuntimeFact label={t('run.runtime.gateway.fact.effectiveAuthority')}>
              <span
                data-testid="runtime-effective-authority"
                className={resolveAuthorityClassName(authorityOverlay)}
              >
                {translateRuntimeMode(effectiveAuthorityMode, t)}
              </span>
            </RuntimeFact>
            <RuntimeFact label={t('run.runtime.gateway.fact.sensorBacklog')}>
              <span className="font-mono text-ds-text">{runtimeStatus?.sensorBacklog ?? 0}</span>
            </RuntimeFact>
            <RuntimeFact label={t('run.runtime.gateway.fact.recoveredSessions')}>
              <span className="font-mono text-ds-text">{runtimeStatus?.recoveredSessions ?? 0}</span>
            </RuntimeFact>
            <RuntimeFact label={t('run.runtime.gateway.fact.timelineWarnings')}>
              <span className="font-mono text-ds-text">{warningCount}</span>
            </RuntimeFact>
            <RuntimeFact label={t('run.runtime.gateway.fact.recurringGoals')}>
              <span className="font-mono text-ds-text">{runtimeStatus?.recurringGoalCount ?? 0}</span>
            </RuntimeFact>
            <RuntimeFact label={t('run.runtime.gateway.fact.standingOrders')}>
              <span className="font-mono text-ds-text">{runtimeStatus?.standingOrderCount ?? 0}</span>
            </RuntimeFact>
          </div>

          {authorityOverlayStartedAt ? (
            <RuntimeFact label={t('run.runtime.gateway.fact.overlayStarted')}>
              {new Date(authorityOverlayStartedAt).toLocaleString()}
            </RuntimeFact>
          ) : null}
          {authorityOverlayExpiresAt ? (
            <RuntimeFact label={t('run.runtime.gateway.fact.overlayExpires')}>
              {new Date(authorityOverlayExpiresAt).toLocaleString()}
            </RuntimeFact>
          ) : null}
          <RuntimeFact label={t('run.runtime.gateway.fact.resourcePressure')}>
            <span className={runtimeStatus?.resourcePressure ? 'text-ds-warning' : 'text-ds-success'}>
              {runtimeStatus?.resourcePressure
                ? t('run.runtime.gateway.resourcePressure.active')
                : t('run.runtime.gateway.resourcePressure.normal')}
            </span>
          </RuntimeFact>

          {authorityOverlay === 'freeze' ? (
            <Card
              role="status"
              className="border-ds-warning/30 bg-ds-warning/10 p-ds-3 text-ds-xs text-ds-warning shadow-none"
            >
              {t('run.runtime.gateway.freezeNotice')}
            </Card>
          ) : null}

          <Button
            variant={autonomyEnabled ? 'secondary' : 'primary'}
            size="sm"
            onClick={() => void toggleAutonomy()}
            disabled={busy || connectionStatus !== 'connected'}
          >
            {autonomyEnabled
              ? t('run.runtime.gateway.autonomy.disable')
              : t('run.runtime.gateway.autonomy.enable')}
          </Button>
        </Card>

        {latestAlert ? (
          <Card className="space-y-ds-2 border-ds-border/70 bg-ds-surface/60 p-ds-3 shadow-none">
            <div className="flex items-center justify-between gap-ds-2">
              <div className="text-[10px] uppercase tracking-wider text-ds-muted">
                {t('run.runtime.gateway.latestAlert')}
              </div>
              <Badge compact tone={resolveAlertTone(latestAlert.severity)}>
                {translateRuntimeSeverity(latestAlert.severity, t)}
              </Badge>
            </div>
            <div className="text-ds-xs text-ds-text">{latestAlert.message}</div>
            <div className="text-[10px] text-ds-muted">
              {latestAlert.category} | {latestAlert.kind}
            </div>
          </Card>
        ) : null}

        {lastUpdatedAt ? (
          <div className="text-[10px] text-ds-muted">
            {t('run.runtime.gateway.updated', {
              time: new Date(lastUpdatedAt).toLocaleTimeString(),
            })}
          </div>
        ) : null}
      </Card>
    </section>
  );
}

function resolveAutonomyTone(
  autonomyEnabled: boolean,
  autonomyRunning: boolean,
): 'neutral' | 'success' | 'warning' {
  if (autonomyRunning) {
    return 'success';
  }
  if (autonomyEnabled) {
    return 'warning';
  }
  return 'neutral';
}

function resolveAlertTone(severity: string): 'neutral' | 'warning' | 'danger' {
  if (severity === 'error') {
    return 'danger';
  }
  if (severity === 'warning') {
    return 'warning';
  }
  return 'neutral';
}

function resolveAuthorityClassName(authorityOverlay: string | null): string {
  if (authorityOverlay === 'freeze') {
    return 'text-ds-error';
  }
  if (authorityOverlay === 'incident') {
    return 'text-ds-warning';
  }
  return 'text-ds-text';
}

function MetricCard({
  labelKey,
  value,
  icon: Icon,
  t,
}: MetricItem & { t: (key: string) => string }) {
  return (
    <Card className="border-ds-border/70 bg-ds-surface/60 p-ds-3 shadow-none">
      <div className="flex items-center gap-ds-2 text-[10px] uppercase tracking-wider text-ds-muted">
        <Icon size={10} aria-hidden="true" />
        {t(labelKey)}
      </div>
      <div className="mt-ds-2 text-ds-lg font-mono text-ds-text">{value}</div>
    </Card>
  );
}

function RuntimeFact({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-ds-3 rounded-ds-lg border border-ds-border/70 bg-ds-bg/60 px-ds-3 py-ds-2 text-ds-xs">
      <span className="text-ds-muted">{label}</span>
      <span className="text-right text-ds-text">{children}</span>
    </div>
  );
}
