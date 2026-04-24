import { useEffect, useMemo, useState, type ReactElement } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, X, ShieldAlert } from 'lucide-react';
import { useWs } from '../../renderer/hooks/WsProvider';
import { useWorkflowStore } from '../../renderer/stores/workflowStore';
import { useAccessRole } from '../../renderer/hooks/useAccessRole';
import {
  getQueuedApprovalCount,
  selectPendingApprovals,
  submitMobileApproval,
  toMobileApprovalView,
  type ApprovalDecision,
  type MobileApprovalView,
  type SubmitApprovalResult,
} from '../approvals/approvalAdapter';
import {
  getApprovalErrorKey,
  resolveApprovalErrorCode,
} from '../errors/mobileError';
import { OUTBOX_CHANGED_EVENT } from '../outbox/indexedDbOutbox';

interface PendingDecision {
  readonly approval: MobileApprovalView;
  readonly decision: ApprovalDecision;
}

export function ApprovalsPage(): ReactElement {
  const { t } = useTranslation('mobile');
  const { rpc, status } = useWs();
  const approvals = useWorkflowStore((state) => state.approvals);
  const { isViewer } = useAccessRole();

  const [busyId, setBusyId] = useState<string | null>(null);
  const [errorId, setErrorId] = useState<string | null>(null);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingDecision | null>(null);
  const [queuedCount, setQueuedCount] = useState(0);
  const [queueMessage, setQueueMessage] = useState<string | null>(null);

  const views = useMemo<readonly MobileApprovalView[]>(
    () => selectPendingApprovals(approvals).map(toMobileApprovalView),
    [approvals],
  );

  const connected = status === 'connected';

  useEffect(() => {
    let cancelled = false;

    const refreshQueuedCount = async (): Promise<void> => {
      const count = await getQueuedApprovalCount();
      if (!cancelled) {
        setQueuedCount(count);
      }
    };

    const handleOutboxChanged = (): void => {
      void refreshQueuedCount();
    };

    void refreshQueuedCount();
    window.addEventListener(OUTBOX_CHANGED_EVENT, handleOutboxChanged as EventListener);
    return () => {
      cancelled = true;
      window.removeEventListener(OUTBOX_CHANGED_EVENT, handleOutboxChanged as EventListener);
    };
  }, []);

  const handleClick = (approval: MobileApprovalView, decision: ApprovalDecision): void => {
    setErrorId(null);
    setErrorKey(null);
    if (decision === 'rejected' || approval.requiresConfirmation) {
      setPending({ approval, decision });
      return;
    }
    void runDecision(approval, decision);
  };

  const runDecision = async (
    approval: MobileApprovalView,
    decision: ApprovalDecision,
  ): Promise<void> => {
    setBusyId(approval.approvalId);
    let outcome: SubmitApprovalResult;
    try {
      outcome = await submitMobileApproval(rpc, {
        approvalId: approval.approvalId,
        decision,
        response: decision === 'approved' ? approval.defaultResponse : null,
        actor: 'mobile',
      });
    } catch (error) {
      setBusyId(null);
      setErrorId(approval.approvalId);
      setErrorKey(getApprovalErrorKey(resolveApprovalErrorCode(error)));
      return;
    }
    setBusyId(null);
    if (outcome.queued) {
      setErrorId(null);
      setErrorKey(null);
      setQueueMessage(t('approvals.queue.saved'));
      return;
    }
    if (!outcome.ok) {
      setErrorId(approval.approvalId);
      setQueueMessage(null);
      setErrorKey(getApprovalErrorKey(outcome.errorCode ?? 'approval_submit_failed'));
      return;
    }
    setQueueMessage(null);
  };

  const handleConfirm = async (): Promise<void> => {
    if (!pending) return;
    const snapshot = pending;
    setPending(null);
    await runDecision(snapshot.approval, snapshot.decision);
  };

  const handleCancel = (): void => {
    setPending(null);
  };

  return (
    <div className="flex flex-col gap-3 p-4">
      <h1 className="text-lg font-semibold text-ds-text">{t('nav.approvals')}</h1>
      <p className="text-sm text-ds-muted">{t('approvals.description')}</p>

      {isViewer && (
        <section
          role="status"
          className="rounded-2xl border border-ds-border bg-ds-surface/70 p-4 text-sm text-ds-muted"
        >
          <div className="flex items-center gap-2 text-ds-text">
            <ShieldAlert size={16} aria-hidden="true" />
            <span className="font-medium">{t('approvals.viewer.title')}</span>
          </div>
          <p className="mt-2">{t('approvals.viewer.description')}</p>
        </section>
      )}

      {!connected && (
        <section
          role="status"
          className="rounded-2xl border border-ds-border bg-ds-surface/70 p-4 text-sm text-ds-muted"
        >
          {t('approvals.connection.waiting')}
        </section>
      )}

      {(queuedCount > 0 || queueMessage) && (
        <section
          role="status"
          className="rounded-2xl border border-ds-border bg-ds-surface/70 p-4 text-sm text-ds-muted"
        >
          <div className="font-medium text-ds-text">{t('approvals.queue.title')}</div>
          {queuedCount > 0 ? (
            <p className="mt-2">{t('approvals.queue.count', { count: queuedCount })}</p>
          ) : null}
          {queueMessage ? <p className="mt-2">{queueMessage}</p> : null}
        </section>
      )}

      <section className="rounded-2xl border border-ds-border bg-ds-surface/70 p-4">
        <h2 className="text-sm font-semibold text-ds-text">{t('approvals.list.title')}</h2>
        <div className="mt-4 space-y-3">
          {views.length === 0 ? (
            <div className="rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3 text-sm text-ds-muted">
              {t('approvals.list.empty')}
            </div>
          ) : (
            views.map((view) => (
              <ApprovalRow
                key={view.approvalId}
                view={view}
                disabled={isViewer || !connected || busyId === view.approvalId}
                busy={busyId === view.approvalId}
                errorKey={errorId === view.approvalId ? errorKey : null}
                onAct={(decision) => handleClick(view, decision)}
                t={t}
              />
            ))
          )}
        </div>
      </section>

      {pending && (
        <ConfirmSheet
          view={pending.approval}
          decision={pending.decision}
          onConfirm={() => void handleConfirm()}
          onCancel={handleCancel}
        />
      )}
    </div>
  );
}

interface ApprovalRowProps {
  readonly view: MobileApprovalView;
  readonly disabled: boolean;
  readonly busy: boolean;
  readonly errorKey: string | null;
  readonly onAct: (decision: ApprovalDecision) => void;
  readonly t: (key: string) => string;
}

function ApprovalRow({
  view,
  disabled,
  busy,
  errorKey,
  onAct,
  t,
}: ApprovalRowProps): ReactElement {
  return (
    <article
      className="rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3"
      aria-busy={busy}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-medium text-ds-text">{view.question}</div>
          <div className="mt-1 break-all text-[11px] text-ds-muted">{view.approvalId}</div>
        </div>
        {view.risk && (
          <span
            className={`shrink-0 rounded-full px-2 py-1 text-[11px] font-medium ${
              view.risk === 'high'
                ? 'bg-rose-500/10 text-rose-200'
                : view.risk === 'medium'
                  ? 'bg-amber-500/10 text-amber-200'
                  : 'bg-emerald-500/10 text-emerald-300'
            }`}
          >
            {t(`approvals.risk.${view.risk}`)}
          </span>
        )}
      </div>

      {view.proposalType && (
        <div className="mt-2 text-[11px] text-ds-muted">
          {t('approvals.field.type')}: <span className="text-ds-text">{view.proposalType}</span>
        </div>
      )}
      {view.targetId && (
        <div className="mt-1 break-all text-[11px] text-ds-muted">
          {t('approvals.field.target')}: <span className="text-ds-text">{view.targetId}</span>
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          aria-label={`${t('approvals.action.approve')} ${view.approvalId}`}
          onClick={() => onAct('approved')}
          disabled={disabled}
          style={{
            minHeight: '44px',
            minWidth: '44px',
            flex: '1 1 140px',
            padding: '0 12px',
            borderRadius: '12px',
            border: '1px solid var(--ds-border)',
            background: disabled ? 'var(--ds-surface)' : 'var(--ds-accent)',
            color: disabled ? 'var(--ds-muted)' : 'var(--ds-bg)',
            fontSize: '14px',
            fontWeight: 600,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            cursor: disabled ? 'not-allowed' : 'pointer',
          }}
        >
          <Check size={16} aria-hidden="true" />
          {t('approvals.action.approve')}
        </button>
        <button
          type="button"
          aria-label={`${t('approvals.action.reject')} ${view.approvalId}`}
          onClick={() => onAct('rejected')}
          disabled={disabled}
          style={{
            minHeight: '44px',
            minWidth: '44px',
            flex: '1 1 140px',
            padding: '0 12px',
            borderRadius: '12px',
            border: '1px solid var(--ds-border)',
            background: 'transparent',
            color: 'var(--ds-text)',
            fontSize: '14px',
            fontWeight: 600,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            cursor: disabled ? 'not-allowed' : 'pointer',
          }}
        >
          <X size={16} aria-hidden="true" />
          {t('approvals.action.reject')}
        </button>
      </div>

      {errorKey && (
        <div role="alert" className="mt-3 text-xs text-rose-300">
          {t('approvals.error.submit')}: {t(errorKey)}
        </div>
      )}
    </article>
  );
}

interface ConfirmSheetProps {
  readonly view: MobileApprovalView;
  readonly decision: ApprovalDecision;
  readonly onConfirm: () => void;
  readonly onCancel: () => void;
}

function ConfirmSheet({
  view,
  decision,
  onConfirm,
  onCancel,
}: ConfirmSheetProps): ReactElement {
  const { t } = useTranslation('mobile');
  const titleKey =
    decision === 'approved'
      ? 'approvals.confirm.approve.title'
      : 'approvals.confirm.reject.title';
  const bodyKey =
    decision === 'approved'
      ? 'approvals.confirm.approve.body'
      : 'approvals.confirm.reject.body';

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="mobile-approval-confirm-title"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.5)',
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
        zIndex: 50,
      }}
      onClick={onCancel}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: '480px',
          background: 'var(--ds-surface)',
          color: 'var(--ds-text)',
          borderTopLeftRadius: '20px',
          borderTopRightRadius: '20px',
          padding: '20px 16px calc(20px + env(safe-area-inset-bottom, 0px))',
          boxShadow: '0 -4px 20px rgba(0,0,0,0.4)',
        }}
      >
        <h2
          id="mobile-approval-confirm-title"
          style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}
        >
          {t(titleKey)}
        </h2>
        <p style={{ marginTop: '8px', fontSize: '13px', color: 'var(--ds-muted)' }}>
          {t(bodyKey)}
        </p>
        <div
          style={{
            marginTop: '12px',
            padding: '12px',
            border: '1px solid var(--ds-border)',
            borderRadius: '12px',
            fontSize: '13px',
          }}
        >
          {view.question}
        </div>
        <div style={{ marginTop: '16px', display: 'flex', gap: '8px' }}>
          <button
            type="button"
            onClick={onCancel}
            style={{
              flex: 1,
              minHeight: '44px',
              borderRadius: '12px',
              border: '1px solid var(--ds-border)',
              background: 'transparent',
              color: 'var(--ds-text)',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {t('approvals.confirm.cancel')}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            style={{
              flex: 1,
              minHeight: '44px',
              borderRadius: '12px',
              border: 'none',
              background:
                decision === 'rejected'
                  ? 'rgba(244, 63, 94, 0.85)'
                  : 'var(--ds-accent)',
              color: decision === 'rejected' ? '#fff' : 'var(--ds-bg)',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {t('approvals.confirm.proceed')}
          </button>
        </div>
      </div>
    </div>
  );
}
