import { useEffect } from 'react';
import { usePortfolio } from '../../hooks/usePortfolio';
import type { PortfolioEntryView } from '../../hooks/usePortfolio';

const PRIORITY_STYLES: Record<string, string> = {
  P0: 'bg-rose-500/15 text-rose-300 border-rose-500/40',
  P1: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
  P2: 'bg-sky-500/15 text-sky-300 border-sky-500/40',
  P3: 'bg-slate-500/15 text-slate-300 border-slate-500/40',
};

function EntryCard({ entry }: { entry: PortfolioEntryView }) {
  const priorityStyle = PRIORITY_STYLES[entry.priority] || PRIORITY_STYLES.P2;
  return (
    <div
      className="rounded-xl border border-ds-border bg-ds-surface/70 px-3 py-2"
      data-testid={`portfolio-entry-${entry.entry_id}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-xs font-medium text-ds-text">{entry.entry_id}</span>
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${priorityStyle}`}>
          {entry.priority}
        </span>
      </div>
      <p className="mt-1 text-[11px] text-ds-muted">{entry.task_contract_id}</p>
      {entry.sla_deadline && (
        <p className="mt-0.5 text-[10px] text-ds-muted">
          SLA: {new Date(entry.sla_deadline).toLocaleString()}
        </p>
      )}
      {entry.tags.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {entry.tags.map((tag) => (
            <span key={tag} className="rounded-full border border-ds-border bg-ds-bg px-1.5 py-0.5 text-[9px] text-ds-muted">
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function QuadrantPanel({
  title,
  entries,
  testId,
  accentColor,
}: {
  title: string;
  entries: PortfolioEntryView[];
  testId: string;
  accentColor: string;
}) {
  return (
    <div
      className={`rounded-2xl border ${accentColor} bg-ds-bg px-3 py-3`}
      data-testid={testId}
    >
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-xs font-semibold text-ds-text">{title}</h4>
        <span className="text-[10px] text-ds-muted">{entries.length}</span>
      </div>
      {entries.length === 0 ? (
        <p className="mt-2 text-[11px] text-ds-muted">No entries</p>
      ) : (
        <div className="mt-2 space-y-2">
          {entries.map((e) => (
            <EntryCard key={e.entry_id} entry={e} />
          ))}
        </div>
      )}
    </div>
  );
}

export function ProjectControlTower() {
  const { overview, loading, error, refresh } = usePortfolio();

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <section
      className="mx-3 rounded-2xl border border-ds-border bg-ds-bg px-4 py-4"
      data-testid="project-control-tower"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ds-text">Portfolio Control Tower</h3>
          <p className="mt-1 text-[11px] text-ds-muted" data-testid="portfolio-slot-usage">
            Slots: {overview.slots.active}/{overview.slots.max} ({overview.slots.available} available)
          </p>
        </div>
        <button
          onClick={() => void refresh()}
          disabled={loading}
          className="rounded-lg border border-ds-border px-3 py-1.5 text-[11px] text-ds-muted hover:border-ds-accent hover:text-ds-text disabled:opacity-40"
          data-testid="portfolio-refresh-btn"
        >
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div className="mt-3 rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
          {error}
        </div>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-2" data-testid="portfolio-grid">
        <QuadrantPanel
          title="Active"
          entries={overview.active}
          testId="portfolio-quadrant-active"
          accentColor="border-emerald-500/30"
        />
        <QuadrantPanel
          title="Waiting"
          entries={overview.waiting}
          testId="portfolio-quadrant-waiting"
          accentColor="border-amber-500/30"
        />
        <QuadrantPanel
          title="Monitoring"
          entries={overview.monitoring}
          testId="portfolio-quadrant-monitoring"
          accentColor="border-sky-500/30"
        />
        <QuadrantPanel
          title="Candidates"
          entries={overview.candidates}
          testId="portfolio-quadrant-candidates"
          accentColor="border-fuchsia-500/30"
        />
      </div>
    </section>
  );
}
