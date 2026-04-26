import { useCallback, useEffect, useState } from 'react';
import { usePortfolio } from '../../hooks/usePortfolio';
import type { PortfolioEntryView } from '../../hooks/usePortfolio';
import { useI18n } from '../../stores/i18nStore';

const PRIORITY_STYLES: Record<string, string> = {
  P0: 'bg-rose-500/15 text-rose-300 border-rose-500/40',
  P1: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
  P2: 'bg-sky-500/15 text-sky-300 border-sky-500/40',
  P3: 'bg-slate-500/15 text-slate-300 border-slate-500/40',
};

const PRIORITY_OPTIONS = ['P0', 'P1', 'P2', 'P3'] as const;

function EntryCard({
  entry,
  onPause,
  onResume,
  onSetSla,
}: {
  entry: PortfolioEntryView;
  onPause: (entryId: string) => Promise<void>;
  onResume: (entryId: string, runId: string) => Promise<void>;
  onSetSla: (entryId: string, priority: string, deadline?: string) => Promise<void>;
}) {
  const { t } = useI18n();
  const priorityStyle = PRIORITY_STYLES[entry.priority] || PRIORITY_STYLES.P2;
  const isWaiting = entry.quadrant === 'waiting';
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [priorityDraft, setPriorityDraft] = useState<string>(entry.priority);

  const runAction = async (fn: () => Promise<void>) => {
    setBusy(true);
    setActionError(null);
    try {
      await fn();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const handlePause = () => void runAction(() => onPause(entry.entry_id));
  const handleResume = () => {
    if (!entry.parent_run_id) {
      setActionError(t('sidebar.portfolio.entry.error.missingRunId'));
      return;
    }
    void runAction(() => onResume(entry.entry_id, entry.parent_run_id as string));
  };
  const handleApplyPriority = () =>
    void runAction(() =>
      onSetSla(entry.entry_id, priorityDraft, entry.sla_deadline ?? undefined),
    );

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
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {isWaiting ? (
          <button
            type="button"
            onClick={handleResume}
            disabled={busy}
            className="rounded-md border border-ds-border bg-ds-bg px-2 py-0.5 text-[10px] text-ds-text hover:border-ds-accent disabled:opacity-40"
            data-testid={`portfolio-entry-${entry.entry_id}-resume`}
          >
            {t('sidebar.portfolio.entry.resume')}
          </button>
        ) : (
          <button
            type="button"
            onClick={handlePause}
            disabled={busy}
            className="rounded-md border border-ds-border bg-ds-bg px-2 py-0.5 text-[10px] text-ds-text hover:border-ds-accent disabled:opacity-40"
            data-testid={`portfolio-entry-${entry.entry_id}-pause`}
          >
            {t('sidebar.portfolio.entry.pause')}
          </button>
        )}
        <label className="sr-only" htmlFor={`portfolio-entry-${entry.entry_id}-priority`}>
          {t('sidebar.portfolio.entry.priorityLabel')}
        </label>
        <select
          id={`portfolio-entry-${entry.entry_id}-priority`}
          value={priorityDraft}
          onChange={(event) => setPriorityDraft(event.target.value)}
          disabled={busy}
          className="rounded-md border border-ds-border bg-ds-bg px-1.5 py-0.5 text-[10px] text-ds-text disabled:opacity-40"
          data-testid={`portfolio-entry-${entry.entry_id}-priority`}
        >
          {PRIORITY_OPTIONS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={handleApplyPriority}
          disabled={busy || priorityDraft === entry.priority}
          className="rounded-md border border-ds-border bg-ds-bg px-2 py-0.5 text-[10px] text-ds-text hover:border-ds-accent disabled:opacity-40"
          data-testid={`portfolio-entry-${entry.entry_id}-apply-sla`}
        >
          {t('sidebar.portfolio.entry.applySla')}
        </button>
      </div>
      {actionError && (
        <p
          role="alert"
          className="mt-1 text-[10px] text-rose-300"
          data-testid={`portfolio-entry-${entry.entry_id}-error`}
        >
          {actionError}
        </p>
      )}
    </div>
  );
}

function QuadrantPanel({
  title,
  entries,
  testId,
  accentColor,
  onPause,
  onResume,
  onSetSla,
}: {
  title: string;
  entries: PortfolioEntryView[];
  testId: string;
  accentColor: string;
  onPause: (entryId: string) => Promise<void>;
  onResume: (entryId: string, runId: string) => Promise<void>;
  onSetSla: (entryId: string, priority: string, deadline?: string) => Promise<void>;
}) {
  const { t } = useI18n();
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
        <p className="mt-2 text-[11px] text-ds-muted">{t('sidebar.portfolio.quadrant.empty')}</p>
      ) : (
        <div className="mt-2 space-y-2">
          {entries.map((e) => (
            <EntryCard
              key={e.entry_id}
              entry={e}
              onPause={onPause}
              onResume={onResume}
              onSetSla={onSetSla}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function ProjectControlTower() {
  const { t } = useI18n();
  const { overview, loading, error, refresh, pause, resume, setSla } = usePortfolio();

  const handlePause = useCallback(
    (entryId: string) => pause(entryId, 'timer', {}, 'paused via UI'),
    [pause],
  );
  const handleResume = useCallback(
    (entryId: string, runId: string) => resume(entryId, runId, 'resumed via UI'),
    [resume],
  );
  const handleSetSla = useCallback(
    (entryId: string, priority: string, deadline?: string) =>
      setSla(entryId, priority, deadline),
    [setSla],
  );

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
          <h3 className="text-sm font-semibold text-ds-text">{t('sidebar.portfolio.title')}</h3>
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
          {loading ? t('sidebar.portfolio.loading') : t('sidebar.portfolio.refresh')}
        </button>
      </div>

      {error && (
        <div className="mt-3 rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
          {error}
        </div>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-2" data-testid="portfolio-grid">
        <QuadrantPanel
          title={t('sidebar.portfolio.quadrant.active')}
          entries={overview.active}
          testId="portfolio-quadrant-active"
          accentColor="border-emerald-500/30"
          onPause={handlePause}
          onResume={handleResume}
          onSetSla={handleSetSla}
        />
        <QuadrantPanel
          title={t('sidebar.portfolio.quadrant.waiting')}
          entries={overview.waiting}
          testId="portfolio-quadrant-waiting"
          accentColor="border-amber-500/30"
          onPause={handlePause}
          onResume={handleResume}
          onSetSla={handleSetSla}
        />
        <QuadrantPanel
          title={t('sidebar.portfolio.quadrant.monitoring')}
          entries={overview.monitoring}
          testId="portfolio-quadrant-monitoring"
          accentColor="border-sky-500/30"
          onPause={handlePause}
          onResume={handleResume}
          onSetSla={handleSetSla}
        />
        <QuadrantPanel
          title={t('sidebar.portfolio.quadrant.candidates')}
          entries={overview.candidates}
          testId="portfolio-quadrant-candidates"
          accentColor="border-fuchsia-500/30"
          onPause={handlePause}
          onResume={handleResume}
          onSetSla={handleSetSla}
        />
      </div>
    </section>
  );
}
