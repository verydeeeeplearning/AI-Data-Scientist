import { useState } from 'react';
import type { AssumptionEntry } from '../../types/taskContract';

interface Props {
  open: boolean;
  entries: AssumptionEntry[];
  verifying: boolean;
  onVerify: (entryId: string, verificationNote?: string) => Promise<void>;
  onClose: () => void;
}

export function AssumptionDrawer({ open, entries, verifying, onVerify, onClose }: Props) {
  const [verificationNotes, setVerificationNotes] = useState<Record<string, string>>({});

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-30 flex justify-end bg-black/40" data-testid="assumption-drawer">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="assumption-drawer-title"
        className="h-full w-full max-w-lg border-l border-ds-border bg-ds-surface shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-ds-border px-5 py-4">
          <div>
            <h2 id="assumption-drawer-title" className="text-base font-semibold text-ds-text">
              Open Assumptions
            </h2>
            <p className="mt-1 text-xs text-ds-muted">
              Unverified assumptions captured in the current contract.
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg border border-ds-border px-3 py-1.5 text-xs text-ds-muted hover:border-ds-accent hover:text-ds-text"
          >
            Close
          </button>
        </div>

        <div className="space-y-3 overflow-y-auto p-5">
          {entries.length === 0 && (
            <div
              className="rounded-2xl border border-ds-border bg-ds-bg px-4 py-3 text-sm text-ds-muted"
              data-testid="assumption-empty-state"
            >
              No open assumptions.
            </div>
          )}
          {entries.map((entry) => (
            <article
              key={entry.entry_id}
              data-testid={`assumption-entry-${entry.entry_id}`}
              className={`rounded-2xl border px-4 py-3 ${
                entry.risk_level === 'high'
                  ? 'border-amber-500/60 bg-amber-500/10'
                  : 'border-ds-border bg-ds-bg'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs font-semibold uppercase tracking-wide text-ds-muted">
                  {entry.risk_level}
                </span>
                <span className="text-[11px] text-ds-muted">{entry.entry_id}</span>
              </div>
              <p className="mt-2 text-sm font-medium text-ds-text">{entry.statement}</p>
              <p className="mt-2 text-xs leading-5 text-ds-muted">{entry.rationale}</p>
              <div className="mt-3 space-y-2">
                <textarea
                  value={verificationNotes[entry.entry_id] ?? ''}
                  onChange={(event) =>
                    setVerificationNotes((current) => ({
                      ...current,
                      [entry.entry_id]: event.target.value,
                    }))
                  }
                  rows={3}
                  placeholder="Verification note (optional)"
                  className="w-full rounded-xl border border-ds-border bg-ds-surface px-3 py-2 text-xs text-ds-text"
                  data-testid={`assumption-note-${entry.entry_id}`}
                />
                <button
                  type="button"
                  disabled={verifying}
                  onClick={() =>
                    void onVerify(entry.entry_id, verificationNotes[entry.entry_id] ?? '')
                  }
                  className="rounded-xl bg-ds-accent px-3 py-2 text-xs font-medium text-white disabled:opacity-60"
                  data-testid={`assumption-verify-${entry.entry_id}`}
                >
                  Mark Verified
                </button>
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
