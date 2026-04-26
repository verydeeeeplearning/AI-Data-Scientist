/**
 * Runtime runs panel with abort control for active runs.
 */

import { CircleStop, ListTree } from 'lucide-react';
import { useState } from 'react';
import { useWs } from '../../hooks/WsProvider';
import { useI18n } from '../../stores/i18nStore';
import { useRuntimeStore, type RuntimeRunEntry } from '../../stores/runtimeStore';
import { translateRuntimeRunStatus } from './runtimeI18n';

const STATUS_STYLES: Record<RuntimeRunEntry['status'], string> = {
  running: 'text-ds-accent',
  succeeded: 'text-ds-success',
  failed: 'text-ds-error',
  cancelled: 'text-ds-muted',
};

export function RunsPanel() {
  const { t } = useI18n();
  const runs = useRuntimeStore((s) => s.runs);
  const selectedRunId = useRuntimeStore((s) => s.selectedRunId);
  const selectRun = useRuntimeStore((s) => s.selectRun);

  return (
    <div className="px-3 py-2">
      <div className="flex items-center gap-2 text-[10px] font-semibold text-ds-muted uppercase tracking-wider mb-2">
        <ListTree size={12} />
        {t('run.runtime.runs.title')}
        <span className="ml-auto text-ds-text normal-case text-xs">{runs.length}</span>
      </div>

      {runs.length === 0 ? (
        <div className="text-xs text-ds-muted">{t('run.runtime.runs.empty')}</div>
      ) : (
        <div className="space-y-2">
          {runs.map((run) => (
            <RunCard
              key={run.runId}
              t={t}
              run={run}
              selected={selectedRunId === run.runId}
              onInspect={() => selectRun(run.runId)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function RunCard({
  t,
  run,
  selected,
  onInspect,
}: {
  t: (key: string, vars?: Record<string, string | number | undefined | null>) => string;
  run: RuntimeRunEntry;
  selected: boolean;
  onInspect: () => void;
}) {
  const { rpc } = useWs();
  const [busy, setBusy] = useState(false);
  const [abortError, setAbortError] = useState<string | null>(null);
  const sessionLabel = run.sessionLabel || run.sessionId;

  const abortRun = async () => {
    setBusy(true);
    setAbortError(null);
    try {
      await rpc('run.abort', { runId: run.runId });
    } catch (err) {
      console.warn('[RunsPanel] run.abort failed:', err);
      const detail = err instanceof Error ? err.message : String(err);
      setAbortError(t('run.runtime.runs.error.abortFailed', { message: detail }));
    } finally {
      setBusy(false);
    }
  };

  const subtitle = run.resultPreview || run.error || run.message;

  return (
    <div
      className={`rounded-md border p-2 space-y-1.5 ${
        selected ? 'border-ds-accent bg-ds-bg/90' : 'border-ds-border bg-ds-bg/70'
      }`}
    >
      <div className="flex items-center gap-2">
        <div className="text-xs font-mono text-ds-text truncate">{run.runId}</div>
        <span className={`ml-auto text-[10px] uppercase ${STATUS_STYLES[run.status]}`}>
          {translateRuntimeRunStatus(run.status, t)}
        </span>
      </div>
      <div className="space-y-0.5 text-[10px] text-ds-muted">
        <div>{run.surface} / {sessionLabel}</div>
        {run.threadLabel && <div className="uppercase">{run.threadLabel}</div>}
      </div>
      <div className="text-xs text-ds-text line-clamp-2">{subtitle}</div>
      <div className="flex items-center justify-between text-[10px] text-ds-muted">
        <span className="font-mono">${run.costUsd.toFixed(4)}</span>
        <div className="flex items-center gap-2">
          <button
            onClick={onInspect}
            className="inline-flex items-center gap-1 rounded border border-ds-border px-2 py-1 hover:text-ds-text"
          >
            {t('run.runtime.runs.action.inspect')}
          </button>
          {run.status === 'running' ? (
            <button
              onClick={() => void abortRun()}
              disabled={busy}
              className="inline-flex items-center gap-1 rounded border border-ds-border px-2 py-1 hover:border-ds-error hover:text-ds-error disabled:opacity-50"
            >
              <CircleStop size={10} />
              {t('run.runtime.runs.action.abort')}
            </button>
          ) : (
            <span>{new Date(run.createdAt * 1000).toLocaleTimeString()}</span>
          )}
        </div>
      </div>
      {abortError ? (
        <p
          role="alert"
          className="text-ds-xs text-ds-error"
          data-testid={`runs-panel-abort-error-${run.runId}`}
        >
          {abortError}
        </p>
      ) : null}
    </div>
  );
}
