/**
 * Experiment table ??model comparison with metrics.
 */

import { useI18n } from '../../stores/i18nStore';
import { useWorkflowStore, type Experiment } from '../../stores/workflowStore';

export function ExperimentTable({
  activeMetricKey,
  onInspectMetric,
}: {
  activeMetricKey?: string | null;
  onInspectMetric?: (metricKey: string) => void;
}) {
  const { t } = useI18n();
  const experiments = useWorkflowStore((s) => s.experiments);

  if (experiments.length === 0) return null;

  const metricKeys = Array.from(
    new Set(experiments.flatMap((experiment) => Object.keys(experiment.metrics))),
  );

  const nonBaseline = experiments.filter((experiment) => !experiment.isBaseline);
  const bestId = nonBaseline.length > 0 && metricKeys.length > 0
    ? nonBaseline.reduce((best, experiment) =>
        (experiment.metrics[metricKeys[0]] ?? 0) > (best.metrics[metricKeys[0]] ?? 0)
          ? experiment
          : best
      ).id
    : null;

  return (
    <div className="px-3 py-2">
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
        {t('workspace.workflow.experiments.title')}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="border-b border-ds-border/50 text-ds-muted">
              <th className="py-1 pr-2 text-left font-medium">
                {t('workspace.workflow.experiments.column.model')}
              </th>
              {metricKeys.map((metricKey) => (
                <th key={metricKey} className="px-1 py-1 text-right font-medium">
                  <button
                    type="button"
                    onClick={() => onInspectMetric?.(metricKey)}
                    onMouseEnter={() => onInspectMetric?.(metricKey)}
                    onFocus={() => onInspectMetric?.(metricKey)}
                    data-testid={`metric-source-trigger-${metricKey}`}
                    title={t('workspace.workflow.experiments.inspectMetric', {
                      metric: metricKey,
                    })}
                    className={`border-b border-dotted transition-colors ${
                      activeMetricKey === metricKey
                        ? 'border-ds-accent text-ds-text'
                        : 'border-ds-border/40 text-ds-muted hover:border-ds-accent hover:text-ds-text'
                    }`}
                  >
                    {metricKey.length > 5 ? metricKey.slice(0, 5) : metricKey}
                  </button>
                </th>
              ))}
              <th className="py-1 pl-1 text-right font-medium">
                {t('workspace.workflow.experiments.column.time')}
              </th>
            </tr>
          </thead>
          <tbody>
            {experiments.map((experiment) => (
              <ExperimentRow
                key={experiment.id}
                exp={experiment}
                metricKeys={metricKeys}
                isBest={experiment.id === bestId}
              />
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-1 text-[9px] text-ds-muted">
        {bestId && (
          <span className="text-ds-accent">
            {t('workspace.workflow.experiments.legend.best')}
          </span>
        )}
        {experiments.some((experiment) => experiment.isBaseline) && (
          <span className="ml-2">{t('workspace.workflow.experiments.legend.baseline')}</span>
        )}
      </div>
    </div>
  );
}

function ExperimentRow({
  exp,
  metricKeys,
  isBest,
}: {
  exp: Experiment;
  metricKeys: string[];
  isBest: boolean;
}) {
  return (
    <tr className={`border-b border-ds-border/30 ${isBest ? 'text-ds-accent' : 'text-ds-text'}`}>
      <td className="py-1 pr-2 font-mono">
        {exp.isBaseline ? '\u25b3' : isBest ? '*' : ''}
        {exp.model}
      </td>
      {metricKeys.map((metricKey) => (
        <td key={metricKey} className="px-1 py-1 text-right font-mono">
          {exp.metrics[metricKey] !== undefined ? exp.metrics[metricKey].toFixed(3) : '\u2014'}
        </td>
      ))}
      <td className="py-1 pl-1 text-right font-mono text-ds-muted">
        {exp.trainingTime !== undefined ? `${exp.trainingTime.toFixed(1)}s` : '\u2014'}
      </td>
    </tr>
  );
}
