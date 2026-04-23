import { ArrowLeftRight, GitCompareArrows, RefreshCcw } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Badge, Button, Card, Input, Select } from '../../design-system/primitives';
import { RunDiffPanel, type RunsCompareResult } from './RunDiffPanel';
import { buildEvidenceWorkspacePath } from '../../application/workspace/workspaceRoute';
import { useHashNavigation } from '../../hooks/useHashNavigation';
import { useWs } from '../../hooks/WsProvider';
import { useRuntimeStore, type RuntimeRunEntry } from '../../stores/runtimeStore';
import {
  filterRunsForComparison,
  formatRunCompareOption,
  getRunWeightedScore,
  parseCompareThreshold,
  sortRunsForComparison,
  type RunCompareFilters,
  type RunCompareScorecardSummary,
  type RunCompareSortKey,
} from './runsCompareBoardModel';

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

function formatUnknownValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (value === null) return 'null';
  if (value === undefined) return 'undefined';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function directionClass(direction: RunsCompareResult['metrics'][number]['direction']): string {
  if (direction === 'better') return 'text-ds-success';
  if (direction === 'worse') return 'text-ds-error';
  return 'text-ds-muted';
}

function runStatusTone(status: RuntimeRunEntry['status']): 'success' | 'accent' | 'danger' | 'neutral' {
  if (status === 'succeeded') return 'success';
  if (status === 'running') return 'accent';
  if (status === 'failed') return 'danger';
  return 'neutral';
}

const SORT_OPTIONS: Array<{ value: RunCompareSortKey; label: string }> = [
  { value: 'newest', label: 'Newest first' },
  { value: 'oldest', label: 'Oldest first' },
  { value: 'cost-desc', label: 'Highest cost' },
  { value: 'cost-asc', label: 'Lowest cost' },
  { value: 'score-desc', label: 'Highest score' },
  { value: 'score-asc', label: 'Lowest score' },
];

export function RunsCompareBoard() {
  const { rpc, status: wsStatus } = useWs();
  const { navigate } = useHashNavigation();
  const runs = useRuntimeStore((state) => state.runs);
  const selectedRunId = useRuntimeStore((state) => state.selectedRunId);
  const requestSerialRef = useRef(0);
  const connected = wsStatus === 'connected';

  const [baseRunId, setBaseRunId] = useState('');
  const [candidateRunId, setCandidateRunId] = useState('');
  const [sortKey, setSortKey] = useState<RunCompareSortKey>('newest');
  const [minCostUsdText, setMinCostUsdText] = useState('');
  const [maxWeightedScoreText, setMaxWeightedScoreText] = useState('');
  const [compareBusy, setCompareBusy] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [compareResult, setCompareResult] = useState<RunsCompareResult | null>(null);
  const [lastComparedAt, setLastComparedAt] = useState<number | null>(null);
  const [scorecardsByRunId, setScorecardsByRunId] = useState<
    Record<string, RunCompareScorecardSummary | null>
  >({});
  const [scorecardsLoading, setScorecardsLoading] = useState(false);

  const scorecardMap = useMemo(
    () => new Map<string, RunCompareScorecardSummary | null>(Object.entries(scorecardsByRunId)),
    [scorecardsByRunId],
  );

  const sortedRuns = useMemo(
    () => sortRunsForComparison(runs, sortKey, scorecardMap),
    [runs, scorecardMap, sortKey],
  );
  const minCostUsd = useMemo(() => parseCompareThreshold(minCostUsdText), [minCostUsdText]);
  const maxWeightedScore = useMemo(
    () => parseCompareThreshold(maxWeightedScoreText),
    [maxWeightedScoreText],
  );
  const filters: RunCompareFilters = useMemo(
    () => ({
      minCostUsd,
      maxWeightedScore,
    }),
    [maxWeightedScore, minCostUsd],
  );
  const visibleRuns = useMemo(
    () => filterRunsForComparison(sortedRuns, filters, scorecardMap),
    [filters, scorecardMap, sortedRuns],
  );
  const visibleRunOptions = useMemo(
    () => visibleRuns.map((run) => ({
      value: run.runId,
      label: formatRunCompareOption(run, scorecardMap),
    })),
    [scorecardMap, visibleRuns],
  );
  const baseRun = visibleRuns.find((run) => run.runId === baseRunId) ?? null;
  const candidateRun = visibleRuns.find((run) => run.runId === candidateRunId) ?? null;
  const baseScore = baseRun ? getRunWeightedScore(baseRun.runId, scorecardMap) : null;
  const candidateScore = candidateRun ? getRunWeightedScore(candidateRun.runId, scorecardMap) : null;

  const compareRuns = useCallback(
    async (runAId: string, runBId: string) => {
      if (!runAId || !runBId) {
        setCompareResult(null);
        setCompareError(null);
        return;
      }
      if (runAId === runBId) {
        setCompareResult(null);
        setCompareError('Base and candidate runs must be different.');
        return;
      }
      if (!connected) {
        setCompareError('WebSocket not connected.');
        return;
      }

      const requestSerial = ++requestSerialRef.current;
      setCompareBusy(true);
      setCompareError(null);

      try {
        const payload = (await rpc('decisionOs.compareRuns', {
          runAId,
          runBId,
        })) as unknown as RunsCompareResult;

        if (requestSerial !== requestSerialRef.current) {
          return;
        }

        setCompareResult(payload);
        setLastComparedAt(Date.now());
      } catch (error) {
        if (requestSerial !== requestSerialRef.current) {
          return;
        }

        const message =
          error instanceof Error ? error.message : 'Unable to compare the selected runs.';
        setCompareResult(null);
        setCompareError(message);
      } finally {
        if (requestSerial === requestSerialRef.current) {
          setCompareBusy(false);
        }
      }
    },
    [connected, rpc],
  );

  useEffect(() => {
    if (!connected || runs.length === 0) {
      setScorecardsLoading(false);
      return;
    }

    let cancelled = false;

    const loadScorecards = async () => {
      setScorecardsLoading(true);
      try {
        const entries = await Promise.all(
          runs.map(async (run) => {
            try {
              const payload = await rpc('run.scorecard', { runId: run.runId });
              const scorecard = (payload as { scorecard?: { weightedScore?: number; toolCallCount?: number } })
                .scorecard;
              if (!scorecard || typeof scorecard.weightedScore !== 'number') {
                return [run.runId, null] as const;
              }
              return [
                run.runId,
                {
                  weightedScore: scorecard.weightedScore,
                  toolCallCount: typeof scorecard.toolCallCount === 'number'
                    ? scorecard.toolCallCount
                    : null,
                },
              ] as const;
            } catch {
              return [run.runId, null] as const;
            }
          }),
        );

        if (cancelled) {
          return;
        }

        setScorecardsByRunId(Object.fromEntries(entries));
      } finally {
        if (!cancelled) {
          setScorecardsLoading(false);
        }
      }
    };

    void loadScorecards();

    return () => {
      cancelled = true;
    };
  }, [connected, rpc, runs]);

  useEffect(() => {
    const runIds = new Set(visibleRuns.map((run) => run.runId));
    const fallbackCandidateId =
      (selectedRunId && runIds.has(selectedRunId) ? selectedRunId : null)
      ?? visibleRuns[0]?.runId
      ?? '';
    const fallbackBaseId =
      visibleRuns.find((run) => run.runId !== fallbackCandidateId)?.runId ?? '';

    setCandidateRunId((current) => (runIds.has(current) ? current : fallbackCandidateId));
    setBaseRunId((current) => {
      if (runIds.has(current)) {
        return current;
      }
      return fallbackBaseId;
    });
  }, [selectedRunId, visibleRuns]);

  useEffect(() => {
    if (!baseRunId || !candidateRunId) {
      setCompareBusy(false);
      setCompareError(null);
      setCompareResult(null);
      return;
    }
    if (baseRunId === candidateRunId) {
      setCompareBusy(false);
      setCompareResult(null);
      setCompareError('Base and candidate runs must be different.');
      return;
    }
    if (!connected) {
      setCompareBusy(false);
      return;
    }

    void compareRuns(baseRunId, candidateRunId);
  }, [baseRunId, candidateRunId, connected, compareRuns]);

  const swapRuns = () => {
    setBaseRunId(candidateRunId);
    setCandidateRunId(baseRunId);
  };

  const clearFilters = () => {
    setSortKey('newest');
    setMinCostUsdText('');
    setMaxWeightedScoreText('');
  };

  const configChangeCount =
    Object.keys(compareResult?.config.changed ?? {}).length
    + Object.keys(compareResult?.config.added ?? {}).length
    + Object.keys(compareResult?.config.removed ?? {}).length;
  const featureChangeCount =
    (compareResult?.feature_set.added.length ?? 0)
    + (compareResult?.feature_set.removed.length ?? 0)
    + (compareResult?.feature_set.version_changed.length ?? 0);
  const artifactChangeCount = compareResult?.artifacts.length ?? 0;
  const decisionChangeCount = compareResult?.decisions.length ?? 0;
  const highlightedMetricCount =
    compareResult?.metrics.filter((metric) => metric.highlighted).length ?? 0;
  const verifierFindingCount =
    (compareResult?.verifier.new_findings.length ?? 0)
    + (compareResult?.verifier.resolved_findings.length ?? 0);

  return (
    <div className="flex h-full min-h-[24rem] flex-col">
      <div className="flex flex-wrap items-start gap-3 border-b border-ds-border px-4 py-3">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ds-muted">
            <GitCompareArrows size={14} />
            Runs Compare Board
          </div>
          <p className="mt-1 text-sm text-ds-text">
            Pick a baseline run and a candidate run, then inspect metrics, parameters,
            artifacts, and decision deltas in one place.
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[11px] text-ds-muted">
            {visibleRuns.length} visible / {runs.length} total
          </span>
          {scorecardsLoading ? (
            <span className="text-[11px] text-ds-muted">Loading scorecards...</span>
          ) : null}
          <Badge tone={connected ? 'success' : 'neutral'} compact className="uppercase tracking-wider">
            {connected ? 'Connected' : 'Disconnected'}
          </Badge>
          {lastComparedAt ? (
            <span className="text-[11px] text-ds-muted">
              Last diff {new Date(lastComparedAt).toLocaleTimeString()}
            </span>
          ) : null}
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {runs.length < 2 ? (
          <Card className="bg-ds-bg/60 text-ds-muted">
            At least two tracked runs are required before the compare board can render a diff.
          </Card>
        ) : visibleRuns.length < 2 ? (
          <Card className="bg-ds-bg/60 text-ds-muted">
            The current sort and filter settings hide too many runs to compare. Relax the filters
            or clear them to continue.
          </Card>
        ) : (
          <>
            <section className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto]">
              <Select
                id="runs-compare-sort"
                value={sortKey}
                onChange={(event) => setSortKey(event.target.value as RunCompareSortKey)}
                aria-label="Sort compare runs"
                label="Sort"
                options={SORT_OPTIONS}
              />

              <Input
                id="runs-compare-min-cost"
                value={minCostUsdText}
                onChange={(event) => setMinCostUsdText(event.target.value)}
                inputMode="decimal"
                placeholder="0.0000"
                aria-label="Minimum cost in USD"
                label="Filter cost >"
              />

              <Input
                id="runs-compare-max-score"
                value={maxWeightedScoreText}
                onChange={(event) => setMaxWeightedScoreText(event.target.value)}
                inputMode="decimal"
                placeholder="0.850"
                aria-label="Maximum weighted score"
                label="Filter score <"
              />

              <div className="flex items-end">
                <Button
                  onClick={clearFilters}
                  variant="secondary"
                  size="sm"
                >
                  Clear
                </Button>
              </div>
            </section>

            <section className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_auto]">
              <Select
                id="runs-compare-base"
                value={baseRunId}
                onChange={(event) => setBaseRunId(event.target.value)}
                aria-label="Select base run"
                data-testid="runs-compare-base"
                label="Base Run"
                options={[{ value: '', label: 'Select base run' }, ...visibleRunOptions]}
              />

              <div className="flex items-end">
                <Button
                  onClick={swapRuns}
                  disabled={!baseRunId || !candidateRunId}
                  aria-label="Swap base and candidate runs"
                  variant="secondary"
                  size="sm"
                  leadingIcon={<ArrowLeftRight size={14} aria-hidden="true" />}
                >
                  Swap
                </Button>
              </div>

              <Select
                id="runs-compare-candidate"
                value={candidateRunId}
                onChange={(event) => setCandidateRunId(event.target.value)}
                aria-label="Select candidate run"
                data-testid="runs-compare-candidate"
                label="Candidate Run"
                options={[{ value: '', label: 'Select candidate run' }, ...visibleRunOptions]}
              />

              <div className="flex items-end">
                <Button
                  onClick={() => void compareRuns(baseRunId, candidateRunId)}
                  disabled={!connected || compareBusy || !baseRunId || !candidateRunId}
                  data-testid="runs-compare-refresh"
                  variant="primary"
                  size="sm"
                  leadingIcon={<RefreshCcw size={14} className={compareBusy ? 'animate-spin' : ''} aria-hidden="true" />}
                >
                  {compareBusy ? 'Comparing...' : 'Refresh Diff'}
                </Button>
              </div>
            </section>

            <section className="grid gap-3 xl:grid-cols-2">
              <RunSelectionCard title="Base" run={baseRun} weightedScore={baseScore} />
              <RunSelectionCard title="Candidate" run={candidateRun} weightedScore={candidateScore} />
            </section>

            {compareError ? (
              <Card tone="danger" className="text-ds-error">
                {compareError}
              </Card>
            ) : null}

            {compareResult ? (
              <>
                <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-6 2xl:grid-cols-7">
                  <SummaryCard label="Metric Deltas" value={String(compareResult.metrics.length)} />
                  <SummaryCard label="Highlighted Metrics" value={String(highlightedMetricCount)} />
                  <SummaryCard label="Artifact Diffs" value={String(artifactChangeCount)} />
                  <SummaryCard label="Decision Diffs" value={String(decisionChangeCount)} />
                  <SummaryCard label="Config Changes" value={String(configChangeCount)} />
                  <SummaryCard label="Feature Changes" value={String(featureChangeCount)} />
                  <SummaryCard label="Verifier Findings" value={String(verifierFindingCount)} />
                </section>

                <Card className="flex flex-wrap items-center gap-ds-2 bg-ds-bg/60">
                  <div className="mr-auto text-sm text-ds-text">
                    Highlight rule: relative metric change {'>='} 5% or absolute delta {'>='}{' '}
                    0.05 on near-zero baselines.
                  </div>
                  <Button
                    onClick={() => navigate(buildEvidenceWorkspacePath('charts'))}
                    variant="secondary"
                    size="sm"
                  >
                    Open Charts Workspace
                  </Button>
                  <Button
                    onClick={() => navigate(buildEvidenceWorkspacePath('files'))}
                    variant="secondary"
                    size="sm"
                  >
                    Open Files Workspace
                  </Button>
                  <Button
                    onClick={() => navigate(buildEvidenceWorkspacePath('export'))}
                    variant="secondary"
                    size="sm"
                  >
                    Open Export Workspace
                  </Button>
                  <Button
                    onClick={() => navigate('/governance/review')}
                    variant="secondary"
                    size="sm"
                  >
                    Open Review Surface
                  </Button>
                </Card>

                <Card className="bg-ds-bg/60">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
                    Summary
                  </div>
                  <div className="mt-3 prose prose-invert prose-sm max-w-none prose-headings:text-ds-text prose-p:text-ds-text prose-li:text-ds-text prose-code:text-ds-accent">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {compareResult.summary_markdown}
                    </ReactMarkdown>
                  </div>
                </Card>

                <RunDiffPanel
                  baseRun={baseRun}
                  candidateRun={candidateRun}
                  compareResult={compareResult}
                  scorecardsByRunId={scorecardMap}
                />

                <section className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)]">
                  <Card className="bg-ds-bg/60">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
                        Metrics
                      </div>
                      <div className="text-[11px] text-ds-muted">
                        {compareResult.run_a_id} {'->'} {compareResult.run_b_id}
                      </div>
                    </div>

                    {compareResult.metrics.length === 0 ? (
                      <div className="mt-3 text-sm text-ds-muted">
                        No overlapping metrics were available for this run pair.
                      </div>
                    ) : (
                      <div className="mt-3 space-y-2">
                        {compareResult.metrics.map((metric) => (
                          <div
                            key={metric.metric}
                            className={`rounded-xl border p-3 ${
                              metric.highlighted
                                ? 'border-ds-accent/40 bg-ds-accent/10'
                                : 'border-ds-border/70 bg-ds-surface/60'
                            }`}
                          >
                            <div className="flex items-center gap-3">
                              <div className="min-w-0">
                                <div className="truncate text-sm font-medium text-ds-text">
                                  {metric.metric}
                                </div>
                                <div className="mt-1 text-[11px] text-ds-muted">
                                  {formatMetricValue(metric.from_value)} {'->'}{' '}
                                  {formatMetricValue(metric.to_value)}
                                </div>
                              </div>
                              {metric.highlighted ? (
                                <Badge tone="accent" compact className="uppercase tracking-wider">
                                  Highlighted
                                </Badge>
                              ) : null}
                              <div className={`ml-auto text-sm font-semibold ${directionClass(metric.direction)}`}>
                                {metric.delta >= 0 ? '+' : ''}
                                {formatMetricValue(metric.delta)}
                              </div>
                            </div>
                            {metric.significance_note ? (
                              <div className="mt-2 text-xs text-ds-muted">
                                {metric.significance_note}
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    )}
                  </Card>

                  <div className="space-y-4">
                    <ReproducibilityCard
                      codeRef={compareResult.code_ref}
                      dataSnapshot={compareResult.data_snapshot}
                    />
                    <VerifierCard verifier={compareResult.verifier} />
                  </div>
                </section>

                <section className="grid gap-4 xl:grid-cols-2">
                  <Card className="bg-ds-bg/60">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
                      Feature Diff
                    </div>
                    <div className="mt-3 grid gap-3 md:grid-cols-3">
                      <FeatureDeltaCard
                        title="Added"
                        items={compareResult.feature_set.added.map(
                          (item) => `${item.feature_id} v${item.version}`,
                        )}
                      />
                      <FeatureDeltaCard
                        title="Removed"
                        items={compareResult.feature_set.removed.map(
                          (item) => `${item.feature_id} v${item.version}`,
                        )}
                      />
                      <FeatureDeltaCard
                        title="Version Changed"
                        items={compareResult.feature_set.version_changed.map(
                          ([featureId, fromVersion, toVersion]) =>
                            `${featureId}: v${fromVersion} -> v${toVersion}`,
                        )}
                      />
                    </div>
                  </Card>

                  <Card className="bg-ds-bg/60">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
                      Config Diff
                    </div>
                    <div className="mt-3 grid gap-3 md:grid-cols-3">
                      <ConfigDeltaCard
                        title="Changed"
                        entries={Object.entries(compareResult.config.changed).map(
                          ([key, [before, after]]) => ({
                            key,
                            before: formatUnknownValue(before),
                            after: formatUnknownValue(after),
                          }),
                        )}
                      />
                      <ConfigPresenceCard
                        title="Added"
                        entries={Object.entries(compareResult.config.added).map(([key, value]) => ({
                          key,
                          value: formatUnknownValue(value),
                        }))}
                      />
                      <ConfigPresenceCard
                        title="Removed"
                        entries={Object.entries(compareResult.config.removed).map(([key, value]) => ({
                          key,
                          value: formatUnknownValue(value),
                        }))}
                      />
                    </div>
                  </Card>
                </section>
              </>
            ) : (
              <Card className="bg-ds-bg/60 text-ds-muted">
                Select two distinct runs to load the compare board.
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function RunSelectionCard({
  title,
  run,
  weightedScore,
}: {
  title: string;
  run: RuntimeRunEntry | null;
  weightedScore: number | null;
}) {
  if (!run) {
    return (
      <Card className="bg-ds-bg/60 text-ds-muted">
        {title} run is not selected.
      </Card>
    );
  }

  const sessionLabel = run.sessionLabel || run.sessionId;
  const subtitle = run.resultPreview || run.error || run.message || '-';

  return (
    <Card className="bg-ds-bg/60">
      <div className="flex items-center gap-2">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
          {title}
        </div>
        <Badge tone={runStatusTone(run.status)} compact className="ml-auto uppercase tracking-wider">
          {run.status}
        </Badge>
      </div>
      <div className="mt-3 space-y-1">
        <div className="break-all font-mono text-sm text-ds-text">{run.runId}</div>
        <div className="text-xs text-ds-muted">
          {run.surface} / {sessionLabel}
        </div>
        {run.threadLabel ? <div className="text-xs uppercase text-ds-muted">{run.threadLabel}</div> : null}
      </div>
      <div className="mt-3 line-clamp-2 text-sm text-ds-text">{subtitle}</div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <SelectionFact label="Started" value={formatDateTime(run.startedAt)} />
        <SelectionFact label="Finished" value={formatDateTime(run.finishedAt)} />
        <SelectionFact label="Cost" value={`$${run.costUsd.toFixed(4)}`} />
        <SelectionFact label="Weighted Score" value={weightedScore === null ? 'n/a' : weightedScore.toFixed(3)} />
        <SelectionFact label="Task" value={run.taskId ?? '-'} mono />
      </div>
    </Card>
  );
}

function SelectionFact({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-xl border border-ds-border/70 bg-ds-surface/60 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-ds-muted">{label}</div>
      <div className={`mt-1 text-xs text-ds-text ${mono ? 'break-all font-mono' : ''}`}>{value}</div>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <Card className="bg-ds-bg/60">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-ds-text">{value}</div>
    </Card>
  );
}

function FeatureDeltaCard({ title, items }: { title: string; items: string[] }) {
  return (
    <Card className="bg-ds-surface/60">
      <div className="text-xs font-medium text-ds-text">{title}</div>
      {items.length === 0 ? (
        <div className="mt-3 text-sm text-ds-muted">No changes.</div>
      ) : (
        <div className="mt-3 space-y-2">
          {items.map((item) => (
            <div
              key={`${title}-${item}`}
              className="rounded-lg border border-ds-border bg-ds-bg/70 px-2 py-1.5 text-xs text-ds-text"
            >
              {item}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function ConfigDeltaCard({
  title,
  entries,
}: {
  title: string;
  entries: Array<{ key: string; before: string; after: string }>;
}) {
  return (
    <Card className="bg-ds-surface/60">
      <div className="text-xs font-medium text-ds-text">{title}</div>
      {entries.length === 0 ? (
        <div className="mt-3 text-sm text-ds-muted">No changes.</div>
      ) : (
        <div className="mt-3 space-y-2">
          {entries.map((entry) => (
            <div
              key={`${title}-${entry.key}`}
              className="rounded-lg border border-ds-border bg-ds-bg/70 p-2"
            >
              <div className="text-xs font-medium text-ds-text">{entry.key}</div>
              <div className="mt-2 grid gap-2 text-[11px] text-ds-muted">
                <ConfigValueBlock label="Before" value={entry.before} />
                <ConfigValueBlock label="After" value={entry.after} />
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function ConfigPresenceCard({
  title,
  entries,
}: {
  title: string;
  entries: Array<{ key: string; value: string }>;
}) {
  return (
    <Card className="bg-ds-surface/60">
      <div className="text-xs font-medium text-ds-text">{title}</div>
      {entries.length === 0 ? (
        <div className="mt-3 text-sm text-ds-muted">No entries.</div>
      ) : (
        <div className="mt-3 space-y-2">
          {entries.map((entry) => (
            <div
              key={`${title}-${entry.key}`}
              className="rounded-lg border border-ds-border bg-ds-bg/70 p-2"
            >
              <div className="text-xs font-medium text-ds-text">{entry.key}</div>
              <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-[11px] text-ds-muted">
                {entry.value}
              </pre>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function ConfigValueBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-ds-border/70 bg-ds-surface/70 px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-wider text-ds-muted">{label}</div>
      <pre className="mt-1 whitespace-pre-wrap break-words font-mono text-[11px] text-ds-text">
        {value}
      </pre>
    </div>
  );
}

function VerifierCard({ verifier }: { verifier: RunsCompareResult['verifier'] }) {
  return (
    <Card className="bg-ds-bg/60">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
        Verifier
      </div>
      <div className="mt-3 space-y-2">
        <VerifierLine label="Statistical" value={verifier.statistical} />
        <VerifierLine label="Data" value={verifier.data} />
        <VerifierLine label="Policy" value={verifier.policy} />
      </div>

      {verifier.new_findings.length > 0 ? (
        <div className="mt-3 space-y-2">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
            New Findings
          </div>
          {verifier.new_findings.map((finding) => (
            <div key={`new-${finding}`} className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-300">
              {finding}
            </div>
          ))}
        </div>
      ) : null}

      {verifier.resolved_findings.length > 0 ? (
        <div className="mt-3 space-y-2">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
            Resolved Findings
          </div>
          {verifier.resolved_findings.map((finding) => (
            <div key={`resolved-${finding}`} className="rounded-xl border border-ds-success/40 bg-ds-success/10 px-3 py-2 text-sm text-ds-success">
              {finding}
            </div>
          ))}
        </div>
      ) : null}
    </Card>
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
  const toneForValue = (current: string): 'success' | 'warning' | 'danger' | 'neutral' => {
    const normalized = current.toLowerCase();
    if (normalized === 'pass' || normalized === 'ok' || normalized === 'approved') return 'success';
    if (normalized === 'warn' || normalized === 'warning' || normalized.startsWith('pending')) return 'warning';
    if (normalized === 'fail' || normalized === 'alert' || normalized === 'rejected') return 'danger';
    return 'neutral';
  };

  return (
    <div className="rounded-xl border border-ds-border/70 bg-ds-surface/60 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-ds-muted">{label}</div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ds-text">
        <Badge tone={toneForValue(value[0])} compact>{value[0]}</Badge>
        <span className="text-ds-muted">{'->'}</span>
        <Badge tone={toneForValue(value[1])} compact>{value[1]}</Badge>
        {changed ? <span className="text-[11px] text-ds-muted">changed</span> : null}
      </div>
    </div>
  );
}

function ReproducibilityCard({
  codeRef,
  dataSnapshot,
}: {
  codeRef: [string, string];
  dataSnapshot: [string, string];
}) {
  return (
    <Card className="bg-ds-bg/60">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
        Reproducibility
      </div>
      <div className="mt-3 space-y-3">
        <ReproducibilityRow label="Code Ref" before={codeRef[0]} after={codeRef[1]} />
        <ReproducibilityRow label="Data Snapshot" before={dataSnapshot[0]} after={dataSnapshot[1]} />
      </div>
    </Card>
  );
}

function ReproducibilityRow({
  label,
  before,
  after,
}: {
  label: string;
  before: string;
  after: string;
}) {
  return (
    <div className="rounded-xl border border-ds-border/70 bg-ds-surface/60 p-3">
      <div className="text-[10px] uppercase tracking-wider text-ds-muted">{label}</div>
      <div className="mt-2 grid gap-2">
        <ConfigValueBlock label="Base" value={before} />
        <ConfigValueBlock label="Candidate" value={after} />
      </div>
    </div>
  );
}
