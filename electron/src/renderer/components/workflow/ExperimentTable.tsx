/**
 * Experiment table — model comparison with metrics.
 */

import { useWorkflowStore, type Experiment } from '../../stores/workflowStore';

export function ExperimentTable({
  activeMetricKey,
  onInspectMetric,
}: {
  activeMetricKey?: string | null;
  onInspectMetric?: (metricKey: string) => void;
}) {
  const experiments = useWorkflowStore((s) => s.experiments);

  if (experiments.length === 0) return null;

  // Collect all metric keys across experiments
  const metricKeys = Array.from(
    new Set(experiments.flatMap((e) => Object.keys(e.metrics)))
  );

  // Find best experiment (highest first metric value, excluding baselines)
  const nonBaseline = experiments.filter((e) => !e.isBaseline);
  const bestId = nonBaseline.length > 0 && metricKeys.length > 0
    ? nonBaseline.reduce((best, e) =>
        (e.metrics[metricKeys[0]] ?? 0) > (best.metrics[metricKeys[0]] ?? 0) ? e : best
      ).id
    : null;

  return (
    <div className="px-3 py-2">
      <div className="text-[10px] font-semibold text-ds-muted uppercase tracking-wider mb-2">
        Experiments
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="text-ds-muted border-b border-ds-border/50">
              <th className="text-left py-1 pr-2 font-medium">Model</th>
              {metricKeys.map((k) => (
                <th key={k} className="text-right py-1 px-1 font-medium">
                  <button
                    type="button"
                    onClick={() => onInspectMetric?.(k)}
                    onMouseEnter={() => onInspectMetric?.(k)}
                    onFocus={() => onInspectMetric?.(k)}
                    data-testid={`metric-source-trigger-${k}`}
                    title={`Inspect semantic source for ${k}`}
                    className={`border-b border-dotted transition-colors ${
                      activeMetricKey === k
                        ? 'border-ds-accent text-ds-text'
                        : 'border-ds-border/40 text-ds-muted hover:border-ds-accent hover:text-ds-text'
                    }`}
                  >
                    {k.length > 5 ? k.slice(0, 5) : k}
                  </button>
                </th>
              ))}
              <th className="text-right py-1 pl-1 font-medium">Time</th>
            </tr>
          </thead>
          <tbody>
            {experiments.map((exp) => (
              <ExperimentRow
                key={exp.id}
                exp={exp}
                metricKeys={metricKeys}
                isBest={exp.id === bestId}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="mt-1 text-[9px] text-ds-muted">
        {bestId && <span className="text-ds-accent">* best</span>}
        {experiments.some((e) => e.isBaseline) && (
          <span className="ml-2">{'  \u25b3 baseline'}</span>
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
        {exp.isBaseline ? '\u25b3' : isBest ? '*' : ''}{exp.model}
      </td>
      {metricKeys.map((k) => (
        <td key={k} className="text-right py-1 px-1 font-mono">
          {exp.metrics[k] !== undefined ? exp.metrics[k].toFixed(3) : '\u2014'}
        </td>
      ))}
      <td className="text-right py-1 pl-1 font-mono text-ds-muted">
        {exp.trainingTime !== undefined ? `${exp.trainingTime.toFixed(1)}s` : '\u2014'}
      </td>
    </tr>
  );
}
