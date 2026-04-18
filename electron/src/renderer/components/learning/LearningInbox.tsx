import { useEffect, useState } from 'react';
import { useLearning } from '../../hooks/useLearning';
import type { LearningItemView } from '../../hooks/useLearning';

const TYPE_STYLES: Record<string, string> = {
  pattern: 'bg-sky-500/15 text-sky-300 border-sky-500/40',
  kb_entry: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
  custom_skill: 'bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/40',
};

const STATUS_STYLES: Record<string, string> = {
  proposed: 'text-amber-300',
  under_review: 'text-sky-300',
  approved: 'text-emerald-300',
  rejected: 'text-rose-300',
  promoted: 'text-fuchsia-300',
};

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
  return (
    <button
      type="button"
      onClick={onSelect}
      data-testid={`learning-item-${item.item_id}`}
      className={`w-full rounded-xl border px-3 py-2 text-left ${
        selected
          ? 'border-ds-accent bg-ds-surface'
          : 'border-ds-border bg-ds-surface/70 hover:border-ds-accent/50'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-xs font-medium text-ds-text">{item.title}</span>
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${typeStyle}`}>
          {item.type}
        </span>
      </div>
      <div className="mt-1 flex items-center gap-2 text-[10px] text-ds-muted">
        <span className={STATUS_STYLES[item.status] || ''}>{item.status}</span>
        <span>score: {item.priority_score.toFixed(2)}</span>
        <span>evidence: {item.evidence_count}</span>
        {item.conflict_count > 0 && (
          <span className="text-amber-300">conflicts: {item.conflict_count}</span>
        )}
      </div>
      {item.tags.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {item.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-ds-border bg-ds-bg px-1.5 py-0.5 text-[9px] text-ds-muted"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </button>
  );
}

export function LearningInbox() {
  const { inbox, loading, error, refreshInbox, reviewItem } = useLearning();
  const [statusFilter, setStatusFilter] = useState('proposed');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    void refreshInbox(statusFilter);
  }, [refreshInbox, statusFilter]);

  const handleReview = async (decision: string) => {
    if (!selectedId) return;
    setActionBusy(true);
    setActionError(null);
    try {
      await reviewItem(selectedId, decision);
      setSelectedId(null);
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
          <p className="mt-1 text-[11px] text-ds-muted">
            {inbox.total} items in inbox
          </p>
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

      <div className="mt-3">
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
      </div>

      {error && (
        <div className="mt-3 rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
          {error}
        </div>
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

      {selectedId && (
        <div className="mt-3 rounded-xl border border-ds-border bg-ds-surface px-3 py-3" data-testid="learning-review-actions">
          {actionError && (
            <div className="mb-2 text-xs text-rose-200">{actionError}</div>
          )}
          <div className="flex gap-2">
            <button
              disabled={actionBusy}
              onClick={() => void handleReview('approve')}
              data-testid="learning-approve-btn"
              className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-[11px] text-emerald-300 hover:bg-emerald-500/20 disabled:opacity-40"
            >
              Approve
            </button>
            <button
              disabled={actionBusy}
              onClick={() => void handleReview('reject')}
              data-testid="learning-reject-btn"
              className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-[11px] text-rose-300 hover:bg-rose-500/20 disabled:opacity-40"
            >
              Reject
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
