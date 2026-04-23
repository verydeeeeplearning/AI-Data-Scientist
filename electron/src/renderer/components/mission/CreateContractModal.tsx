import { useEffect, useMemo, useState } from 'react';
import {
  DEFAULT_USE_CASE_ID,
  ONBOARDING_USE_CASE_IDS,
  type OnboardingUseCaseId,
} from '../../../shared/useCaseMapping';
import {
  RECOVERY_TASK_CONTRACT_USE_CASE_LABELS,
  resolveRecoveryTaskContractDefaults,
} from '../../application/onboarding/recoveryTaskContractDefaults';
import type { TaskContractCreatePayload } from '../../types/taskContract';

interface CreateContractModalProps {
  open: boolean;
  sessionId: string;
  initialBusinessGoal?: string;
  saving: boolean;
  onClose: () => void;
  onSubmit: (payload: TaskContractCreatePayload) => Promise<void>;
}

export function buildRecoveryTaskContractDraft(args: {
  sessionId: string;
  useCaseId: OnboardingUseCaseId;
  businessGoal: string;
}): TaskContractCreatePayload {
  const businessGoal = args.businessGoal.trim();
  const { useCaseSpec, goalBriefTemplate } = resolveRecoveryTaskContractDefaults(args.useCaseId);

  return {
    session_id: args.sessionId.trim(),
    contract_type: useCaseSpec.contractType,
    business_goal: businessGoal,
    goal_brief: {
      business_question: businessGoal,
      ds_problem_statement: goalBriefTemplate.ds_problem_statement,
      comparison_baseline: goalBriefTemplate.comparison_baseline,
      decision_to_make: goalBriefTemplate.decision_to_make,
      hypothesis: null,
      expected_effort: goalBriefTemplate.expected_effort,
    },
    required_deliverables: useCaseSpec.defaultDeliverableSpecs.map((item) => ({ ...item })),
    allowed_data_sources: [],
    forbidden_data_patterns: [],
    budget: {},
    autonomy: {},
    authority: useCaseSpec.defaultAuthority,
    audience: useCaseSpec.defaultAudience,
    mission: useCaseSpec.defaultMission,
    created_by: 'user',
  };
}

export function CreateContractModal({
  open,
  sessionId,
  initialBusinessGoal = '',
  saving,
  onClose,
  onSubmit,
}: CreateContractModalProps) {
  const [useCaseId, setUseCaseId] = useState<OnboardingUseCaseId>(DEFAULT_USE_CASE_ID);
  const [businessGoal, setBusinessGoal] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    setUseCaseId(DEFAULT_USE_CASE_ID);
    setBusinessGoal(initialBusinessGoal.trim());
    setValidationError(null);
  }, [initialBusinessGoal, open, sessionId]);

  const recoveryDefaults = useMemo(
    () => resolveRecoveryTaskContractDefaults(useCaseId),
    [useCaseId],
  );
  const useCaseSpec = recoveryDefaults.useCaseSpec;

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 px-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="mission-brief-create-title"
        aria-describedby="mission-brief-create-description"
        className="w-full max-w-2xl rounded-2xl border border-ds-border bg-ds-surface shadow-2xl"
        data-testid="mission-brief-create-contract-dialog"
      >
        <div className="flex items-center justify-between border-b border-ds-border px-5 py-4">
          <div>
            <h2
              id="mission-brief-create-title"
              className="text-base font-semibold text-ds-text"
            >
              Draft Task Contract
            </h2>
            <p
              id="mission-brief-create-description"
              className="mt-1 text-xs text-ds-muted"
            >
              Create a manual recovery draft for the current session when no active contract is present.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="rounded-lg border border-ds-border px-3 py-1.5 text-xs text-ds-muted hover:border-ds-accent hover:text-ds-text disabled:opacity-60"
          >
            Cancel
          </button>
        </div>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            const normalizedGoal = businessGoal.trim();
            if (!normalizedGoal) {
              setValidationError('Business goal is required.');
              return;
            }
            setValidationError(null);
            void onSubmit(
              buildRecoveryTaskContractDraft({
                sessionId,
                useCaseId,
                businessGoal: normalizedGoal,
              }),
            );
          }}
        >
          <div className="grid gap-4 p-5">
            <div className="rounded-xl border border-ds-border bg-ds-bg/50 px-3 py-2 text-[11px] text-ds-muted">
              Session: <span className="font-mono text-ds-text">{sessionId}</span>
            </div>

            <label className="grid gap-2 text-xs text-ds-muted">
              Use Case
              <select
                value={useCaseId}
                onChange={(event) => setUseCaseId(event.target.value as OnboardingUseCaseId)}
                data-testid="mission-brief-create-contract-use-case"
                className="rounded-xl border border-ds-border bg-ds-bg px-3 py-2 text-sm text-ds-text outline-none focus:border-ds-accent"
              >
                {ONBOARDING_USE_CASE_IDS.map((value) => (
                  <option key={value} value={value}>
                    {RECOVERY_TASK_CONTRACT_USE_CASE_LABELS[value]}
                  </option>
                ))}
              </select>
            </label>

            <label className="grid gap-2 text-xs text-ds-muted">
              Business Goal
              <textarea
                value={businessGoal}
                onChange={(event) => setBusinessGoal(event.target.value)}
                rows={4}
                data-testid="mission-brief-create-contract-business-goal"
                placeholder="Describe the decision, question, or analysis goal for this session."
                className="rounded-xl border border-ds-border bg-ds-bg px-3 py-2 text-sm text-ds-text outline-none focus:border-ds-accent"
              />
            </label>

            <div className="rounded-xl border border-ds-border bg-ds-bg/60 px-4 py-3">
              <p className="text-[11px] uppercase tracking-wide text-ds-muted">Draft Defaults</p>
              <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                <span className="rounded-full border border-ds-border bg-ds-surface px-2 py-1 text-ds-text">
                  Contract Type: {useCaseSpec.contractType}
                </span>
                <span className="rounded-full border border-ds-border bg-ds-surface px-2 py-1 text-ds-text">
                  Authority: {useCaseSpec.defaultAuthority}
                </span>
                <span className="rounded-full border border-ds-border bg-ds-surface px-2 py-1 text-ds-text">
                  Audience: {useCaseSpec.defaultAudience}
                </span>
              </div>
              <div className="mt-3 grid gap-2">
                {useCaseSpec.defaultDeliverableSpecs.map((item) => (
                  <div
                    key={`${item.type}-${item.audience}-${item.format}`}
                    className="rounded-lg border border-ds-border bg-ds-surface px-3 py-2 text-[11px] text-ds-muted"
                  >
                    <span className="font-medium text-ds-text">{item.type}</span>
                    {` -> ${item.audience} (${item.format})`}
                  </div>
                ))}
              </div>
            </div>

            {validationError && (
              <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                {validationError}
              </div>
            )}
          </div>

          <div className="flex items-center justify-end border-t border-ds-border px-5 py-4">
            <button
              type="submit"
              disabled={saving}
              data-testid="mission-brief-create-contract-submit"
              className="rounded-xl bg-ds-accent px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? 'Drafting...' : 'Create Draft'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
