/**
 * Policy panel for autonomous runtime state and editing.
 */

import { ShieldAlert } from 'lucide-react';
import { useId, useMemo } from 'react';
import { Badge, Card } from '../../design-system/primitives';
import { useI18n } from '../../stores/i18nStore';
import { usePolicyStore } from '../../stores/policyStore';
import { useRuntimeStore } from '../../stores/runtimeStore';
import { RecurringGoalsPanel } from './RecurringGoalsPanel';
import { translateRuntimeProfile } from './runtimeI18n';
import { StandingOrdersPanel } from './StandingOrdersPanel';

export function PolicyPanel() {
  const { t } = useI18n();
  const headingId = useId();
  const snapshot = usePolicyStore((s) => s.snapshot);
  const lastUpdatedAt = usePolicyStore((s) => s.lastUpdatedAt);
  const runtimeStatus = useRuntimeStore((s) => s.status);

  const recurringGoals = snapshot?.recurringGoals ?? [];
  const standingOrders = snapshot?.standingOrders ?? [];
  const actionMatrixOverrideCount = snapshot?.actionMatrixOverrideCount ?? 0;
  const profile = runtimeStatus?.automationProfile ?? snapshot?.automationProfile ?? 'balanced';

  const summary = useMemo(
    () => t(`run.runtime.profile.description.${profile}`),
    [profile, t],
  );

  return (
    <section className="px-3 py-2" aria-labelledby={headingId}>
      <Card tone="accent" className="space-y-4">
        <header className="flex flex-wrap items-center gap-2">
          <div
            id={headingId}
            className="inline-flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-ds-muted"
          >
            <ShieldAlert size={12} aria-hidden="true" />
            {t('run.runtime.policy.title')}
          </div>
          <Badge tone="accent" compact className="ml-auto uppercase tracking-[0.16em]">
            {translateRuntimeProfile(profile, t)}
          </Badge>
        </header>

        <p className="text-sm leading-6 text-ds-text">{summary}</p>

        <dl className="grid grid-cols-3 gap-3">
          <PolicySummaryCard label={t('run.runtime.policy.summary.recurringGoals')} value={recurringGoals.length} />
          <PolicySummaryCard label={t('run.runtime.policy.summary.standingOrders')} value={standingOrders.length} />
          <PolicySummaryCard label={t('run.runtime.policy.summary.matrixOverrides')} value={actionMatrixOverrideCount} />
        </dl>

        <div className="space-y-4">
          <RecurringGoalsPanel />
          <StandingOrdersPanel />
        </div>

        {lastUpdatedAt ? (
          <p className="text-xs text-ds-muted">
            {t('run.runtime.policy.updated', {
              time: new Date(lastUpdatedAt).toLocaleTimeString(),
            })}
          </p>
        ) : null}
      </Card>
    </section>
  );
}

function PolicySummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <Card className="space-y-2 bg-ds-bg/60">
      <dt className="text-[10px] font-medium uppercase tracking-[0.16em] text-ds-muted">
        {label}
      </dt>
      <dd className="font-mono text-lg text-ds-text">{value}</dd>
    </Card>
  );
}
