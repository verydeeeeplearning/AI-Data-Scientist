/**
 * Workflow progress — visual pipeline steps with status and quality scores.
 */

import { useWorkflowStore, type WorkflowStage } from '../../stores/workflowStore';

const STATUS_STYLES: Record<string, { icon: string; color: string }> = {
  done: { icon: '\u2713', color: 'text-ds-success' },
  running: { icon: '\u25ce', color: 'text-ds-accent animate-pulse' },
  error: { icon: '\u2717', color: 'text-ds-error' },
  pending: { icon: '\u25cb', color: 'text-ds-muted' },
};

export function WorkflowProgress() {
  const stages = useWorkflowStore((s) => s.stages);
  const overallQuality = useWorkflowStore((s) => s.overallQuality);

  const doneCount = stages.filter((s) => s.status === 'done').length;
  const pct = Math.round((doneCount / stages.length) * 100);

  return (
    <div className="px-3 py-2">
      <div className="text-[10px] font-semibold text-ds-muted uppercase tracking-wider mb-2">
        Workflow
      </div>

      {/* Stage list */}
      <div className="space-y-0.5">
        {stages.map((stage) => (
          <StageRow key={stage.id} stage={stage} />
        ))}
      </div>

      {/* Progress bar */}
      <div className="mt-2">
        <div className="flex items-center justify-between text-[10px] text-ds-muted mb-1">
          <span>{doneCount}/{stages.length}</span>
          {overallQuality && (
            <span className="font-mono font-semibold text-ds-text">
              {overallQuality.grade} ({overallQuality.score})
            </span>
          )}
        </div>
        <div className="h-1 bg-ds-border rounded-full overflow-hidden">
          <div
            className="h-full bg-ds-accent rounded-full transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}

function StageRow({ stage }: { stage: WorkflowStage }) {
  const style = STATUS_STYLES[stage.status] ?? STATUS_STYLES.pending;

  return (
    <div className="flex items-center gap-2 text-xs py-0.5">
      <span className={`w-3 text-center ${style.color}`}>{style.icon}</span>
      <span className={stage.status === 'done' ? 'text-ds-text' : 'text-ds-muted'}>
        {stage.label}
      </span>
      {stage.score !== undefined && stage.status === 'done' && (
        <span className="ml-auto text-[10px] font-mono text-ds-muted">{stage.score}</span>
      )}
    </div>
  );
}
