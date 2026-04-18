import { useEffect, useMemo, useState } from 'react';
import { useWorkObjects } from '../../hooks/useWorkObjects';
import type { WorkObjectPhase } from '../../types/workObject';
import {
  canAdvance,
  canClose,
  filterWorkObjectItems,
  formatExternalReferenceLabel,
  formatWorkObjectPhaseLabel,
  getPendingPolicyActionCount,
  nextPhase,
} from './workObjectPanelModel';

const PHASE_OPTIONS: Array<{ value: WorkObjectPhase | 'all'; label: string }> = [
  { value: 'all', label: 'All phases' },
  { value: 'intake', label: 'Intake' },
  { value: 'executing', label: 'Executing' },
  { value: 'review', label: 'Review' },
  { value: 'documenting', label: 'Documenting' },
  { value: 'followup', label: 'Follow-up' },
  { value: 'closed', label: 'Closed' },
  { value: 'failed', label: 'Failed' },
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

  useEffect(() => {
    if (filteredItems.length === 0) {
      setSelectedWorkObjectId(null);
      return;
    }
    if (!selectedWorkObjectId || !filteredItems.some((item) => item.work_object_id === selectedWorkObjectId)) {
      setSelectedWorkObjectId(filteredItems[0].work_object_id);
    }
  }, [filteredItems, selectedWorkObjectId]);

  if (!sessionId) {
    return (
      <section className="mx-3 rounded-2xl border border-ds-border bg-ds-bg px-4 py-3">
        <h3 className="text-sm font-semibold text-ds-text">Work Objects</h3>
        <p className="mt-2 text-xs leading-5 text-ds-muted">
          Start a chat turn first. Workflow-linked work objects appear here for the active session.
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
          <h3 className="text-sm font-semibold text-ds-text">Work Objects</h3>
          <p className="mt-1 text-[11px] text-ds-muted">Session: {sessionId}</p>
        </div>
        <button
          onClick={() => void refresh()}
          className="rounded-lg border border-ds-border px-3 py-1.5 text-[11px] text-ds-muted hover:border-ds-accent hover:text-ds-text"
        >
          Refresh
        </button>
      </div>

      <div className="mt-3 grid gap-2">
        <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_140px]">
          <input
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            placeholder="Search work object or task id"
            data-testid="work-object-search"
            className="min-w-0 rounded-xl border border-ds-border bg-ds-surface px-3 py-2 text-xs text-ds-text"
          />
          <select
            value={phaseFilter}
            onChange={(event) => setPhaseFilter(event.target.value as WorkObjectPhase | 'all')}
            data-testid="work-object-phase-filter"
            className="rounded-xl border border-ds-border bg-ds-surface px-3 py-2 text-xs text-ds-text"
          >
            {PHASE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading && <p className="mt-3 text-xs text-ds-muted">Loading work objects...</p>}

      {error && (
        <div className="mt-3 rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
          {error}
        </div>
      )}

      {!loading && filteredItems.length === 0 && !error && (
        <p className="mt-3 text-xs leading-5 text-ds-muted">
          No workflow-linked work objects for this session yet.
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
                    {formatWorkObjectPhaseLabel(item.phase)}
                  </span>
                </div>
                <p className="mt-2 text-sm font-medium text-ds-text">{item.title}</p>
                <p className="mt-1 text-[11px] text-ds-muted">
                  {item.task_contract_id} | refs {item.reference_count} | follow-up {item.follow_up_count}
                </p>
              </button>
            ))}
          </div>

          {detailLoading && (
            <div className="rounded-2xl border border-ds-border bg-ds-surface px-4 py-3 text-xs text-ds-muted">
              Loading selected work object...
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
                    {detail.work_object.work_object_id} | task {detail.work_object.execution.task_contract_id}
                  </p>
                </div>
                <span
                  className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${PHASE_BADGES[detail.work_object.execution.current_phase]}`}
                >
                  {formatWorkObjectPhaseLabel(detail.work_object.execution.current_phase)}
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
                {canAdvance(detail.work_object.execution.current_phase) && (
                  <button
                    disabled={actionBusy}
                    onClick={() => {
                      const next = nextPhase(detail.work_object.execution.current_phase);
                      if (!next) return;
                      void runAction(async () => {
                        await advance(detail.work_object.work_object_id, next);
                        setActionNotice(`Advanced to ${formatWorkObjectPhaseLabel(next)}.`);
                      });
                    }}
                    data-testid="work-object-advance-btn"
                    className="rounded-lg border border-ds-accent bg-ds-accent/10 px-3 py-1.5 text-[11px] font-medium text-ds-accent hover:bg-ds-accent/20 disabled:opacity-40"
                  >
                    {actionBusy ? 'Processing...' : `Advance to ${formatWorkObjectPhaseLabel(nextPhase(detail.work_object.execution.current_phase)!)}`}
                  </button>
                )}
                {canClose(detail.work_object.execution.current_phase) && (
                  <button
                    disabled={actionBusy}
                    onClick={() => { setShowCloseModal(true); setCloseReason(''); }}
                    data-testid="work-object-close-btn"
                    className="rounded-lg border border-ds-border px-3 py-1.5 text-[11px] text-ds-muted hover:border-rose-500/50 hover:text-rose-300 disabled:opacity-40"
                  >
                    Close
                  </button>
                )}
              </div>

              {showCloseModal && (
                <div className="mt-2 rounded-xl border border-ds-border bg-ds-bg/80 px-3 py-3">
                  <p className="text-xs font-medium text-ds-text">Close reason</p>
                  <input
                    value={closeReason}
                    onChange={(e) => setCloseReason(e.target.value)}
                    placeholder="Enter close reason..."
                    data-testid="work-object-close-reason"
                    className="mt-2 w-full rounded-lg border border-ds-border bg-ds-surface px-3 py-2 text-xs text-ds-text"
                  />
                  <div className="mt-2 flex gap-2">
                    <button
                      disabled={actionBusy || !closeReason.trim()}
                      onClick={() => {
                        void runAction(async () => {
                          await close(detail!.work_object.work_object_id, closeReason.trim());
                          setShowCloseModal(false);
                          setActionNotice('Work object closed.');
                        });
                      }}
                      data-testid="work-object-close-confirm"
                      className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-[11px] text-rose-300 hover:bg-rose-500/20 disabled:opacity-40"
                    >
                      Confirm Close
                    </button>
                    <button
                      onClick={() => setShowCloseModal(false)}
                      className="rounded-lg border border-ds-border px-3 py-1.5 text-[11px] text-ds-muted hover:text-ds-text"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              <div className="mt-3 grid gap-2 text-xs text-ds-muted">
                <div>
                  Request: {detail.work_object.request.source} by {detail.work_object.request.requestor_display}
                  {detail.work_object.request.channel ? ` in ${detail.work_object.request.channel}` : ''}
                </div>
                <div>Runs: {detail.work_object.execution.run_ids.join(', ') || '-'}</div>
                <div>Tags: {detail.work_object.tags.join(', ') || '-'}</div>
                <div>
                  Pending policy actions: {getPendingPolicyActionCount(detail.work_object.metadata)}
                </div>
                <div className="rounded-xl border border-ds-border bg-ds-bg/60 px-3 py-2 leading-5">
                  {detail.work_object.request.original_text}
                </div>
              </div>

              <div className="mt-4 space-y-3">
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-ds-muted">Documentation</p>
                  {detail.work_object.documentation.references.length === 0 ? (
                    <p className="mt-2 text-xs text-ds-muted">No external documentation references yet.</p>
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
                  <p className="text-[11px] uppercase tracking-wide text-ds-muted">Follow-up</p>
                  {detail.work_object.follow_up.actions.length === 0 ? (
                    <p className="mt-2 text-xs text-ds-muted">No follow-up actions recorded yet.</p>
                  ) : (
                    <div className="mt-2 space-y-2">
                      {detail.work_object.follow_up.actions.map((action) => (
                        <div
                          key={action.external_ref.idempotency_key}
                          className="rounded-xl border border-ds-border bg-ds-bg/60 px-3 py-2 text-xs text-ds-muted"
                        >
                          <div className="text-ds-text">{action.description}</div>
                          <div className="mt-1">
                            {action.action_type} | {action.status} | {formatExternalReferenceLabel(action.external_ref)}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <p className="text-[11px] uppercase tracking-wide text-ds-muted">Timeline</p>
                  {detail.timeline.length === 0 ? (
                    <p className="mt-2 text-xs text-ds-muted">No integration events recorded yet.</p>
                  ) : (
                    <div className="mt-2 space-y-2" data-testid="work-object-timeline">
                      {detail.timeline.map((event) => (
                        <div
                          key={event.event_id}
                          className="rounded-xl border border-ds-border bg-ds-bg/60 px-3 py-2 text-xs text-ds-muted"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-ds-text">{event.system}.{event.action}</span>
                            <span>{event.status}</span>
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
