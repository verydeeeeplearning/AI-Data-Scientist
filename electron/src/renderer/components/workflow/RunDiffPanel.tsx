import { GitCompareArrows } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useWs } from '../../hooks/WsProvider';
import { InlineError, StatusLine } from './DecisionOsReviewPrimitives';
import {
  directionClass,
  RunDiffResult,
  ReviewRun,
  runOptionLabel,
  severityClass,
} from './decisionOsReviewModel';

interface Props {
  runs: ReviewRun[];
  connected: boolean;
  onOpenPromotionModal: (candidateRunId: string) => void;
}

export function RunDiffPanel({ runs, connected, onOpenPromotionModal }: Props) {
  const { rpc } = useWs();
  const [runAId, setRunAId] = useState('');
  const [runBId, setRunBId] = useState('');
  const [diffBusy, setDiffBusy] = useState(false);
  const [diffError, setDiffError] = useState<string | null>(null);
  const [diffResult, setDiffResult] = useState<RunDiffResult | null>(null);

  useEffect(() => {
    const runIds = new Set(runs.map((run) => run.run_id));
    if (!runIds.has(runAId)) {
      setRunAId(runs[0]?.run_id ?? '');
    }
    if (!runIds.has(runBId)) {
      setRunBId(runs[1]?.run_id ?? runs[0]?.run_id ?? '');
    }
  }, [runAId, runBId, runs]);

  const compareRuns = async () => {
    if (!runAId || !runBId) {
      setDiffError('Select both runs.');
      return;
    }
    setDiffBusy(true);
    setDiffError(null);
    try {
      const payload = await rpc('decisionOs.compareRuns', { runAId, runBId });
      setDiffResult(payload as unknown as RunDiffResult);
    } catch (err) {
      setDiffError(err instanceof Error ? err.message : String(err));
    } finally {
      setDiffBusy(false);
    }
  };

  return (
    <section
      data-testid="decision-os-run-diff"
      className="space-y-2 rounded-md border border-ds-border bg-ds-bg/70 p-3"
    >
      <div className="flex items-center gap-2 text-xs font-semibold text-ds-text">
        <GitCompareArrows size={14} />
        Run Diff
      </div>
      <div className="grid gap-2">
        <select
          value={runAId}
          onChange={(event) => setRunAId(event.target.value)}
          data-testid="decision-os-run-diff-base"
          className="rounded border border-ds-border bg-ds-surface px-2 py-1.5 text-xs text-ds-text"
        >
          <option value="">Select base run</option>
          {runs.map((run) => (
            <option key={run.run_id} value={run.run_id}>
              {runOptionLabel(run)}
            </option>
          ))}
        </select>
        <select
          value={runBId}
          onChange={(event) => setRunBId(event.target.value)}
          data-testid="decision-os-run-diff-candidate"
          className="rounded border border-ds-border bg-ds-surface px-2 py-1.5 text-xs text-ds-text"
        >
          <option value="">Select candidate run</option>
          {runs.map((run) => (
            <option key={run.run_id} value={run.run_id}>
              {runOptionLabel(run)}
            </option>
          ))}
        </select>
        <button
          onClick={() => void compareRuns()}
          disabled={diffBusy || !connected}
          data-testid="decision-os-run-diff-compare"
          className="rounded bg-ds-accent px-2 py-1.5 text-xs text-white disabled:opacity-50"
        >
          {diffBusy ? 'Comparing...' : 'Compare runs'}
        </button>
      </div>
      {diffError && <InlineError message={diffError} />}
      {diffResult && (
        <div data-testid="decision-os-run-diff-result" className="space-y-2 text-xs">
          <div className="whitespace-pre-wrap rounded border border-ds-border/70 bg-ds-surface/60 p-2 text-ds-text">
            {diffResult.summary_markdown}
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            <StatusLine
              label="Code ref"
              value={`${diffResult.code_ref[0]} -> ${diffResult.code_ref[1]}`}
            />
            <StatusLine
              label="Data snapshot"
              value={`${diffResult.data_snapshot[0]} -> ${diffResult.data_snapshot[1]}`}
            />
          </div>
          <div className="grid gap-2">
            {diffResult.metrics.map((metric) => (
              <div
                key={metric.metric}
                className="rounded border border-ds-border/70 bg-ds-surface/60 p-2"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-ds-text">{metric.metric}</span>
                  <span className={directionClass(metric.direction)}>
                    {metric.delta >= 0 ? '+' : ''}
                    {metric.delta.toFixed(3)}
                  </span>
                </div>
                <div className="mt-1 text-[10px] text-ds-muted">
                  {metric.from_value.toFixed(3)} {'->'} {metric.to_value.toFixed(3)}
                </div>
              </div>
            ))}
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            <FeatureChangeCard title="Added features" items={diffResult.feature_set.added.map(
              (item) => `${item.feature_id} v${item.version}`,
            )} />
            <FeatureChangeCard title="Removed features" items={diffResult.feature_set.removed.map(
              (item) => `${item.feature_id} v${item.version}`,
            )} />
            <FeatureChangeCard title="Version changes" items={diffResult.feature_set.version_changed.map(
              ([featureId, fromVersion, toVersion]) =>
                `${featureId}: v${fromVersion} -> v${toVersion}`,
            )} />
            <VerifierCard diff={diffResult} />
          </div>
          <div className="flex justify-end">
            <button
              onClick={() => onOpenPromotionModal(runBId)}
              data-testid="decision-os-run-diff-open-promotion"
              className="rounded border border-ds-accent px-2 py-1.5 text-xs text-ds-accent hover:bg-ds-accent/10"
            >
              Open promotion gate for candidate
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function FeatureChangeCard({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded border border-ds-border/70 bg-ds-surface/60 p-2 text-[10px]">
      <div className="font-medium text-ds-text">{title}</div>
      {items.length === 0 ? (
        <div className="mt-1 text-ds-muted">No changes.</div>
      ) : (
        <div className="mt-2 space-y-1 text-ds-muted">
          {items.map((item) => (
            <div key={item} className="rounded border border-ds-border bg-ds-bg/70 px-2 py-1">
              {item}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function VerifierCard({ diff }: { diff: RunDiffResult }) {
  return (
    <div className="rounded border border-ds-border/70 bg-ds-surface/60 p-2 text-[10px]">
      <div className="font-medium text-ds-text">Verifier delta</div>
      <div className="mt-2 grid gap-2">
        <VerifierLine label="Statistical" value={diff.verifier.statistical} />
        <VerifierLine label="Data" value={diff.verifier.data} />
        <VerifierLine label="Policy" value={diff.verifier.policy} />
      </div>
      {diff.verifier.new_findings.length > 0 ? (
        <div className="mt-2 space-y-1">
          {diff.verifier.new_findings.map((finding) => (
            <div
              key={finding}
              className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-amber-300"
            >
              New: {finding}
            </div>
          ))}
        </div>
      ) : null}
      {diff.verifier.resolved_findings.length > 0 ? (
        <div className="mt-2 space-y-1">
          {diff.verifier.resolved_findings.map((finding) => (
            <div
              key={finding}
              className="rounded border border-ds-success/30 bg-ds-success/10 px-2 py-1 text-ds-success"
            >
              Resolved: {finding}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function VerifierLine({
  label,
  value,
}: {
  label: string;
  value: [string, string];
}) {
  const changed = value[0] !== value[1];

  return (
    <div className="rounded border border-ds-border bg-ds-bg/70 px-2 py-1.5">
      <div className="text-ds-muted">{label}</div>
      <div className="mt-1 flex items-center gap-2 text-ds-text">
        <span className={`rounded border px-1.5 py-0.5 ${severityClass(value[0].toLowerCase())}`}>
          {value[0]}
        </span>
        <span className="text-ds-muted">{'->'}</span>
        <span className={`rounded border px-1.5 py-0.5 ${severityClass(value[1].toLowerCase())}`}>
          {value[1]}
        </span>
        {changed ? <span className="text-[9px] text-ds-muted">changed</span> : null}
      </div>
    </div>
  );
}
