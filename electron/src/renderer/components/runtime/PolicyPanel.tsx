/**
 * Policy panel for autonomous runtime state and editing.
 */

import { ShieldAlert } from 'lucide-react';
import { useId, useMemo } from 'react';
import { Badge, Card } from '../../design-system/primitives';
import { usePolicyStore } from '../../stores/policyStore';
import { useRuntimeStore } from '../../stores/runtimeStore';
import { RecurringGoalsPanel } from './RecurringGoalsPanel';
import { StandingOrdersPanel } from './StandingOrdersPanel';

const PROFILE_DESCRIPTIONS: Record<'manual' | 'balanced' | 'aggressive', string> = {
  manual: 'Suppresses proactive automation until an operator or direct runtime trigger intervenes.',
  balanced: 'Allows direct runtime wake-ups while keeping monitoring-driven remediation conservative.',
  aggressive: 'Allows proactive review and monitoring-driven remediation when the runtime is healthy.',
};

export function PolicyPanel() {
  const headingId = useId();
  const snapshot = usePolicyStore((s) => s.snapshot);
  const lastUpdatedAt = usePolicyStore((s) => s.lastUpdatedAt);
  const runtimeStatus = useRuntimeStore((s) => s.status);

  const recurringGoals = snapshot?.recurringGoals ?? [];
  const standingOrders = snapshot?.standingOrders ?? [];
  const actionMatrixOverrideCount = snapshot?.actionMatrixOverrideCount ?? 0;
  const profile = runtimeStatus?.automationProfile ?? snapshot?.automationProfile ?? 'balanced';

  const summary = useMemo(
    () => PROFILE_DESCRIPTIONS[profile],
    [profile],
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
            Policy
          </div>
          <Badge tone="accent" compact className="ml-auto uppercase tracking-[0.16em]">
            {profile}
          </Badge>
        </header>

        <p className="text-sm leading-6 text-ds-text">{summary}</p>

        <dl className="grid grid-cols-3 gap-3">
          <PolicySummaryCard label="Recurring goals" value={recurringGoals.length} />
          <PolicySummaryCard label="Standing orders" value={standingOrders.length} />
          <PolicySummaryCard label="Matrix overrides" value={actionMatrixOverrideCount} />
        </dl>

        <div className="space-y-4">
          <RecurringGoalsPanel />
          <StandingOrdersPanel />
        </div>

        {lastUpdatedAt ? (
          <p className="text-xs text-ds-muted">
            Policy updated {new Date(lastUpdatedAt).toLocaleTimeString()}
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
