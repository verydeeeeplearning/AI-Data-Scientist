/**
 * Quality panel ??shows stage quality scores and latest verifier status.
 */

import { useTaskContract } from '../../hooks/useTaskContract';
import { useWorkflowStore } from '../../stores/workflowStore';
import {
  buildQualityPanelVerifierModel,
  pickEffectiveReviewVerdict,
} from './qualityPanelModel';

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
    shadowComparison
  );
  const latestVerdict = verifierModel?.verdict ?? null;

  if (scoredStages.length === 0 && !overallQuality && !latestVerdict) return null;

  return (
    <div className="px-3 py-2">
      <div className="text-[10px] font-semibold text-ds-muted uppercase tracking-wider mb-2">
        Quality
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
            className={`text-xs font-bold font-mono ${
              GRADE_COLORS[overallQuality.grade] ?? 'text-ds-text'
            }`}
          >
            {overallQuality.grade}
          </span>
          <span className="text-[10px] font-mono text-ds-muted">{overallQuality.score}</span>
        </div>
      )}

      <div className="space-y-0.5">
        {scoredStages.map((stage) => (
          <div key={stage.id} className="flex items-center justify-between text-[11px]">
            <span className="text-ds-muted">{stage.label}</span>
            <span className="font-mono text-ds-text">{stage.score}</span>
          </div>
        ))}
      </div>

      {latestVerdict && (
        <div className="mt-3 rounded-xl border border-ds-border bg-ds-surface px-3 py-3">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
              Verifier
            </div>
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                VERDICT_STYLES[latestVerdict.result] ?? 'border-ds-border text-ds-text'
              }`}
            >
              {latestVerdict.result}
            </span>
          </div>

          <div className="mt-2 grid grid-cols-2 gap-2">
            <div className="rounded-lg bg-ds-bg px-2 py-2">
              <div className="text-[10px] uppercase tracking-wide text-ds-muted">Confidence</div>
              <div className="mt-1 text-xs font-mono text-ds-text">
                {verifierModel?.confidenceGrade ?? 'unknown'}
                {verifierModel?.confidencePercent !== null &&
                  verifierModel?.confidencePercent !== undefined &&
                  ` (${verifierModel.confidencePercent}%)`}
              </div>
            </div>
            <div className="rounded-lg bg-ds-bg px-2 py-2">
              <div className="text-[10px] uppercase tracking-wide text-ds-muted">Blockers</div>
              <div className="mt-1 text-xs font-mono text-ds-text">
                {verifierModel?.blockingCount ?? 0}
              </div>
            </div>
          </div>

          {verifierModel?.judgeMode && (
            <p className="mt-2 text-[11px] text-ds-muted">
              Judge mode: <span className="font-mono text-ds-text">{verifierModel.judgeMode}</span>
            </p>
          )}

          {verifierModel?.shadowMatchRate !== null &&
            verifierModel?.shadowMatchRate !== undefined &&
            verifierModel?.shadowMismatchCount !== null &&
            verifierModel?.shadowMismatchCount !== undefined && (
            <p className="mt-1 text-[11px] text-ds-muted">
              Shadow match:{' '}
              <span className="font-mono text-ds-text">
                {Math.round(verifierModel.shadowMatchRate * 100)}% (
                {verifierModel.shadowMismatchCount} mismatches)
              </span>
            </p>
            )}

          {shadowComparisonLoading && verifierModel?.shadowMismatchCount && verifierModel.shadowMismatchCount > 0 && (
            <p className="mt-1 text-[11px] text-ds-muted">Loading shadow diff review...</p>
          )}

          {shadowComparisonError && verifierModel?.shadowMismatchCount && verifierModel.shadowMismatchCount > 0 && (
            <p className="mt-1 text-[11px] text-ds-error">
              Shadow diff unavailable: {shadowComparisonError}
            </p>
          )}

          {latestVerdict.layers && latestVerdict.layers.length > 0 && (
            <div className="mt-2 space-y-1">
              {latestVerdict.layers.map((layer) => (
                <div key={layer.layer} className="flex items-center justify-between text-[11px]">
                  <span className="text-ds-muted">{layer.layer}</span>
                  <span className="font-mono text-ds-text">{layer.overall ?? 'pass'}</span>
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
                  {item.comparisonKey}: {item.note}{' '}
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
                  {issue.scope}: {issue.message}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
