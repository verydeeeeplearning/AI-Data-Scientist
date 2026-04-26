/**
 * Runtime regression dashboard for the evaluation harness.
 */

import { Activity, RefreshCcw, Snowflake } from 'lucide-react';
import { useEffect, useId, useMemo, useState } from 'react';
import {
  ResultCardSectionPanel,
  ResultCardSectionTitle,
} from '../../design-system/composites';
import { Badge, Button, Card, Select } from '../../design-system/primitives';
import { useRegressionBoard } from '../../hooks/useRegressionBoard';
import { useI18n } from '../../stores/i18nStore';
import {
  buildRegressionBoardModel,
  getDefaultRegressionPointKey,
} from './regressionBoardModel';

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'n/a';
  }
  return `${Math.round(value * 100)}%`;
}

function formatDecimal(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'n/a';
  }
  return value.toFixed(3);
}

function formatPercentPoints(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'n/a';
  }
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}pp`;
}

function formatDeltaFromScore(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'n/a';
  }
  return formatPercentPoints(Math.round(value * 1000) / 10);
}

function formatTimestamp(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleString();
}

function boardNoticeToneClass(tone: 'neutral' | 'danger' = 'neutral'): string {
  return tone === 'danger'
    ? 'border-ds-error/30 bg-ds-error/10 text-ds-error'
    : 'bg-ds-surface/60 text-ds-muted';
}

function deltaTone(value: number | null | undefined): 'success' | 'warn' {
  return (value ?? 0) < 0 ? 'warn' : 'success';
}

function alertTone(severity: string): 'danger' | 'warning' {
  return severity === 'high' ? 'danger' : 'warning';
}

export function RegressionBoard() {
  const { t } = useI18n();
  const {
    board,
    selectedMode,
    setSelectedMode,
    selectedDomain,
    setSelectedDomain,
    loading,
    error,
    freezeLoading,
    freezeError,
    refresh,
    freezeBaseline,
  } = useRegressionBoard();
  const [selectedPointKey, setSelectedPointKey] = useState<string | null>(null);
  const titleId = useId();

  useEffect(() => {
    if (!board) {
      setSelectedPointKey(null);
      return;
    }
    const hasSelectedPoint =
      selectedPointKey !== null && board.points.some((item) => item.axisKey === selectedPointKey);
    if (!hasSelectedPoint) {
      setSelectedPointKey(getDefaultRegressionPointKey(board));
    }
  }, [board, selectedPointKey]);

  const model = useMemo(
    () => buildRegressionBoardModel(board, selectedPointKey),
    [board, selectedPointKey]
  );
  const freezeDisabled =
    !model || !model.canFreezeBaseline || !model.selectedPoint || freezeLoading;
  const freezeDisabledReason = (() => {
    if (!model || freezeLoading) return null;
    if (!model.selectedPoint) return t('run.regression.freezeDisabledNoPoint');
    if (model.axisKind !== 'commit') return t('run.regression.freezeDisabledCommitOnly');
    if (model.selectedPointIsFrozenBaseline)
      return t('run.regression.freezeDisabledAlreadyBaseline');
    return null;
  })();
  const freezeButtonTitle = freezeDisabled && freezeDisabledReason
    ? freezeDisabledReason
    : t('run.regression.freezeActionTitle');
  const modeOptions = [
    { value: '', label: t('run.regression.allModes') },
    { value: 'offline', label: 'offline' },
    { value: 'online', label: 'online' },
    { value: 'shadow', label: 'shadow' },
  ];
  const domainOptions = [
    { value: '', label: t('run.regression.allDomains') },
    ...(board?.availableDomains ?? []).map((domain) => ({
      value: domain,
      label: domain,
    })),
  ];
  const pointOptions =
    board && board.points.length > 0
      ? board.points.map((point) => ({
          value: point.axisKey,
          label: `${point.axisLabel} (${point.runCount})`,
        }))
      : [{ value: '', label: t('run.regression.noBoardPoints') }];

  return (
    <Card className="space-y-ds-3 bg-ds-bg/70 p-ds-3" aria-labelledby={titleId}>
      <header className="flex flex-wrap items-start gap-ds-2">
        <div className="space-y-ds-1">
          <div
            id={titleId}
            className="flex items-center gap-ds-2 text-ds-xs font-semibold uppercase tracking-[0.16em] text-ds-muted"
          >
            <Activity size={14} aria-hidden="true" />
            <span>{t('run.regression.title')}</span>
          </div>
          <p className="text-ds-xs text-ds-muted">
            {t('run.regression.description')}
          </p>
        </div>
        <Badge compact className="ml-auto">
          {t('run.regression.recordCount', { count: model?.totalRecords ?? 0 })}
        </Badge>
      </header>

      <section className="grid gap-ds-3">
        <Select
          id="regression-board-mode"
          label="Mode"
          value={selectedMode ?? ''}
          onChange={(event) => setSelectedMode(event.target.value || null)}
          options={modeOptions}
          disabled={loading}
        />
        <Select
          id="regression-board-domain"
          label="Domain"
          value={selectedDomain ?? ''}
          onChange={(event) => setSelectedDomain(event.target.value || null)}
          options={domainOptions}
          disabled={loading}
        />
        <div className="flex justify-end">
          <Button
            onClick={() => void refresh()}
            variant="secondary"
            size="sm"
            disabled={loading}
            leadingIcon={
              <RefreshCcw
                size={14}
                className={loading ? 'animate-spin' : undefined}
                aria-hidden="true"
              />
            }
            title={t('run.regression.refreshTitle')}
          >
            {t('run.regression.sync')}
          </Button>
        </div>
      </section>

      {loading && !board ? (
        <ResultCardSectionPanel
          role="status"
          aria-live="polite"
          className={boardNoticeToneClass()}
        >
          {t('run.regression.loading')}
        </ResultCardSectionPanel>
      ) : error ? (
        <ResultCardSectionPanel role="alert" className={boardNoticeToneClass('danger')}>
          {error}
        </ResultCardSectionPanel>
      ) : !board || !model ? (
        <ResultCardSectionPanel
          role="status"
          aria-live="polite"
          className={boardNoticeToneClass()}
        >
          {t('run.regression.unavailable')}
        </ResultCardSectionPanel>
      ) : board.totalRecords === 0 ? (
        <ResultCardSectionPanel
          role="status"
          aria-live="polite"
          className={boardNoticeToneClass()}
        >
          {t('run.regression.noRecords')}
        </ResultCardSectionPanel>
      ) : (
        <>
          <section className="grid grid-cols-2 gap-ds-2" aria-label={t('run.regression.overallMetricsAria')}>
            <MetricCard
              label={t('run.regression.metric.recentScore')}
              value={formatPercent(board.overall.recent.avgWeightedScore)}
            />
            <MetricCard
              label={t('run.regression.metric.baselineScore')}
              value={formatPercent(board.overall.baseline.avgWeightedScore)}
            />
            <MetricCard
              label={t('run.regression.metric.scoreDelta')}
              value={formatPercentPoints(model.deltaScorePercentPoints)}
              tone={deltaTone(model.deltaScorePercentPoints)}
            />
            <MetricCard
              label={t('run.regression.metric.passDelta')}
              value={formatPercentPoints(model.deltaPassRatePercentPoints)}
              tone={deltaTone(model.deltaPassRatePercentPoints)}
            />
          </section>

          <ResultCardSectionPanel className="space-y-ds-2 bg-ds-surface/60">
            <div className="flex flex-wrap items-center gap-ds-2">
              <ResultCardSectionTitle>{t('run.regression.baseline')}</ResultCardSectionTitle>
              <Badge
                compact
                tone={model.baselineSource === 'frozen' ? 'accent' : 'neutral'}
                leadingIcon={<Snowflake size={12} aria-hidden="true" />}
                className="ml-auto"
              >
                {model.baselineSource === 'frozen' ? t('run.regression.frozen') : t('run.regression.rolling')}
              </Badge>
            </div>
            <p className="text-ds-xs text-ds-muted">
              Axis {model.axisKind} / {t('run.regression.pointCount', { count: model.pointCount })}
            </p>
            {board.frozenBaseline ? (
              <div className="space-y-ds-1 text-ds-xs">
                <p className="text-ds-text">
                  commit {board.frozenBaseline.commitSha}
                  <span className="text-ds-muted">
                    {' '}
                    / {board.frozenBaseline.sourcePointCount} records
                  </span>
                </p>
                <p className="text-ds-muted">
                  score {formatDecimal(board.frozenBaseline.weightedScoreMean)} / pass{' '}
                  {formatPercent(board.frozenBaseline.passRate)} / frozen{' '}
                  {formatTimestamp(board.frozenBaseline.createdAt)}
                </p>
                {model.selectedPointIsFrozenBaseline ? (
                  <p className="text-ds-xs text-ds-success">
                    {t('run.regression.alreadyFrozen')}
                  </p>
                ) : null}
              </div>
            ) : (
              <p className="text-ds-xs text-ds-muted">
                {t('run.regression.rollingBaselineInfo', { count: board.baselineWindowDays })}
              </p>
            )}
          </ResultCardSectionPanel>

          <ResultCardSectionPanel className="space-y-ds-3 bg-ds-surface/60">
            <div className="flex flex-wrap items-center gap-ds-2">
              <ResultCardSectionTitle>{t('run.regression.pointDiff')}</ResultCardSectionTitle>
              <Badge compact tone="neutral" className="ml-auto">
                {t('run.regression.pointCount', { count: board.points.length })}
              </Badge>
            </div>

            <section className="grid gap-ds-3">
              <Select
                id="regression-board-point"
                label="Point"
                value={selectedPointKey ?? ''}
                onChange={(event) => setSelectedPointKey(event.target.value || null)}
                options={pointOptions}
                disabled={loading || board.points.length === 0}
              />
              <div className="flex justify-end">
                <Button
                  onClick={() =>
                    model.selectedPoint && void freezeBaseline(model.selectedPoint.axisKey)
                  }
                  disabled={freezeDisabled}
                  variant="secondary"
                  size="sm"
                  loading={freezeLoading}
                  leadingIcon={<Snowflake size={14} aria-hidden="true" />}
                  title={freezeButtonTitle}
                  aria-label={freezeButtonTitle}
                >
                  {freezeLoading ? t('run.regression.freezing') : t('run.regression.freeze')}
                </Button>
              </div>
            </section>

            {freezeError ? (
              <p role="alert" className="text-ds-xs text-ds-error">
                {freezeError}
              </p>
            ) : null}

            {!freezeError && model.axisKind !== 'commit' ? (
              <p className="text-ds-xs text-ds-muted">
                {t('run.regression.freezeCommitOnly')}
              </p>
            ) : null}

            {!freezeError && model.selectedPointIsFrozenBaseline ? (
              <p className="text-ds-xs text-ds-success">
                {t('run.regression.commitAlreadyBaseline')}
              </p>
            ) : null}

            {model.selectedPoint ? (
              <div className="space-y-ds-3">
                <ResultCardSectionPanel className="space-y-ds-2 bg-ds-bg/60">
                  <p className="text-ds-xs text-ds-text">
                    {model.selectedPoint.axisLabel}
                    <span className="text-ds-muted">
                      {' '}
                      / score {formatDecimal(model.selectedPoint.weightedScoreMean)} / pass{' '}
                      {formatPercent(model.selectedPoint.passRate)}
                    </span>
                  </p>
                </ResultCardSectionPanel>

                {model.previousPoint ? (
                  <>
                    <ResultCardSectionPanel className="space-y-ds-2 bg-ds-bg/60">
                      <p className="text-ds-xs text-ds-muted">
                        {t('run.regression.comparingAgainst', {
                          label: model.previousPoint.axisLabel,
                          count: model.previousPoint.runCount,
                        })}
                      </p>
                      <section
                        className="grid grid-cols-2 gap-ds-2"
                        aria-label={t('run.regression.pointComparisonAria')}
                      >
                        <MetricCard
                          label={t('run.regression.metric.vsPreviousScore')}
                          value={formatPercentPoints(model.pointScoreDeltaPercentPoints)}
                          tone={deltaTone(model.pointScoreDeltaPercentPoints)}
                        />
                        <MetricCard
                          label={t('run.regression.metric.vsPreviousPass')}
                          value={formatPercentPoints(model.pointPassRateDeltaPercentPoints)}
                          tone={deltaTone(model.pointPassRateDeltaPercentPoints)}
                        />
                      </section>
                    </ResultCardSectionPanel>

                    {model.pointModeDiffs.length > 0 ? (
                      <DeltaListSection
                        title={t('run.regression.modeDeltas')}
                        items={model.pointModeDiffs.map((item) => ({
                          key: item.mode,
                          label: item.mode,
                          range: `${formatPercent(item.previousScore)} -> ${formatPercent(item.currentScore)}`,
                          delta: formatDeltaFromScore(item.deltaScore),
                          tone: deltaTone(item.deltaScore),
                        }))}
                      />
                    ) : null}

                    {model.pointDiffs.length > 0 ? (
                      <DeltaListSection
                        title={t('run.regression.dimensionDeltas')}
                        items={model.pointDiffs.map((item) => ({
                          key: item.name,
                          label: item.label,
                          range: `${formatPercent(item.previousScore)} -> ${formatPercent(item.currentScore)}`,
                          delta: formatDeltaFromScore(item.deltaScore),
                          tone: deltaTone(item.deltaScore),
                        }))}
                      />
                    ) : (
                      <p className="text-ds-xs text-ds-muted">
                        No per-dimension diff available for this point pair.
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-ds-xs text-ds-muted">
                    {t('run.regression.selectLaterPoint')}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-ds-xs text-ds-muted">{t('run.regression.noBoardPointsAvailable')}</p>
            )}
          </ResultCardSectionPanel>

          <ResultCardSectionPanel className="space-y-ds-2 bg-ds-surface/60">
            <div className="flex flex-wrap items-center gap-ds-2">
              <ResultCardSectionTitle>{t('run.regression.alerts')}</ResultCardSectionTitle>
              <Badge compact className="ml-auto">
                {model.alertCount}
              </Badge>
            </div>
            {model.topAlerts.length > 0 ? (
              <ul className="space-y-ds-2" aria-label={t('run.regression.alertsAria')}>
                {model.topAlerts.map((alert) => (
                  <li
                    key={`${alert.kind}-${alert.scopeKey ?? 'global'}`}
                    className="rounded-ds-lg border border-ds-border/70 bg-ds-bg/60 px-ds-3 py-ds-2"
                  >
                    <div className="flex flex-wrap items-center gap-ds-2">
                      <Badge compact tone={alertTone(alert.severity)} className="uppercase">
                        {alert.severity}
                      </Badge>
                      <p
                        className={
                          alert.severity === 'high' ? 'text-ds-error' : 'text-ds-warning'
                        }
                      >
                        {alert.message}
                      </p>
                    </div>
                    <p className="mt-ds-1 text-ds-xs text-ds-muted">
                      {alert.scope}
                      {alert.scopeKey ? ` / ${alert.scopeKey}` : ''}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-ds-xs text-ds-success">{t('run.regression.noAlerts')}</p>
            )}
          </ResultCardSectionPanel>

          <ResultCardSectionPanel className="space-y-ds-2 bg-ds-surface/60">
            <ResultCardSectionTitle>{t('run.regression.tasks')}</ResultCardSectionTitle>
            {model.topTaskRegressions.length > 0 ? (
              <ul className="space-y-ds-2" aria-label={t('run.regression.regressedTasksAria')}>
                {model.topTaskRegressions.map((task) => (
                  <li
                    key={task.taskId}
                    className="rounded-ds-lg border border-ds-border/70 bg-ds-bg/60 px-ds-3 py-ds-2"
                  >
                    <p className="text-ds-xs text-ds-text">
                      {task.taskId} <span className="text-ds-muted">({task.status})</span>
                    </p>
                    <p className="mt-ds-1 text-ds-xs text-ds-muted">
                      latest {formatPercent(task.latestWeightedScore)} / delta{' '}
                      {formatPercentPoints(
                        task.deltaScore === null ? null : Math.round(task.deltaScore * 1000) / 10
                      )}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-ds-xs text-ds-muted">{t('run.regression.noRegressedTasks')}</p>
            )}
          </ResultCardSectionPanel>

          <ResultCardSectionPanel className="space-y-ds-2 bg-ds-surface/60">
            <ResultCardSectionTitle>{t('run.regression.dimensions')}</ResultCardSectionTitle>
            {model.topDimensionRegressions.length > 0 ? (
              <ul className="space-y-ds-2" aria-label={t('run.regression.dimensionRegressionsAria')}>
                {model.topDimensionRegressions.map((dimension) => (
                  <li
                    key={dimension.name}
                    className="flex items-center justify-between gap-ds-3 rounded-ds-lg border border-ds-border/70 bg-ds-bg/60 px-ds-3 py-ds-2 text-ds-xs"
                  >
                    <span className="text-ds-text">{dimension.label}</span>
                    <span className="font-medium text-ds-warning">
                      {formatPercentPoints(
                        dimension.deltaScore === null
                          ? null
                          : Math.round(dimension.deltaScore * 1000) / 10
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-ds-xs text-ds-muted">
                {t('run.regression.noDimensionDrift')}
              </p>
            )}
          </ResultCardSectionPanel>

          <footer className="text-ds-xs text-ds-muted">
            {t('run.regression.footer', {
              timestamp: formatTimestamp(board.generatedAt),
              recentWindow: board.recentWindow,
              days: board.baselineWindowDays,
              source: board.baselineSource === 'frozen' ? 'frozen-aware' : 'rolling',
            })}
          </footer>
        </>
      )}
    </Card>
  );
}

function MetricCard({
  label,
  value,
  tone = 'normal',
}: {
  label: string;
  value: string;
  tone?: 'normal' | 'success' | 'warn';
}) {
  const toneClass =
    tone === 'success' ? 'text-ds-success' : tone === 'warn' ? 'text-ds-warning' : 'text-ds-text';

  return (
    <ResultCardSectionPanel className="space-y-ds-1 bg-ds-surface/60 px-ds-3 py-ds-2">
      <ResultCardSectionTitle>{label}</ResultCardSectionTitle>
      <div className={`font-mono text-ds-lg ${toneClass}`}>{value}</div>
    </ResultCardSectionPanel>
  );
}

function DeltaListSection({
  title,
  items,
}: {
  title: string;
  items: Array<{
    key: string;
    label: string;
    range: string;
    delta: string;
    tone: 'success' | 'warn';
  }>;
}) {
  return (
    <ResultCardSectionPanel className="space-y-ds-2 bg-ds-bg/60">
      <ResultCardSectionTitle>{title}</ResultCardSectionTitle>
      <ul className="space-y-ds-2">
        {items.map((item) => (
          <li
            key={item.key}
            className="flex items-center justify-between gap-ds-3 text-ds-xs"
          >
            <span className="text-ds-text">{item.label}</span>
            <span className="text-ds-muted">{item.range}</span>
            <span className={item.tone === 'warn' ? 'text-ds-warning' : 'text-ds-success'}>
              {item.delta}
            </span>
          </li>
        ))}
      </ul>
    </ResultCardSectionPanel>
  );
}
