/**
 * Alert banner — displays harness warnings at top of chat panel.
 */

import { X } from 'lucide-react';
import { useWorkflowStore, type HarnessWarning } from '../../stores/workflowStore';

const SEVERITY_STYLES: Record<string, string> = {
  high: 'border-l-ds-error bg-ds-error/10',
  medium: 'border-l-ds-warning bg-ds-warning/10',
  low: 'border-l-ds-accent bg-ds-accent/10',
};

export function AlertBanner() {
  const warnings = useWorkflowStore((s) => s.warnings);
  const dismissWarning = useWorkflowStore((s) => s.dismissWarning);

  const active = warnings.filter((w) => !w.dismissed);
  if (active.length === 0) return null;

  return (
    <div className="space-y-1 p-2">
      {active.map((warning) => (
        <WarningCard key={warning.id} warning={warning} onDismiss={dismissWarning} />
      ))}
    </div>
  );
}

function WarningCard({
  warning,
  onDismiss,
}: {
  warning: HarnessWarning;
  onDismiss: (id: string) => void;
}) {
  const style = SEVERITY_STYLES[warning.severity] ?? SEVERITY_STYLES.medium;

  return (
    <div className={`border-l-4 rounded-r px-3 py-2 ${style}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-xs font-medium text-ds-text">{warning.message}</div>
          {warning.suggestion && (
            <div className="text-[11px] text-ds-muted mt-0.5">{warning.suggestion}</div>
          )}
        </div>
        <button
          onClick={() => onDismiss(warning.id)}
          className="p-0.5 rounded hover:bg-ds-border/50 text-ds-muted flex-shrink-0"
        >
          <X size={12} />
        </button>
      </div>
    </div>
  );
}
