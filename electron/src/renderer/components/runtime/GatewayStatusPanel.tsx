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
import { useRuntimeEventStore } from '../../stores/runtimeEventStore';
import { useRuntimeStore } from '../../stores/runtimeStore';

function getBackendPort(): string {
  const params = new URLSearchParams(window.location.search);
  return params.get('port') ?? '18790';
}

type MetricItem = {
  readonly label: string;
  readonly value: number;
  readonly icon: typeof Bot;
};

const PROFILE_OPTIONS = [
  { value: 'manual', label: 'manual' },
  { value: 'balanced', label: 'balanced' },
  { value: 'aggressive', label: 'aggressive' },
] as const;

const OVERLAY_OPTIONS = [
  { value: 'none', label: 'none' },
  { value: 'incident', label: 'incident' },
  { value: 'freeze', label: 'freeze' },
] as const;

export function GatewayStatusPanel() {
  const { status: connectionStatus, rpc } = useWs();
  const runtimeStatus = useRuntimeStore((s) => s.status);
  const lastUpdatedAt = useRuntimeStore((s) => s.lastUpdatedAt);
  const runtimeEvents = useRuntimeEventStore((s) => s.events);
  const [busy, setBusy] = useState(false);

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
    setBusy(true);
    try {
      await rpc('config.set', {
        path: 'gateway.autonomous_runtime_enabled',
        value: !autonomyEnabled,
      });
    } catch (err) {
      console.warn('[GatewayStatusPanel] autonomous toggle failed:', err);
    } finally {
      setBusy(false);
    }
  };

  const updateAutomationProfile = async (profile: 'manual' | 'balanced' | 'aggressive') => {
    setBusy(true);
    try {
      await rpc('config.set', {
        path: 'gateway.automation_profile',
        value: profile,
      });
    } catch (err) {
      console.warn('[GatewayStatusPanel] automation profile update failed:', err);
    } finally {
      setBusy(false);
    }
  };

  const updateAuthorityOverlay = async (overlay: 'none' | 'incident' | 'freeze') => {
    setBusy(true);
    try {
      await rpc('config.set', {
        path: 'gateway.authority_overlay',
        value: overlay === 'none' ? null : overlay,
      });
    } catch (err) {
      console.warn('[GatewayStatusPanel] authority overlay update failed:', err);
    } finally {
      setBusy(false);
    }
  };

  const metrics: MetricItem[] = [
    { label: 'Sessions', value: runtimeStatus?.activeSessions ?? 0, icon: Bot },
    { label: 'Runs', value: runtimeStatus?.activeRuns ?? 0, icon: Activity },
    { label: 'Tasks', value: runtimeStatus?.activeTasks ?? 0, icon: Activity },
    { label: 'Approvals', value: runtimeStatus?.pendingApprovals ?? 0, icon: ShieldAlert },
  ];

  return (
    <section className="px-3 py-2" aria-labelledby="gateway-status-title" aria-busy={busy}>
      <Card className="space-y-ds-4 border-ds-border bg-ds-bg/70 p-ds-3">
        <header className="flex items-center gap-ds-2 text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
          <Server size={12} aria-hidden="true" />
          <h2 id="gateway-status-title" className="text-inherit">
            Runtime Console
          </h2>
          <Badge
            compact
            tone={connectionStatus === 'connected' ? 'success' : 'danger'}
            className="ml-auto normal-case text-ds-text"
          >
            {connectionStatus}
          </Badge>
        </header>

        <div className="flex flex-wrap items-center justify-between gap-ds-3">
          <div className="flex min-w-0 items-center gap-ds-2 text-ds-xs text-ds-text">
            {connectionStatus === 'connected' ? (
              <Wifi size={14} className="text-ds-success" aria-hidden="true" />
            ) : (
              <WifiOff size={14} className="text-ds-error" aria-hidden="true" />
            )}
            <span className="truncate">Gateway {connectionStatus}</span>
          </div>
          <Button
            variant="secondary"
            size="sm"
            leadingIcon={<RefreshCcw size={12} aria-hidden="true" />}
            onClick={() => window.location.reload()}
            title="Reconnect renderer"
          >
            Reload
          </Button>
        </div>

        <Card className="border-ds-border/70 bg-ds-surface/60 p-ds-3 text-ds-xs text-ds-muted shadow-none">
          <div className="text-[10px] uppercase tracking-wider text-ds-muted">Endpoint</div>
          <div className="mt-ds-2 break-all font-mono text-[10px] text-ds-text">{endpoint}</div>
        </Card>

        <div className="grid grid-cols-2 gap-ds-2">
          {metrics.map((metric) => (
            <MetricCard key={metric.label} {...metric} />
          ))}
        </div>

        <Card className="space-y-ds-3 border-ds-border/70 bg-ds-surface/60 p-ds-3 shadow-none">
          <div className="flex flex-wrap items-center justify-between gap-ds-2">
            <div className="text-ds-sm font-semibold text-ds-text">Autonomous Runtime</div>
            <Badge compact tone={resolveAutonomyTone(autonomyEnabled, autonomyRunning)}>
              {autonomyRunning ? 'running' : autonomyEnabled ? 'enabled' : 'disabled'}
            </Badge>
          </div>

          <div className="grid gap-ds-3 sm:grid-cols-2">
            <Select
              label="Automation profile"
              value={automationProfile}
              onChange={(event) =>
                void updateAutomationProfile(
                  event.target.value as 'manual' | 'balanced' | 'aggressive',
                )
              }
              disabled={busy || connectionStatus !== 'connected'}
              options={PROFILE_OPTIONS}
            />
            <Select
              id="runtime-authority-overlay"
              label="Authority overlay"
              value={overlaySelectValue}
              onChange={(event) =>
                void updateAuthorityOverlay(
                  event.target.value as 'none' | 'incident' | 'freeze',
                )
              }
              disabled={busy || connectionStatus !== 'connected'}
              options={OVERLAY_OPTIONS}
              data-testid="runtime-authority-overlay"
            />
          </div>

          <div className="grid gap-ds-2 sm:grid-cols-2">
            <RuntimeFact label="Effective authority">
              <span
                data-testid="runtime-effective-authority"
                className={resolveAuthorityClassName(authorityOverlay)}
              >
                {effectiveAuthorityMode}
              </span>
            </RuntimeFact>
            <RuntimeFact label="Sensor backlog">
              <span className="font-mono text-ds-text">{runtimeStatus?.sensorBacklog ?? 0}</span>
            </RuntimeFact>
            <RuntimeFact label="Recovered sessions">
              <span className="font-mono text-ds-text">{runtimeStatus?.recoveredSessions ?? 0}</span>
            </RuntimeFact>
            <RuntimeFact label="Timeline warnings">
              <span className="font-mono text-ds-text">{warningCount}</span>
            </RuntimeFact>
            <RuntimeFact label="Recurring goals">
              <span className="font-mono text-ds-text">{runtimeStatus?.recurringGoalCount ?? 0}</span>
            </RuntimeFact>
            <RuntimeFact label="Standing orders">
              <span className="font-mono text-ds-text">{runtimeStatus?.standingOrderCount ?? 0}</span>
            </RuntimeFact>
          </div>

          {authorityOverlayStartedAt ? (
            <RuntimeFact label="Overlay started">
              {new Date(authorityOverlayStartedAt).toLocaleString()}
            </RuntimeFact>
          ) : null}
          {authorityOverlayExpiresAt ? (
            <RuntimeFact label="Overlay expires">
              {new Date(authorityOverlayExpiresAt).toLocaleString()}
            </RuntimeFact>
          ) : null}
          <RuntimeFact label="Resource pressure">
            <span className={runtimeStatus?.resourcePressure ? 'text-ds-warning' : 'text-ds-success'}>
              {runtimeStatus?.resourcePressure ? 'active' : 'normal'}
            </span>
          </RuntimeFact>

          {authorityOverlay === 'freeze' ? (
            <Card
              role="status"
              className="border-ds-warning/30 bg-ds-warning/10 p-ds-3 text-ds-xs text-ds-warning shadow-none"
            >
              Freeze blocks write-side tool actions until the overlay is cleared.
            </Card>
          ) : null}

          <Button
            variant={autonomyEnabled ? 'secondary' : 'primary'}
            size="sm"
            onClick={() => void toggleAutonomy()}
            disabled={busy || connectionStatus !== 'connected'}
          >
            {autonomyEnabled ? 'Disable autonomous runtime' : 'Enable autonomous runtime'}
          </Button>
        </Card>

        {latestAlert ? (
          <Card className="space-y-ds-2 border-ds-border/70 bg-ds-surface/60 p-ds-3 shadow-none">
            <div className="flex items-center justify-between gap-ds-2">
              <div className="text-[10px] uppercase tracking-wider text-ds-muted">Latest alert</div>
              <Badge compact tone={resolveAlertTone(latestAlert.severity)}>
                {latestAlert.severity}
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
            Updated {new Date(lastUpdatedAt).toLocaleTimeString()}
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

function MetricCard({ label, value, icon: Icon }: MetricItem) {
  return (
    <Card className="border-ds-border/70 bg-ds-surface/60 p-ds-3 shadow-none">
      <div className="flex items-center gap-ds-2 text-[10px] uppercase tracking-wider text-ds-muted">
        <Icon size={10} aria-hidden="true" />
        {label}
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
