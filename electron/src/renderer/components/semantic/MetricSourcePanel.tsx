import { BookOpen, Database, Search, ShieldCheck } from 'lucide-react';
import { useDeferredValue, useEffect, useMemo, useState } from 'react';
import { useSemanticSource } from '../../hooks/useSemanticSource';

const SUGGESTED_QUERIES = ['이탈률', 'MAU', 'LTV'] as const;

function toneForGrade(grade: string): string {
  switch (grade) {
    case 'gold':
      return 'border-amber-400/40 bg-amber-400/10 text-amber-200';
    case 'silver':
      return 'border-slate-300/40 bg-slate-300/10 text-slate-100';
    case 'bronze':
      return 'border-orange-400/40 bg-orange-400/10 text-orange-200';
    case 'untrusted':
      return 'border-red-500/40 bg-red-500/10 text-red-200';
    default:
      return 'border-ds-border bg-ds-bg text-ds-muted';
  }
}

function toneForTrustAction(action: string | null): string {
  switch (action) {
    case 'allow':
      return 'border-ds-success/40 bg-ds-success/10 text-ds-success';
    case 'caveat':
      return 'border-amber-400/40 bg-amber-400/10 text-amber-200';
    case 'confirm':
      return 'border-orange-400/40 bg-orange-400/10 text-orange-200';
    case 'block':
      return 'border-ds-error/40 bg-ds-error/10 text-ds-error';
    default:
      return 'border-ds-border bg-ds-bg text-ds-muted';
  }
}

function formatRange(range: [number, number] | null): string | null {
  return range ? `${range[0]} - ${range[1]}` : null;
}

function formatDate(value: string | null): string | null {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString();
}

function InfoChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="rounded-full border border-ds-border bg-ds-bg px-2 py-0.5 text-[10px] text-ds-muted">
      {label}: <span className="text-ds-text">{value}</span>
    </span>
  );
}

export function MetricSourcePanel({
  metricQuery,
}: {
  metricQuery?: string | null;
}) {
  const [queryInput, setQueryInput] = useState(metricQuery ?? '');

  useEffect(() => {
    if (metricQuery && metricQuery !== queryInput) {
      setQueryInput(metricQuery);
    }
  }, [metricQuery, queryInput]);

  const deferredQuery = useDeferredValue(queryInput.trim());
  const source = useSemanticSource(deferredQuery || null);
  const summaryChips = useMemo(() => {
    if (!source.metric) {
      return [];
    }

    const rangeValue = formatRange(source.metric.typicalRange);
    return [
      source.metric.grain ? { label: 'grain', value: source.metric.grain } : null,
      source.metric.unit ? { label: 'unit', value: source.metric.unit } : null,
      source.metric.direction ? { label: 'direction', value: source.metric.direction } : null,
      rangeValue ? { label: 'range', value: rangeValue } : null,
    ].filter((chip): chip is { label: string; value: string } => chip !== null);
  }, [source.metric]);

  return (
    <div className="px-3 py-2 space-y-2" data-testid="metric-source-panel">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
        <Database size={12} />
        Metric Source
      </div>

      <div className="rounded-md border border-ds-border bg-ds-bg/70 p-2 space-y-2">
        <label className="block">
          <span className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wider text-ds-muted">
            <Search size={10} />
            Inspect semantic metric
          </span>
          <input
            value={queryInput}
            onChange={(event) => setQueryInput(event.target.value)}
            placeholder="Hover a metric header or type MAU / 이탈률 / LTV"
            className="w-full rounded border border-ds-border bg-ds-surface px-2 py-1.5 text-[11px] text-ds-text outline-none placeholder:text-ds-muted/70 focus:border-ds-accent"
          />
        </label>

        <div className="flex flex-wrap gap-1">
          {SUGGESTED_QUERIES.map((query) => (
            <button
              key={query}
              type="button"
              onMouseEnter={() => setQueryInput(query)}
              onFocus={() => setQueryInput(query)}
              onClick={() => setQueryInput(query)}
              className="rounded-full border border-ds-border bg-ds-surface px-2 py-0.5 text-[10px] text-ds-muted transition-colors hover:border-ds-accent hover:text-ds-text"
            >
              {query}
            </button>
          ))}
        </div>

        {!deferredQuery ? (
          <div className="text-[11px] text-ds-muted">
            Hover a metric header or one of the KPI probes above to inspect owner, definition,
            verified query, and trust context.
          </div>
        ) : source.loading ? (
          <div className="text-[11px] text-ds-muted">
            Loading semantic source for <span className="text-ds-text">{deferredQuery}</span>...
          </div>
        ) : source.error ? (
          <div className="text-[11px] text-ds-error">{source.error}</div>
        ) : source.notFound || !source.metric ? (
          <div className="text-[11px] text-ds-muted">
            No semantic grounding found for <span className="text-ds-text">{deferredQuery}</span>.
          </div>
        ) : (
          <div className="space-y-2">
            <div className="rounded border border-ds-border/70 bg-ds-surface/70 px-2 py-2 space-y-1">
              <div className="flex items-start gap-2">
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] font-medium text-ds-text">
                    {source.metric.displayName}
                  </div>
                  <div className="text-[10px] font-mono text-ds-muted">
                    {source.metric.metricId}
                  </div>
                </div>
                <span className="rounded-full border border-ds-border bg-ds-bg px-2 py-0.5 text-[10px] text-ds-muted">
                  owner <span className="text-ds-text">{source.metric.owner}</span>
                </span>
              </div>

              <div className="text-[11px] text-ds-text">{source.metric.definition}</div>

              {summaryChips.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {summaryChips.map((chip) => (
                    <InfoChip key={chip.label} label={chip.label} value={chip.value} />
                  ))}
                </div>
              ) : null}

              {source.metric.caveats.length > 0 ? (
                <div className="text-[10px] text-amber-200">
                  Caveat: {source.metric.caveats[0]}
                </div>
              ) : null}
            </div>

            <div className="rounded border border-ds-border/70 bg-ds-surface/70 px-2 py-2 space-y-1">
              <div className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-ds-muted">
                <BookOpen size={10} />
                Verified Query
              </div>
              {source.verifiedQuery ? (
                <>
                  <div className="flex flex-wrap items-center gap-1">
                    <span className="rounded-full border border-ds-border bg-ds-bg px-2 py-0.5 text-[10px] text-ds-text">
                      {source.verifiedQuery.vqId}
                    </span>
                    <span className="rounded-full border border-ds-border bg-ds-bg px-2 py-0.5 text-[10px] text-ds-muted">
                      {source.verifiedQuery.dialect}
                    </span>
                  </div>
                  <div className="text-[11px] text-ds-text">{source.verifiedQuery.description}</div>
                  <div className="text-[10px] text-ds-muted">
                    verified by {source.verifiedQuery.verifiedBy}
                    {formatDate(source.verifiedQuery.lastVerified)
                      ? ` / ${formatDate(source.verifiedQuery.lastVerified)}`
                      : ''}
                  </div>
                </>
              ) : (
                <div className="text-[11px] text-ds-muted">
                  No postgres verified query is registered for this metric yet.
                </div>
              )}
            </div>

            {source.trustAction || source.trustTables.length > 0 ? (
              <div className="rounded border border-ds-border/70 bg-ds-surface/70 px-2 py-2 space-y-1">
                <div className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-ds-muted">
                  <ShieldCheck size={10} />
                  Trust Context
                  {source.trustAction ? (
                    <span
                      className={`ml-auto rounded-full border px-2 py-0.5 text-[10px] ${toneForTrustAction(
                        source.trustAction
                      )}`}
                    >
                      {source.trustAction}
                    </span>
                  ) : null}
                </div>

                {source.trustTables.map((table) => (
                  <div
                    key={table.fqtn}
                    className="rounded border border-ds-border/60 bg-ds-bg/60 px-2 py-1.5 text-[10px]"
                  >
                    <div className="flex items-center gap-1">
                      <span className="min-w-0 flex-1 truncate font-mono text-ds-text" title={table.fqtn}>
                        {table.fqtn}
                      </span>
                      <span
                        className={`rounded-full border px-2 py-0.5 ${toneForGrade(table.grade)}`}
                      >
                        {table.grade}
                      </span>
                    </div>
                    <div className="text-ds-muted">
                      {table.owner} · {table.description}
                    </div>
                  </div>
                ))}

                {source.trustWarnings.length > 0 ? (
                  <div className="text-[10px] text-amber-200">{source.trustWarnings[0]}</div>
                ) : null}
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
