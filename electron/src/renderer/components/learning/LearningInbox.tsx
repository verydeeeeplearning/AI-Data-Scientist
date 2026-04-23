import { useEffect, useState } from 'react';
import {
  extractFailureTaxonomyCandidateSummary,
  extractHarnessWarningReviewSummary,
  isHarnessWarningLearningItem,
  normalizeLearningItemDetail,
  useLearning,
} from '../../hooks/useLearning';
import type {
  LearningGovernanceStatusView,
  LearningItemDetailView,
  LearningItemView,
} from '../../hooks/useLearning';

const TYPE_STYLES: Record<string, string> = {
  pattern: 'border-sky-500/40 bg-sky-500/15 text-sky-300',
  kb_entry: 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300',
  custom_skill: 'border-fuchsia-500/40 bg-fuchsia-500/15 text-fuchsia-300',
};

const STATUS_STYLES: Record<string, string> = {
  proposed: 'text-amber-300',
  under_review: 'text-sky-300',
  approved: 'text-emerald-300',
  rejected: 'text-rose-300',
  promoted: 'text-fuchsia-300',
};

const WARNING_SEVERITY_STYLES: Record<string, string> = {
  high: 'border-rose-500/40 bg-rose-500/10 text-rose-200',
  medium: 'border-amber-500/40 bg-amber-500/10 text-amber-200',
  low: 'border-sky-500/40 bg-sky-500/10 text-sky-200',
};

const WARNING_META_PILL =
  'rounded-full border border-ds-border bg-ds-bg px-1.5 py-0.5 text-[9px] text-ds-muted';

function formatLabel(value: string): string {
  return value
    .split(/[_:-]+/g)
    .filter((segment) => segment.length > 0)
    .map((segment) => segment[0].toUpperCase() + segment.slice(1))
    .join(' ');
}

function formatTimestamp(value?: string): string | null {
  if (!value) {
    return null;
  }

  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return null;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(timestamp);
}

function formatJsonPreview(payload: Record<string, unknown>): string {
  const rendered = JSON.stringify(payload, null, 2) ?? '';
  return rendered.length > 1200 ? `${rendered.slice(0, 1200)}\n...` : rendered;
}

function formatRecurrenceLabel(count: number): string {
  return count <= 1 ? 'First seen' : `Repeated x${count}`;
}

function formatMaybeTimestamp(value: string | null | undefined): string | null {
  return value ? formatTimestamp(value) ?? value : null;
}

function TagPill({ tag }: { tag: string }) {
  return (
    <span className="rounded-full border border-ds-border bg-ds-bg px-1.5 py-0.5 text-[9px] text-ds-muted">
      {tag}
    </span>
  );
}

function ItemCard({
  item,
  onSelect,
  selected,
}: {
  item: LearningItemView;
  onSelect: () => void;
  selected: boolean;
}) {
  const typeStyle = TYPE_STYLES[item.type] || TYPE_STYLES.kb_entry;
  const warningSummary = extractHarnessWarningReviewSummary(item);
  const candidateSummary = extractFailureTaxonomyCandidateSummary(item);

  return (
    <button
      type="button"
      onClick={onSelect}
      data-testid={`learning-item-${item.item_id}`}
      className={`w-full rounded-xl border px-3 py-2 text-left transition-colors ${
        selected
          ? 'border-ds-accent bg-ds-surface'
          : 'border-ds-border bg-ds-surface/70 hover:border-ds-accent/50'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-xs font-medium text-ds-text">{item.title}</div>
          {warningSummary && (
            <div className="mt-1 text-[10px] text-ds-muted">
              {formatLabel(warningSummary.warningType)}
              {warningSummary.surface ? ` / ${warningSummary.surface}` : ''}
            </div>
          )}
        </div>
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${typeStyle}`}>
          {item.type}
        </span>
      </div>

      <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-ds-muted">
        <span className={STATUS_STYLES[item.status] || ''}>{item.status}</span>
        <span>score: {item.priority_score.toFixed(2)}</span>
        <span>evidence: {item.evidence_count}</span>
        {item.conflict_count > 0 && (
          <span className="text-amber-300">conflicts: {item.conflict_count}</span>
        )}
      </div>

      {warningSummary && (
        <div className="mt-2 flex flex-wrap gap-1">
          <span className={WARNING_META_PILL}>harness warning</span>
          <span
            className={`rounded-full border px-1.5 py-0.5 text-[9px] ${
              WARNING_SEVERITY_STYLES[warningSummary.severity] || WARNING_SEVERITY_STYLES.medium
            }`}
          >
            {warningSummary.severity}
          </span>
          {warningSummary.taxonomyClass && (
            <span className={WARNING_META_PILL} data-testid={`learning-item-taxonomy-${item.item_id}`}>
              {formatLabel(warningSummary.taxonomyClass)}
            </span>
          )}
          {candidateSummary?.candidateId && (
            <span className={WARNING_META_PILL}>
              candidate {formatLabel(candidateSummary.status ?? 'pending_promotion')}
            </span>
          )}
          <span className={WARNING_META_PILL} data-testid={`learning-item-recurrence-${item.item_id}`}>
            {formatRecurrenceLabel(warningSummary.recurrenceCount)}
          </span>
        </div>
      )}

      {item.tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {item.tags.slice(0, warningSummary ? 4 : 3).map((tag) => (
            <TagPill key={tag} tag={tag} />
          ))}
        </div>
      )}

      {item.sourceKinds && item.sourceKinds.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1" data-testid={`learning-item-source-kinds-${item.item_id}`}>
          {item.sourceKinds.map((kind) => (
            <span
              key={kind}
              className="rounded-full border border-violet-500/40 bg-violet-500/10 px-1.5 py-0.5 text-[9px] text-violet-300"
            >
              {formatLabel(kind)}
            </span>
          ))}
        </div>
      )}
    </button>
  );
}

function DetailStat({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string | number;
  mono?: boolean;
}) {
  return (
    <div className="rounded-xl border border-ds-border bg-ds-bg/70 px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">{label}</div>
      <div className={`mt-1 text-xs text-ds-text ${mono ? 'font-mono' : ''}`}>{value}</div>
    </div>
  );
}

function GovernanceStatusSummary({
  status,
  reviewEnabled,
}: {
  status: LearningGovernanceStatusView;
  reviewEnabled: boolean;
}) {
  const nextRunAt = formatMaybeTimestamp(status.standingOrder?.nextRunAt);
  const lastRunAt = formatMaybeTimestamp(status.standingOrder?.lastRunAt);
  const lastGcAt = formatMaybeTimestamp(status.backlog.lastGcAt);
  const lastCompletedAt = formatMaybeTimestamp(status.latestCompletedRun?.recordedAt);
  const promotionClasses = status.latestCompletedRun?.promotionCandidateClasses.length
    ? status.latestCompletedRun.promotionCandidateClasses
    : status.backlog.promotionCandidateClasses;

  return (
    <div
      className="mt-3 rounded-2xl border border-ds-border bg-ds-surface px-3 py-3"
      data-testid="learning-governance-summary"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold text-ds-text">GC Operational Snapshot</div>
          <p className="mt-1 text-[11px] text-ds-muted">
            {reviewEnabled
              ? 'Review actions are enabled for this workspace.'
              : 'Read-only visibility is available, but review actions are disabled.'}
          </p>
        </div>
        {status.standingOrder?.cron && (
          <span className={WARNING_META_PILL}>{status.standingOrder.cron}</span>
        )}
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <DetailStat label="Active Warnings" value={status.backlog.activeWarningItems} />
        <DetailStat label="Recurrences" value={status.backlog.activeWarningRecurrences} />
        <DetailStat label="Promotion Items" value={status.backlog.promotionCandidateItems} />
        <DetailStat
          label="Next GC"
          value={nextRunAt ?? status.standingOrder?.cron ?? 'Not scheduled'}
        />
      </div>

      {(lastRunAt || lastGcAt || lastCompletedAt) && (
        <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-ds-muted">
          {lastRunAt && <span>Last scheduled run: {lastRunAt}</span>}
          {lastCompletedAt && <span>Last completed: {lastCompletedAt}</span>}
          {lastGcAt && <span>Latest taxonomy stamp: {lastGcAt}</span>}
        </div>
      )}

      {promotionClasses.length > 0 && (
        <div className="mt-3">
          <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">
            Promotion Candidates
          </div>
          <div className="mt-2 flex flex-wrap gap-1">
            {promotionClasses.map((failureClass) => (
              <span key={failureClass} className={WARNING_META_PILL}>
                {formatLabel(failureClass)}
              </span>
            ))}
          </div>
        </div>
      )}

      {status.latestCompletedRun?.summary && (
        <div className="mt-3 rounded-xl border border-ds-border bg-ds-bg/70 px-3 py-2 text-xs text-ds-text">
          {status.latestCompletedRun.summary}
        </div>
      )}

      {status.latestReport?.path && (
        <div className="mt-3 text-[11px] text-ds-muted">
          Latest report: <span className="font-mono text-ds-text">{status.latestReport.path}</span>
        </div>
      )}
    </div>
  );
}

function DetailPanel({
  item,
  reviewEnabled,
  loading,
  error,
  actionBusy,
  actionError,
  onApprove,
  onReject,
  onFinalizePromotion,
}: {
  item: LearningItemDetailView;
  reviewEnabled: boolean;
  loading: boolean;
  error: string | null;
  actionBusy: boolean;
  actionError: string | null;
  onApprove: () => void;
  onReject: () => void;
  onFinalizePromotion: (values: {
    candidateId: string;
    candidateScore: string;
    baselineScore: string;
    passedTasks: string;
    totalTasks: string;
    deltaThreshold: string;
  }) => void;
}) {
  const warningSummary = extractHarnessWarningReviewSummary(item);
  const candidateSummary = extractFailureTaxonomyCandidateSummary(item);
  const createdAt = formatTimestamp(item.created_at);
  const updatedAt = formatTimestamp(item.updated_at);
  const typeStyle = TYPE_STYLES[item.type] || TYPE_STYLES.kb_entry;
  const firstSeenAt = warningSummary?.firstSeenAt
    ? formatTimestamp(warningSummary.firstSeenAt) ?? warningSummary.firstSeenAt
    : null;
  const lastSeenAt = warningSummary?.lastSeenAt
    ? formatTimestamp(warningSummary.lastSeenAt) ?? warningSummary.lastSeenAt
    : null;
  const [candidateScore, setCandidateScore] = useState('0.82');
  const [baselineScore, setBaselineScore] = useState('0.80');
  const [passedTasks, setPassedTasks] = useState('1');
  const [totalTasks, setTotalTasks] = useState('1');
  const [deltaThreshold, setDeltaThreshold] = useState('0.03');

  useEffect(() => {
    setCandidateScore('0.82');
    setBaselineScore('0.80');
    setPassedTasks('1');
    setTotalTasks('1');
    setDeltaThreshold('0.03');
  }, [candidateSummary?.candidateId, item.item_id]);

  return (
    <div
      className="mt-3 rounded-2xl border border-ds-border bg-ds-surface px-3 py-3"
      data-testid="learning-item-detail"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="truncate text-sm font-semibold text-ds-text">{item.title}</h4>
          <p className="mt-1 text-[11px] text-ds-muted">
            {warningSummary
              ? 'Harness warning proposal queued for learning governance review.'
              : 'Review the proposal details before approving or rejecting it.'}
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-1">
          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${typeStyle}`}>
            {item.type}
          </span>
          <span className={`text-[11px] ${STATUS_STYLES[item.status] || 'text-ds-muted'}`}>
            {item.status}
          </span>
        </div>
      </div>

      {error && (
        <div className="mt-3 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
          Detail refresh failed: {error}
        </div>
      )}

      {warningSummary && (
        <div
          className="mt-3 rounded-xl border border-ds-border bg-ds-bg/80 px-3 py-3"
          data-testid="learning-warning-summary"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-ds-border bg-ds-surface px-2 py-0.5 text-[10px] font-semibold text-ds-text">
              {formatLabel(warningSummary.warningType)}
            </span>
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] ${
                WARNING_SEVERITY_STYLES[warningSummary.severity] || WARNING_SEVERITY_STYLES.medium
              }`}
            >
              {warningSummary.severity}
            </span>
            {warningSummary.taxonomyClass && (
              <span
                className="rounded-full border border-ds-border bg-ds-surface px-2 py-0.5 text-[10px] text-ds-muted"
                data-testid="learning-warning-taxonomy"
              >
                {formatLabel(warningSummary.taxonomyClass)}
              </span>
            )}
            <span
              className="rounded-full border border-ds-border bg-ds-surface px-2 py-0.5 text-[10px] text-ds-muted"
              data-testid="learning-warning-recurrence"
            >
              {formatRecurrenceLabel(warningSummary.recurrenceCount)}
            </span>
            {warningSummary.surface && (
              <span className="rounded-full border border-ds-border bg-ds-surface px-2 py-0.5 text-[10px] text-ds-muted">
                {warningSummary.surface}
              </span>
            )}
          </div>

          {warningSummary.message && (
            <p className="mt-3 text-xs leading-5 text-ds-text">{warningSummary.message}</p>
          )}

          {warningSummary.suggestion && (
            <div className="mt-2 rounded-xl border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-100">
              Suggestion: {warningSummary.suggestion}
            </div>
          )}

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <DetailStat label="Recurrence" value={warningSummary.recurrenceCount} />
            {warningSummary.sessionId && (
              <DetailStat label="Session" value={warningSummary.sessionId} mono />
            )}
            {warningSummary.runId && (
              <DetailStat label="Run" value={warningSummary.runId} mono />
            )}
            {firstSeenAt && <DetailStat label="First Seen" value={firstSeenAt} />}
            {lastSeenAt && <DetailStat label="Last Seen" value={lastSeenAt} />}
            {warningSummary.surfaces.length > 1 && (
              <DetailStat
                label="Surfaces"
                value={warningSummary.surfaces.map((surface) => formatLabel(surface)).join(', ')}
              />
            )}
          </div>

          {warningSummary.rawPayload && (
            <div className="mt-3">
              <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">
                Raw Payload
              </div>
              <pre
                className="mt-1 overflow-x-auto rounded-xl border border-ds-border bg-[#0d1320] px-3 py-2 text-[11px] leading-5 text-sky-100"
                data-testid="learning-warning-raw-payload"
              >
                {formatJsonPreview(warningSummary.rawPayload)}
              </pre>
            </div>
          )}
        </div>
      )}

      {!warningSummary && item.content && (
        <div className="mt-3 rounded-xl border border-ds-border bg-ds-bg/80 px-3 py-3">
          <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">Content</div>
          <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-ds-text">{item.content}</p>
        </div>
      )}

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <DetailStat label="Scope" value={item.scope} />
        <DetailStat label="Evidence" value={item.evidence_count} />
        <DetailStat label="Conflicts" value={item.conflict_count} />
        <DetailStat label="Priority" value={item.priority_score.toFixed(2)} />
        {typeof item.review_count === 'number' && (
          <DetailStat label="Reviews" value={item.review_count} />
        )}
        {createdAt && <DetailStat label="Created" value={createdAt} />}
        {updatedAt && <DetailStat label="Updated" value={updatedAt} />}
      </div>

      {item.tags.length > 0 && (
        <div className="mt-3">
          <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">Tags</div>
          <div className="mt-2 flex flex-wrap gap-1">
            {item.tags.map((tag) => (
              <TagPill key={tag} tag={tag} />
            ))}
          </div>
        </div>
      )}

      {loading && (
        <div className="mt-3 rounded-xl border border-ds-border bg-ds-bg/70 px-3 py-2 text-xs text-ds-muted">
          Refreshing item detail...
        </div>
      )}

      {candidateSummary?.candidateId && (
        <div
          className="mt-3 rounded-xl border border-fuchsia-500/30 bg-fuchsia-500/10 px-3 py-3"
          data-testid="learning-candidate-promotion"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-fuchsia-500/40 bg-fuchsia-500/15 px-2 py-0.5 text-[10px] font-semibold text-fuchsia-200">
              {candidateSummary.candidateId}
            </span>
            {candidateSummary.status && (
              <span className="rounded-full border border-ds-border bg-ds-surface px-2 py-0.5 text-[10px] text-ds-muted">
                {formatLabel(candidateSummary.status)}
              </span>
            )}
          </div>
          <p className="mt-2 text-[11px] text-ds-muted">
            Finalize this GC candidate into active custom skills with an explicit evaluation
            verdict.
          </p>

          {candidateSummary.status !== 'promoted' && (
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <label className="text-[11px] text-ds-muted">
                Candidate Score
                <input
                  value={candidateScore}
                  onChange={(event) => setCandidateScore(event.target.value)}
                  inputMode="decimal"
                  className="mt-1 w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text"
                />
              </label>
              <label className="text-[11px] text-ds-muted">
                Baseline Score
                <input
                  value={baselineScore}
                  onChange={(event) => setBaselineScore(event.target.value)}
                  inputMode="decimal"
                  className="mt-1 w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text"
                />
              </label>
              <label className="text-[11px] text-ds-muted">
                Passed Tasks
                <input
                  value={passedTasks}
                  onChange={(event) => setPassedTasks(event.target.value)}
                  inputMode="numeric"
                  className="mt-1 w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text"
                />
              </label>
              <label className="text-[11px] text-ds-muted">
                Total Tasks
                <input
                  value={totalTasks}
                  onChange={(event) => setTotalTasks(event.target.value)}
                  inputMode="numeric"
                  className="mt-1 w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text"
                />
              </label>
              <label className="text-[11px] text-ds-muted sm:col-span-2">
                Delta Threshold
                <input
                  value={deltaThreshold}
                  onChange={(event) => setDeltaThreshold(event.target.value)}
                  inputMode="decimal"
                  className="mt-1 w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text"
                />
              </label>
              <div className="sm:col-span-2">
                <button
                  disabled={actionBusy || !reviewEnabled}
                  onClick={() =>
                    onFinalizePromotion({
                      candidateId: candidateSummary.candidateId!,
                      candidateScore,
                      baselineScore,
                      passedTasks,
                      totalTasks,
                      deltaThreshold,
                    })
                  }
                  data-testid="learning-finalize-promotion-btn"
                  className="rounded-lg border border-fuchsia-500/40 bg-fuchsia-500/10 px-3 py-1.5 text-[11px] text-fuchsia-200 hover:bg-fuchsia-500/20 disabled:opacity-40"
                >
                  Finalize Promotion
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <div
        className="mt-3 rounded-xl border border-ds-border bg-ds-bg/70 px-3 py-3"
        data-testid="learning-review-actions"
      >
        {!reviewEnabled && (
          <div
            className="mb-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100"
            data-testid="learning-readonly-banner"
          >
            Review actions require the self-improve governance flag, but the inbox remains visible
            for operational inspection.
          </div>
        )}
        {actionError && <div className="mb-2 text-xs text-rose-200">{actionError}</div>}
        <div className="flex gap-2">
          <button
            disabled={actionBusy || !reviewEnabled}
            onClick={onApprove}
            data-testid="learning-approve-btn"
            className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-[11px] text-emerald-300 hover:bg-emerald-500/20 disabled:opacity-40"
          >
            Approve
          </button>
          <button
            disabled={actionBusy || !reviewEnabled}
            onClick={onReject}
            data-testid="learning-reject-btn"
            className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-[11px] text-rose-300 hover:bg-rose-500/20 disabled:opacity-40"
          >
            Reject
          </button>
        </div>
      </div>
    </div>
  );
}

export function LearningInbox() {
  const {
    enabled,
    status,
    inbox,
    loading,
    error,
    refreshInbox,
    fetchItemDetail,
    reviewItem,
    finalizeCandidatePromotion,
  } = useLearning();
  const [statusFilter, setStatusFilter] = useState('proposed');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<LearningItemDetailView | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const harnessWarnings = inbox.items.filter((item) => isHarnessWarningLearningItem(item));
  const harnessWarningRecurrences = harnessWarnings.reduce((total, item) => {
    const summary = extractHarnessWarningReviewSummary(item);
    return total + (summary?.recurrenceCount ?? 1);
  }, 0);

  useEffect(() => {
    void refreshInbox(statusFilter);
  }, [refreshInbox, statusFilter]);

  useEffect(() => {
    if (!selectedId) {
      setSelectedDetail(null);
      setDetailLoading(false);
      setDetailError(null);
      return;
    }

    const baseItem = inbox.items.find((item) => item.item_id === selectedId);
    if (!baseItem) {
      setSelectedId(null);
      setSelectedDetail(null);
      setDetailLoading(false);
      setDetailError(null);
      return;
    }

    let cancelled = false;
    setSelectedDetail(normalizeLearningItemDetail(baseItem, null));
    setDetailLoading(true);
    setDetailError(null);

    void fetchItemDetail(baseItem)
      .then((detail) => {
        if (cancelled) {
          return;
        }
        setSelectedDetail(detail ?? normalizeLearningItemDetail(baseItem, null));
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }
        setSelectedDetail(normalizeLearningItemDetail(baseItem, null));
        setDetailError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) {
          setDetailLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [fetchItemDetail, inbox.items, selectedId]);

  const handleReview = async (decision: string) => {
    if (!selectedId || !enabled) {
      return;
    }

    setActionBusy(true);
    setActionError(null);
    try {
      await reviewItem(selectedId, decision);
      setSelectedId(null);
      setSelectedDetail(null);
      setDetailLoading(false);
      setDetailError(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionBusy(false);
    }
  };

  const handleFinalizePromotion = async (values: {
    candidateId: string;
    candidateScore: string;
    baselineScore: string;
    passedTasks: string;
    totalTasks: string;
    deltaThreshold: string;
  }) => {
    if (!enabled) {
      return;
    }

    const parsedCandidateScore = Number(values.candidateScore);
    const parsedPassedTasks = Number.parseInt(values.passedTasks, 10);
    const parsedTotalTasks = Number.parseInt(values.totalTasks, 10);
    const parsedDeltaThreshold = Number(values.deltaThreshold);
    const parsedBaselineScore =
      values.baselineScore.trim().length > 0 ? Number(values.baselineScore) : undefined;

    if (
      !Number.isFinite(parsedCandidateScore) ||
      !Number.isFinite(parsedPassedTasks) ||
      !Number.isFinite(parsedTotalTasks) ||
      !Number.isFinite(parsedDeltaThreshold) ||
      (parsedBaselineScore !== undefined && !Number.isFinite(parsedBaselineScore))
    ) {
      setActionError('Finalize promotion requires numeric evaluation inputs.');
      return;
    }

    setActionBusy(true);
    setActionError(null);
    try {
      await finalizeCandidatePromotion({
        candidateId: values.candidateId,
        candidateScore: parsedCandidateScore,
        baselineScore: parsedBaselineScore,
        passedTasks: parsedPassedTasks,
        totalTasks: parsedTotalTasks,
        deltaThreshold: parsedDeltaThreshold,
      });
      setSelectedId(null);
      setSelectedDetail(null);
      setDetailLoading(false);
      setDetailError(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionBusy(false);
    }
  };

  return (
    <section
      className="mx-3 rounded-2xl border border-ds-border bg-ds-bg px-4 py-4"
      data-testid="learning-inbox"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ds-text">Learning Governance</h3>
          <p className="mt-1 text-[11px] text-ds-muted">{inbox.total} items in inbox</p>
        </div>
        <button
          onClick={() => void refreshInbox(statusFilter)}
          disabled={loading}
          className="rounded-lg border border-ds-border px-3 py-1.5 text-[11px] text-ds-muted hover:border-ds-accent hover:text-ds-text disabled:opacity-40"
          data-testid="learning-refresh-btn"
        >
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      <GovernanceStatusSummary status={status} reviewEnabled={enabled} />

      <div className="mt-3 flex items-center justify-between gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          data-testid="learning-status-filter"
          className="rounded-xl border border-ds-border bg-ds-surface px-3 py-2 text-xs text-ds-text"
        >
          <option value="proposed">Proposed</option>
          <option value="under_review">Under Review</option>
          <option value="all">All</option>
        </select>

        <div className="text-[11px] text-ds-muted">
          {harnessWarnings.length} harness warnings / {harnessWarningRecurrences} recurrences
        </div>
      </div>

      {error && (
        <div className="mt-3 rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
          {error}
        </div>
      )}

      {!loading && !enabled && !error && (
        <p className="mt-3 text-xs text-ds-muted" data-testid="learning-readonly-copy">
          Review actions are disabled for this workspace, but persisted items and GC status remain
          visible.
        </p>
      )}

      {!loading && inbox.items.length === 0 && !error && (
        <p className="mt-3 text-xs text-ds-muted">No items matching the current filter.</p>
      )}

      {inbox.items.length > 0 && (
        <div className="mt-3 space-y-2" data-testid="learning-item-list">
          {inbox.items.map((item) => (
            <ItemCard
              key={item.item_id}
              item={item}
              onSelect={() => setSelectedId(item.item_id)}
              selected={selectedId === item.item_id}
            />
          ))}
        </div>
      )}

      {!selectedDetail && inbox.items.length > 0 && (
        <div className="mt-3 rounded-xl border border-ds-border bg-ds-surface px-3 py-3 text-xs text-ds-muted">
          Select an item to inspect its learning proposal details.
        </div>
      )}

      {selectedDetail && (
        <DetailPanel
          item={selectedDetail}
          reviewEnabled={enabled}
          loading={detailLoading}
          error={detailError}
          actionBusy={actionBusy}
          actionError={actionError}
          onApprove={() => void handleReview('approve')}
          onReject={() => void handleReview('reject')}
          onFinalizePromotion={(values) => void handleFinalizePromotion(values)}
        />
      )}
    </section>
  );
}
