import { ArrowLeftRight, GitCompareArrows, RefreshCcw } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Badge, Button, Card, Input, Select } from '../../design-system/primitives';
import { RunDiffPanel, type RunsCompareResult } from './RunDiffPanel';
import { buildEvidenceWorkspacePath } from '../../application/workspace/workspaceRoute';
import { useHashNavigation } from '../../hooks/useHashNavigation';
import { useWs } from '../../hooks/WsProvider';
import { useI18n } from '../../stores/i18nStore';
import { useRuntimeStore } from '../../stores/runtimeStore';
import {
  filterRunsForComparison,
  formatRunCompareOption,
  getRunWeightedScore,
  parseCompareThreshold,
  sortRunsForComparison,
  type RunCompareEntry,
  type RunCompareFilters,
  type RunCompareScorecardSummary,
  type RunCompareSortKey,
} from './runsCompareBoardModel';

interface DecisionRunSummary {
  run_id: string;
  experiment_group?: string | null;
  sequence?: number | null;
  owner?: string | null;
  status?: string | null;
  created_at?: string | null;
  method?: {
    model_family?: string | null;
  } | null;
  result?: {
    metrics?: Record<string, number> | null;
  } | null;
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

function runStatusTone(status: string): 'success' | 'accent' | 'danger' | 'neutral' {
  if (status === 'succeeded') return 'success';
  if (status === 'completed') return 'success';
  if (status === 'pass') return 'success';
  if (status === 'running') return 'accent';
  if (status === 'failed') return 'danger';
  if (status === 'fail') return 'danger';
  return 'neutral';
}

function parseDecisionRunTimestamp(value?: string | null): number {
  if (!value) return Date.now() / 1000;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed / 1000 : Date.now() / 1000;
}

function metricPreview(metrics?: Record<string, number> | null): string {
  const firstMetric = Object.entries(metrics ?? {})[0];
  if (!firstMetric) return '';
  return `${firstMetric[0]} ${firstMetric[1].toFixed(3)}`;
}

function normalizeDecisionRun(run: DecisionRunSummary): RunCompareEntry {
  const createdAt = parseDecisionRunTimestamp(run.created_at);
  const group = run.experiment_group || 'decision-os';
  const modelFamily = run.method?.model_family || group;
  const preview = metricPreview(run.result?.metrics);
  const sequence = typeof run.sequence === 'number' ? `#${run.sequence}` : '';

  return {
    runId: run.run_id,
    sessionId: group,
    sessionLabel: [group, sequence].filter(Boolean).join(' '),
    threadLabel: run.owner ?? null,
    surface: 'decision_os',
    status: run.status || 'unknown',
    message: modelFamily,
    taskId: null,
    error: null,
    resultPreview: preview || modelFamily,
    costUsd: 0,
    createdAt,
    startedAt: createdAt,
    finishedAt: createdAt,
  };
}

const SORT_OPTION_KEYS: ReadonlyArray<{
  value: RunCompareSortKey;
  labelKey: string;
}> = [
  { value: 'newest', labelKey: 'run.runtime.compare.sort.newest' },
  { value: 'oldest', labelKey: 'run.runtime.compare.sort.oldest' },
  { value: 'cost-desc', labelKey: 'run.runtime.compare.sort.costDesc' },
  { value: 'cost-asc', labelKey: 'run.runtime.compare.sort.costAsc' },
  { value: 'score-desc', labelKey: 'run.runtime.compare.sort.scoreDesc' },
  { value: 'score-asc', labelKey: 'run.runtime.compare.sort.scoreAsc' },
];

export function RunsCompareBoard() {
  const { t } = useI18n();
  const sortOptions = useMemo(
    () => SORT_OPTION_KEYS.map(({ value, labelKey }) => ({ value, label: t(labelKey) })),
    [t],
  );
  const { rpc, status: wsStatus } = useWs();
  const { navigate } = useHashNavigation();
  const selectedRunId = useRuntimeStore((state) => state.selectedRunId);
  const requestSerialRef = useRef(0);
  const connected = wsStatus === 'connected';

  const [runs, setRuns] = useState<RunCompareEntry[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsError, setRunsError] = useState<string | null>(null);
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
  const scorecardsLoading = false;

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
      label: formatRunCompareOption(run, scorecardMap, {
        score: t('run.runtime.compare.option.score'),
        scoreUnavailable: t('run.runtime.compare.option.scoreUnavailable'),
      }),
    })),
    [scorecardMap, t, visibleRuns],
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
        setCompareError(t('run.compare.mustBeDifferent'));
        return;
      }
      if (!connected) {
        setCompareError(t('run.compare.wsDisconnected'));
        return;
      }

      const requestSerial = ++requestSerialRef.current;
      setCompareBusy(true);
      setCompareError(null);

      try {
        const payload = (await rpc('decisionOs.compareRuns', {
          runAId,
          runBId,
        }, { timeoutMs: 120_000 })) as unknown as RunsCompareResult;

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
          error instanceof Error ? error.message : t('run.runtime.compare.error.compareFailed');
        setCompareResult(null);
        setCompareError(message);
      } finally {
        if (requestSerial === requestSerialRef.current) {
          setCompareBusy(false);
        }
      }
    },
    [connected, rpc, t],
  );

  useEffect(() => {
    if (!connected) {
      setRuns([]);
      setRunsError(null);
      setRunsLoading(false);
      setScorecardsByRunId({});
      return;
    }

    let cancelled = false;

    const loadDecisionRuns = async () => {
      setRunsLoading(true);
      setRunsError(null);
      try {
        const payload = await rpc('decisionOs.overview', {
          runLimit: 20,
          modelLimit: 1,
          decisionLimit: 1,
        });
        if (cancelled) {
          return;
        }
        const overviewRuns = Array.isArray(payload.runs)
          ? (payload.runs as DecisionRunSummary[])
          : [];
        setRuns(
          overviewRuns
            .filter((run) => typeof run.run_id === 'string' && run.run_id.trim().length > 0)
            .map(normalizeDecisionRun),
        );
        setScorecardsByRunId({});
      } catch (error) {
        if (!cancelled) {
          setRuns([]);
          setRunsError(
            error instanceof Error ? error.message : t('run.runtime.compare.error.loadRunsFailed'),
          );
        }
      } finally {
        if (!cancelled) {
          setRunsLoading(false);
        }
      }
    };

    void loadDecisionRuns();
    const timer = window.setInterval(() => {
      void loadDecisionRuns();
    }, 5000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [connected, rpc, t]);

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
      setCompareError(t('run.compare.mustBeDifferent'));
      return;
    }
    if (!connected) {
      setCompareBusy(false);
      return;
    }

    void compareRuns(baseRunId, candidateRunId);
  }, [baseRunId, candidateRunId, connected, compareRuns, t]);

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
            {t('run.compare.title')}
          </div>
          <p className="mt-1 text-sm text-ds-text">
            {t('run.compare.description')}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[11px] text-ds-muted">
            {t('run.runtime.compare.status.visibleTotal', {
              visible: visibleRuns.length,
              total: runs.length,
            })}
          </span>
          {runsLoading ? (
            <span className="text-[11px] text-ds-muted">{t('run.runtime.compare.status.loadingRuns')}</span>
          ) : null}
          {scorecardsLoading ? (
            <span className="text-[11px] text-ds-muted">{t('run.runtime.compare.status.loadingScorecards')}</span>
          ) : null}
          <Badge tone={connected ? 'success' : 'neutral'} compact className="uppercase tracking-wider">
            {connected ? t('run.runtime.compare.status.connected') : t('run.runtime.compare.status.disconnected')}
          </Badge>
          {lastComparedAt ? (
            <span className="text-[11px] text-ds-muted">
              {t('run.runtime.compare.status.lastDiff', {
                time: new Date(lastComparedAt).toLocaleTimeString(),
              })}
            </span>
          ) : null}
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {runsError ? (
          <Card tone="danger" className="text-ds-error">
            {runsError}
          </Card>
        ) : runs.length < 2 ? (
          <Card className="bg-ds-bg/60 text-ds-muted">
            {t('run.compare.needTwoRuns')}
          </Card>
        ) : visibleRuns.length < 2 ? (
          <Card className="bg-ds-bg/60 text-ds-muted">
            {t('run.compare.filterTooStrict')}
          </Card>
        ) : (
          <>
            <section className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto]">
              <Select
                id="runs-compare-sort"
                value={sortKey}
                onChange={(event) => setSortKey(event.target.value as RunCompareSortKey)}
                aria-label={t('run.compare.sortAria')}
                label={t('run.compare.sortLabel')}
                options={sortOptions}
              />

              <Input
                id="runs-compare-min-cost"
                value={minCostUsdText}
                onChange={(event) => setMinCostUsdText(event.target.value)}
                inputMode="decimal"
                placeholder="0.0000"
                aria-label={t('run.compare.minCostAria')}
                label={t('run.compare.filterCostLabel')}
              />

              <Input
                id="runs-compare-max-score"
                value={maxWeightedScoreText}
                onChange={(event) => setMaxWeightedScoreText(event.target.value)}
                inputMode="decimal"
                placeholder="0.850"
                aria-label={t('run.compare.maxScoreAria')}
                label={t('run.compare.filterScoreLabel')}
              />

              <div className="flex items-end">
                <Button
                  onClick={clearFilters}
                  variant="secondary"
                  size="sm"
                >
                  {t('run.compare.clear')}
                </Button>
              </div>
            </section>

            <section className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_auto]">
              <Select
                id="runs-compare-base"
                value={baseRunId}
                onChange={(event) => setBaseRunId(event.target.value)}
                aria-label={t('run.compare.selectBaseRun')}
                data-testid="runs-compare-base"
                label={t('run.compare.baseRunLabel')}
                options={[{ value: '', label: t('run.compare.selectBaseRun') }, ...visibleRunOptions]}
              />

              <div className="flex items-end">
                <Button
                  onClick={swapRuns}
                  disabled={!baseRunId || !candidateRunId}
                  aria-label={t('run.compare.swapAria')}
                  variant="secondary"
                  size="sm"
                  leadingIcon={<ArrowLeftRight size={14} aria-hidden="true" />}
                >
                  {t('run.compare.swap')}
                </Button>
              </div>

              <Select
                id="runs-compare-candidate"
                value={candidateRunId}
                onChange={(event) => setCandidateRunId(event.target.value)}
                aria-label={t('run.compare.selectCandidateRun')}
                data-testid="runs-compare-candidate"
                label={t('run.compare.candidateRunLabel')}
                options={[{ value: '', label: t('run.compare.selectCandidateRun') }, ...visibleRunOptions]}
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
                  {compareBusy ? t('run.compare.comparing') : t('run.compare.refreshDiff')}
                </Button>
              </div>
            </section>

            <section className="grid gap-3 xl:grid-cols-2">
              <RunSelectionCard
                title={t('run.runtime.compare.selection.title.base')}
                run={baseRun}
                weightedScore={baseScore}
              />
              <RunSelectionCard
                title={t('run.runtime.compare.selection.title.candidate')}
                run={candidateRun}
                weightedScore={candidateScore}
              />
            </section>

            {compareError ? (
              <Card tone="danger" className="text-ds-error">
                {compareError}
              </Card>
            ) : null}

            {compareResult ? (
              <>
                <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-6 2xl:grid-cols-7">
                  <SummaryCard
                    label={t('run.runtime.compare.summary.metricDeltas')}
                    value={String(compareResult.metrics.length)}
                  />
                  <SummaryCard
                    label={t('run.runtime.compare.summary.highlightedMetrics')}
                    value={String(highlightedMetricCount)}
                  />
                  <SummaryCard
                    label={t('run.runtime.compare.summary.artifactDiffs')}
                    value={String(artifactChangeCount)}
                  />
                  <SummaryCard
                    label={t('run.runtime.compare.summary.decisionDiffs')}
                    value={String(decisionChangeCount)}
                  />
                  <SummaryCard
                    label={t('run.runtime.compare.summary.configChanges')}
                    value={String(configChangeCount)}
                  />
                  <SummaryCard
                    label={t('run.runtime.compare.summary.featureChanges')}
                    value={String(featureChangeCount)}
                  />
                  <SummaryCard
                    label={t('run.runtime.compare.summary.verifierFindings')}
                    value={String(verifierFindingCount)}
                  />
                </section>

                <Card className="flex flex-wrap items-center gap-ds-2 bg-ds-bg/60">
                  <div className="mr-auto text-sm text-ds-text">
                    {t('run.runtime.compare.highlightRule')}
                  </div>
                  <Button
                    onClick={() => navigate('/artifacts/files')}
                    variant="secondary"
                    size="sm"
                  >
                    {t('run.runtime.compare.action.openCharts')}
                  </Button>
                  <Button
                    onClick={() => navigate('/artifacts/files')}
                    variant="secondary"
                    size="sm"
                  >
                    {t('run.runtime.compare.action.openFiles')}
                  </Button>
                  <Button
                    onClick={() => navigate(buildEvidenceWorkspacePath('export'))}
                    variant="secondary"
                    size="sm"
                  >
                    {t('run.runtime.compare.action.openExport')}
                  </Button>
                  <Button
                    onClick={() => navigate('/governance/review')}
                    variant="secondary"
                    size="sm"
                  >
                    {t('run.runtime.compare.action.openReview')}
                  </Button>
                </Card>

                <Card className="bg-ds-bg/60">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
                    {t('run.compare.section.summary')}
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
                        {t('run.compare.section.metrics')}
                      </div>
                      <div className="text-[11px] text-ds-muted">
                        {compareResult.run_a_id} {'->'} {compareResult.run_b_id}
                      </div>
                    </div>

                    {compareResult.metrics.length === 0 ? (
                      <div className="mt-3 text-sm text-ds-muted">
                        {t('run.runtime.compare.empty.noOverlap')}
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
                                  {t('run.runtime.compare.metric.highlighted')}
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
                      {t('run.compare.section.featureDiff')}
                    </div>
                    <div className="mt-3 grid gap-3 md:grid-cols-3">
                      <FeatureDeltaCard
                        title={t('run.runtime.compare.feature.added')}
                        items={compareResult.feature_set.added.map(
                          (item) => `${item.feature_id} v${item.version}`,
                        )}
                      />
                      <FeatureDeltaCard
                        title={t('run.runtime.compare.feature.removed')}
                        items={compareResult.feature_set.removed.map(
                          (item) => `${item.feature_id} v${item.version}`,
                        )}
                      />
                      <FeatureDeltaCard
                        title={t('run.runtime.compare.feature.versionChanged')}
                        items={compareResult.feature_set.version_changed.map(
                          ([featureId, fromVersion, toVersion]) =>
                            `${featureId}: v${fromVersion} -> v${toVersion}`,
                        )}
                      />
                    </div>
                  </Card>

                  <Card className="bg-ds-bg/60">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
                      {t('run.compare.section.configDiff')}
                    </div>
                    <div className="mt-3 grid gap-3 md:grid-cols-3">
                      <ConfigDeltaCard
                        title={t('run.runtime.compare.config.changed')}
                        entries={Object.entries(compareResult.config.changed).map(
                          ([key, [before, after]]) => ({
                            key,
                            before: formatUnknownValue(before),
                            after: formatUnknownValue(after),
                          }),
                        )}
                      />
                      <ConfigPresenceCard
                        title={t('run.runtime.compare.config.added')}
                        entries={Object.entries(compareResult.config.added).map(([key, value]) => ({
                          key,
                          value: formatUnknownValue(value),
                        }))}
                      />
                      <ConfigPresenceCard
                        title={t('run.runtime.compare.config.removed')}
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
                {t('run.compare.selectTwo')}
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
  run: RunCompareEntry | null;
  weightedScore: number | null;
}) {
  const { t } = useI18n();
  if (!run) {
    return (
      <Card className="bg-ds-bg/60 text-ds-muted">
        {t('run.runtime.compare.selection.notSelected', { title })}
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
        <SelectionFact label={t('run.runtime.compare.selection.label.started')} value={formatDateTime(run.startedAt)} />
        <SelectionFact label={t('run.runtime.compare.selection.label.finished')} value={formatDateTime(run.finishedAt)} />
        <SelectionFact label={t('run.runtime.compare.selection.label.cost')} value={`$${run.costUsd.toFixed(4)}`} />
        <SelectionFact
          label={t('run.runtime.compare.selection.label.weightedScore')}
          value={
            weightedScore === null
              ? t('run.runtime.compare.selection.weightedScoreUnknown')
              : weightedScore.toFixed(3)
          }
        />
        <SelectionFact label={t('run.runtime.compare.selection.label.task')} value={run.taskId ?? '-'} mono />
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
  const { t } = useI18n();
  return (
    <Card className="bg-ds-surface/60">
      <div className="text-xs font-medium text-ds-text">{title}</div>
      {items.length === 0 ? (
        <div className="mt-3 text-sm text-ds-muted">{t('run.runtime.compare.empty.noChanges')}</div>
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
  const { t } = useI18n();
  return (
    <Card className="bg-ds-surface/60">
      <div className="text-xs font-medium text-ds-text">{title}</div>
      {entries.length === 0 ? (
        <div className="mt-3 text-sm text-ds-muted">{t('run.runtime.compare.empty.noChanges')}</div>
      ) : (
        <div className="mt-3 space-y-2">
          {entries.map((entry) => (
            <div
              key={`${title}-${entry.key}`}
              className="rounded-lg border border-ds-border bg-ds-bg/70 p-2"
            >
              <div className="text-xs font-medium text-ds-text">{entry.key}</div>
              <div className="mt-2 grid gap-2 text-[11px] text-ds-muted">
                <ConfigValueBlock label={t('run.runtime.compare.config.before')} value={entry.before} />
                <ConfigValueBlock label={t('run.runtime.compare.config.after')} value={entry.after} />
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
  const { t } = useI18n();
  return (
    <Card className="bg-ds-surface/60">
      <div className="text-xs font-medium text-ds-text">{title}</div>
      {entries.length === 0 ? (
        <div className="mt-3 text-sm text-ds-muted">{t('run.runtime.compare.empty.noEntries')}</div>
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
  const { t } = useI18n();
  return (
    <Card className="bg-ds-bg/60">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
        {t('run.compare.section.verifier')}
      </div>
      <div className="mt-3 space-y-2">
        <VerifierLine label={t('run.runtime.compare.verifier.statistical')} value={verifier.statistical} />
        <VerifierLine label={t('run.runtime.compare.verifier.data')} value={verifier.data} />
        <VerifierLine label={t('run.runtime.compare.verifier.policy')} value={verifier.policy} />
      </div>

      {verifier.new_findings.length > 0 ? (
        <div className="mt-3 space-y-2">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
            {t('run.compare.section.newFindings')}
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
            {t('run.compare.section.resolvedFindings')}
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
  const { t } = useI18n();
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
        {changed ? <span className="text-[11px] text-ds-muted">{t('run.runtime.compare.verifier.changed')}</span> : null}
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
  const { t } = useI18n();
  return (
    <Card className="bg-ds-bg/60">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
        {t('run.compare.section.reproducibility')}
      </div>
      <div className="mt-3 space-y-3">
        <ReproducibilityRow
          label={t('run.runtime.compare.repro.codeRef')}
          before={codeRef[0]}
          after={codeRef[1]}
        />
        <ReproducibilityRow
          label={t('run.runtime.compare.repro.dataSnapshot')}
          before={dataSnapshot[0]}
          after={dataSnapshot[1]}
        />
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
  const { t } = useI18n();
  return (
    <div className="rounded-xl border border-ds-border/70 bg-ds-surface/60 p-3">
      <div className="text-[10px] uppercase tracking-wider text-ds-muted">{label}</div>
      <div className="mt-2 grid gap-2">
        <ConfigValueBlock label={t('run.runtime.compare.repro.base')} value={before} />
        <ConfigValueBlock label={t('run.runtime.compare.repro.candidate')} value={after} />
      </div>
    </div>
  );
}
