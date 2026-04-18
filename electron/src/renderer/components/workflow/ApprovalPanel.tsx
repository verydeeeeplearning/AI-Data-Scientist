/**
 * Approval inbox for pending approval requests.
 */

import { ShieldAlert, Check, X } from 'lucide-react';
import { useState } from 'react';
import { useWs } from '../../hooks/WsProvider';
import { useWorkflowStore } from '../../stores/workflowStore';

export function ApprovalPanel() {
  const approvals = useWorkflowStore((s) => s.approvals);
  const pending = approvals.filter((item) => item.status === 'pending');

  return (
    <div className="px-3 py-2">
      <div className="flex items-center gap-2 text-[10px] font-semibold text-ds-muted uppercase tracking-wider mb-2">
        <ShieldAlert size={12} />
        Approval Inbox
        <span className="ml-auto text-ds-text normal-case text-xs">{pending.length}</span>
      </div>

      {pending.length === 0 ? (
        <div className="text-xs text-ds-muted">No pending approvals.</div>
      ) : (
        <div className="space-y-2">
          {pending.map((approval) => (
            <ApprovalCard key={approval.approvalId} approval={approval} />
          ))}
        </div>
      )}
    </div>
  );
}

function ApprovalCard({
  approval,
}: {
  approval: {
    approvalId: string;
    question: string;
    kind: string;
    metadata: Record<string, unknown>;
    options: string[];
    default?: string | null;
    sessionId: string;
    runId?: string | null;
  };
}) {
  const { rpc } = useWs();
  const [busy, setBusy] = useState(false);

  const resolve = async (decision: 'approved' | 'rejected', response?: string) => {
    setBusy(true);
    try {
      await rpc('approval.resolve', {
        approvalId: approval.approvalId,
        decision,
        response,
        actor: 'electron',
      });
    } catch (err) {
      console.warn('[ApprovalPanel] approval.resolve failed:', err);
    } finally {
      setBusy(false);
    }
  };

  const openPrompt = async () => {
    const initial = approval.default ?? '';
    const response = window.prompt(approval.question, initial);
    if (response === null) return;
    await resolve('approved', response);
  };

  const semanticMeta = approval.kind === 'semantic_proposal'
    ? approval.metadata
    : null;
  const proposalType =
    semanticMeta && typeof semanticMeta.proposalType === 'string'
      ? semanticMeta.proposalType
      : null;
  const targetId =
    semanticMeta && typeof semanticMeta.targetId === 'string'
      ? semanticMeta.targetId
      : null;
  const risk =
    semanticMeta && typeof semanticMeta.risk === 'string'
      ? semanticMeta.risk
      : null;

  return (
    <div className="rounded-md border border-ds-border bg-ds-bg/70 p-2 space-y-2">
      <div className="text-xs text-ds-text leading-relaxed">{approval.question}</div>
      {semanticMeta && (
        <div className="rounded border border-ds-border/70 bg-ds-surface/60 p-2 text-[11px] text-ds-muted space-y-1">
          {proposalType && <div>Type: {proposalType}</div>}
          {targetId && <div>Target: {targetId}</div>}
          {risk && <div>Risk: {risk}</div>}
        </div>
      )}
      <div className="text-[10px] text-ds-muted font-mono">
        {approval.approvalId} {approval.runId ? `• ${approval.runId}` : ''}
      </div>

      {approval.options.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {approval.options.map((option) => (
            <button
              key={option}
              onClick={() => void resolve('approved', option)}
              disabled={busy}
              className="px-2 py-1 rounded bg-ds-surface border border-ds-border text-xs hover:border-ds-accent disabled:opacity-50"
            >
              {option}
            </button>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2">
        <button
          onClick={() => void openPrompt()}
          disabled={busy}
          className="px-2 py-1 rounded bg-ds-accent text-white text-xs disabled:opacity-50 inline-flex items-center gap-1"
        >
          <Check size={12} />
          Respond
        </button>
        <button
          onClick={() => void resolve('rejected')}
          disabled={busy}
          className="px-2 py-1 rounded border border-ds-border text-xs text-ds-muted hover:text-ds-error hover:border-ds-error disabled:opacity-50 inline-flex items-center gap-1"
        >
          <X size={12} />
          Reject
        </button>
      </div>
    </div>
  );
}
