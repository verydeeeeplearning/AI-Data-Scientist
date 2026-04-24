/**
 * Quality panel ??shows stage quality scores and latest verifier status.
 */

import { useTaskContract } from '../../hooks/useTaskContract';
import { useI18n } from '../../stores/i18nStore';
import { useWorkflowStore, type WorkflowStage } from '../../stores/workflowStore';
import {
  buildQualityPanelVerifierModel,
  pickEffectiveReviewVerdict,
} from './qualityPanelModel';

type TranslateFn = (
  key: string,
  vars?: Record<string, string | number | undefined | null>,
) => string;

const GRADE_COLORS: Record<string, string> = {
  A: 'text-ds-success',
  B: 'text-ds-accent',
  C: 'text-ds-warning',
  D: 'text-ds-error',
  F: 'text-ds-error',
};

const VERDICT_STYLES: Record<string, string> = {
  pass: 'bg-emerald-500/15 text-emerald-200 border-emerald-500/40',
  warn: 'bg-amber-500/15 text-amber-200 border-amber-500/40',
  fail: 'bg-rose-500/15 text-rose-200 border-rose-500/40',
};

export function QualityPanel() {
  const { t } = useI18n();
  const stages = useWorkflowStore((s) => s.stages);
  const overallQuality = useWorkflowStore((s) => s.overallQuality);
  const {
    activeContract,
    shadowComparison,
    shadowComparisonError,
    shadowComparisonLoading,
  } = useTaskContract();

  const scoredStages = stages.filter((s) => s.score !== undefined && s.status === 'done');
  const verifierModel = buildQualityPanelVerifierModel(
    pickEffectiveReviewVerdict(activeContract?.review_verdicts ?? []),
    shadowComparison,
  );
  const latestVerdict = verifierModel?.verdict ?? null;

  if (scoredStages.length === 0 && !overallQuality && !latestVerdict) return null;

  return (
    <div className="px-3 py-2">
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
        {t('workspace.workflow.quality.title')}
      </div>

      {overallQuality && (
        <div className="mb-2 flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ds-border">
            <div
              className="h-full rounded-full bg-ds-accent transition-all duration-300"
              style={{ width: `${overallQuality.score}%` }}
            />
          </div>
          <span
            className={`font-mono text-xs font-bold ${
              GRADE_COLORS[overallQuality.grade] ?? 'text-ds-text'
            }`}
          >
            {overallQuality.grade}
          </span>
          <span className="font-mono text-[10px] text-ds-muted">{overallQuality.score}</span>
        </div>
      )}

      <div className="space-y-0.5">
        {scoredStages.map((stage) => (
          <div key={stage.id} className="flex items-center justify-between text-[11px]">
            <span className="text-ds-muted">{translateWorkflowStage(stage, t)}</span>
            <span className="font-mono text-ds-text">{stage.score}</span>
          </div>
        ))}
      </div>

      {latestVerdict && (
        <div className="mt-3 rounded-xl border border-ds-border bg-ds-surface px-3 py-3">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
              {t('workspace.workflow.quality.verifier.title')}
            </div>
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                VERDICT_STYLES[latestVerdict.result] ?? 'border-ds-border text-ds-text'
              }`}
            >
              {translateVerifierStatus(latestVerdict.result, t)}
            </span>
          </div>

          <div className="mt-2 grid grid-cols-2 gap-2">
            <div className="rounded-lg bg-ds-bg px-2 py-2">
              <div className="text-[10px] uppercase tracking-wide text-ds-muted">
                {t('workspace.workflow.quality.verifier.confidence')}
              </div>
              <div className="mt-1 text-xs font-mono text-ds-text">
                {translateConfidenceGrade(verifierModel?.confidenceGrade, t)}
                {verifierModel?.confidencePercent !== null
                  && verifierModel?.confidencePercent !== undefined
                  && ` (${verifierModel.confidencePercent}%)`}
              </div>
            </div>
            <div className="rounded-lg bg-ds-bg px-2 py-2">
              <div className="text-[10px] uppercase tracking-wide text-ds-muted">
                {t('workspace.workflow.quality.verifier.blockers')}
              </div>
              <div className="mt-1 text-xs font-mono text-ds-text">
                {verifierModel?.blockingCount ?? 0}
              </div>
            </div>
          </div>

          {verifierModel?.judgeMode && (
            <p className="mt-2 text-[11px] text-ds-muted">
              {t('workspace.workflow.quality.verifier.judgeMode', {
                value: verifierModel.judgeMode,
              })}
            </p>
          )}

          {verifierModel?.shadowMatchRate !== null
            && verifierModel?.shadowMatchRate !== undefined
            && verifierModel?.shadowMismatchCount !== null
            && verifierModel?.shadowMismatchCount !== undefined && (
            <p className="mt-1 text-[11px] text-ds-muted">
              <span className="font-mono text-ds-text">
                {t('workspace.workflow.quality.verifier.shadowMatch', {
                  percent: Math.round(verifierModel.shadowMatchRate * 100),
                  count: verifierModel.shadowMismatchCount,
                })}
              </span>
            </p>
          )}

          {shadowComparisonLoading
            && verifierModel?.shadowMismatchCount
            && verifierModel.shadowMismatchCount > 0 && (
            <p className="mt-1 text-[11px] text-ds-muted">
              {t('workspace.workflow.quality.verifier.loadingShadowDiff')}
            </p>
          )}

          {shadowComparisonError
            && verifierModel?.shadowMismatchCount
            && verifierModel.shadowMismatchCount > 0 && (
            <p className="mt-1 text-[11px] text-ds-error">
              {t('workspace.workflow.quality.verifier.shadowDiffUnavailable', {
                error: shadowComparisonError,
              })}
            </p>
          )}

          {latestVerdict.layers && latestVerdict.layers.length > 0 && (
            <div className="mt-2 space-y-1">
              {latestVerdict.layers.map((layer) => (
                <div key={layer.layer} className="flex items-center justify-between text-[11px]">
                  <span className="text-ds-muted">{layer.layer}</span>
                  <span className="font-mono text-ds-text">
                    {translateVerifierStatus(layer.overall ?? 'pass', t)}
                  </span>
                </div>
              ))}
            </div>
          )}

          {verifierModel && verifierModel.shadowMismatchPreview.length > 0 && (
            <div className="mt-2 space-y-1">
              {verifierModel.shadowMismatchPreview.map((item) => (
                <p
                  key={`${item.comparisonKey}:${item.stateSummary}`}
                  className="text-[11px] leading-4 text-ds-muted"
                >
                  {item.comparisonKey}:{' '}
                  {item.note === 'Shadow mismatch recorded.'
                    ? t('workspace.workflow.quality.verifier.shadowMismatchRecorded')
                    : item.note}{' '}
                  <span className="font-mono text-ds-text">({item.stateSummary})</span>
                </p>
              ))}
            </div>
          )}

          {verifierModel && verifierModel.blockingIssues.length > 0 && (
            <div className="mt-2 space-y-1">
              {verifierModel.blockingIssues.slice(0, 2).map((issue, index) => (
                <p
                  key={`${issue.scope}-${index}`}
                  className="text-[11px] leading-4 text-ds-muted"
                >
                  {issue.scope === 'general'
                    ? t('workspace.workflow.quality.verifier.general')
                    : issue.scope}
                  : {issue.message}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function translateVerifierStatus(
  value: string,
  t: TranslateFn,
): string {
  const keyByStatus: Record<string, string> = {
    pass: 'workspace.workflow.quality.verifier.pass',
    warn: 'workspace.workflow.quality.verifier.warn',
    fail: 'workspace.workflow.quality.verifier.fail',
    error: 'workspace.workflow.quality.verifier.error',
    general: 'workspace.workflow.quality.verifier.general',
  };
  const key = keyByStatus[value];
  return key ? t(key) : value;
}

function translateConfidenceGrade(value: string | null | undefined, t: TranslateFn): string {
  const keyByGrade: Record<string, string> = {
    high: 'workspace.workflow.quality.verifier.confidenceGrade.high',
    medium: 'workspace.workflow.quality.verifier.confidenceGrade.medium',
    low: 'workspace.workflow.quality.verifier.confidenceGrade.low',
    insufficient: 'workspace.workflow.quality.verifier.confidenceGrade.insufficient',
    unknown: 'workspace.workflow.quality.verifier.unknown',
  };
  const key = value ? keyByGrade[value] : undefined;
  return key ? t(key) : value ?? t('workspace.workflow.quality.verifier.unknown');
}

function translateWorkflowStage(
  stage: WorkflowStage,
  t: TranslateFn,
): string {
  const keyByStageId: Partial<Record<WorkflowStage['id'], string>> = {
    scoping: 'workspace.workflow.progress.stage.scoping',
    data_loading: 'workspace.workflow.progress.stage.dataLoading',
    profiling: 'workspace.workflow.progress.stage.profiling',
    eda: 'workspace.workflow.progress.stage.eda',
    feature_eng: 'workspace.workflow.progress.stage.featureEngineering',
    modeling: 'workspace.workflow.progress.stage.modeling',
    evaluation: 'workspace.workflow.progress.stage.evaluation',
    reporting: 'workspace.workflow.progress.stage.reporting',
  };
  const key = keyByStageId[stage.id];
  return key ? t(key) : stage.label;
}
