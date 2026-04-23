/**
 * Legacy raw tool activity stream — preserved as a feature-flag rollback target
 * for the new ExecutionTimeline (W1-F). Activated when
 * `configStore.useNewExecutionTimeline` is false.
 */

import { CheckCircle2, Loader2, XCircle } from 'lucide-react';
import { prefersReducedMotion } from '../../application/a11y/reducedMotion';
import type { ToolActivity as ToolActivityType } from '../../stores/chatStore';

interface Props {
  activities: ToolActivityType[];
}

export function LegacyToolActivity({ activities }: Props) {
  const reduceMotion = prefersReducedMotion();

  if (activities.length === 0) {
    return null;
  }

  return (
    <div className="border-t border-ds-border bg-ds-surface/30 px-4 py-2">
      <div className="text-xs text-ds-muted mb-1.5 font-medium">Tool Activity</div>
      <ul className="space-y-1 list-none p-0">
        {activities.map((tool, i) => (
          <li
            key={`${tool.name}-${tool.startedAt}-${i}`}
            className="flex items-center gap-2 text-xs"
          >
            {tool.status === 'running' && (
              <Loader2
                size={12}
                className={reduceMotion ? 'text-ds-accent' : 'text-ds-accent animate-spin'}
                aria-hidden="true"
              />
            )}
            {tool.status === 'done' && (
              <CheckCircle2 size={12} className="text-ds-success" aria-hidden="true" />
            )}
            {tool.status === 'error' && (
              <XCircle size={12} className="text-ds-error" aria-hidden="true" />
            )}

            <span className="text-ds-text font-mono">{tool.name}</span>

            {tool.elapsed !== undefined && (
              <span className="text-ds-muted">
                {(tool.elapsed / 1000).toFixed(1)}s
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
