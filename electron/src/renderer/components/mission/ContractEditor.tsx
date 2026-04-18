import { useEffect, useState } from 'react';
import type { TaskContractView } from '../../types/taskContract';

interface Props {
  contract: TaskContractView;
  open: boolean;
  saving: boolean;
  onClose: () => void;
  onSave: (patch: Record<string, unknown>) => Promise<void>;
}

function linesToList(value: string): string[] {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}

export function ContractEditor({ contract, open, saving, onClose, onSave }: Props) {
  const [businessGoal, setBusinessGoal] = useState(contract.contract.business_goal);
  const [decisionOwner, setDecisionOwner] = useState(contract.contract.decision_owner ?? '');
  const [forbiddenPatterns, setForbiddenPatterns] = useState(
    contract.contract.forbidden_data_patterns.join('\n')
  );
  const [escalations, setEscalations] = useState(
    contract.contract.autonomy.agent_will_escalate.join('\n')
  );

  useEffect(() => {
    if (!open) {
      return;
    }
    setBusinessGoal(contract.contract.business_goal);
    setDecisionOwner(contract.contract.decision_owner ?? '');
    setForbiddenPatterns(contract.contract.forbidden_data_patterns.join('\n'));
    setEscalations(contract.contract.autonomy.agent_will_escalate.join('\n'));
  }, [contract, open]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 px-4"
      data-testid="contract-editor"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="contract-editor-title"
        className="w-full max-w-2xl rounded-2xl border border-ds-border bg-ds-surface shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-ds-border px-5 py-4">
          <div>
            <h2 id="contract-editor-title" className="text-base font-semibold text-ds-text">
              Edit Task Contract
            </h2>
            <p className="mt-1 text-xs text-ds-muted">
              Update the active task contract before the next state transition.
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg border border-ds-border px-3 py-1.5 text-xs text-ds-muted hover:border-ds-accent hover:text-ds-text"
          >
            Close
          </button>
        </div>

        <div className="grid gap-4 p-5">
          <label className="grid gap-2 text-xs text-ds-muted">
            Business Goal
            <textarea
              value={businessGoal}
              onChange={(event) => setBusinessGoal(event.target.value)}
              rows={3}
              data-testid="contract-editor-business-goal"
              className="rounded-xl border border-ds-border bg-ds-bg px-3 py-2 text-sm text-ds-text outline-none focus:border-ds-accent"
            />
          </label>

          <label className="grid gap-2 text-xs text-ds-muted">
            Decision Owner
            <input
              value={decisionOwner}
              onChange={(event) => setDecisionOwner(event.target.value)}
              data-testid="contract-editor-decision-owner"
              className="rounded-xl border border-ds-border bg-ds-bg px-3 py-2 text-sm text-ds-text outline-none focus:border-ds-accent"
            />
          </label>

          <label className="grid gap-2 text-xs text-ds-muted">
            Forbidden Data Patterns
            <textarea
              value={forbiddenPatterns}
              onChange={(event) => setForbiddenPatterns(event.target.value)}
              rows={4}
              data-testid="contract-editor-forbidden-patterns"
              className="rounded-xl border border-ds-border bg-ds-bg px-3 py-2 text-sm text-ds-text outline-none focus:border-ds-accent"
            />
          </label>

          <label className="grid gap-2 text-xs text-ds-muted">
            Escalation Triggers
            <textarea
              value={escalations}
              onChange={(event) => setEscalations(event.target.value)}
              rows={4}
              data-testid="contract-editor-escalations"
              className="rounded-xl border border-ds-border bg-ds-bg px-3 py-2 text-sm text-ds-text outline-none focus:border-ds-accent"
            />
          </label>
        </div>

        <div className="flex items-center justify-between border-t border-ds-border px-5 py-4">
          <p className="text-xs text-ds-muted">
            Removing escalation triggers broadens autonomous execution scope.
          </p>
          <button
            disabled={saving}
            onClick={() => onSave({
              business_goal: businessGoal.trim(),
              decision_owner: decisionOwner.trim() || null,
              forbidden_data_patterns: linesToList(forbiddenPatterns),
              autonomy: {
                ...contract.contract.autonomy,
                agent_will_escalate: linesToList(escalations),
              },
            })}
            data-testid="contract-editor-save"
            className="rounded-xl bg-ds-accent px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}
