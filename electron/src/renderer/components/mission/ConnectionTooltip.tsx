import type { MissionConnectionState } from '../../domain/mission';
import { Badge, Card } from '../../design-system/primitives';
import { useI18n } from '../../stores/i18nStore';

interface Props {
  readonly state: MissionConnectionState;
  readonly latencyMs?: number;
}

export function ConnectionTooltip({ state, latencyMs }: Props) {
  const { t } = useI18n();
  const stateLabel = describeConnectionState(state, t);
  const message = describeConnection(state, t);
  const latencyLabel
    = typeof latencyMs === 'number'
      ? `${Math.round(latencyMs)} ms`
      : t('mission.header.noLatency');

  return (
    <Card
      tone={getConnectionTooltipTone(state)}
      role="tooltip"
      className="bg-ds-bg/90 p-ds-3 text-xs shadow-lg"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">
          {t('mission.connection.tooltip.label')}
        </div>
        <Badge compact tone={getConnectionBadgeTone(state)}>
          {stateLabel}
        </Badge>
      </div>
      <p className="mt-2 leading-5 text-ds-text">{message}</p>
      <p className="mt-2 text-[11px] text-ds-muted">{latencyLabel}</p>
    </Card>
  );
}

function describeConnection(
  state: MissionConnectionState,
  t: (key: string) => string,
): string {
  switch (state) {
    case 'connected':
      return t('mission.connection.tooltip.healthy');
    case 'reconnecting':
      return t('mission.connection.tooltip.reconnecting');
    case 'disconnected':
    default:
      return t('mission.connection.tooltip.disconnected');
  }
}

function describeConnectionState(
  state: MissionConnectionState,
  t: (key: string) => string,
): string {
  switch (state) {
    case 'connected':
      return t('mission.header.connection.connected');
    case 'reconnecting':
      return t('mission.header.connection.reconnecting');
    case 'disconnected':
    default:
      return t('mission.header.connection.disconnected');
  }
}

function getConnectionBadgeTone(
  state: MissionConnectionState,
): 'success' | 'warning' | 'danger' {
  switch (state) {
    case 'connected':
      return 'success';
    case 'reconnecting':
      return 'warning';
    case 'disconnected':
    default:
      return 'danger';
  }
}

function getConnectionTooltipTone(
  state: MissionConnectionState,
): 'elevated' | 'accent' | 'danger' {
  switch (state) {
    case 'connected':
      return 'elevated';
    case 'reconnecting':
      return 'accent';
    case 'disconnected':
    default:
      return 'danger';
  }
}
