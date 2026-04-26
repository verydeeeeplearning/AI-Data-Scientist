/**
 * Blocking approval modal for pending sandbox and operator requests.
 *
 * Wave 2 modal v2 keeps compatibility with the current workflow store payload
 * while opportunistically hydrating richer context via `approval.get`.
 */

import {
  AlertTriangle,
  Bot,
  Check,
  Clock3,
  FolderTree,
  Globe,
  KeyRound,
  ShieldAlert,
  Sparkles,
  TerminalSquare,
  X,
} from 'lucide-react';
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from 'react';
import { ResultCardSectionPanel, ResultCardSectionTitle } from '../../design-system/composites';
import { Badge, Button, Card, Textarea, cn } from '../../design-system/primitives';
import { useWs } from '../../hooks/WsProvider';
import { useI18n } from '../../stores/i18nStore';
import { useWorkflowStore } from '../../stores/workflowStore';
import type { ApprovalRequest } from '../../stores/workflowStore';
import { createApprovalModalA11yController } from '../approval/approvalModalA11y';
import {
  highlightLine,
  normalizeHighlightLanguage,
  tokenClassName,
} from '../approval/codePreviewHighlighter';
import {
  buildApprovalModalViewModel,
  mergeApprovalDetails,
  type ApprovalAffectedScope,
  type ApprovalDetails,
  type ApprovalScope,
} from '../approval/approvalModalModel';

export function SandboxApprovalModal() {
  const approvals = useWorkflowStore((s) => s.approvals);
  const oldestPending = useMemo<ApprovalRequest | null>(() => {
    const pending = approvals.filter((item) => item.status === 'pending');
    if (pending.length === 0) return null;
    return [...pending].sort((a, b) => a.createdAt - b.createdAt)[0];
  }, [approvals]);

  if (!oldestPending) return null;

  return (
    <ApprovalDialog
      approval={oldestPending}
      pendingCount={approvals.filter((item) => item.status === 'pending').length}
    />
  );
}

function ApprovalDialog({
  approval,
  pendingCount,
}: {
  approval: ApprovalRequest;
  pendingCount: number;
}) {
  const { rpc } = useWs();
  const { t } = useI18n();
  const dialogRef = useRef<HTMLDivElement>(null);
  const a11yRef = useRef<ReturnType<typeof createApprovalModalA11yController> | null>(null);
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(true);
  const [detailsError, setDetailsError] = useState<string | null>(null);
  const [allowScope, setAllowScope] = useState<ApprovalScope>('once');
  const [allowFallback, setAllowFallback] = useState(false);
  const [responseDraft, setResponseDraft] = useState(approval.default ?? '');
  const [denyReason, setDenyReason] = useState('');
  const [details, setDetails] = useState<ApprovalDetails>(() => mergeApprovalDetails(approval));

  useEffect(() => {
    const initial = mergeApprovalDetails(approval);
    setBusy(false);
    setDetails(initial);
    setDetailsLoading(true);
    setDetailsError(null);
    setAllowScope('once');
    setAllowFallback(Boolean(initial.recommendedAlternative));
    setResponseDraft(approval.default ?? '');
    setDenyReason('');

    let cancelled = false;

    const loadDetails = async () => {
      try {
        const payload = await rpc('approval.get', { approvalId: approval.approvalId });
        if (cancelled) return;
        const next = mergeApprovalDetails(approval, payload);
        setDetails(next);
        setAllowFallback(Boolean(next.recommendedAlternative));
      } catch (err) {
        if (cancelled) return;
        console.warn('[SandboxApprovalModal] approval.get failed:', err);
        setDetailsError('Detailed risk context is unavailable. Showing the live approval payload.');
      } finally {
        if (!cancelled) {
          setDetailsLoading(false);
        }
      }
    };

    void loadDetails();
    return () => {
      cancelled = true;
    };
  }, [approval.approvalId, approval.default, approval.updatedAt, rpc]);

  useEffect(() => {
    if (!dialogRef.current) return undefined;
    const controller = createApprovalModalA11yController(dialogRef.current);
    a11yRef.current = controller;
    controller.activate();
    return () => {
      controller.deactivate();
      a11yRef.current = null;
    };
  }, [approval.approvalId]);

  const viewModel = useMemo(() => buildApprovalModalViewModel(details), [details]);

  const submitDecision = async (decision: 'allow' | 'deny') => {
    if (busy) return;
    setBusy(true);
    setSubmitError(null);
    try {
      await rpc('approval.submit', {
        approvalId: details.approvalId,
        decision,
        scope: decision === 'allow' ? allowScope : undefined,
        response: decision === 'allow' ? responseDraft.trim() || undefined : undefined,
        denyReason: decision === 'deny' ? denyReason.trim() || undefined : undefined,
        allowFallback: decision === 'deny' ? allowFallback : undefined,
        actor: 'electron',
        source: 'electron',
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      console.warn('[SandboxApprovalModal] approval.submit failed:', err);
      setSubmitError(t('approval.modal.submitError', { message }));
      setBusy(false);
    }
  };

  const handleDialogKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const action = a11yRef.current?.handleKeyDown(event.nativeEvent);
    if (action === 'escape') {
      void submitDecision('deny');
    }
  };

  const responseLabel = viewModel.responseOptions.length > 0
    ? 'Selected response or custom note'
    : 'Response passed to the agent (optional)';
  const severityTone = severityTonePresentation(viewModel.severity);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ds-bg/80 px-ds-4 py-ds-4 backdrop-blur-sm"
      onKeyDown={handleDialogKeyDown}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="sandbox-approval-title"
        aria-describedby="sandbox-approval-summary"
        tabIndex={-1}
        className="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-ds-xl border border-ds-border bg-ds-surface-elevated/96 text-ds-text shadow-ds-lg"
      >
        <header className="border-b border-ds-border/80 bg-ds-bg/40 px-ds-4 py-ds-4">
          <div className="flex items-start gap-ds-3">
            <div className={cn('mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-ds-lg border', severityTone.iconClassName)}>
              <ShieldAlert size={18} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-ds-2">
                <h2 id="sandbox-approval-title" className="text-ds-lg font-semibold text-ds-text">
                  {viewModel.title}
                </h2>
                <Badge compact tone={severityTone.badgeTone}>
                  {viewModel.severityLabel}
                </Badge>
                {pendingCount > 1 && (
                  <Badge compact className="text-ds-muted">
                    {pendingCount} pending approvals
                  </Badge>
                )}
              </div>
              <p
                id="sandbox-approval-summary"
                className="mt-ds-2 whitespace-pre-line text-ds-sm leading-6 text-ds-text"
              >
                {viewModel.summary}
              </p>
              <div className="mt-ds-3 flex flex-wrap gap-ds-2 text-ds-xs text-ds-muted">
                <InlineMeta icon={<Bot size={12} />} text={`Surface: ${details.surface}`} />
                {details.runId && <InlineMeta icon={<Sparkles size={12} />} text={`Run: ${details.runId}`} />}
                <InlineMeta icon={<Clock3 size={12} />} text={`Request: ${details.approvalId}`} />
                {detailsLoading && (
                  <Badge compact className="text-ds-muted">
                    Loading richer approval context...
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </header>

        <div className="grid min-h-0 flex-1 overflow-hidden md:grid-cols-[1.2fr_0.8fr]">
          <section className="min-h-0 overflow-y-auto border-b border-ds-border/80 px-ds-4 py-ds-4 md:border-b-0 md:border-r">
            <div className="space-y-ds-4">
              {detailsError && (
                <div
                  role="status"
                  className="rounded-ds-lg border border-ds-warning/30 bg-ds-warning/10 px-ds-3 py-ds-3 text-ds-xs text-ds-text"
                >
                  {detailsError}
                </div>
              )}

              <Card className="space-y-ds-3 bg-ds-bg/40 shadow-none">
                <div className="flex items-center gap-ds-2">
                  <AlertTriangle size={14} className="text-ds-warning" />
                  <ResultCardSectionTitle>Why approval is needed</ResultCardSectionTitle>
                </div>
                <p className="text-ds-sm leading-6 text-ds-text">
                  {viewModel.explanation}
                </p>
                {viewModel.recommendedAlternative && (
                  <Card tone="accent" className="space-y-ds-2 rounded-ds-lg p-ds-3 shadow-none">
                    <ResultCardSectionTitle className="text-ds-accent">
                      Suggested safer path
                    </ResultCardSectionTitle>
                    <div className="text-ds-sm leading-6 text-ds-text">
                      {viewModel.recommendedAlternative}
                    </div>
                  </Card>
                )}
              </Card>

              {viewModel.impactItems.length > 0 && (
                <Card className="space-y-ds-3 bg-ds-bg/30 shadow-none">
                  <ResultCardSectionTitle>Scope of impact</ResultCardSectionTitle>
                  <div className="grid gap-ds-3 sm:grid-cols-2">
                    {viewModel.impactItems.map((item) => (
                      <ResultCardSectionPanel key={item.id} className="bg-ds-surface/70">
                        <div className="flex items-center gap-ds-2 text-ds-sm font-medium text-ds-text">
                          {renderImpactIcon(item.id)}
                          {item.label}
                        </div>
                        <p className="mt-ds-2 text-ds-xs leading-5 text-ds-muted">
                          {item.description}
                        </p>
                      </ResultCardSectionPanel>
                    ))}
                  </div>
                </Card>
              )}

              {viewModel.patternCards.length > 0 && (
                <Card className="space-y-ds-3 bg-ds-bg/30 shadow-none">
                  <ResultCardSectionTitle>Matched policy signals</ResultCardSectionTitle>
                  <div className="space-y-ds-3">
                    {viewModel.patternCards.map((card) => (
                      <ResultCardSectionPanel key={card.id} className="bg-ds-surface/70">
                        <div className="text-ds-sm font-medium text-ds-text">{card.title}</div>
                        {card.highlights.length > 0 && (
                          <ul className="mt-ds-2 space-y-1 text-ds-xs text-ds-muted">
                            {card.highlights.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        )}
                      </ResultCardSectionPanel>
                    ))}
                  </div>
                </Card>
              )}

              {viewModel.codePreview && (
                <Card className="space-y-ds-3 bg-ds-bg/30 shadow-none">
                  <div className="flex items-center justify-between gap-ds-2">
                    <ResultCardSectionTitle>
                      {viewModel.codePreview.label}
                    </ResultCardSectionTitle>
                    <Badge compact className="text-ds-muted">
                      {viewModel.codePreview.language}
                    </Badge>
                  </div>
                  <div className="overflow-hidden rounded-ds-lg border border-ds-border/70 bg-[#101215]">
                    <pre className="max-h-72 overflow-auto px-0 py-0 text-ds-xs text-slate-100">
                      {viewModel.codePreview.lines.map((line) => {
                        const language = normalizeHighlightLanguage(viewModel.codePreview?.language);
                        const tokens = highlightLine(line.text || ' ', language);
                        return (
                          <div
                            key={line.number}
                            className={line.reason ? 'bg-amber-500/10' : undefined}
                          >
                            <div className="grid grid-cols-[3.5rem_1fr] gap-0">
                              <span className="border-r border-slate-800 px-ds-3 py-ds-2 text-right text-slate-500">
                                {line.number}
                              </span>
                              <span className="px-ds-3 py-ds-2 whitespace-pre-wrap break-words font-mono">
                                {tokens.length > 0
                                  ? tokens.map((token, index) => (
                                      <span
                                        key={`${line.number}-${index}`}
                                        className={tokenClassName(token.kind) || undefined}
                                      >
                                        {token.text}
                                      </span>
                                    ))
                                  : line.text || ' '}
                              </span>
                            </div>
                            {line.reason && (
                              <div className="border-t border-amber-500/20 px-ds-3 py-1 text-[11px] text-amber-200">
                                {line.reason}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </pre>
                  </div>
                  {viewModel.codePreview.truncated && (
                    <div className="text-[11px] text-ds-muted">
                      Preview trimmed around the most relevant lines.
                    </div>
                  )}
                </Card>
              )}

              {viewModel.infoRows.length > 0 && (
                <Card className="space-y-ds-3 bg-ds-bg/30 shadow-none">
                  <ResultCardSectionTitle>Request context</ResultCardSectionTitle>
                  <dl className="grid gap-ds-3 sm:grid-cols-2">
                    {viewModel.infoRows.map((item) => (
                      <div
                        key={item.label}
                        className="rounded-ds-lg border border-ds-border/70 bg-ds-surface/70 px-ds-3 py-ds-3"
                      >
                        <dt className="text-[11px] uppercase tracking-[0.14em] text-ds-muted">
                          {item.label}
                        </dt>
                        <dd className="mt-ds-1 break-words text-ds-sm text-ds-text">{item.value}</dd>
                      </div>
                    ))}
                  </dl>
                </Card>
              )}
            </div>
          </section>

          <aside className="min-h-0 overflow-y-auto px-ds-4 py-ds-4">
            <div className="space-y-ds-4">
              <Card className="space-y-ds-3 bg-ds-bg/40 shadow-none">
                <ResultCardSectionTitle>Allow scope</ResultCardSectionTitle>
                <div className="space-y-ds-3">
                  {viewModel.scopeOptions.map((option) => (
                    <label
                      key={option.id}
                      className={cn(
                        'flex items-start gap-ds-3 rounded-ds-lg border p-ds-3 transition-colors',
                        allowScope === option.id
                          ? 'border-ds-accent/60 bg-ds-accent/10'
                          : 'border-ds-border/70 bg-ds-surface/70',
                        busy ? 'cursor-not-allowed opacity-60' : 'cursor-pointer hover:border-ds-accent/40',
                      )}
                    >
                      <input
                        type="radio"
                        name="approval-scope"
                        value={option.id}
                        checked={allowScope === option.id}
                        onChange={() => setAllowScope(option.id)}
                        disabled={busy}
                        className="mt-1 shrink-0"
                      />
                      <span className="min-w-0">
                        <span className="flex flex-wrap items-center gap-ds-2 text-ds-sm font-medium text-ds-text">
                          {option.label}
                          {option.recommended && (
                            <Badge compact tone="success">
                              Recommended
                            </Badge>
                          )}
                        </span>
                        <span className="mt-ds-1 block text-ds-xs leading-5 text-ds-muted">
                          {option.description}
                        </span>
                      </span>
                    </label>
                  ))}
                </div>
                <ResultCardSectionPanel className="bg-ds-surface/60">
                  <p className="text-[11px] leading-5 text-ds-muted">
                    Session and workspace selections are recorded in the approval decision today.
                    Automatic expiry and revoke flows are still being completed in Wave 2.
                  </p>
                </ResultCardSectionPanel>
              </Card>

              {viewModel.responseOptions.length > 0 && (
                <Card className="space-y-ds-3 bg-ds-bg/40 shadow-none">
                  <ResultCardSectionTitle>Common responses</ResultCardSectionTitle>
                  <div className="flex flex-wrap gap-ds-2">
                    {viewModel.responseOptions.map((option) => {
                      const active = responseDraft.trim() === option;
                      return (
                        <Badge<'button'>
                          key={option}
                          as="button"
                          type="button"
                          compact
                          onClick={() => setResponseDraft(option)}
                          disabled={busy}
                          tone={active ? 'accent' : 'neutral'}
                          className={cn(
                            'px-ds-3 py-ds-2 normal-case tracking-normal transition-colors duration-ds-fast ease-ds-standard',
                            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg',
                            'disabled:cursor-not-allowed disabled:opacity-50',
                            active
                              ? 'border-ds-accent/40 bg-ds-accent/10 text-ds-text'
                              : 'text-ds-muted hover:border-ds-accent/40 hover:text-ds-accent',
                          )}
                        >
                          {option}
                        </Badge>
                      );
                    })}
                  </div>
                </Card>
              )}

              <Card className="bg-ds-bg/40 shadow-none">
                <Textarea
                  id="sandbox-approval-response"
                  value={responseDraft}
                  onChange={(event) => setResponseDraft(event.target.value)}
                  disabled={busy}
                  rows={4}
                  resize="vertical"
                  label={responseLabel}
                  hint="The allow action sends this value back to the agent. If you use a quick response above, it populates this field so you can still edit it before submitting."
                  placeholder="Optional note or structured response for the agent"
                  className="min-h-28"
                />
              </Card>

              <Card tone="danger" className="space-y-ds-3 shadow-none">
                <ResultCardSectionTitle className="text-ds-error">Deny path</ResultCardSectionTitle>
                <Textarea
                  value={denyReason}
                  onChange={(event) => setDenyReason(event.target.value)}
                  disabled={busy}
                  rows={3}
                  resize="vertical"
                  label="Optional denial reason"
                  placeholder="Optional denial reason for the audit trail and agent context"
                  className="min-h-24"
                />
                <label
                  className={cn(
                    'flex items-start gap-ds-3 rounded-ds-lg border border-ds-border/70 bg-ds-surface/80 p-ds-3 text-ds-sm text-ds-text',
                    busy ? 'cursor-not-allowed opacity-60' : 'cursor-pointer hover:border-ds-accent/40',
                  )}
                >
                  <input
                    type="checkbox"
                    checked={allowFallback}
                    onChange={(event) => setAllowFallback(event.target.checked)}
                    disabled={busy}
                    className="mt-1 shrink-0"
                  />
                  <span className="min-w-0">
                    <span className="font-medium">Allow safer fallback after denial</span>
                    <span className="mt-ds-1 block text-ds-xs leading-5 text-ds-muted">
                      The agent may attempt an alternative route instead of stopping completely
                      after you deny this request.
                    </span>
                  </span>
                </label>
              </Card>
            </div>
          </aside>
        </div>

        <footer className="border-t border-ds-border/80 bg-ds-bg/40 px-ds-4 py-ds-4">
          <div className="flex flex-col gap-ds-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-ds-xs leading-5 text-ds-muted">
              Escape denies the request and restores focus to the previously active control when the modal clears.
            </div>
            <div className="flex flex-col items-end gap-ds-2">
              {submitError && (
                <p role="alert" className="text-ds-xs text-ds-error">
                  {submitError}
                </p>
              )}
              <div className="flex flex-col gap-ds-2 sm:flex-row">
                <Button
                  variant="danger"
                  onClick={() => void submitDecision('deny')}
                  disabled={busy}
                  leadingIcon={<X size={14} aria-hidden="true" />}
                >
                  Deny request
                </Button>
                <Button
                  variant="primary"
                  onClick={() => void submitDecision('allow')}
                  disabled={busy}
                  leadingIcon={<Check size={14} aria-hidden="true" />}
                >
                  Allow selected scope
                </Button>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}

function InlineMeta({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <Badge
      compact
      leadingIcon={<span className="shrink-0" aria-hidden="true">{icon}</span>}
      className="text-ds-muted"
    >
      {text}
    </Badge>
  );
}

function renderImpactIcon(scope: ApprovalAffectedScope) {
  if (scope === 'network') return <Globe size={14} className="text-ds-info" />;
  if (scope === 'filesystem') return <FolderTree size={14} className="text-ds-warning" />;
  if (scope === 'secret') return <KeyRound size={14} className="text-ds-error" />;
  return <TerminalSquare size={14} className="text-ds-accent" />;
}

function severityTonePresentation(
  severity: 'high' | 'medium' | 'low',
): {
  badgeTone: 'danger' | 'warning' | 'info';
  iconClassName: string;
} {
  if (severity === 'high') {
    return {
      badgeTone: 'danger',
      iconClassName: 'border-ds-error/30 bg-ds-error/10 text-ds-error',
    };
  }
  if (severity === 'medium') {
    return {
      badgeTone: 'warning',
      iconClassName: 'border-ds-warning/30 bg-ds-warning/10 text-ds-warning',
    };
  }
  return {
    badgeTone: 'info',
    iconClassName: 'border-ds-info/30 bg-ds-info/10 text-ds-info',
  };
}
