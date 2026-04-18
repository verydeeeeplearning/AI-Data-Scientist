/**
 * Tool activity stream — shows running/completed tool calls.
 */

import { CheckCircle2, Loader2, XCircle } from 'lucide-react';
import type { ToolActivity as ToolActivityType } from '../../stores/chatStore';

interface Props {
  activities: ToolActivityType[];
}

export function ToolActivity({ activities }: Props) {
  if (activities.length === 0) return null;

  return (
    <div className="border-t border-ds-border bg-ds-surface/30 px-4 py-2">
      <div className="text-xs text-ds-muted mb-1.5 font-medium">Tool Activity</div>
      <div className="space-y-1">
        {activities.map((tool, i) => (
          <div
            key={`${tool.name}-${i}`}
            className="flex items-center gap-2 text-xs"
          >
            {/* Status icon */}
            {tool.status === 'running' && (
              <Loader2 size={12} className="text-ds-accent animate-spin" />
            )}
            {tool.status === 'done' && (
              <CheckCircle2 size={12} className="text-ds-success" />
            )}
            {tool.status === 'error' && (
              <XCircle size={12} className="text-ds-error" />
            )}

            {/* Tool name */}
            <span className="text-ds-text font-mono">{tool.name}</span>

            {/* Elapsed time */}
            {tool.elapsed !== undefined && (
              <span className="text-ds-muted">
                {(tool.elapsed / 1000).toFixed(1)}s
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
