import type { MissionContext } from '../../domain/mission';
import { getLocaleOption, useI18n } from '../../stores/i18nStore';
import { MissionDrawerShell } from './MissionDrawerShell';

interface Props {
  readonly open: boolean;
  readonly mission: MissionContext;
  readonly onClose: () => void;
}

export function DataSourcesDrawer({ open, mission, onClose }: Props) {
  const { locale, t } = useI18n();
  const localeTag = getLocaleOption(locale).bcp47;

  return (
    <MissionDrawerShell
      open={open}
      title={t('mission.drawer.title.dataSources')}
      description={t('mission.drawer.description.dataSources')}
      onClose={onClose}
      testId="mission-drawer-data-sources"
    >
      {mission.dataSources.length === 0 ? (
        <p className="text-xs text-ds-muted">
          {t('mission.header.detail.noDataSources')}
        </p>
      ) : (
        <ul className="space-y-2">
          {mission.dataSources.map((source) => (
            <li
              key={source.label}
              className="rounded-2xl border border-ds-border bg-ds-bg/70 px-3 py-2 text-sm text-ds-text"
            >
              <div className="font-medium">{source.label}</div>
              <div className="mt-1 text-[11px] uppercase tracking-[0.18em] text-ds-muted">
                {source.type}
                {typeof source.rowCount === 'number'
                  && ` · ${t('mission.header.rows', {
                    count: source.rowCount.toLocaleString(localeTag),
                  })}`}
              </div>
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
