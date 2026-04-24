import { GitCompareArrows } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useWs } from '../../hooks/WsProvider';
import { useI18n } from '../../stores/i18nStore';
import { InlineError, StatusLine } from './DecisionOsReviewPrimitives';
import {
  directionClass,
  RunDiffResult,
  ReviewRun,
  runOptionLabel,
  severityClass,
} from './decisionOsReviewModel';
import { translateReviewStatus } from './reviewI18n';

interface Props {
  runs: ReviewRun[];
  connected: boolean;
  onOpenPromotionModal: (candidateRunId: string) => void;
}

export function RunDiffPanel({ runs, connected, onOpenPromotionModal }: Props) {
  const { t } = useI18n();
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
      setDiffError(t('workspace.workflow.review.runDiff.selectBothError'));
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
        {t('workspace.workflow.review.runDiff.title')}
      </div>
      <div className="grid gap-2">
        <select
          value={runAId}
          onChange={(event) => setRunAId(event.target.value)}
          aria-label={t('workspace.workflow.review.runDiff.baseRunAria')}
          data-testid="decision-os-run-diff-base"
          className="rounded border border-ds-border bg-ds-surface px-2 py-1.5 text-xs text-ds-text"
        >
          <option value="">{t('workspace.workflow.review.runDiff.selectBaseRun')}</option>
          {runs.map((run) => (
            <option key={run.run_id} value={run.run_id}>
              {runOptionLabel(run)}
            </option>
          ))}
        </select>
        <select
          value={runBId}
          onChange={(event) => setRunBId(event.target.value)}
          aria-label={t('workspace.workflow.review.runDiff.candidateRunAria')}
          data-testid="decision-os-run-diff-candidate"
          className="rounded border border-ds-border bg-ds-surface px-2 py-1.5 text-xs text-ds-text"
        >
          <option value="">{t('workspace.workflow.review.runDiff.selectCandidateRun')}</option>
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
          {diffBusy
            ? t('workspace.workflow.review.runDiff.comparing')
            : t('workspace.workflow.review.runDiff.compareRuns')}
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
              label={t('workspace.workflow.review.runDiff.codeRef')}
              value={`${diffResult.code_ref[0]} -> ${diffResult.code_ref[1]}`}
            />
            <StatusLine
              label={t('workspace.workflow.review.runDiff.dataSnapshot')}
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
            <FeatureChangeCard titleKey="workspace.workflow.review.runDiff.addedFeatures" items={diffResult.feature_set.added.map(
              (item) => `${item.feature_id} v${item.version}`,
            )} />
            <FeatureChangeCard titleKey="workspace.workflow.review.runDiff.removedFeatures" items={diffResult.feature_set.removed.map(
              (item) => `${item.feature_id} v${item.version}`,
            )} />
            <FeatureChangeCard titleKey="workspace.workflow.review.runDiff.versionChanges" items={diffResult.feature_set.version_changed.map(
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
              {t('workspace.workflow.review.runDiff.openPromotionForCandidate')}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function FeatureChangeCard({ titleKey, items }: { titleKey: string; items: string[] }) {
  const { t } = useI18n();

  return (
    <div className="rounded border border-ds-border/70 bg-ds-surface/60 p-2 text-[10px]">
      <div className="font-medium text-ds-text">{t(titleKey)}</div>
      {items.length === 0 ? (
        <div className="mt-1 text-ds-muted">{t('workspace.workflow.review.runDiff.noChanges')}</div>
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
  const { t } = useI18n();

  return (
    <div className="rounded border border-ds-border/70 bg-ds-surface/60 p-2 text-[10px]">
      <div className="font-medium text-ds-text">{t('workspace.workflow.review.runDiff.verifierDelta')}</div>
      <div className="mt-2 grid gap-2">
        <VerifierLine label={t('workspace.workflow.review.runDiff.statistical')} value={diff.verifier.statistical} />
        <VerifierLine label={t('workspace.workflow.review.runDiff.data')} value={diff.verifier.data} />
        <VerifierLine label={t('workspace.workflow.review.runDiff.policy')} value={diff.verifier.policy} />
      </div>
      {diff.verifier.new_findings.length > 0 ? (
        <div className="mt-2 space-y-1">
          {diff.verifier.new_findings.map((finding) => (
            <div
              key={finding}
              className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-amber-300"
            >
              {t('workspace.workflow.review.runDiff.newFinding', { finding })}
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
              {t('workspace.workflow.review.runDiff.resolvedFinding', { finding })}
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
  const { t } = useI18n();
  const changed = value[0] !== value[1];

  return (
    <div className="rounded border border-ds-border bg-ds-bg/70 px-2 py-1.5">
      <div className="text-ds-muted">{label}</div>
      <div className="mt-1 flex items-center gap-2 text-ds-text">
        <span className={`rounded border px-1.5 py-0.5 ${severityClass(value[0].toLowerCase())}`}>
          {translateReviewStatus(value[0].toLowerCase(), t)}
        </span>
        <span className="text-ds-muted">{'->'}</span>
        <span className={`rounded border px-1.5 py-0.5 ${severityClass(value[1].toLowerCase())}`}>
          {translateReviewStatus(value[1].toLowerCase(), t)}
        </span>
        {changed ? <span className="text-[9px] text-ds-muted">{t('workspace.workflow.review.runDiff.changed')}</span> : null}
      </div>
    </div>
  );
}
