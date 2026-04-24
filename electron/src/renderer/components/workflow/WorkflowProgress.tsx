/**
 * Workflow progress ??visual pipeline steps with status and quality scores.
 */

import { useI18n } from '../../stores/i18nStore';
import { useWorkflowStore, type WorkflowStage } from '../../stores/workflowStore';

const STATUS_STYLES: Record<string, { icon: string; color: string }> = {
  done: { icon: '\u2713', color: 'text-ds-success' },
  running: { icon: '\u25ce', color: 'text-ds-accent animate-pulse' },
  error: { icon: '\u2717', color: 'text-ds-error' },
  pending: { icon: '\u25cb', color: 'text-ds-muted' },
};

export function WorkflowProgress() {
  const { t } = useI18n();
  const stages = useWorkflowStore((s) => s.stages);
  const overallQuality = useWorkflowStore((s) => s.overallQuality);

  const doneCount = stages.filter((s) => s.status === 'done').length;
  const pct = stages.length > 0 ? Math.round((doneCount / stages.length) * 100) : 0;

  return (
    <div className="px-3 py-2">
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
        {t('workspace.workflow.progress.title')}
      </div>

      <div className="space-y-0.5">
        {stages.map((stage) => (
          <StageRow key={stage.id} stage={stage} />
        ))}
      </div>

      <div className="mt-2">
        <div className="mb-1 flex items-center justify-between text-[10px] text-ds-muted">
          <span>{doneCount}/{stages.length}</span>
          {overallQuality && (
            <span className="font-mono font-semibold text-ds-text">
              {overallQuality.grade} ({overallQuality.score})
            </span>
          )}
        </div>
        <div className="h-1 overflow-hidden rounded-full bg-ds-border">
          <div
            className="h-full rounded-full bg-ds-accent transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}

function StageRow({ stage }: { stage: WorkflowStage }) {
  const { t } = useI18n();
  const style = STATUS_STYLES[stage.status] ?? STATUS_STYLES.pending;

  return (
    <div className="flex items-center gap-2 py-0.5 text-xs">
      <span className={`w-3 text-center ${style.color}`}>{style.icon}</span>
      <span className={stage.status === 'done' ? 'text-ds-text' : 'text-ds-muted'}>
        {translateWorkflowStageLabel(stage, t)}
      </span>
      {stage.score !== undefined && stage.status === 'done' && (
        <span className="ml-auto font-mono text-[10px] text-ds-muted">{stage.score}</span>
      )}
    </div>
  );
}

function translateWorkflowStageLabel(
  stage: WorkflowStage,
  t: (key: string, vars?: Record<string, string | number | undefined | null>) => string,
): string {
  const key = {
    scoping: 'workspace.workflow.progress.stage.scoping',
    data_loading: 'workspace.workflow.progress.stage.dataLoading',
    profiling: 'workspace.workflow.progress.stage.profiling',
    eda: 'workspace.workflow.progress.stage.eda',
    feature_engineering: 'workspace.workflow.progress.stage.featureEngineering',
    modeling: 'workspace.workflow.progress.stage.modeling',
    evaluation: 'workspace.workflow.progress.stage.evaluation',
    reporting: 'workspace.workflow.progress.stage.reporting',
  }[stage.id];

  return key ? t(key) : stage.label;
}
