import type { MissionContext } from '../../domain/mission';
import { useI18n } from '../../stores/i18nStore';
import { MissionDrawerShell } from './MissionDrawerShell';

interface Props {
  readonly open: boolean;
  readonly mission: MissionContext;
  readonly onClose: () => void;
}

export function ConstraintsDrawer({ open, mission, onClose }: Props) {
  const { t } = useI18n();
  const yes = t('mission.header.yes');
  const no = t('mission.header.no');

  const rows: Array<{ label: string; value: string }> = [
    {
      label: t('mission.header.detail.language'),
      value: mission.constraints.language,
    },
    {
      label: t('mission.header.detail.requiresApproval'),
      value: mission.constraints.requiresApproval ? yes : no,
    },
    {
      label: t('mission.header.detail.localOnlyModel'),
      value: mission.constraints.localOnlyModel ? yes : no,
    },
  ];

  return (
    <MissionDrawerShell
      open={open}
      title={t('mission.drawer.title.constraints')}
      description={t('mission.drawer.description.constraints')}
      onClose={onClose}
      testId="mission-drawer-constraints"
    >
      <dl className="space-y-2">
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex items-center justify-between rounded-2xl border border-ds-border bg-ds-bg/70 px-3 py-2 text-sm text-ds-text"
          >
            <dt className="text-[11px] uppercase tracking-[0.18em] text-ds-muted">
              {row.label}
            </dt>
            <dd className="font-medium">{row.value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 text-[11px] text-ds-muted">
        {t('mission.drawer.readonly')}
      </p>
    </MissionDrawerShell>
  );
}
