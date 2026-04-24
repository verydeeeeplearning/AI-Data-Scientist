/**
 * Budget bar ??cost and context token usage visualization.
 */

import { useI18n } from '../../stores/i18nStore';
import { useWorkflowStore } from '../../stores/workflowStore';

function pctColor(pct: number): string {
  if (pct >= 80) return 'bg-ds-error';
  if (pct >= 60) return 'bg-ds-warning';
  return 'bg-ds-success';
}

export function BudgetBar() {
  const { t } = useI18n();
  const budget = useWorkflowStore((s) => s.budget);
  const context = useWorkflowStore((s) => s.context);

  if (!budget && !context) return null;

  return (
    <div className="space-y-1.5 px-3 py-2">
      {budget && (
        <div>
          <div className="mb-0.5 flex items-center justify-between text-[10px] text-ds-muted">
            <span>{t('workspace.workflow.budget.title')}</span>
            <span className="font-mono">
              ${budget.costUsd.toFixed(2)} / ${budget.costMax.toFixed(2)}
            </span>
          </div>
          <div className="h-1 overflow-hidden rounded-full bg-ds-border">
            <div
              className={`h-full rounded-full transition-all duration-300 ${pctColor(
                (budget.costUsd / Math.max(budget.costMax, 0.01)) * 100,
              )}`}
              style={{
                width: `${Math.min(100, (budget.costUsd / Math.max(budget.costMax, 0.01)) * 100)}%`,
              }}
            />
          </div>
        </div>
      )}

      {context && (
        <div>
          <div className="mb-0.5 flex items-center justify-between text-[10px] text-ds-muted">
            <span>{t('workspace.workflow.budget.context')}</span>
            <span className="font-mono">{context.usedPct}%</span>
          </div>
          <div className="h-1 overflow-hidden rounded-full bg-ds-border">
            <div
              className={`h-full rounded-full transition-all duration-300 ${pctColor(context.usedPct)}`}
              style={{ width: `${Math.min(100, context.usedPct)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
