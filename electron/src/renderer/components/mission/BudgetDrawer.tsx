import type { MissionContext } from '../../domain/mission';
import { getMissionBudgetRatio, getMissionBudgetState } from '../../domain/mission';
import { getLocaleOption, useI18n } from '../../stores/i18nStore';
import { MissionDrawerShell } from './MissionDrawerShell';

interface Props {
  readonly open: boolean;
  readonly mission: MissionContext;
  readonly onClose: () => void;
}

function formatUsd(value: number, localeTag: string): string {
  return new Intl.NumberFormat(localeTag, {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  }
  if (seconds < 3600) {
    return `${Math.round(seconds / 60)}m`;
  }
  return `${(seconds / 3600).toFixed(1)}h`;
}

export function BudgetDrawer({ open, mission, onClose }: Props) {
  const { locale, t } = useI18n();
  const localeTag = getLocaleOption(locale).bcp47;
  const state = getMissionBudgetState(mission.budget);
  const ratio = getMissionBudgetRatio(mission.budget) * 100;

  return (
    <MissionDrawerShell
      open={open}
      title={t('mission.drawer.title.budget')}
      description={t('mission.drawer.description.budget')}
      onClose={onClose}
      testId="mission-drawer-budget"
    >
      <div
        className={`rounded-2xl border px-4 py-3 ${
          state === 'error'
            ? 'border-rose-500/40 bg-rose-500/10'
            : state === 'warning'
              ? 'border-amber-500/40 bg-amber-500/10'
              : 'border-ds-border bg-ds-bg/70'
        }`}
      >
        <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">
          {t('mission.header.slot.budget')}
        </div>
        <div className="mt-1 text-base font-semibold text-ds-text">
          {`${formatUsd(mission.budget.spentUsd, localeTag)} / ${formatUsd(
            mission.budget.limitUsd,
            localeTag,
          )}`}
        </div>
        <div
          className="mt-3 h-1.5 overflow-hidden rounded-full bg-ds-border/60"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(ratio)}
        >
          <div
            className={`h-full rounded-full ${
              state === 'error'
                ? 'bg-rose-400'
                : state === 'warning'
                  ? 'bg-amber-400'
                  : 'bg-ds-accent'
            }`}
            style={{ width: `${Math.max(0, Math.min(100, ratio))}%` }}
          />
        </div>
        <dl className="mt-3 space-y-1 text-xs text-ds-muted">
          <div className="flex justify-between">
            <dt>{t('mission.header.detail.elapsed')}</dt>
            <dd>{formatElapsed(mission.budget.elapsedSec)}</dd>
          </div>
          <div className="flex justify-between">
            <dt>{t('mission.header.detail.nearLimit')}</dt>
            <dd>
              {mission.budget.nearLimit
                ? t('mission.header.yes')
                : t('mission.header.no')}
            </dd>
          </div>
        </dl>
      </div>
      <p className="mt-4 text-[11px] text-ds-muted">
        {t('mission.drawer.readonly')}
      </p>
    </MissionDrawerShell>
  );
}
