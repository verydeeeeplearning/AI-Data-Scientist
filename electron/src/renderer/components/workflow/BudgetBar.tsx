/**
 * Budget bar — cost and context token usage visualization.
 */

import { useWorkflowStore } from '../../stores/workflowStore';

function pctColor(pct: number): string {
  if (pct >= 80) return 'bg-ds-error';
  if (pct >= 60) return 'bg-ds-warning';
  return 'bg-ds-success';
}

export function BudgetBar() {
  const budget = useWorkflowStore((s) => s.budget);
  const context = useWorkflowStore((s) => s.context);

  if (!budget && !context) return null;

  return (
    <div className="px-3 py-2 space-y-1.5">
      {/* Cost budget */}
      {budget && (
        <div>
          <div className="flex items-center justify-between text-[10px] text-ds-muted mb-0.5">
            <span>Budget</span>
            <span className="font-mono">
              ${budget.costUsd.toFixed(2)} / ${budget.costMax.toFixed(2)}
            </span>
          </div>
          <div className="h-1 bg-ds-border rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${pctColor(
                (budget.costUsd / Math.max(budget.costMax, 0.01)) * 100
              )}`}
              style={{
                width: `${Math.min(100, (budget.costUsd / Math.max(budget.costMax, 0.01)) * 100)}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* Context tokens */}
      {context && (
        <div>
          <div className="flex items-center justify-between text-[10px] text-ds-muted mb-0.5">
            <span>Context</span>
            <span className="font-mono">{context.usedPct}%</span>
          </div>
          <div className="h-1 bg-ds-border rounded-full overflow-hidden">
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
