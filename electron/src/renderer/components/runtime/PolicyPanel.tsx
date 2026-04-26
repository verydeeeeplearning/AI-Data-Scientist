/**
 * Policy panel for autonomous runtime state and editing.
 */

import { RefreshCw, ShieldAlert } from 'lucide-react';
import { useId, useMemo, useState } from 'react';
import { Badge, Button, Card } from '../../design-system/primitives';
import { useWs } from '../../hooks/WsProvider';
import { fetchPolicySnapshot } from '../../hooks/usePolicy';
import { useI18n } from '../../stores/i18nStore';
import { usePolicyStore } from '../../stores/policyStore';
import { useRuntimeStore } from '../../stores/runtimeStore';
import { RecurringGoalsPanel } from './RecurringGoalsPanel';
import { translateRuntimeProfile } from './runtimeI18n';
import { StandingOrdersPanel } from './StandingOrdersPanel';

export function PolicyPanel() {
  const { t } = useI18n();
  const headingId = useId();
  const { rpc } = useWs();
  const snapshot = usePolicyStore((s) => s.snapshot);
  const setSnapshot = usePolicyStore((s) => s.setSnapshot);
  const markUpdated = usePolicyStore((s) => s.markUpdated);
  const lastUpdatedAt = usePolicyStore((s) => s.lastUpdatedAt);
  const runtimeStatus = useRuntimeStore((s) => s.status);
  const [refreshing, setRefreshing] = useState(false);

  const profile = runtimeStatus?.automationProfile ?? snapshot?.automationProfile ?? 'balanced';

  const summary = useMemo(
    () => t(`run.runtime.profile.description.${profile}`),
    [profile, t],
  );

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      setSnapshot(await fetchPolicySnapshot(rpc));
      markUpdated();
    } catch (err) {
      console.warn('[PolicyPanel] manual refresh failed:', err);
    } finally {
      setRefreshing(false);
    }
  };

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
          <Badge tone="accent" compact className="uppercase tracking-[0.16em]">
            {translateRuntimeProfile(profile, t)}
          </Badge>
          <Button
            type="button"
            onClick={() => void handleRefresh()}
            variant="secondary"
            size="sm"
            loading={refreshing}
            leadingIcon={<RefreshCw size={14} aria-hidden="true" />}
            className="ml-auto"
          >
            {t('run.runtime.policy.action.refresh')}
          </Button>
        </header>

        <p className="text-sm leading-6 text-ds-text">{summary}</p>

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
