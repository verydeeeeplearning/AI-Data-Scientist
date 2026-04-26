/**
 * Drawer for inspecting one runtime run and its linked task/session context.
 */

import { CircleStop, ExternalLink, ListTree, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { branchRun } from '../../application/run/branchRun';
import { resumeFromCheckpoint } from '../../application/run/resumeFromCheckpoint';
import {
  DrawerSurface,
  DrawerSurfaceBody,
  DrawerSurfaceEyebrow,
  DrawerSurfaceHeader,
  DrawerSurfaceSection,
  DrawerSurfaceSectionTitle,
  DrawerSurfaceStat,
  DrawerSurfaceStatGrid,
} from '../../design-system/composites/DrawerSurface';
import { Badge, Button, Input, Textarea } from '../../design-system/primitives';
import { useBranchRun } from '../../hooks/useBranchRun';
import { useListLineage } from '../../hooks/useListLineage';
import { useModels } from '../../hooks/useModels';
import { useResumeFromCheckpoint } from '../../hooks/useResumeFromCheckpoint';
import { useSessionHistory } from '../../hooks/useSessionHistory';
import { useWs } from '../../hooks/WsProvider';
import {
  buildCheckpointResumePrompt,
  copyCheckpointResumePrompt,
} from '../../infrastructure/api/checkpointResume';
import { useI18n } from '../../stores/i18nStore';
import {
  useRuntimeStore,
  type RuntimeRunEntry,
  type RuntimeTaskEntry,
} from '../../stores/runtimeStore';
import { AccessBanner } from '../sharing/AccessBanner';
import { ShareButton } from '../sharing/ShareButton';
import { BranchRunDialog } from './BranchRunDialog';
import { LineagePanel } from './LineagePanel';
import { ResumePromptFallbackDialog } from './ResumePromptFallbackDialog';

const STATUS_TONES: Record<RuntimeRunEntry['status'], 'accent' | 'success' | 'danger' | 'neutral'> = {
  running: 'accent',
  succeeded: 'success',
  failed: 'danger',
  cancelled: 'neutral',
};

interface RunScoreDimension {
  name: string;
  label: string;
  value: number;
  weight: number;
  weightedContribution: number;
  judgeType: string;
  rubricJudge?: string | null;
  rationale: string;
  subScores: Record<string, number>;
  evidenceRefs: string[];
}

interface RunHumanRubric {
  reviewerId: string;
  comment?: string | null;
  recordedAt?: number | null;
  dimensions: Record<string, number>;
}

interface RunReviewSamplingSummary {
  sampled: boolean;
  status: 'requested' | 'completed' | 'optional';
  targetRate: number;
  bucket: number;
  stratum: string;
  policyVersion: string;
  recordedAt: number;
  hasHumanRubric: boolean;
}

interface RunShadowDimensionDelta {
  name: string;
  label: string;
  delta: number;
  baselineValue: number;
  shadowValue: number;
}

interface RunShadowComparisonSummary {
  comparisonId: string;
  createdAt: number;
  shadowRunId: string;
  shadowModel?: string | null;
  shadowBudgetFactor: number;
  baselineWeightedScore: number;
  shadowWeightedScore: number;
  weightedScoreDelta: number;
  baselinePassed: boolean;
  shadowPassed: boolean;
  topImprovements: RunShadowDimensionDelta[];
  topRegressions: RunShadowDimensionDelta[];
}

interface RunScorecard {
  runId: string;
  sessionId?: string | null;
  taskId: string;
  mode: string;
  domain: string;
  difficulty: string;
  tags: string[];
  weightedScore: number;
  passed: boolean;
  passThreshold: number;
  alertOnDropBelow: number;
  costUsd: number;
  decisionLatencySeconds?: number | null;
  metricChoices: string[];
  artifactTypes: string[];
  toolCallCount: number;
  approvalCount: number;
  artifactCount: number;
  timingSource?: string | null;
  surface?: string | null;
  runtimeStatus?: string | null;
  recoveryContext: Record<string, string | number>;
  humanRubric?: RunHumanRubric | null;
  reviewSampling?: RunReviewSamplingSummary | null;
  shadowComparison?: RunShadowComparisonSummary | null;
  dimensions: RunScoreDimension[];
}

interface RunScorecardRpcResponse {
  scorecard?: RunScorecard;
}

function formatDateTime(timestamp?: number | null): string {
  if (!timestamp) return '-';
  return new Date(timestamp * 1000).toLocaleString();
}

function formatDuration(run: RuntimeRunEntry): string {
  const finished = run.finishedAt ?? undefined;
  if (!finished) return 'running';
  const seconds = Math.max(0, Math.round(finished - run.startedAt));
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${Math.round(seconds / 3600)}h`;
}

function linkedTask(tasks: RuntimeTaskEntry[], run: RuntimeRunEntry): RuntimeTaskEntry | undefined {
  if (run.taskId) {
    const byTaskId = tasks.find((task) => task.taskId === run.taskId);
    if (byTaskId) return byTaskId;
  }
  return tasks.find((task) => task.runId === run.runId);
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatLatency(seconds?: number | null): string {
  if (seconds === undefined || seconds === null) return '-';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${Math.round(seconds / 3600)}h`;
}

function formatScoreInput(value: number): string {
  return value.toFixed(2);
}

function buildRubricDraft(scorecard: RunScorecard) {
  const dimensions: Record<string, string> = {};
  for (const dimension of scorecard.dimensions) {
    const sourceValue =
      scorecard.humanRubric?.dimensions[dimension.name] ??
      dimension.subScores.auto_score ??
      dimension.value;
    dimensions[dimension.name] = formatScoreInput(sourceValue);
  }
  return {
    reviewerId: scorecard.humanRubric?.reviewerId ?? 'local-operator',
    comment: scorecard.humanRubric?.comment ?? '',
    dimensions,
  };
}

export function RunDetailDrawer() {
  const { rpc, status: wsStatus } = useWs();
  const { openSession, openingSessionId } = useSessionHistory();
  const { t } = useI18n();
  const { grouped: modelGroups } = useModels(rpc, wsStatus === 'connected');
  const resumePort = useResumeFromCheckpoint();
  const branchPort = useBranchRun();
  const selectedRunId = useRuntimeStore((s) => s.selectedRunId);
  const runs = useRuntimeStore((s) => s.runs);
  const tasks = useRuntimeStore((s) => s.tasks);
  const clearSelectedRun = useRuntimeStore((s) => s.clearSelectedRun);
  const [busyAbort, setBusyAbort] = useState(false);
  const [abortError, setAbortError] = useState<string | null>(null);
  const [scorecard, setScorecard] = useState<RunScorecard | null>(null);
  const [scorecardBusy, setScorecardBusy] = useState(false);
  const [scorecardError, setScorecardError] = useState<string | null>(null);
  const [rubricReviewerId, setRubricReviewerId] = useState('local-operator');
  const [rubricComment, setRubricComment] = useState('');
  const [rubricDimensions, setRubricDimensions] = useState<Record<string, string>>({});
  const [rubricBusy, setRubricBusy] = useState(false);
  const [rubricError, setRubricError] = useState<string | null>(null);
  const [rubricStatus, setRubricStatus] = useState<string | null>(null);
  const [shadowBusy, setShadowBusy] = useState(false);
  const [shadowError, setShadowError] = useState<string | null>(null);
  const [shadowStatus, setShadowStatus] = useState<string | null>(null);
  const [resumeBusy, setResumeBusy] = useState(false);
  const [resumeError, setResumeError] = useState<string | null>(null);
  const [resumeStatus, setResumeStatus] = useState<string | null>(null);
  const [branchBusy, setBranchBusy] = useState(false);
  const [branchError, setBranchError] = useState<string | null>(null);
  const [branchStatus, setBranchStatus] = useState<string | null>(null);
  const [branchDialogOpen, setBranchDialogOpen] = useState(false);
  const [resumeFallback, setResumeFallback] = useState<{
    prompt: string;
    errorDetail: string | null;
    clipboardCopied: boolean;
  } | null>(null);

  const run = useMemo(
    () => runs.find((item) => item.runId === selectedRunId) ?? null,
    [runs, selectedRunId],
  );
  const task = useMemo(() => (run ? linkedTask(tasks, run) : undefined), [run, tasks]);
  const modelOptions = useMemo(() => {
    const flattened = modelGroups.flatMap((group) => group.models);
    const seen = new Set<string>();
    return flattened
      .filter((entry) => {
        if (seen.has(entry.id)) {
          return false;
        }
        seen.add(entry.id);
        return true;
      })
      .map((entry) => ({
        value: entry.id,
        label: entry.displayName || entry.id,
      }));
  }, [modelGroups]);
  const {
    nodes: lineageNodes,
    loading: lineageLoading,
    error: lineageError,
  } = useListLineage(run?.runId);

  useEffect(() => {
    if (!run) {
      setScorecard(null);
      setScorecardBusy(false);
      setScorecardError(null);
      setShadowBusy(false);
      setShadowError(null);
      setShadowStatus(null);
      setResumeBusy(false);
      setResumeError(null);
      setResumeStatus(null);
      return;
    }

    let cancelled = false;
    const loadScorecard = async () => {
      setScorecardBusy(true);
      setScorecardError(null);
      try {
        const response = (await rpc('run.scorecard', {
          runId: run.runId,
        })) as RunScorecardRpcResponse;
        if (!cancelled) {
          setScorecard(response.scorecard ?? null);
        }
      } catch (err) {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : t('run.runtime.runDetail.error.scorecardUnavailable');
          setScorecard(null);
          setScorecardError(message);
        }
      } finally {
        if (!cancelled) {
          setScorecardBusy(false);
        }
      }
    };

    void loadScorecard();
    return () => {
      cancelled = true;
    };
  }, [rpc, run?.finishedAt, run?.runId, run?.status, run?.taskId]);

  useEffect(() => {
    if (!scorecard) {
      setRubricReviewerId('local-operator');
      setRubricComment('');
      setRubricDimensions({});
      setRubricBusy(false);
      setRubricError(null);
      setRubricStatus(null);
      setShadowBusy(false);
      setShadowError(null);
      setShadowStatus(null);
      return;
    }

    const draft = buildRubricDraft(scorecard);
    setRubricReviewerId(draft.reviewerId);
    setRubricComment(draft.comment);
    setRubricDimensions(draft.dimensions);
    setRubricBusy(false);
    setRubricError(null);
  }, [scorecard]);

  useEffect(() => {
    setResumeBusy(false);
    setResumeError(null);
    setResumeStatus(null);
    setBranchBusy(false);
    setBranchError(null);
    setBranchStatus(null);
    setBranchDialogOpen(false);
  }, [run?.runId]);

  useEffect(() => {
    if (!resumeStatus && !resumeError) {
      return;
    }
    const timer = window.setTimeout(() => {
      setResumeError(null);
      setResumeStatus(null);
    }, 8_000);
    return () => window.clearTimeout(timer);
  }, [resumeError, resumeStatus]);

  useEffect(() => {
    if (!branchStatus && !branchError) {
      return;
    }
    const timer = window.setTimeout(() => {
      setBranchError(null);
      setBranchStatus(null);
    }, 8_000);
    return () => window.clearTimeout(timer);
  }, [branchError, branchStatus]);

  if (!run) return null;

  const abortRun = async () => {
    setBusyAbort(true);
    setAbortError(null);
    try {
      await rpc('run.abort', { runId: run.runId });
    } catch (err) {
      console.warn('[RunDetailDrawer] run.abort failed:', err);
      const detail = err instanceof Error ? err.message : String(err);
      setAbortError(t('run.runtime.runs.error.abortFailed', { message: detail }));
    } finally {
      setBusyAbort(false);
    }
  };

  const resetRubricDraft = () => {
    if (!scorecard) return;
    const draft = buildRubricDraft(scorecard);
    setRubricReviewerId(draft.reviewerId);
    setRubricComment(draft.comment);
    setRubricDimensions(draft.dimensions);
    setRubricError(null);
    setRubricStatus(null);
  };

  const submitHumanRubric = async () => {
    if (!scorecard) return;
    const reviewerId = rubricReviewerId.trim();
    if (!reviewerId) {
      setRubricError(t('run.runtime.runDetail.review.reviewerRequired'));
      return;
    }

    const parsedDimensions: Record<string, number> = {};
    for (const dimension of scorecard.dimensions) {
      const rawValue = rubricDimensions[dimension.name] ?? '';
      const parsedValue = Number(rawValue);
      if (!Number.isFinite(parsedValue) || parsedValue < 0 || parsedValue > 1) {
        setRubricError(
          t('run.runtime.runDetail.review.invalidScore', { label: dimension.label }),
        );
        return;
      }
      parsedDimensions[dimension.name] = parsedValue;
    }

    setRubricBusy(true);
    setRubricError(null);
    setRubricStatus(null);
    try {
      const response = (await rpc('run.submitHumanRubric', {
        runId: run.runId,
        reviewerId,
        comment: rubricComment.trim() || undefined,
        dimensions: parsedDimensions,
      })) as RunScorecardRpcResponse;
      setScorecard(response.scorecard ?? null);
      setRubricStatus(t('run.runtime.runDetail.review.saved'));
    } catch (error) {
      const message =
        error instanceof Error ? error.message : t('run.runtime.runDetail.review.saveFailed');
      setRubricError(message);
    } finally {
      setRubricBusy(false);
    }
  };

  const runShadowCompare = async () => {
    setShadowBusy(true);
    setShadowError(null);
    setShadowStatus(null);
    try {
      const response = (await rpc('run.shadowCompare', {
        runId: run.runId,
      })) as RunScorecardRpcResponse;
      setScorecard(response.scorecard ?? null);
      setShadowStatus(t('run.runtime.runDetail.shadow.refreshed'));
    } catch (error) {
      const message =
        error instanceof Error ? error.message : t('run.runtime.runDetail.shadow.failed');
      setShadowError(message);
    } finally {
      setShadowBusy(false);
    }
  };

  const submitBranchRun = async (draft: { message: string; model: string | null }) => {
    if (!run) {
      return;
    }

    setBranchBusy(true);
    setBranchError(null);
    setBranchStatus(null);
    try {
      const result = await branchRun(branchPort, {
        parentRunId: run.runId,
        message: draft.message.trim(),
        model: draft.model,
      });
      setBranchStatus(
        t('run:branchDialog.status.started', {
          runId: result.runId,
          parentRunId: run.runId,
        }),
      );
      setBranchDialogOpen(false);
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      setBranchError(t('run:branchDialog.status.failed', { reason: detail }));
    } finally {
      setBranchBusy(false);
    }
  };

  const prepareCheckpointResume = async () => {
    setResumeBusy(true);
    setResumeError(null);
    setResumeStatus(null);
    try {
      const opened = await openSession(run.sessionId);
      if (!opened) {
        setResumeError(t('run.runtime.runDetail.resume.openSessionFailed'));
        return;
      }

      const prompt = buildCheckpointResumePrompt({
        sessionId: run.sessionId,
        sessionLabel: run.sessionLabel,
        runId: run.runId,
        taskId: run.taskId ?? task?.taskId ?? null,
      });

      try {
        const result = await resumeFromCheckpoint(resumePort, {
          sessionId: run.sessionId,
          message: prompt,
        });
        setResumeStatus(
          result.resumed
            ? t('run.runtime.runDetail.resume.fromCheckpoint')
            : t('run.runtime.runDetail.resume.fromFreshTurn'),
        );
      } catch (err) {
        const detail = err instanceof Error ? err.message : String(err);
        const copied = await copyCheckpointResumePrompt(prompt);
        setResumeFallback({ prompt, errorDetail: detail, clipboardCopied: copied });
        setResumeError(
          copied
            ? t('run.runtime.runDetail.resume.failedCopied', { reason: detail })
            : t('run.runtime.runDetail.resume.failedManual', { reason: detail }),
        );
      }
    } finally {
      setResumeBusy(false);
    }
  };

  const sessionLabel = run.sessionLabel || run.sessionId;

  return (
    <>
      <DrawerSurface className="w-[24rem] min-w-0">
        <DrawerSurfaceHeader className="items-center">
          <div className="min-w-0 flex-1 space-y-ds-1">
            <DrawerSurfaceEyebrow className="flex items-center gap-ds-2">
              <ListTree size={12} aria-hidden="true" />
              {t('run.runtime.runDetail.eyebrow')}
            </DrawerSurfaceEyebrow>
            <p className="text-ds-sm text-ds-muted">
              {t('run.runtime.runDetail.description')}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-ds-1">
            <ShareButton resourceType="run" resourceId={run.runId} />
            <Button
              variant="ghost"
              size="sm"
              onClick={clearSelectedRun}
              title={t('run.runtime.runDetail.closeTitle')}
              aria-label={t('run.runtime.runDetail.closeAria')}
            >
              <X size={16} aria-hidden="true" />
            </Button>
          </div>
        </DrawerSurfaceHeader>

        <DrawerSurfaceBody>
          <AccessBanner className="mx-ds-4 mt-ds-2" />
          <DrawerSurfaceSection className="space-y-ds-3">
            <div className="flex items-start gap-ds-2">
              <div className="min-w-0 flex-1 break-all font-mono text-ds-sm text-ds-text">
                {run.runId}
              </div>
              <Badge tone={STATUS_TONES[run.status]} compact className="uppercase">
                {run.status}
              </Badge>
            </div>
            <div className="space-y-0.5 text-ds-xs text-ds-muted">
              <div>
                {run.surface} / {sessionLabel}
              </div>
              {run.threadLabel && <div className="uppercase">{run.threadLabel}</div>}
            </div>
            <div className="flex flex-wrap items-center gap-ds-2">
              <Button
                variant="primary"
                size="sm"
                onClick={() => void prepareCheckpointResume()}
                disabled={resumeBusy || openingSessionId === run.sessionId}
                title={t('run.runtime.runDetail.action.resumeTitle')}
              >
                {resumeBusy || openingSessionId === run.sessionId
                  ? t('run.runtime.runDetail.action.resumePreparing')
                  : t('run.runtime.runDetail.action.resume')}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                leadingIcon={<ExternalLink size={12} aria-hidden="true" />}
                onClick={() => void openSession(run.sessionId)}
                disabled={openingSessionId === run.sessionId}
              >
                {openingSessionId === run.sessionId
                  ? t('run.runtime.runDetail.action.openSessionOpening')
                  : t('run.runtime.runDetail.action.openSession')}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setBranchError(null);
                  setBranchDialogOpen(true);
                }}
                disabled={branchBusy}
                title={t('run.runtime.runDetail.action.branchTitle')}
              >
                {branchBusy ? t('run:branchDialog.confirmBusy') : t('run:branchDialog.confirm')}
              </Button>
              {run.status === 'running' && (
                <Button
                  variant="danger"
                  size="sm"
                  leadingIcon={<CircleStop size={12} aria-hidden="true" />}
                  onClick={() => void abortRun()}
                  disabled={busyAbort}
                >
                  {t('run.runtime.runDetail.action.abort')}
                </Button>
              )}
            </div>
            <div className="text-[10px] text-ds-muted">
              {t('run.runtime.runDetail.helper.checkpointResume')}
            </div>
            {abortError && (
              <p
                role="alert"
                className="text-ds-xs text-ds-error"
                data-testid="run-detail-abort-error"
              >
                {abortError}
              </p>
            )}
            {resumeError && (
              <div className="text-[11px] text-ds-error" role="status" aria-live="polite">
                {resumeError}
              </div>
            )}
            {resumeStatus && (
              <div className="text-[11px] text-ds-success" role="status" aria-live="polite">
                {resumeStatus}
              </div>
            )}
            {branchError && (
              <div className="text-[11px] text-ds-error" role="status" aria-live="polite">
                {branchError}
              </div>
            )}
            {branchStatus && (
              <div className="text-[11px] text-ds-success" role="status" aria-live="polite">
                {branchStatus}
              </div>
            )}
          </DrawerSurfaceSection>

          <LineagePanel
            loading={lineageLoading}
            error={lineageError}
            nodes={lineageNodes}
            activeRunId={run.runId}
          />

          <DrawerSurfaceSection className="space-y-ds-2">
            <DrawerSurfaceSectionTitle>{t('run.runtime.runDetail.section.lifecycle')}</DrawerSurfaceSectionTitle>
            <DetailRow label={t('run.runtime.runDetail.label.created')} value={formatDateTime(run.createdAt)} />
            <DetailRow label={t('run.runtime.runDetail.label.started')} value={formatDateTime(run.startedAt)} />
            <DetailRow label={t('run.runtime.runDetail.label.finished')} value={formatDateTime(run.finishedAt)} />
            <DetailRow label={t('run.runtime.runDetail.label.duration')} value={formatDuration(run)} />
            <DetailRow label={t('run.runtime.runDetail.label.cost')} value={`$${run.costUsd.toFixed(4)}`} />
            <DetailRow label={t('run.runtime.runDetail.label.conversation')} value={run.conversationId ?? '-'} />
            <DetailRow label={t('run.runtime.runDetail.label.thread')} value={run.threadLabel ?? '-'} />
            <DetailRow label={t('run.runtime.runDetail.label.task')} value={run.taskId ?? task?.taskId ?? '-'} mono />
          </DrawerSurfaceSection>

          <DrawerSurfaceSection className="space-y-ds-3">
            <DrawerSurfaceSectionTitle>{t('run.runtime.runDetail.section.scorecard')}</DrawerSurfaceSectionTitle>
          {scorecardBusy ? (
            <div className="text-xs text-ds-muted">{t('run.runtime.runDetail.loading.scorecard')}</div>
          ) : scorecardError ? (
            <div className="text-xs text-ds-error">{scorecardError}</div>
          ) : scorecard ? (
            <>
              <div className="flex items-end gap-3">
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-ds-muted">{t('run.runtime.runDetail.label.overall')}</div>
                  <div className="text-2xl font-semibold text-ds-text">
                    {formatPercent(scorecard.weightedScore)}
                  </div>
                </div>
                <Badge
                  tone={scorecard.passed ? 'success' : 'danger'}
                  compact
                  className="uppercase"
                >
                  {scorecard.passed ? t('run.runtime.runDetail.label.pass') : t('run.runtime.runDetail.label.fail')}
                </Badge>
              </div>

              <DrawerSurfaceStatGrid>
                <SummaryChip label={t('run.runtime.runDetail.label.threshold')} value={formatPercent(scorecard.passThreshold)} />
                <SummaryChip label={t('run.runtime.runDetail.label.decision')} value={formatLatency(scorecard.decisionLatencySeconds)} />
                <SummaryChip label={t('run.runtime.runDetail.label.tools')} value={String(scorecard.toolCallCount)} />
                <SummaryChip label={t('run.runtime.runDetail.label.approvals')} value={String(scorecard.approvalCount)} />
              </DrawerSurfaceStatGrid>

              <DrawerSurfaceSection className="space-y-ds-3 bg-ds-surface/60">
                <div className="flex items-center gap-2">
                  <DrawerSurfaceSectionTitle>{t('run.runtime.runDetail.section.shadowCompare')}</DrawerSurfaceSectionTitle>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => void runShadowCompare()}
                    disabled={shadowBusy}
                    className="ml-auto"
                  >
                    {shadowBusy ? t('run.runtime.runDetail.button.runShadowBusy') : t('run.runtime.runDetail.button.runShadow')}
                  </Button>
                </div>

                {shadowError && <div className="text-xs text-ds-error">{shadowError}</div>}
                {shadowStatus && <div className="text-xs text-ds-success">{shadowStatus}</div>}

                {scorecard.shadowComparison ? (
                  <div className="space-y-3">
                    <DrawerSurfaceStatGrid>
                      <SummaryChip
                        label={t('run.runtime.runDetail.label.baseline')}
                        value={formatPercent(scorecard.shadowComparison.baselineWeightedScore)}
                      />
                      <SummaryChip
                        label={t('run.runtime.runDetail.label.shadow')}
                        value={formatPercent(scorecard.shadowComparison.shadowWeightedScore)}
                      />
                      <SummaryChip
                        label={t('run.runtime.runDetail.label.delta')}
                        value={`${scorecard.shadowComparison.weightedScoreDelta >= 0 ? '+' : ''}${formatPercent(scorecard.shadowComparison.weightedScoreDelta)}`}
                      />
                      <SummaryChip
                        label={t('run.runtime.runDetail.label.budget')}
                        value={`${Math.round(scorecard.shadowComparison.shadowBudgetFactor * 100)}%`}
                      />
                    </DrawerSurfaceStatGrid>
                    <div className="text-xs text-ds-muted">
                      {t('run.runtime.runDetail.label.modelSavedAt', {
                        model:
                          scorecard.shadowComparison.shadowModel ||
                          t('run.runtime.runDetail.label.defaultModel'),
                        date: formatDateTime(scorecard.shadowComparison.createdAt),
                      })}
                    </div>
                    {scorecard.shadowComparison.topImprovements.length > 0 && (
                      <ComparisonList
                        title={t('run.runtime.runDetail.label.topImprovements')}
                        items={scorecard.shadowComparison.topImprovements}
                      />
                    )}
                    {scorecard.shadowComparison.topRegressions.length > 0 && (
                      <ComparisonList
                        title={t('run.runtime.runDetail.label.topRegressions')}
                        items={scorecard.shadowComparison.topRegressions}
                      />
                    )}
                  </div>
                ) : (
                  <div className="text-xs text-ds-muted">
                    {t('run.runtime.runDetail.empty.shadowComparison')}
                  </div>
                )}
              </DrawerSurfaceSection>

              {Object.keys(scorecard.recoveryContext).length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {Object.entries(scorecard.recoveryContext).map(([key, value]) => (
                    <Badge
                      key={key}
                      compact
                      className="normal-case tracking-normal"
                    >
                      {key}: {String(value)}
                    </Badge>
                  ))}
                </div>
              )}

              <div className="space-y-2">
                {scorecard.dimensions.map((dimension) => (
                  <div
                    key={dimension.name}
                    className="rounded border border-ds-border/70 bg-ds-surface/60 p-2"
                  >
                    <div className="flex items-center gap-2">
                      <div className="text-xs font-medium text-ds-text">{dimension.label}</div>
                      <div className="ml-auto text-[10px] uppercase tracking-wider text-ds-muted">
                        {formatPercent(dimension.value)}
                      </div>
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-[10px] text-ds-muted">
                      <span>{t('run.runtime.runDetail.label.weight', { value: formatPercent(dimension.weight) })}</span>
                      <span>{t('run.runtime.runDetail.label.judge', { value: dimension.judgeType })}</span>
                    </div>
                    <div className="mt-2 text-xs text-ds-text">{dimension.rationale}</div>
                    {Object.keys(dimension.subScores).length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {Object.entries(dimension.subScores).map(([name, value]) => (
                          <span
                            key={name}
                            className="rounded border border-ds-border px-2 py-0.5 text-[10px] text-ds-muted"
                          >
                            {name}: {formatPercent(value)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <DrawerSurfaceSection className="space-y-ds-3 bg-ds-surface/60">
                <div className="flex items-center gap-2">
                  <DrawerSurfaceSectionTitle>{t('run.runtime.runDetail.section.reviewerRubric')}</DrawerSurfaceSectionTitle>
                  {scorecard.humanRubric?.recordedAt && (
                    <div className="ml-auto text-[10px] text-ds-muted">
                      {t('run.runtime.runDetail.label.savedAt', {
                        date: formatDateTime(scorecard.humanRubric.recordedAt),
                      })}
                    </div>
                  )}
                </div>

                {scorecard.reviewSampling && (
                  <div
                    className={`rounded border px-2 py-2 text-xs ${
                      scorecard.reviewSampling.sampled && !scorecard.reviewSampling.hasHumanRubric
                        ? 'border-ds-border bg-ds-bg/70 text-ds-warning'
                        : 'border-ds-border text-ds-muted'
                    }`}
                  >
                    <div className="font-medium">
                      {scorecard.reviewSampling.status === 'requested'
                        ? t('run.runtime.runDetail.review.requested')
                        : scorecard.reviewSampling.status === 'completed'
                          ? t('run.runtime.runDetail.review.completed')
                          : t('run.runtime.runDetail.review.optional')}
                    </div>
                    <div className="mt-1 text-[10px]">
                      {t('run.runtime.runDetail.label.targetStratum', {
                        target: formatPercent(scorecard.reviewSampling.targetRate),
                        stratum: scorecard.reviewSampling.stratum,
                      })}
                    </div>
                  </div>
                )}

                <Input
                  value={rubricReviewerId}
                  onChange={(event) => {
                    setRubricReviewerId(event.target.value);
                    setRubricError(null);
                    setRubricStatus(null);
                  }}
                  label={t('run.runtime.runDetail.label.reviewer')}
                  placeholder={t('run.runtime.runDetail.placeholder.reviewer')}
                />

                <div className="space-y-2">
                  {scorecard.dimensions.map((dimension) => {
                    const autoScore = dimension.subScores.auto_score ?? dimension.value;
                    return (
                      <div
                        key={`rubric-${dimension.name}`}
                        className="grid grid-cols-[1fr_auto] items-center gap-2"
                      >
                        <div className="min-w-0">
                          <div className="text-xs text-ds-text">{dimension.label}</div>
                          <div className="text-[10px] text-ds-muted">
                            {t('run.runtime.runDetail.label.auto', {
                              value: formatPercent(autoScore),
                              judge: dimension.judgeType,
                            })}
                          </div>
                        </div>
                        <input
                          type="number"
                          min={0}
                          max={1}
                          step={0.05}
                          value={rubricDimensions[dimension.name] ?? ''}
                          onChange={(event) => {
                            setRubricDimensions((current) => ({
                              ...current,
                              [dimension.name]: event.target.value,
                            }));
                            setRubricError(null);
                            setRubricStatus(null);
                          }}
                          className="w-20 rounded border border-ds-border bg-ds-bg px-2 py-1.5 text-right text-xs text-ds-text focus:border-ds-accent focus:outline-none"
                        />
                      </div>
                    );
                  })}
                </div>

                <Textarea
                  value={rubricComment}
                  onChange={(event) => {
                    setRubricComment(event.target.value);
                    setRubricError(null);
                    setRubricStatus(null);
                  }}
                  rows={3}
                  resize="none"
                  label={t('run.runtime.runDetail.label.comment')}
                  placeholder={t('run.runtime.runDetail.placeholder.comment')}
                />

                {rubricError && <div className="text-xs text-ds-error">{rubricError}</div>}
                {rubricStatus && <div className="text-xs text-ds-success">{rubricStatus}</div>}

                <div className="flex items-center gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => void submitHumanRubric()}
                    disabled={rubricBusy}
                  >
                    {rubricBusy
                      ? t('run.runtime.runDetail.button.saveReviewBusy')
                      : t('run.runtime.runDetail.button.saveReview')}
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={resetRubricDraft}
                    disabled={rubricBusy}
                  >
                    {t('run.runtime.runDetail.button.reset')}
                  </Button>
                </div>
              </DrawerSurfaceSection>
            </>
          ) : (
            <div className="text-xs text-ds-muted">{t('run.runtime.runDetail.empty.scorecard')}</div>
          )}
          </DrawerSurfaceSection>

          <DrawerSurfaceSection className="space-y-ds-2">
            <DrawerSurfaceSectionTitle>{t('run.runtime.runDetail.section.message')}</DrawerSurfaceSectionTitle>
          <pre className="whitespace-pre-wrap break-words text-xs text-ds-text font-sans">
            {run.message || '-'}
          </pre>
          </DrawerSurfaceSection>

          <DrawerSurfaceSection className="space-y-ds-2">
            <DrawerSurfaceSectionTitle>{t('run.runtime.runDetail.section.resultPreview')}</DrawerSurfaceSectionTitle>
          <pre className="whitespace-pre-wrap break-words text-xs text-ds-text font-sans">
            {run.resultPreview || '-'}
          </pre>
          </DrawerSurfaceSection>

          <DrawerSurfaceSection className="space-y-ds-2">
            <DrawerSurfaceSectionTitle>{t('run.runtime.runDetail.section.error')}</DrawerSurfaceSectionTitle>
          <pre className="whitespace-pre-wrap break-words text-xs font-sans text-ds-error">
            {run.error || '-'}
          </pre>
          </DrawerSurfaceSection>

          <DrawerSurfaceSection className="space-y-ds-2">
            <DrawerSurfaceSectionTitle>{t('run.runtime.runDetail.section.taskContext')}</DrawerSurfaceSectionTitle>
          {task ? (
            <>
              <DetailRow label={t('run.runtime.runDetail.label.taskId')} value={task.taskId} mono />
              <DetailRow label={t('run.runtime.runDetail.label.status')} value={task.status} />
              <DetailRow label={t('run.runtime.runDetail.label.created')} value={formatDateTime(task.createdAt)} />
              <DetailRow label={t('run.runtime.runDetail.label.started')} value={formatDateTime(task.startedAt)} />
              <DetailRow label={t('run.runtime.runDetail.label.finished')} value={formatDateTime(task.finishedAt)} />
              <DetailRow label={t('run.runtime.runDetail.label.taskError')} value={task.error || '-'} />
            </>
          ) : (
            <div className="text-xs text-ds-muted">{t('run.runtime.runDetail.empty.taskInfo')}</div>
          )}
          </DrawerSurfaceSection>
        </DrawerSurfaceBody>
      </DrawerSurface>
      <BranchRunDialog
        open={branchDialogOpen}
        busy={branchBusy}
        error={branchError}
        initialMessage={run.message}
        initialModel={null}
        modelOptions={modelOptions}
        onClose={() => {
          if (!branchBusy) {
            setBranchDialogOpen(false);
          }
        }}
        onSubmit={(draft) => void submitBranchRun(draft)}
      />

      <ResumePromptFallbackDialog
        open={resumeFallback !== null}
        prompt={resumeFallback?.prompt ?? ''}
        errorDetail={resumeFallback?.errorDetail ?? null}
        clipboardCopied={resumeFallback?.clipboardCopied ?? false}
        onCopy={async () => {
          if (!resumeFallback) {
            return;
          }
          const copied = await copyCheckpointResumePrompt(resumeFallback.prompt);
          setResumeFallback({ ...resumeFallback, clipboardCopied: copied });
        }}
        onClose={() => setResumeFallback(null)}
      />
    </>
  );
}

function DetailRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3 text-xs">
      <div className="text-ds-muted">{label}</div>
      <div className={`text-right text-ds-text ${mono ? 'font-mono break-all' : ''}`}>{value}</div>
    </div>
  );
}

function SummaryChip({ label, value }: { label: string; value: string }) {
  return <DrawerSurfaceStat label={label} value={value} />;
}

function ComparisonList({
  title,
  items,
}: {
  title: string;
  items: RunShadowDimensionDelta[];
}) {
  return (
    <div className="space-y-2">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
        {title}
      </div>
      <div className="space-y-1">
        {items.map((item) => (
          <div
            key={`${title}-${item.name}`}
            className="rounded border border-ds-border/70 bg-ds-bg/60 px-2 py-1.5 text-xs"
          >
            <div className="flex items-center gap-2">
              <div className="text-ds-text">{item.label}</div>
              <div className="ml-auto text-ds-muted">
                {item.delta >= 0 ? '+' : ''}
                {formatPercent(item.delta)}
              </div>
            </div>
            <div className="mt-1 text-[10px] text-ds-muted">
              {formatPercent(item.baselineValue)} -&gt; {formatPercent(item.shadowValue)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
