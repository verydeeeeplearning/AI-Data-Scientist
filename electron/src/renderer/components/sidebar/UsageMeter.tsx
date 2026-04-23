import { Badge, Card, cn } from '../../design-system/primitives';
import { useUsageStore } from '../../stores/usageStore';

function meterTone(pct: number): string {
  if (pct >= 100) return 'bg-ds-error';
  if (pct >= 60) return 'bg-ds-warning';
  return 'bg-ds-success';
}

function statusTone(pct: number, limitExceeded: boolean): 'danger' | 'warning' | 'success' {
  if (limitExceeded) return 'danger';
  if (pct >= 60) return 'warning';
  return 'success';
}

function formatBudget(budget: number | null): string {
  return budget == null ? 'Unlimited' : `$${budget.toFixed(0)}`;
}

export function UsageMeter() {
  const summary = useUsageStore((s) => s.summary);

  if (!summary) return null;

  const pct = Math.min(summary.budgetUsedPct, 100);

  return (
    <section aria-labelledby="usage-meter-title" className="border-t border-ds-border/50 px-3 py-2">
      <Card className="space-y-3 bg-ds-bg/40 px-ds-3 py-ds-3 shadow-none">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2
              id="usage-meter-title"
              className="text-[10px] font-medium uppercase tracking-wider text-ds-muted"
            >
              Monthly Usage
            </h2>
            <div className="mt-1 text-sm font-semibold text-ds-text">
              ${summary.monthlyCostUsd.toFixed(2)}
            </div>
          </div>
          <Badge
            compact
            tone={statusTone(pct, summary.limitExceeded)}
            className="shrink-0 px-ds-2 py-0.5 normal-case shadow-none"
          >
            {summary.monthRunCount} runs
          </Badge>
        </div>

        <div className="flex items-end justify-between gap-2">
          <div className="text-[11px] text-ds-muted">
            {summary.monthlyBudgetUsd == null ? 'Unlimited budget' : `${pct.toFixed(0)}% used`}
          </div>
          <div className="text-[11px] text-ds-muted">{formatBudget(summary.monthlyBudgetUsd)}</div>
        </div>

        <div
          className="h-1.5 overflow-hidden rounded-full bg-ds-border"
          role={summary.monthlyBudgetUsd == null ? undefined : 'progressbar'}
          aria-valuemin={summary.monthlyBudgetUsd == null ? undefined : 0}
          aria-valuemax={summary.monthlyBudgetUsd == null ? undefined : 100}
          aria-valuenow={summary.monthlyBudgetUsd == null ? undefined : pct}
          aria-valuetext={
            summary.monthlyBudgetUsd == null
              ? 'No monthly budget cap configured.'
              : `${pct.toFixed(0)}% of the monthly budget used.`
          }
        >
          <div
            className={cn(
              'h-full rounded-full transition-all duration-300',
              meterTone(pct),
              summary.monthlyBudgetUsd == null && 'bg-ds-muted/40',
            )}
            style={{ width: `${summary.monthlyBudgetUsd == null ? 0 : pct}%` }}
          />
        </div>

        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <div className="rounded-ds-lg border border-ds-border bg-ds-surface/70 px-ds-3 py-ds-2">
            <div className="text-ds-muted">Session</div>
            <div className="mt-1 text-ds-text">${summary.sessionCostUsd.toFixed(2)}</div>
          </div>
          <div className="rounded-ds-lg border border-ds-border bg-ds-surface/70 px-ds-3 py-ds-2">
            <div className="text-ds-muted">Today</div>
            <div className="mt-1 text-ds-text">${summary.todayCostUsd.toFixed(2)}</div>
          </div>
        </div>

        {summary.cacheSavingsUsd > 0 && (
          <div
            className="rounded-ds-lg border border-ds-success/30 bg-ds-success/10 px-ds-3 py-ds-2 text-[11px] text-ds-success"
            role="status"
            aria-live="polite"
          >
            Saved ${summary.cacheSavingsUsd.toFixed(2)} via caching
          </div>
        )}

        {summary.warningLevel === 'warning' && (
          <div
            className="rounded-ds-lg border border-ds-warning/30 bg-ds-warning/10 px-ds-3 py-ds-2 text-[11px] text-ds-warning"
            role="status"
            aria-live="polite"
          >
            {summary.warningThresholdPct.toFixed(0)}% of the monthly budget has been used.
          </div>
        )}

        {summary.limitExceeded && (
          <div
            className="rounded-ds-lg border border-ds-error/30 bg-ds-error/10 px-ds-3 py-ds-2 text-[11px] text-ds-error"
            role="status"
            aria-live="polite"
          >
            Monthly budget reached. New analyses will be blocked until the limit is raised.
          </div>
        )}
      </Card>
    </section>
  );
}
