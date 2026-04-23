import type { MissionContext } from '../../domain/mission';
import { useI18n } from '../../stores/i18nStore';
import { MissionDrawerShell } from './MissionDrawerShell';

interface Props {
  readonly open: boolean;
  readonly mission: MissionContext;
  readonly onClose: () => void;
}

export function DeliverablesDrawer({ open, mission, onClose }: Props) {
  const { t } = useI18n();
  return (
    <MissionDrawerShell
      open={open}
      title={t('mission.drawer.title.deliverables')}
      description={t('mission.drawer.description.deliverables')}
      onClose={onClose}
      testId="mission-drawer-deliverables"
    >
      {mission.deliverables.length === 0 ? (
        <p className="text-xs text-ds-muted">
          {t('mission.header.detail.noDeliverables')}
        </p>
      ) : (
        <ul className="space-y-2">
          {mission.deliverables.map((item) => (
            <li
              key={item}
              className="rounded-2xl border border-ds-border bg-ds-bg/70 px-3 py-2 text-sm text-ds-text"
            >
              {item}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-4 text-[11px] text-ds-muted">
        {t('mission.drawer.readonly')}
      </p>
    </MissionDrawerShell>
  );
}
