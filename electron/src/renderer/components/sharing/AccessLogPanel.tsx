/**
 * Owner-only access-log surface.
 */

import { RefreshCw } from 'lucide-react';
import { useEffect, useState } from 'react';

import { useAccessRole } from '../../hooks/useAccessRole';
import { useAccessLogs, type AccessLogEntrySummary } from '../../hooks/useAccessLogs';
import { useI18n } from '../../stores/i18nStore';

interface AccessLogFilters {
  resourceType: string;
  since: string;
  until: string;
  limit: string;
}

const DEFAULT_FILTERS: AccessLogFilters = {
  resourceType: '',
  since: '',
  until: '',
  limit: '50',
};

function parseDateInputToStartOfDay(value: string): number | undefined {
  const parts = value.split('-').map((part) => Number.parseInt(part, 10));
  if (parts.length !== 3 || parts.some((part) => Number.isNaN(part))) {
    return undefined;
  }
  const [year, month, day] = parts;
  return new Date(year, month - 1, day, 0, 0, 0, 0).getTime() / 1000;
}

function parseDateInputToEndOfDay(value: string): number | undefined {
  const parts = value.split('-').map((part) => Number.parseInt(part, 10));
  if (parts.length !== 3 || parts.some((part) => Number.isNaN(part))) {
    return undefined;
  }
  const [year, month, day] = parts;
  return new Date(year, month - 1, day, 23, 59, 59, 999).getTime() / 1000;
}

function normalizeLimit(value: string): number {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    return 50;
  }
  return Math.min(Math.max(parsed, 1), 200);
}

function buildQuery(filters: AccessLogFilters) {
  return {
    resourceType: filters.resourceType.trim() || undefined,
    since: filters.since ? parseDateInputToStartOfDay(filters.since) : undefined,
    until: filters.until ? parseDateInputToEndOfDay(filters.until) : undefined,
    limit: normalizeLimit(filters.limit),
  };
}

function formatTimestamp(value: number): string {
  return new Date(value * 1000).toLocaleString();
}

export function AccessLogPanel() {
  const { isOwner } = useAccessRole();
  const { fetchAccessLogs } = useAccessLogs();
  const { t } = useI18n();
  const [filters, setFilters] = useState<AccessLogFilters>(DEFAULT_FILTERS);
  const [entries, setEntries] = useState<AccessLogEntrySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadEntries = async (nextFilters: AccessLogFilters = filters) => {
    setLoading(true);
    setError(null);
    try {
      const next = await fetchAccessLogs(buildQuery(nextFilters));
      setEntries(next);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(t('share.accessLog.error', { message }));
    } finally {
      setLoading(false);
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!isOwner) {
      return;
    }
    void loadEntries();
    // Intentionally load once on mount; filters are applied explicitly.
  }, [isOwner]);

  if (!isOwner) {
    return null;
  }

  const handleApplyFilters = () => {
    void loadEntries(filters);
  };

  const handleResetFilters = () => {
    setFilters(DEFAULT_FILTERS);
    void loadEntries(DEFAULT_FILTERS);
  };

  return (
    <section
      aria-labelledby="access-log-title"
      aria-describedby="access-log-description"
      aria-busy={loading}
      className="rounded-xl border border-ds-border bg-ds-surface p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 id="access-log-title" className="text-sm font-semibold text-ds-text">
            {t('share.accessLog.title')}
          </h4>
          <p id="access-log-description" className="mt-1 text-[11px] text-ds-muted">
            {t('share.accessLog.description')}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadEntries(filters)}
          className="inline-flex items-center gap-2 rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50"
        >
          <RefreshCw size={12} />
          {t('share.accessLog.refresh')}
        </button>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-[1.1fr_0.9fr_0.9fr_0.5fr]">
        <label className="space-y-1">
          <span className="text-[11px] font-medium text-ds-text">
            {t('share.accessLog.filters.resourceType')}
          </span>
          <input
            type="text"
            value={filters.resourceType}
            onChange={(event) =>
              setFilters((current) => ({ ...current, resourceType: event.target.value }))
            }
            placeholder={t('share.accessLog.filters.resourceTypePlaceholder')}
            className="w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
          />
        </label>

        <label className="space-y-1">
          <span className="text-[11px] font-medium text-ds-text">
            {t('share.accessLog.filters.since')}
          </span>
          <input
            type="date"
            value={filters.since}
            onChange={(event) => setFilters((current) => ({ ...current, since: event.target.value }))}
            className="w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
          />
        </label>

        <label className="space-y-1">
          <span className="text-[11px] font-medium text-ds-text">
            {t('share.accessLog.filters.until')}
          </span>
          <input
            type="date"
            value={filters.until}
            onChange={(event) => setFilters((current) => ({ ...current, until: event.target.value }))}
            className="w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
          />
        </label>

        <label className="space-y-1">
          <span className="text-[11px] font-medium text-ds-text">
            {t('share.accessLog.filters.limit')}
          </span>
          <input
            type="number"
            min={1}
            max={200}
            value={filters.limit}
            onChange={(event) => setFilters((current) => ({ ...current, limit: event.target.value }))}
            className="w-full rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
          />
        </label>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <div className="text-[11px] text-ds-muted">
          {t('share.accessLog.summary', { count: entries.length })}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleApplyFilters}
            disabled={loading}
            className="rounded-lg bg-ds-accent px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-ds-accent-hover disabled:opacity-40"
          >
            {t('share.accessLog.applyFilters')}
          </button>
          <button
            type="button"
            onClick={handleResetFilters}
            disabled={loading}
            className="rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50 disabled:opacity-40"
          >
            {t('share.accessLog.resetFilters')}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="mt-4 rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-4 text-[11px] text-ds-muted">
          {t('share.accessLog.loading')}
        </div>
      ) : error ? (
        <div className="mt-4 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-[11px] text-red-200">
          {error}
        </div>
      ) : entries.length === 0 ? (
        <div className="mt-4 rounded-lg border border-ds-border/60 bg-ds-bg px-3 py-4 text-[11px] text-ds-muted">
          {t('share.accessLog.empty')}
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto rounded-lg border border-ds-border/60">
          <table className="min-w-[860px] w-full border-collapse text-left text-xs">
            <thead className="bg-ds-bg/70 text-ds-muted">
              <tr>
                <th className="border-b border-ds-border px-3 py-2 font-medium">
                  {t('share.accessLog.columns.timestamp')}
                </th>
                <th className="border-b border-ds-border px-3 py-2 font-medium">
                  {t('share.accessLog.columns.action')}
                </th>
                <th className="border-b border-ds-border px-3 py-2 font-medium">
                  {t('share.accessLog.columns.resource')}
                </th>
                <th className="border-b border-ds-border px-3 py-2 font-medium">
                  {t('share.accessLog.columns.outcome')}
                </th>
                <th className="border-b border-ds-border px-3 py-2 font-medium">
                  {t('share.accessLog.columns.reason')}
                </th>
                <th className="border-b border-ds-border px-3 py-2 font-medium">
                  {t('share.accessLog.columns.actor')}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ds-border">
              {entries.map((entry) => (
                <tr key={entry.entryId} className="bg-ds-surface/60">
                  <td className="px-3 py-2 align-top text-ds-muted">
                    {formatTimestamp(entry.createdAt)}
                  </td>
                  <td className="px-3 py-2 align-top text-ds-text">{entry.action}</td>
                  <td className="px-3 py-2 align-top text-ds-text">
                    <div className="font-mono text-[11px]">{entry.resourceType}</div>
                    <div className="font-mono text-[10px] text-ds-muted">{entry.resourceId}</div>
                  </td>
                  <td className="px-3 py-2 align-top">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                        entry.allowed
                          ? 'bg-ds-success/15 text-ds-success'
                          : 'bg-ds-error/15 text-ds-error'
                      }`}
                    >
                      {entry.allowed
                        ? t('share.accessLog.outcome.allowed')
                        : t('share.accessLog.outcome.denied')}
                    </span>
                  </td>
                  <td className="px-3 py-2 align-top text-ds-muted">
                    {entry.reason ?? '-'}
                  </td>
                  <td className="px-3 py-2 align-top font-mono text-[11px] text-ds-muted">
                    {entry.actorRef}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
