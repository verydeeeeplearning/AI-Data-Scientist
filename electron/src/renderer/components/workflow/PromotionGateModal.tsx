import { Check, ShieldCheck, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useWs } from '../../hooks/WsProvider';
import { InlineError } from './DecisionOsReviewPrimitives';
import {
  formatDate,
  parseApprovers,
  ReviewDecision,
  ReviewRun,
  severityClass,
  promotionOptionLabel,
} from './decisionOsReviewModel';

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
      setError('Select a candidate run.');
      return;
    }
    const approvers = parseApprovers(approversText);
    if (approvers.length < 3) {
      setError('Provide DS, Lead, and MLOps approvers.');
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
              Promotion Gate
            </h2>
            <p className="mt-1 text-[10px] text-ds-muted">
              Review policy checks and submit a Decision OS promotion request.
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close promotion gate"
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
              <option value="">Select candidate run</option>
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
              <option value="staging">staging</option>
              <option value="production">production</option>
              <option value="canary">canary</option>
            </select>
            <input
              value={approversText}
              onChange={(event) => setApproversText(event.target.value)}
              placeholder="DS, Lead, MLOps"
              data-testid="decision-os-promotion-approvers"
              className="rounded border border-ds-border bg-ds-surface px-2 py-1.5 text-xs text-ds-text md:col-span-2"
            />
            <input
              value={rollbackPlanRef}
              onChange={(event) => setRollbackPlanRef(event.target.value)}
              placeholder="registry/rollback/example.yaml"
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
                  {selectedRun.promotion_state}
                </span>
              </div>
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                <div className="rounded border border-ds-border bg-ds-surface/60 px-2 py-1.5">
                  <div className="text-[10px] text-ds-muted">Model family</div>
                  <div className="mt-1 text-ds-text">{selectedRun.method.model_family}</div>
                </div>
                <div className="rounded border border-ds-border bg-ds-surface/60 px-2 py-1.5">
                  <div className="text-[10px] text-ds-muted">Created</div>
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
                  {result.chain_state}
                </span>
              </div>
              <div className="text-[10px] text-ds-muted">
                {result.candidate_run_id} {'->'} {result.target_stage} / {result.candidate_model_id}
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
                        {check.status}
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
            Close
          </button>
          <button
            onClick={() => void requestPromotion()}
            disabled={busy || !connected}
            data-testid="decision-os-promotion-submit"
            className="inline-flex items-center gap-1 rounded bg-ds-accent px-3 py-1.5 text-xs text-white disabled:opacity-50"
          >
            <Check size={12} />
            {busy ? 'Requesting...' : 'Request promotion'}
          </button>
        </div>
      </div>
    </div>
  );
}
