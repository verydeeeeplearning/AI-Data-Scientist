/**
 * Approval inbox for pending approval requests.
 */

import { ShieldAlert, Check, X } from 'lucide-react';
import { useId, useState, type FormEvent } from 'react';
import {
  Badge,
  Button,
  Card,
  Popover,
  Textarea,
} from '../../design-system/primitives';
import { useCanMutate } from '../../hooks/useCanMutate';
import { useWs } from '../../hooks/WsProvider';
import { useWorkflowStore } from '../../stores/workflowStore';

type ApprovalRecord = {
  approvalId: string;
  question: string;
  kind: string;
  metadata: Record<string, unknown>;
  options: string[];
  default?: string | null;
  sessionId: string;
  runId?: string | null;
};

export function ApprovalPanel() {
  const headingId = useId().replace(/:/g, '');
  const approvals = useWorkflowStore((s) => s.approvals);
  const pending = approvals.filter((item) => item.status === 'pending');

  return (
    <section aria-labelledby={headingId} className="px-3 py-2">
      <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
        <ShieldAlert size={12} />
        <h2 id={headingId} className="text-inherit">
          Approval Inbox
        </h2>
        <Badge
          tone={pending.length > 0 ? 'warning' : 'neutral'}
          compact
          className="ml-auto normal-case"
          aria-label={`${pending.length} pending approvals`}
        >
          {pending.length}
        </Badge>
      </div>

      {pending.length === 0 ? (
        <div className="text-xs text-ds-muted">No pending approvals.</div>
      ) : (
        <div className="space-y-2" role="list" aria-label="Pending approvals">
          {pending.map((approval) => (
            <div key={approval.approvalId} role="listitem">
              <ApprovalCard approval={approval} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function ApprovalCard({
  approval,
}: {
  approval: ApprovalRecord;
}) {
  const cardTitleId = useId().replace(/:/g, '');
  const responseFieldId = useId().replace(/:/g, '');
  const { rpc } = useWs();
  const { canMutate, reason: mutateBlockedReason } = useCanMutate();
  const mutationBlocked = !canMutate;
  const [busy, setBusy] = useState(false);
  const [respondOpen, setRespondOpen] = useState(false);
  const [responseDraft, setResponseDraft] = useState(approval.default ?? '');

  const resolve = async (decision: 'approved' | 'rejected', response?: string) => {
    setRespondOpen(false);
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

  const handleRespondOpenChange = (nextOpen: boolean) => {
    if (nextOpen) {
      setResponseDraft(approval.default ?? '');
    }
    setRespondOpen(nextOpen);
  };

  const handleResponseSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void resolve('approved', responseDraft);
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
    <Card
      role="group"
      aria-labelledby={cardTitleId}
      aria-busy={busy}
      className="space-y-ds-3 border-ds-border bg-ds-bg/70 p-ds-3"
    >
      <div id={cardTitleId} className="text-xs leading-relaxed text-ds-text">
        {approval.question}
      </div>

      {semanticMeta && (
        <div className="rounded-ds-lg border border-ds-border/70 bg-ds-surface/60 p-ds-3 text-[11px] text-ds-muted">
          <dl className="space-y-1">
            {proposalType && (
              <div className="flex gap-2">
                <dt className="font-medium text-ds-text">Type:</dt>
                <dd className="min-w-0 break-all">{proposalType}</dd>
              </div>
            )}
            {targetId && (
              <div className="flex gap-2">
                <dt className="font-medium text-ds-text">Target:</dt>
                <dd className="min-w-0 break-all">{targetId}</dd>
              </div>
            )}
            {risk && (
              <div className="flex gap-2">
                <dt className="font-medium text-ds-text">Risk:</dt>
                <dd className="min-w-0 break-all">{risk}</dd>
              </div>
            )}
          </dl>
        </div>
      )}

      <div className="text-[10px] font-mono text-ds-muted">
        {approval.approvalId} {approval.runId ? ` | ${approval.runId}` : ''}
      </div>

      {approval.options.length > 0 && (
        <div className="flex flex-wrap gap-1" role="group" aria-label="Approval options">
          {approval.options.map((option) => (
            <Button
              key={option}
              variant="secondary"
              size="sm"
              onClick={() => void resolve('approved', option)}
              disabled={busy || mutationBlocked}
              aria-disabled={mutationBlocked || undefined}
              title={mutationBlocked ? mutateBlockedReason : undefined}
            >
              {option}
            </Button>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2">
        <Popover
          open={respondOpen}
          onOpenChange={handleRespondOpenChange}
          tone="accent"
          align="start"
          title="Approval response"
          description="Submit an optional freeform response while keeping the current approval context in view."
          trigger={(
            <Button
              variant="primary"
              size="sm"
              leadingIcon={<Check size={12} />}
              disabled={busy || mutationBlocked}
              aria-disabled={mutationBlocked || undefined}
              title={mutationBlocked ? mutateBlockedReason : undefined}
              aria-label={`Respond to approval ${approval.approvalId}`}
            >
              Respond
            </Button>
          )}
        >
          <form className="space-y-ds-3" onSubmit={handleResponseSubmit}>
            <Textarea
              id={responseFieldId}
              label="Response"
              value={responseDraft}
              onChange={(event) => setResponseDraft(event.target.value)}
              rows={4}
              resize="vertical"
              disabled={busy || mutationBlocked}
              aria-disabled={mutationBlocked || undefined}
              title={mutationBlocked ? mutateBlockedReason : undefined}
            />
            <div className="flex items-center justify-end gap-ds-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setRespondOpen(false)}
                disabled={busy || mutationBlocked}
                aria-disabled={mutationBlocked || undefined}
                title={mutationBlocked ? mutateBlockedReason : undefined}
                aria-label={`Cancel response for approval ${approval.approvalId}`}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                leadingIcon={<Check size={12} />}
                disabled={busy || mutationBlocked}
                aria-disabled={mutationBlocked || undefined}
                title={mutationBlocked ? mutateBlockedReason : undefined}
              >
                Approve
              </Button>
            </div>
          </form>
        </Popover>
        <Button
          onClick={() => void resolve('rejected')}
          disabled={busy}
          variant="danger"
          size="sm"
          leadingIcon={<X size={12} />}
          aria-label={`Reject approval ${approval.approvalId}`}
        >
          Reject
        </Button>
      </div>
    </Card>
  );
}
