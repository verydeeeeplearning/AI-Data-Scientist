import { CheckCircle2, Loader2, XCircle } from 'lucide-react';
import { prefersReducedMotion } from '../../application/a11y/reducedMotion';
import type { ExecutionToolEvent } from '../../domain/execution/stage';
import { useI18n } from '../../stores/i18nStore';

interface Props {
  toolEvents: readonly ExecutionToolEvent[];
}

function formatDuration(elapsedMs?: number): string | null {
  if (elapsedMs === undefined) {
    return null;
  }
  return `${(elapsedMs / 1000).toFixed(1)}s`;
}

export function RawToolLog({ toolEvents }: Props) {
  const t = useI18n((state) => state.t);
  const reduceMotion = prefersReducedMotion();

  if (toolEvents.length === 0) {
    return (
      <div className="mt-2 rounded-md border border-ds-border bg-ds-bg/60 p-2 text-[11px] text-ds-muted">
        {t('execution.raw_log.empty')}
      </div>
    );
  }

  return (
    <ul
      className="mt-2 space-y-1 rounded-md border border-ds-border bg-ds-bg/60 p-2 list-none"
      aria-label={t('execution.raw_log.toggle')}
    >
      {toolEvents.map((toolEvent, index) => (
        <li
          key={`${toolEvent.toolName}-${toolEvent.startedAt ?? index}`}
          className="flex items-start gap-2 text-[11px]"
        >
          {toolEvent.status === 'running' && (
            <Loader2
              size={12}
              className={
                reduceMotion
                  ? 'mt-0.5 flex-shrink-0 text-ds-accent'
                  : 'mt-0.5 flex-shrink-0 animate-spin text-ds-accent'
              }
              aria-hidden="true"
            />
          )}
          {toolEvent.status === 'completed' && (
            <CheckCircle2 size={12} className="mt-0.5 flex-shrink-0 text-ds-success" aria-hidden="true" />
          )}
          {toolEvent.status === 'failed' && (
            <XCircle size={12} className="mt-0.5 flex-shrink-0 text-ds-error" aria-hidden="true" />
          )}

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="font-mono text-ds-text">{toolEvent.toolName}</span>
              {formatDuration(toolEvent.elapsedMs) && (
                <span className="text-ds-muted">{formatDuration(toolEvent.elapsedMs)}</span>
              )}
            </div>
            {toolEvent.outputPreview && (
              <div className="mt-1 line-clamp-2 text-ds-muted">{toolEvent.outputPreview}</div>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
