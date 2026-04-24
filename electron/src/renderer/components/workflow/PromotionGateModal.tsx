import { Check, ShieldCheck, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useWs } from '../../hooks/WsProvider';
import { useI18n } from '../../stores/i18nStore';
import { InlineError } from './DecisionOsReviewPrimitives';
import {
  formatDate,
  parseApprovers,
  ReviewDecision,
  ReviewRun,
  severityClass,
  promotionOptionLabel,
} from './decisionOsReviewModel';
import { translatePromotionStage, translateReviewStatus } from './reviewI18n';

interface Props {
  open: boolean;
  connected: boolean;
  runs: ReviewRun[];
  initialCandidateRunId?: string | null;
  defaultRollbackPlanRef?: string;
  onClose: () => void;
  onSubmitted: () => Promise<void> | void;
}

export function PromotionGateModal({
  open,
  connected,
  runs,
  initialCandidateRunId,
  defaultRollbackPlanRef = 'registry/rollback/churn.yaml',
  onClose,
  onSubmitted,
}: Props) {
  const { t } = useI18n();
  const { rpc } = useWs();
  const [candidateRunId, setCandidateRunId] = useState('');
  const [targetStage, setTargetStage] = useState<'staging' | 'production' | 'canary'>('staging');
  const [approversText, setApproversText] = useState('growth-ds, ml-lead, mlops-oncall');
  const [rollbackPlanRef, setRollbackPlanRef] = useState(defaultRollbackPlanRef);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReviewDecision | null>(null);
  const wasOpenRef = useRef(false);

  useEffect(() => {
    if (!open) {
      wasOpenRef.current = false;
      return;
    }
    if (wasOpenRef.current) {
      return;
    }
    wasOpenRef.current = true;
    setCandidateRunId(initialCandidateRunId ?? runs[0]?.run_id ?? '');
    setTargetStage('staging');
    setApproversText('growth-ds, ml-lead, mlops-oncall');
    setRollbackPlanRef(defaultRollbackPlanRef);
    setBusy(false);
    setError(null);
    setResult(null);
  }, [defaultRollbackPlanRef, initialCandidateRunId, open, runs]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const runIds = new Set(runs.map((run) => run.run_id));
    if (!runIds.has(candidateRunId)) {
      setCandidateRunId(initialCandidateRunId ?? runs[0]?.run_id ?? '');
    }
  }, [candidateRunId, initialCandidateRunId, open, runs]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose, open]);

  const selectedRun = useMemo(
    () => runs.find((run) => run.run_id === candidateRunId) ?? null,
    [candidateRunId, runs],
  );

  if (!open) {
    return null;
  }

  const requestPromotion = async () => {
    if (!candidateRunId) {
      setError(t('workspace.workflow.review.promotionGate.selectCandidateError'));
      return;
    }
    const approvers = parseApprovers(approversText);
    if (approvers.length < 3) {
      setError(t('workspace.workflow.review.promotionGate.approverError'));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const payload = await rpc('decisionOs.requestPromotion', {
        candidateRunId,
        targetStage,
        approvers,
        rollbackPlanRef,
      });
      setResult(payload as unknown as ReviewDecision);
      await onSubmitted();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="promotion-gate-modal-title"
      data-testid="decision-os-promotion-gate-modal"
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex max-h-[85vh] w-[min(720px,92vw)] flex-col overflow-hidden rounded-lg border border-ds-border bg-ds-surface shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-ds-border px-4 py-3">
          <ShieldCheck size={16} className="text-ds-accent" />
          <div>
            <h2 id="promotion-gate-modal-title" className="text-sm font-semibold text-ds-text">
              {t('workspace.workflow.review.promotionGate.title')}
            </h2>
            <p className="mt-1 text-[10px] text-ds-muted">
              {t('workspace.workflow.review.promotionGate.description')}
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label={t('workspace.workflow.review.promotionGate.closeAria')}
            data-testid="decision-os-promotion-close"
            className="ml-auto rounded border border-ds-border px-2 py-1 text-[10px] text-ds-muted hover:border-ds-accent hover:text-ds-text"
          >
            <X size={12} />
          </button>
        </div>

        <div className="space-y-3 overflow-y-auto px-4 py-4">
          <div className="grid gap-2 md:grid-cols-2">
            <select
              value={candidateRunId}
              onChange={(event) => setCandidateRunId(event.target.value)}
              data-testid="decision-os-promotion-candidate"
              className="rounded border border-ds-border bg-ds-surface px-2 py-1.5 text-xs text-ds-text"
            >
              <option value="">{t('workspace.workflow.review.promotionGate.selectCandidate')}</option>
              {runs.map((run) => (
                <option key={run.run_id} value={run.run_id}>
                  {promotionOptionLabel(run)}
                </option>
              ))}
            </select>
            <select
              value={targetStage}
              onChange={(event) =>
                setTargetStage(event.target.value as 'staging' | 'production' | 'canary')
              }
              data-testid="decision-os-promotion-stage"
              className="rounded border border-ds-border bg-ds-surface px-2 py-1.5 text-xs text-ds-text"
            >
              <option value="staging">{t('workspace.workflow.review.promotionGate.stage.staging')}</option>
              <option value="production">{t('workspace.workflow.review.promotionGate.stage.production')}</option>
              <option value="canary">{t('workspace.workflow.review.promotionGate.stage.canary')}</option>
            </select>
            <input
              value={approversText}
              onChange={(event) => setApproversText(event.target.value)}
              placeholder={t('workspace.workflow.review.promotionGate.approversPlaceholder')}
              data-testid="decision-os-promotion-approvers"
              className="rounded border border-ds-border bg-ds-surface px-2 py-1.5 text-xs text-ds-text md:col-span-2"
            />
            <input
              value={rollbackPlanRef}
              onChange={(event) => setRollbackPlanRef(event.target.value)}
              placeholder={t('workspace.workflow.review.promotionGate.rollbackPlaceholder')}
              data-testid="decision-os-promotion-rollback-plan"
              className="rounded border border-ds-border bg-ds-surface px-2 py-1.5 text-xs text-ds-text md:col-span-2"
            />
          </div>

          {selectedRun ? (
            <div className="rounded border border-ds-border/70 bg-ds-bg/70 p-3 text-xs">
              <div className="flex items-center gap-2 text-ds-text">
                <span className="font-mono">{selectedRun.run_id}</span>
                <span
                  className={`rounded border px-1.5 py-0.5 text-[10px] ${severityClass(selectedRun.promotion_state)}`}
                >
                  {translateReviewStatus(selectedRun.promotion_state, t)}
                </span>
              </div>
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                <div className="rounded border border-ds-border bg-ds-surface/60 px-2 py-1.5">
                  <div className="text-[10px] text-ds-muted">
                    {t('workspace.workflow.review.promotionGate.modelFamily')}
                  </div>
                  <div className="mt-1 text-ds-text">{selectedRun.method.model_family}</div>
                </div>
                <div className="rounded border border-ds-border bg-ds-surface/60 px-2 py-1.5">
                  <div className="text-[10px] text-ds-muted">
                    {t('workspace.workflow.review.promotionGate.created')}
                  </div>
                  <div className="mt-1 text-ds-text">{formatDate(selectedRun.created_at)}</div>
                </div>
              </div>
            </div>
          ) : null}

          {error ? <InlineError message={error} /> : null}

          {result ? (
            <div
              data-testid="decision-os-promotion-result"
              className="space-y-2 rounded border border-ds-border/70 bg-ds-bg/70 p-3"
            >
              <div className="flex items-center gap-2 text-xs text-ds-text">
                <span className="font-mono">{result.decision_id}</span>
                <span
                  className={`rounded border px-1.5 py-0.5 text-[10px] ${severityClass(result.chain_state)}`}
                >
                  {translateReviewStatus(result.chain_state, t)}
                </span>
              </div>
              <div className="text-[10px] text-ds-muted">
                {result.candidate_run_id} {'->'} {translatePromotionStage(result.target_stage, t)} / {result.candidate_model_id}
              </div>
              <div className="space-y-2">
                {result.policy_checks.map((check) => (
                  <div
                    key={check.name}
                    className="rounded border border-ds-border bg-ds-surface/60 px-2 py-1.5 text-[10px]"
                  >
                    <div className="flex items-center gap-2 text-ds-text">
                      <span>{check.name}</span>
                      <span
                        className={`rounded border px-1.5 py-0.5 ${severityClass(check.status)}`}
                      >
                        {translateReviewStatus(check.status, t)}
                      </span>
                    </div>
                    <div className="mt-1 text-ds-muted">{check.detail}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-ds-border bg-ds-bg/40 px-4 py-3">
          <button
            onClick={onClose}
            className="rounded border border-ds-border px-3 py-1.5 text-xs text-ds-muted hover:border-ds-accent hover:text-ds-text"
          >
            {t('workspace.workflow.review.promotionGate.close')}
          </button>
          <button
            onClick={() => void requestPromotion()}
            disabled={busy || !connected}
            data-testid="decision-os-promotion-submit"
            className="inline-flex items-center gap-1 rounded bg-ds-accent px-3 py-1.5 text-xs text-white disabled:opacity-50"
          >
            <Check size={12} />
            {busy
              ? t('workspace.workflow.review.promotionGate.requesting')
              : t('workspace.workflow.review.promotionGate.requestPromotion')}
          </button>
        </div>
      </div>
    </div>
  );
}
