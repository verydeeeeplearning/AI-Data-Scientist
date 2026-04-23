import type { MissionContext } from '../../domain/mission';
import { useI18n } from '../../stores/i18nStore';
import { MissionDrawerShell } from './MissionDrawerShell';

interface Props {
  readonly open: boolean;
  readonly mission: MissionContext;
  readonly onClose: () => void;
}

export function StageDrawer({ open, mission, onClose }: Props) {
  const { t } = useI18n();
  const ratio = Math.max(
    0,
    Math.min(100, (mission.stage.current / Math.max(1, mission.stage.total)) * 100),
  );

  return (
    <MissionDrawerShell
      open={open}
      title={t('mission.drawer.title.stage')}
      description={t('mission.drawer.description.stage')}
      onClose={onClose}
      testId="mission-drawer-stage"
    >
      <div className="rounded-2xl border border-ds-border bg-ds-bg/70 px-4 py-3">
        <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">
          {t('mission.header.detail.stageLine', {
            current: mission.stage.current,
            total: mission.stage.total,
          })}
        </div>
        <div className="mt-1 text-base font-semibold text-ds-text">
          {mission.stage.label}
        </div>
        <div
          className="mt-3 h-1.5 overflow-hidden rounded-full bg-ds-border/60"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={mission.stage.total}
          aria-valuenow={mission.stage.current}
        >
          <div
            className="h-full rounded-full bg-ds-accent"
            style={{ width: `${ratio}%` }}
          />
        </div>
      </div>
      <p className="mt-4 text-[11px] text-ds-muted">
        {t('mission.drawer.readonly')}
      </p>
    </MissionDrawerShell>
  );
}
