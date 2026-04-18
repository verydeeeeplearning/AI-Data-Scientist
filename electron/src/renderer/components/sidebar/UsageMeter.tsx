import { useUsageStore } from '../../stores/usageStore';

function meterTone(pct: number): string {
  if (pct >= 100) return 'bg-ds-error';
  if (pct >= 60) return 'bg-ds-warning';
  return 'bg-ds-success';
}

function formatBudget(budget: number | null): string {
  return budget == null ? 'Unlimited' : `$${budget.toFixed(0)}`;
}

export function UsageMeter() {
  const summary = useUsageStore((s) => s.summary);

  if (!summary) return null;

  const pct = Math.min(summary.budgetUsedPct, 100);
  const showVisualWarning = pct >= 60;

  return (
    <div className="px-3 py-2 border-t border-ds-border/50">
      <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-ds-muted">
        <span>Monthly Usage</span>
        <span className={summary.limitExceeded ? 'text-ds-error' : showVisualWarning ? 'text-ds-warning' : ''}>
          {summary.monthRunCount} runs
        </span>
      </div>

      <div className="mt-2 flex items-end justify-between gap-2">
        <div className="text-sm font-semibold text-ds-text">
          ${summary.monthlyCostUsd.toFixed(2)}
        </div>
        <div className="text-[11px] text-ds-muted">{formatBudget(summary.monthlyBudgetUsd)}</div>
      </div>

      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-ds-border">
        <div
          className={`h-full rounded-full transition-all duration-300 ${meterTone(pct)}`}
          style={{ width: `${summary.monthlyBudgetUsd == null ? 0 : pct}%` }}
        />
      </div>

      <div className="mt-2 text-[11px] text-ds-muted">
        Session ${summary.sessionCostUsd.toFixed(2)} · Today ${summary.todayCostUsd.toFixed(2)}
      </div>

      {summary.cacheSavingsUsd > 0 && (
        <div className="mt-1 text-[11px] text-ds-success">
          Saved ${summary.cacheSavingsUsd.toFixed(2)} via caching
        </div>
      )}

      {summary.warningLevel === 'warning' && (
        <div className="mt-1 text-[11px] text-ds-warning">
          {summary.warningThresholdPct.toFixed(0)}% of the monthly budget has been used.
        </div>
      )}

      {summary.limitExceeded && (
        <div className="mt-1 text-[11px] text-ds-error">
          Monthly budget reached. New analyses will be blocked until the limit is raised.
        </div>
      )}
    </div>
  );
}
