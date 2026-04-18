/**
 * Blocking modal that surfaces the latest pending sandbox approval.
 *
 * The agent halts execution while a network/policy approval is outstanding;
 * the user must explicitly approve or reject before work continues. Freeform
 * responses are entered via a textarea (replacing the legacy window.prompt
 * flow in ApprovalPanel).
 */

import { ShieldAlert, Check, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useWs } from '../../hooks/WsProvider';
import { useWorkflowStore } from '../../stores/workflowStore';
import type { ApprovalRequest } from '../../stores/workflowStore';

export function SandboxApprovalModal() {
  const approvals = useWorkflowStore((s) => s.approvals);
  const oldestPending = useMemo<ApprovalRequest | null>(() => {
    const pending = approvals.filter((a) => a.status === 'pending');
    if (pending.length === 0) return null;
    return [...pending].sort((a, b) => a.createdAt - b.createdAt)[0];
  }, [approvals]);

  if (!oldestPending) return null;

  return <ApprovalDialog approval={oldestPending} pendingCount={
    approvals.filter((a) => a.status === 'pending').length
  } />;
}

function ApprovalDialog({
  approval,
  pendingCount,
}: {
  approval: ApprovalRequest;
  pendingCount: number;
}) {
  const { rpc } = useWs();
  const [busy, setBusy] = useState(false);
  const [freeform, setFreeform] = useState(approval.default ?? '');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Reset draft when the surfaced approval changes.
  useEffect(() => {
    setFreeform(approval.default ?? '');
    setBusy(false);
  }, [approval.approvalId, approval.default]);

  // Auto-focus when modal opens for keyboard-only users.
  useEffect(() => {
    textareaRef.current?.focus();
  }, [approval.approvalId]);

  const resolve = async (decision: 'approved' | 'rejected', response?: string) => {
    if (busy) return;
    setBusy(true);
    try {
      await rpc('approval.resolve', {
        approvalId: approval.approvalId,
        decision,
        response,
        actor: 'electron',
      });
    } catch (err) {
      console.warn('[SandboxApprovalModal] approval.resolve failed:', err);
      setBusy(false);
    }
  };

  // Esc rejects (matches the cancel intent of OS-level dialogs).
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        void resolve('rejected');
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [approval.approvalId]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="sandbox-approval-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    >
      <div className="w-[min(560px,90vw)] rounded-lg border border-ds-border bg-ds-surface shadow-2xl">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-ds-border">
          <ShieldAlert size={16} className="text-ds-accent" />
          <h2 id="sandbox-approval-title" className="text-sm font-semibold text-ds-text">
            Sandbox approval required
          </h2>
          {pendingCount > 1 && (
            <span className="ml-auto text-[10px] text-ds-muted">
              +{pendingCount - 1} more pending
            </span>
          )}
        </div>

        <div className="px-4 py-4 space-y-3">
          <p className="text-sm text-ds-text leading-relaxed whitespace-pre-line">
            {approval.question}
          </p>
          <div className="text-[10px] text-ds-muted font-mono">
            id: {approval.approvalId}
            {approval.runId ? ` • run: ${approval.runId}` : ''}
          </div>

          {approval.options.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {approval.options.map((option) => (
                <button
                  key={option}
                  onClick={() => void resolve('approved', option)}
                  disabled={busy}
                  className="px-2 py-1 rounded bg-ds-bg border border-ds-border text-xs hover:border-ds-accent disabled:opacity-50"
                >
                  {option}
                </button>
              ))}
            </div>
          )}

          <div className="space-y-1">
            <label htmlFor="sandbox-approval-response" className="text-[10px] uppercase tracking-wider text-ds-muted">
              Response (optional)
            </label>
            <textarea
              id="sandbox-approval-response"
              ref={textareaRef}
              value={freeform}
              onChange={(e) => setFreeform(e.target.value)}
              disabled={busy}
              rows={3}
              className="w-full rounded-md border border-ds-border bg-ds-bg px-2 py-1 text-xs text-ds-text font-mono resize-y disabled:opacity-50"
              placeholder="Provide context the agent should see (optional)…"
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-ds-border bg-ds-bg/40">
          <button
            onClick={() => void resolve('rejected')}
            disabled={busy}
            className="px-3 py-1.5 rounded border border-ds-border text-xs text-ds-muted hover:text-ds-error hover:border-ds-error disabled:opacity-50 inline-flex items-center gap-1"
          >
            <X size={12} />
            Reject (Esc)
          </button>
          <button
            onClick={() => void resolve('approved', freeform.trim() || undefined)}
            disabled={busy}
            className="px-3 py-1.5 rounded bg-ds-accent text-white text-xs disabled:opacity-50 inline-flex items-center gap-1"
          >
            <Check size={12} />
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
