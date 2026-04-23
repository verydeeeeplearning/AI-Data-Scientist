import type { MissionContext } from '../../domain/mission';
import { useI18n } from '../../stores/i18nStore';
import { MissionDrawerShell } from './MissionDrawerShell';

interface Props {
  readonly open: boolean;
  readonly mission: MissionContext;
  readonly onClose: () => void;
}

export function GoalDrawer({ open, mission, onClose }: Props) {
  const { t } = useI18n();
  return (
    <MissionDrawerShell
      open={open}
      title={t('mission.drawer.title.goal')}
      description={t('mission.drawer.description.goal')}
      onClose={onClose}
      testId="mission-drawer-goal"
    >
      <div className="space-y-4">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">
            {t('mission.header.slot.goal')}
          </div>
          <p className="mt-1 text-base font-semibold text-ds-text">
            {mission.goal.title}
          </p>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">
            {t('mission.header.detail.successCriteria')}
          </div>
          {mission.goal.successCriteria.length === 0 ? (
            <p className="mt-1 text-xs text-ds-muted">
              {t('mission.header.noSuccessCriteria')}
            </p>
          ) : (
            <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-ds-text">
              {mission.goal.successCriteria.map((criteria) => (
                <li key={criteria}>{criteria}</li>
              ))}
            </ul>
          )}
        </div>
        <p className="text-[11px] text-ds-muted">{t('mission.drawer.readonly')}</p>
      </div>
    </MissionDrawerShell>
  );
}
