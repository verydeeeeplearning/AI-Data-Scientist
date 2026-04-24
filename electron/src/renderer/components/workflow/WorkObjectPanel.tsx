import { useEffect, useMemo, useState } from 'react';
import { useWorkObjects } from '../../hooks/useWorkObjects';
import { useI18n } from '../../stores/i18nStore';
import type { WorkObjectPhase } from '../../types/workObject';
import {
  canAdvance,
  canClose,
  filterWorkObjectItems,
  formatExternalReferenceLabel,
  getPendingPolicyActionCount,
  nextPhase,
} from './workObjectPanelModel';

type TranslateFn = (
  key: string,
  vars?: Record<string, string | number | undefined | null>,
) => string;

const PHASE_OPTIONS: Array<WorkObjectPhase | 'all'> = [
  'all',
  'intake',
  'executing',
  'review',
  'documenting',
  'followup',
  'closed',
  'failed',
];

const PHASE_BADGES: Record<WorkObjectPhase, string> = {
  intake: 'bg-sky-500/15 text-sky-300 border-sky-500/40',
  executing: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
  review: 'bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/40',
  documenting: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/40',
  followup: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
  closed: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
  failed: 'bg-rose-500/15 text-rose-300 border-rose-500/40',
};

export function WorkObjectPanel() {
  const { t } = useI18n();
  const [phaseFilter, setPhaseFilter] = useState<WorkObjectPhase | 'all'>('all');
  const [searchText, setSearchText] = useState('');
  const [selectedWorkObjectId, setSelectedWorkObjectId] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [closeReason, setCloseReason] = useState('');
  const [showCloseModal, setShowCloseModal] = useState(false);
  const {
    sessionId,
    items,
    loading,
    error,
    detail,
    detailLoading,
    detailError,
    refresh,
    advance,
    close,
  } = useWorkObjects(phaseFilter, selectedWorkObjectId);

  const runAction = async (fn: () => Promise<void>) => {
    setActionBusy(true);
    setActionError(null);
    setActionNotice(null);
    try {
      await fn();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionBusy(false);
    }
  };

  const filteredItems = useMemo(
    () => filterWorkObjectItems(items, searchText),
    [items, searchText],
  );
  const nextDetailPhase = detail
    ? nextPhase(detail.work_object.execution.current_phase)
    : null;

  useEffect(() => {
    if (filteredItems.length === 0) {
      setSelectedWorkObjectId(null);
      return;
    }
    if (
      !selectedWorkObjectId
      || !filteredItems.some((item) => item.work_object_id === selectedWorkObjectId)
    ) {
      setSelectedWorkObjectId(filteredItems[0].work_object_id);
    }
  }, [filteredItems, selectedWorkObjectId]);

  if (!sessionId) {
    return (
      <section
        className="mx-3 rounded-2xl border border-ds-border bg-ds-bg px-4 py-3"
        data-testid="work-object-panel"
      >
        <h3 className="text-sm font-semibold text-ds-text">
          {t('workspace.workflow.workObject.title')}
        </h3>
        <p className="mt-2 text-xs leading-5 text-ds-muted">
          {t('workspace.workflow.workObject.noSession')}
        </p>
      </section>
    );
  }

  return (
    <section
      className="mx-3 rounded-2xl border border-ds-border bg-ds-bg px-4 py-4"
      data-testid="work-object-panel"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ds-text">
            {t('workspace.workflow.workObject.title')}
          </h3>
          <p className="mt-1 text-[11px] text-ds-muted">
            {t('workspace.workflow.workObject.session', { sessionId })}
          </p>
        </div>
        <button
          onClick={() => void refresh()}
          className="rounded-lg border border-ds-border px-3 py-1.5 text-[11px] text-ds-muted hover:border-ds-accent hover:text-ds-text"
        >
          {t('workspace.workflow.workObject.refresh')}
        </button>
      </div>

      <div className="mt-3 grid gap-2">
        <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_140px]">
          <input
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            placeholder={t('workspace.workflow.workObject.searchPlaceholder')}
            data-testid="work-object-search"
            className="min-w-0 rounded-xl border border-ds-border bg-ds-surface px-3 py-2 text-xs text-ds-text"
          />
          <select
            value={phaseFilter}
            onChange={(event) => setPhaseFilter(event.target.value as WorkObjectPhase | 'all')}
            aria-label={t('workspace.workflow.workObject.phaseFilterAria')}
            data-testid="work-object-phase-filter"
            className="rounded-xl border border-ds-border bg-ds-surface px-3 py-2 text-xs text-ds-text"
          >
            {PHASE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {t(`workspace.workflow.workObject.phase.${option}`)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading && (
        <p className="mt-3 text-xs text-ds-muted">
          {t('workspace.workflow.workObject.loading')}
        </p>
      )}

      {error && (
        <div className="mt-3 rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
          {error}
        </div>
      )}

      {!loading && filteredItems.length === 0 && !error && (
        <p className="mt-3 text-xs leading-5 text-ds-muted">
          {t('workspace.workflow.workObject.empty')}
        </p>
      )}

      {filteredItems.length > 0 && (
        <div className="mt-4 space-y-3">
          <div className="space-y-2">
            {filteredItems.map((item) => (
              <button
                key={item.work_object_id}
                type="button"
                onClick={() => setSelectedWorkObjectId(item.work_object_id)}
                data-testid={`work-object-item-${item.work_object_id}`}
                className={`w-full rounded-2xl border px-3 py-3 text-left ${
                  selectedWorkObjectId === item.work_object_id
                    ? 'border-ds-accent bg-ds-surface'
                    : 'border-ds-border bg-ds-surface/70 hover:border-ds-accent/50'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-ds-text">{item.work_object_id}</span>
                  <span
                    className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${PHASE_BADGES[item.phase]}`}
                  >
                    {t(`workspace.workflow.workObject.phase.${item.phase}`)}
                  </span>
                </div>
                <p className="mt-2 text-sm font-medium text-ds-text">{item.title}</p>
                <p className="mt-1 text-[11px] text-ds-muted">
                  {t('workspace.workflow.workObject.itemMeta', {
                    taskId: item.task_contract_id,
                    referenceCount: item.reference_count,
                    followUpCount: item.follow_up_count,
                  })}
                </p>
              </button>
            ))}
          </div>

          {detailLoading && (
            <div className="rounded-2xl border border-ds-border bg-ds-surface px-4 py-3 text-xs text-ds-muted">
              {t('workspace.workflow.workObject.detailLoading')}
            </div>
          )}

          {detailError && (
            <div className="rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-xs text-rose-200">
              {detailError}
            </div>
          )}

          {detail && (
            <div
              className="rounded-2xl border border-ds-border bg-ds-surface px-4 py-4"
              data-testid="work-object-detail"
            >
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-ds-text">{detail.work_object.title}</p>
                  <p className="mt-1 text-[11px] text-ds-muted">
                    {t('workspace.workflow.workObject.detailTask', {
                      workObjectId: detail.work_object.work_object_id,
                      taskId: detail.work_object.execution.task_contract_id,
                    })}
                  </p>
                </div>
                <span
                  className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${PHASE_BADGES[detail.work_object.execution.current_phase]}`}
                >
                  {t(`workspace.workflow.workObject.phase.${detail.work_object.execution.current_phase}`)}
                </span>
              </div>

              {actionError && (
                <div className="mt-3 rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                  {actionError}
                </div>
              )}
              {actionNotice && (
                <div className="mt-3 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
                  {actionNotice}
                </div>
              )}

              <div className="mt-3 flex items-center gap-2" data-testid="work-object-actions">
                {canAdvance(detail.work_object.execution.current_phase) && nextDetailPhase && (
                  <button
                    disabled={actionBusy}
                    onClick={() => {
                      void runAction(async () => {
                        await advance(detail.work_object.work_object_id, nextDetailPhase);
                        setActionNotice(
                          t('workspace.workflow.workObject.action.advanced', {
                            phase: t(`workspace.workflow.workObject.phase.${nextDetailPhase}`),
                          }),
                        );
                      });
                    }}
                    data-testid="work-object-advance-btn"
                    className="rounded-lg border border-ds-accent bg-ds-accent/10 px-3 py-1.5 text-[11px] font-medium text-ds-accent hover:bg-ds-accent/20 disabled:opacity-40"
                  >
                    {actionBusy
                      ? t('workspace.workflow.workObject.action.processing')
                      : t('workspace.workflow.workObject.action.advanceTo', {
                        phase: t(`workspace.workflow.workObject.phase.${nextDetailPhase}`),
                      })}
                  </button>
                )}
                {canClose(detail.work_object.execution.current_phase) && (
                  <button
                    disabled={actionBusy}
                    onClick={() => {
                      setShowCloseModal(true);
                      setCloseReason('');
                    }}
                    data-testid="work-object-close-btn"
                    className="rounded-lg border border-ds-border px-3 py-1.5 text-[11px] text-ds-muted hover:border-rose-500/50 hover:text-rose-300 disabled:opacity-40"
                  >
                    {t('workspace.workflow.workObject.action.close')}
                  </button>
                )}
              </div>

              {showCloseModal && (
                <div className="mt-2 rounded-xl border border-ds-border bg-ds-bg/80 px-3 py-3">
                  <p className="text-xs font-medium text-ds-text">
                    {t('workspace.workflow.workObject.closeReason')}
                  </p>
                  <input
                    value={closeReason}
                    onChange={(event) => setCloseReason(event.target.value)}
                    placeholder={t('workspace.workflow.workObject.closePlaceholder')}
                    data-testid="work-object-close-reason"
                    className="mt-2 w-full rounded-lg border border-ds-border bg-ds-surface px-3 py-2 text-xs text-ds-text"
                  />
                  <div className="mt-2 flex gap-2">
                    <button
                      disabled={actionBusy || !closeReason.trim()}
                      onClick={() => {
                        void runAction(async () => {
                          await close(detail.work_object.work_object_id, closeReason.trim());
                          setShowCloseModal(false);
                          setActionNotice(t('workspace.workflow.workObject.action.closed'));
                        });
                      }}
                      data-testid="work-object-close-confirm"
                      className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-[11px] text-rose-300 hover:bg-rose-500/20 disabled:opacity-40"
                    >
                      {t('workspace.workflow.workObject.action.confirmClose')}
                    </button>
                    <button
                      onClick={() => setShowCloseModal(false)}
                      className="rounded-lg border border-ds-border px-3 py-1.5 text-[11px] text-ds-muted hover:text-ds-text"
                    >
                      {t('workspace.workflow.workObject.action.cancel')}
                    </button>
                  </div>
                </div>
              )}

              <div className="mt-3 grid gap-2 text-xs text-ds-muted">
                <div>
                  {detail.work_object.request.channel
                    ? t('workspace.workflow.workObject.requestWithChannel', {
                      source: detail.work_object.request.source,
                      requestor: detail.work_object.request.requestor_display,
                      channel: detail.work_object.request.channel,
                    })
                    : t('workspace.workflow.workObject.requestWithoutChannel', {
                      source: detail.work_object.request.source,
                      requestor: detail.work_object.request.requestor_display,
                    })}
                </div>
                <div>
                  {t('workspace.workflow.workObject.runs', {
                    value: detail.work_object.execution.run_ids.join(', ') || '-',
                  })}
                </div>
                <div>
                  {t('workspace.workflow.workObject.tags', {
                    value: detail.work_object.tags.join(', ') || '-',
                  })}
                </div>
                <div>
                  {t('workspace.workflow.workObject.pendingPolicyActions', {
                    count: getPendingPolicyActionCount(detail.work_object.metadata),
                  })}
                </div>
                <div className="rounded-xl border border-ds-border bg-ds-bg/60 px-3 py-2 leading-5">
                  {detail.work_object.request.original_text}
                </div>
              </div>

              <div className="mt-4 space-y-3">
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-ds-muted">
                    {t('workspace.workflow.workObject.documentation')}
                  </p>
                  {detail.work_object.documentation.references.length === 0 ? (
                    <p className="mt-2 text-xs text-ds-muted">
                      {t('workspace.workflow.workObject.noDocumentation')}
                    </p>
                  ) : (
                    <div className="mt-2 space-y-2">
                      {detail.work_object.documentation.references.map((reference) => (
                        <div
                          key={reference.idempotency_key}
                          className="rounded-xl border border-ds-border bg-ds-bg/60 px-3 py-2 text-xs text-ds-muted"
                        >
                          {formatExternalReferenceLabel(reference)}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <p className="text-[11px] uppercase tracking-wide text-ds-muted">
                    {t('workspace.workflow.workObject.followUp')}
                  </p>
                  {detail.work_object.follow_up.actions.length === 0 ? (
                    <p className="mt-2 text-xs text-ds-muted">
                      {t('workspace.workflow.workObject.noFollowUp')}
                    </p>
                  ) : (
                    <div className="mt-2 space-y-2">
                      {detail.work_object.follow_up.actions.map((action) => (
                        <div
                          key={action.external_ref.idempotency_key}
                          className="rounded-xl border border-ds-border bg-ds-bg/60 px-3 py-2 text-xs text-ds-muted"
                        >
                          <div className="text-ds-text">{action.description}</div>
                          <div className="mt-1">
                            {translateFollowUpActionType(action.action_type, t)} |{' '}
                            {translateFollowUpStatus(action.status, t)} |{' '}
                            {formatExternalReferenceLabel(action.external_ref)}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <p className="text-[11px] uppercase tracking-wide text-ds-muted">
                    {t('workspace.workflow.workObject.timeline')}
                  </p>
                  {detail.timeline.length === 0 ? (
                    <p className="mt-2 text-xs text-ds-muted">
                      {t('workspace.workflow.workObject.noTimeline')}
                    </p>
                  ) : (
                    <div className="mt-2 space-y-2" data-testid="work-object-timeline">
                      {detail.timeline.map((event) => (
                        <div
                          key={event.event_id}
                          className="rounded-xl border border-ds-border bg-ds-bg/60 px-3 py-2 text-xs text-ds-muted"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-ds-text">{event.system}.{event.action}</span>
                            <span>{translateTimelineStatus(event.status, t)}</span>
                          </div>
                          <div className="mt-1">
                            {new Date(event.started_at).toLocaleString()} | {formatExternalReferenceLabel(event.external_ref)}
                          </div>
                          {event.error_message && <div className="mt-1 text-rose-200">{event.error_message}</div>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function translateFollowUpActionType(value: string, t: TranslateFn): string {
  const keyByActionType: Record<string, string> = {
    ticket: 'workspace.workflow.workObject.followUp.actionType.ticket',
    calendar: 'workspace.workflow.workObject.followUp.actionType.calendar',
    message: 'workspace.workflow.workObject.followUp.actionType.message',
    dashboard_update: 'workspace.workflow.workObject.followUp.actionType.dashboardUpdate',
  };
  const key = keyByActionType[value];
  return key ? t(key) : value;
}

function translateFollowUpStatus(value: string, t: TranslateFn): string {
  const keyByStatus: Record<string, string> = {
    pending: 'workspace.workflow.workObject.followUp.status.pending',
    completed: 'workspace.workflow.workObject.followUp.status.completed',
    cancelled: 'workspace.workflow.workObject.followUp.status.cancelled',
  };
  const key = keyByStatus[value];
  return key ? t(key) : value;
}

function translateTimelineStatus(value: string, t: TranslateFn): string {
  const keyByStatus: Record<string, string> = {
    pending: 'workspace.workflow.workObject.timeline.status.pending',
    success: 'workspace.workflow.workObject.timeline.status.success',
    failed: 'workspace.workflow.workObject.timeline.status.failed',
    dlq: 'workspace.workflow.workObject.timeline.status.dlq',
    duplicate: 'workspace.workflow.workObject.timeline.status.duplicate',
  };
  const key = keyByStatus[value];
  return key ? t(key) : value;
}
