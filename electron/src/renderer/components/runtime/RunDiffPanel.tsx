import { GitCompareArrows } from 'lucide-react';
import { useId } from 'react';
import { Badge, Card, cn } from '../../design-system/primitives';
import type { RunCompareEntry, RunCompareScorecardSummary } from './runsCompareBoardModel';

type BadgeTone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger' | 'info';

export interface RunsCompareResult {
  run_a_id: string;
  run_b_id: string;
  summary_markdown: string;
  feature_set: {
    added: Array<{ feature_id: string; version: number }>;
    removed: Array<{ feature_id: string; version: number }>;
    version_changed: Array<[string, number, number]>;
  };
  config: {
    changed: Record<string, [unknown, unknown]>;
    added: Record<string, unknown>;
    removed: Record<string, unknown>;
  };
  metrics: Array<{
    metric: string;
    from_value: number;
    to_value: number;
    delta: number;
    direction: 'better' | 'worse' | 'neutral';
    highlighted?: boolean;
    significance_note?: string | null;
  }>;
  artifacts: Array<{
    key: string;
    label: string;
    artifact_kind: 'plot' | 'review_artifact';
    status: 'added' | 'removed' | 'changed' | 'shared';
    run_a_value?: string | null;
    run_b_value?: string | null;
    summary: string;
  }>;
  decisions: Array<{
    key: string;
    decision_kind:
      | 'hypothesis'
      | 'feature_strategy'
      | 'model_strategy'
      | 'verifier'
      | 'review_artifact';
    divergence_point: string;
    run_a_summary?: string | null;
    run_b_summary?: string | null;
  }>;
  verifier: {
    statistical: [string, string];
    data: [string, string];
    policy: [string, string];
    new_findings: string[];
    resolved_findings: string[];
  };
  code_ref: [string, string];
  data_snapshot: [string, string];
}

interface Props {
  readonly baseRun: RunCompareEntry | null;
  readonly candidateRun: RunCompareEntry | null;
  readonly compareResult: RunsCompareResult | null;
  readonly scorecardsByRunId: ReadonlyMap<string, RunCompareScorecardSummary | null>;
}

function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'n/a';
  }
  return value.toFixed(3);
}

function formatDelta(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(3)}`;
}

function directionClass(direction: RunsCompareResult['metrics'][number]['direction']): string {
  if (direction === 'better') return 'text-ds-success';
  if (direction === 'worse') return 'text-ds-error';
  return 'text-ds-muted';
}

function severityTone(status: string): BadgeTone {
  const normalized = status.toLowerCase();
  if (normalized === 'fail' || normalized === 'alert' || normalized === 'rejected') {
    return 'danger';
  }
  if (normalized === 'warn' || normalized === 'warning' || normalized.startsWith('pending')) {
    return 'warning';
  }
  if (normalized === 'pass' || normalized === 'ok' || normalized === 'approved') {
    return 'success';
  }
  return 'neutral';
}

function artifactStatusTone(
  status: RunsCompareResult['artifacts'][number]['status'],
): BadgeTone {
  if (status === 'added') return 'success';
  if (status === 'removed') return 'danger';
  if (status === 'changed') return 'accent';
  return 'neutral';
}

function decisionKindLabel(
  kind: RunsCompareResult['decisions'][number]['decision_kind'],
): string {
  if (kind === 'hypothesis') return 'Hypothesis';
  if (kind === 'feature_strategy') return 'Features';
  if (kind === 'model_strategy') return 'Model';
  if (kind === 'review_artifact') return 'Review';
  return 'Verifier';
}

function formatDateTime(timestamp?: number | null): string {
  if (!timestamp) return '-';
  return new Date(timestamp * 1000).toLocaleString();
}

function formatMetricValue(value: number): string {
  if (!Number.isFinite(value)) return String(value);
  if (Math.abs(value) >= 1000) {
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  if (Math.abs(value) >= 1) {
    return value.toFixed(3);
  }
  return value.toFixed(4);
}

function sectionHeadingClassName(): string {
  return 'text-ds-xs font-medium text-ds-text';
}

function pillClassName(): string {
  return 'uppercase tracking-[0.16em] text-[10px]';
}

export function RunDiffPanel({
  baseRun,
  candidateRun,
  compareResult,
  scorecardsByRunId,
}: Props) {
  const titleId = useId();

  if (!baseRun || !candidateRun) {
    return (
      <Card className="border-dashed bg-ds-bg/50 p-ds-4 text-sm text-ds-muted shadow-none">
        Pick two runs to inspect the diff view.
      </Card>
    );
  }

  const baseScore = scorecardsByRunId.get(baseRun.runId) ?? null;
  const candidateScore = scorecardsByRunId.get(candidateRun.runId) ?? null;
  const metrics = compareResult?.metrics ?? [];
  const artifacts = compareResult?.artifacts ?? [];
  const decisions = compareResult?.decisions ?? [];

  return (
    <section aria-labelledby={titleId}>
      <Card className="bg-ds-bg/60 p-ds-4 shadow-none">
        <header className="flex items-center gap-ds-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-ds-muted">
          <GitCompareArrows size={14} aria-hidden="true" />
          <h2 id={titleId}>Run Diff</h2>
        </header>

        <div className="mt-ds-3 grid gap-ds-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.9fr)]">
          <RunSnapshotCard
            title="Base Run"
            run={baseRun}
            weightedScore={baseScore?.weightedScore ?? null}
            toolCallCount={baseScore?.toolCallCount ?? null}
          />
          <RunSnapshotCard
            title="Candidate Run"
            run={candidateRun}
            weightedScore={candidateScore?.weightedScore ?? null}
            toolCallCount={candidateScore?.toolCallCount ?? null}
          />
          <MetricOverviewCard metrics={metrics} />
        </div>

        <div className="mt-ds-4 grid gap-ds-4 xl:grid-cols-2">
          <ArtifactDiffColumn entries={artifacts} />
          <DecisionTraceColumn entries={decisions} />
        </div>
      </Card>
    </section>
  );
}

function RunSnapshotCard({
  title,
  run,
  weightedScore,
  toolCallCount,
}: {
  title: string;
  run: RunCompareEntry;
  weightedScore: number | null;
  toolCallCount: number | null;
}) {
  const titleId = useId();

  return (
    <article aria-labelledby={titleId}>
      <Card className="h-full p-ds-3 shadow-none">
        <header className="flex items-center gap-ds-2">
          <h3 id={titleId} className={sectionHeadingClassName()}>
            {title}
          </h3>
          <Badge tone={severityTone(run.status)} compact className={cn('ml-auto', pillClassName())}>
            {run.status}
          </Badge>
        </header>

        <div className="mt-ds-3 space-y-1">
          <div className="break-all font-mono text-sm text-ds-text">{run.runId}</div>
          <div className="text-xs text-ds-muted">
            {run.surface} / {run.sessionLabel || run.sessionId}
          </div>
        </div>

        <dl className="mt-ds-3 grid gap-ds-2 sm:grid-cols-2">
          <SnapshotFact label="Started" value={formatDateTime(run.startedAt)} />
          <SnapshotFact label="Cost" value={`$${run.costUsd.toFixed(4)}`} />
          <SnapshotFact label="Score" value={formatScore(weightedScore)} />
          <SnapshotFact
            label="Tool Calls"
            value={toolCallCount === null ? 'n/a' : String(toolCallCount)}
          />
          <SnapshotFact label="Task" value={run.taskId ?? '-'} mono />
        </dl>
      </Card>
    </article>
  );
}

function SnapshotFact({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <Card className="rounded-ds-lg bg-ds-bg/70 px-ds-2 py-ds-2 shadow-none">
      <dt className="text-[10px] uppercase tracking-wider text-ds-muted">{label}</dt>
      <dd className={cn('mt-ds-1 text-xs text-ds-text', mono && 'break-all font-mono')}>
        {value}
      </dd>
    </Card>
  );
}

function MetricOverviewCard({
  metrics,
}: {
  metrics: RunsCompareResult['metrics'];
}) {
  const titleId = useId();

  if (metrics.length === 0) {
    return (
      <section aria-labelledby={titleId}>
        <Card className="h-full p-ds-3 shadow-none">
          <h3 id={titleId} className={sectionHeadingClassName()}>
            Metric Delta
          </h3>
          <div className="mt-ds-3 text-sm text-ds-muted">No overlapping metrics were returned.</div>
        </Card>
      </section>
    );
  }

  return (
    <section aria-labelledby={titleId}>
      <Card className="h-full p-ds-3 shadow-none">
        <header className="flex items-center justify-between gap-ds-2">
          <h3 id={titleId} className={sectionHeadingClassName()}>
            Metric Delta
          </h3>
          <div className="text-[11px] text-ds-muted">
            {metrics.filter((metric) => metric.highlighted).length} highlighted
          </div>
        </header>

        <ul className="mt-ds-3 space-y-ds-2" role="list">
          {metrics.map((metric) => (
            <li key={metric.metric}>
              <Card
                tone={metric.highlighted ? 'accent' : 'default'}
                className={cn(
                  'rounded-ds-lg p-ds-2 shadow-none',
                  metric.highlighted ? 'bg-ds-accent/10' : 'bg-ds-bg/70',
                )}
              >
                <div className="flex items-center justify-between gap-ds-2">
                  <span className="text-xs font-medium text-ds-text">{metric.metric}</span>
                  <span className={cn('text-xs font-semibold', directionClass(metric.direction))}>
                    {formatDelta(metric.delta)}
                  </span>
                </div>
                <div className="mt-1 text-[11px] text-ds-muted">
                  {formatMetricValue(metric.from_value)} {'->'} {formatMetricValue(metric.to_value)}
                </div>
                {metric.significance_note ? (
                  <div className="mt-ds-2 text-[11px] text-ds-muted">
                    {metric.significance_note}
                  </div>
                ) : null}
              </Card>
            </li>
          ))}
        </ul>
      </Card>
    </section>
  );
}

function ArtifactDiffColumn({
  entries,
}: {
  entries: RunsCompareResult['artifacts'];
}) {
  const titleId = useId();

  return (
    <section aria-labelledby={titleId}>
      <Card className="h-full p-ds-3 shadow-none">
        <header className="flex items-center justify-between gap-ds-2">
          <h3 id={titleId} className={sectionHeadingClassName()}>
            Artifact Diff
          </h3>
          <div className="text-[11px] text-ds-muted">{entries.length} changes</div>
        </header>

        {entries.length === 0 ? (
          <div className="mt-ds-3 text-sm text-ds-muted">
            No artifact-level changes were detected.
          </div>
        ) : (
          <ul className="mt-ds-3 space-y-ds-2" role="list">
            {entries.map((entry) => (
              <li key={entry.key}>
                <article aria-label={`${entry.label} artifact diff`}>
                  <Card className="rounded-ds-lg bg-ds-bg/70 p-ds-3 shadow-none">
                    <div className="flex flex-wrap items-center gap-ds-2">
                      <h4 className="text-xs font-medium text-ds-text">{entry.label}</h4>
                      <Badge
                        tone={artifactStatusTone(entry.status)}
                        compact
                        className={pillClassName()}
                      >
                        {entry.status}
                      </Badge>
                      <Badge compact className={pillClassName()}>
                        {entry.artifact_kind === 'review_artifact' ? 'review artifact' : 'plot'}
                      </Badge>
                    </div>
                    <div className="mt-ds-2 text-sm text-ds-text">{entry.summary}</div>
                    <div className="mt-ds-2 grid gap-ds-2 md:grid-cols-2">
                      <DiffValueBlock label="Base" value={entry.run_a_value ?? 'Not present.'} />
                      <DiffValueBlock
                        label="Candidate"
                        value={entry.run_b_value ?? 'Not present.'}
                      />
                    </div>
                  </Card>
                </article>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </section>
  );
}

function DecisionTraceColumn({
  entries,
}: {
  entries: RunsCompareResult['decisions'];
}) {
  const titleId = useId();

  return (
    <section aria-labelledby={titleId}>
      <Card className="h-full p-ds-3 shadow-none">
        <header className="flex items-center justify-between gap-ds-2">
          <h3 id={titleId} className={sectionHeadingClassName()}>
            Decision Trace
          </h3>
          <div className="text-[11px] text-ds-muted">{entries.length} divergence points</div>
        </header>

        {entries.length === 0 ? (
          <div className="mt-ds-3 text-sm text-ds-muted">
            No decision-trace divergences were detected for this run pair.
          </div>
        ) : (
          <ul className="mt-ds-3 space-y-ds-2" role="list">
            {entries.map((entry) => (
              <li key={entry.key}>
                <article aria-label={`${entry.divergence_point} decision divergence`}>
                  <Card className="rounded-ds-lg bg-ds-bg/70 p-ds-3 shadow-none">
                    <div className="flex flex-wrap items-center gap-ds-2">
                      <h4 className="text-xs font-medium text-ds-text">
                        {entry.divergence_point}
                      </h4>
                      <Badge compact className={pillClassName()}>
                        {decisionKindLabel(entry.decision_kind)}
                      </Badge>
                    </div>
                    <div className="mt-ds-2 grid gap-ds-2 md:grid-cols-2">
                      <DiffValueBlock label="Base" value={entry.run_a_summary ?? 'Not present.'} />
                      <DiffValueBlock
                        label="Candidate"
                        value={entry.run_b_summary ?? 'Not present.'}
                      />
                    </div>
                  </Card>
                </article>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </section>
  );
}

function DiffValueBlock({ label, value }: { label: string; value: string }) {
  return (
    <Card className="rounded-ds-md bg-ds-surface/70 px-ds-2 py-ds-2 shadow-none">
      <div className="text-[10px] uppercase tracking-wider text-ds-muted">{label}</div>
      <div className="mt-ds-1 text-xs text-ds-text">{value}</div>
    </Card>
  );
}
