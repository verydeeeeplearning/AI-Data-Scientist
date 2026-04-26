import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleDot,
  Clock3,
  Loader2,
  XCircle,
} from 'lucide-react';
import type { KeyboardEvent } from 'react';
import { prefersReducedMotion } from '../../application/a11y/reducedMotion';
import { localizeOutcomeSummary } from '../../application/runtime/localizeOutcomeSummary';
import type { Stage, StageStatus } from '../../domain/execution/stage';
import { useI18n } from '../../stores/i18nStore';
import { RawToolLog } from './RawToolLog';
import { ReasoningTracePanel } from './ReasoningTracePanel';
import { StageOutcomeLink } from './StageOutcomeLink';

interface Props {
  stage: Stage;
  expanded: boolean;
  onToggle: () => void;
  latestResultCardId?: string | null;
  latestAssistantMessageId?: string | null;
}

function statusIcon(status: StageStatus, reduceMotion: boolean) {
  if (status === 'running') {
    return (
      <Loader2
        size={12}
        className={reduceMotion ? 'text-ds-accent' : 'animate-spin text-ds-accent'}
        aria-hidden="true"
      />
    );
  }
  if (status === 'completed') {
    return <CheckCircle2 size={12} className="text-ds-success" aria-hidden="true" />;
  }
  if (status === 'failed') {
    return <XCircle size={12} className="text-ds-error" aria-hidden="true" />;
  }
  if (status === 'pending') {
    return <Clock3 size={12} className="text-ds-muted" aria-hidden="true" />;
  }
  return <CircleDot size={12} className="text-ds-muted" aria-hidden="true" />;
}

function statusClasses(status: StageStatus): string {
  if (status === 'failed') {
    return 'border-ds-error/30 bg-ds-error/10';
  }
  if (status === 'running') {
    return 'border-ds-accent/30 bg-ds-accent/10';
  }
  if (status === 'completed') {
    return 'border-ds-success/30 bg-ds-success/10';
  }
  return 'border-ds-border bg-ds-bg/60';
}

export function StageRow({
  stage,
  expanded,
  onToggle,
  latestResultCardId,
  latestAssistantMessageId,
}: Props) {
  const t = useI18n((state) => state.t);
  const reduceMotion = prefersReducedMotion();
  const stageLabel = t(`execution.stage.${stage.key}`) || stage.label;
  const statusLabel = t(`execution.status.${stage.status}`) || stage.status;
  const toggleLabel = expanded ? t('execution.row.collapse') : t('execution.row.expand');
  const outcomeSummary = stage.outcome?.summary
    ? localizeOutcomeSummary(t, stage.outcome.summary)
    : null;

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onToggle();
    }
  };

  return (
    <div className={`rounded-md border p-2 ${statusClasses(stage.status)}`}>
      <button
        type="button"
        onClick={onToggle}
        onKeyDown={handleKeyDown}
        aria-expanded={expanded}
        aria-label={`${stageLabel}: ${statusLabel}. ${toggleLabel}`}
        className="flex w-full items-start gap-2 text-left focus:outline-none focus-visible:ring-1 focus-visible:ring-ds-accent rounded"
      >
        <span className="mt-0.5 text-ds-muted" aria-hidden="true">
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
        <span className="mt-0.5">{statusIcon(stage.status, reduceMotion)}</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-ds-text">{stageLabel}</span>
            <span className="text-[10px] uppercase tracking-wider text-ds-muted">
              {statusLabel}
            </span>
          </div>
          {outcomeSummary && (
            <div className="mt-1 text-[11px] text-ds-muted">{outcomeSummary}</div>
          )}
          {(stage.status === 'completed' || stage.status === 'failed') && (
            <StageOutcomeLink
              stage={stage}
              latestResultCardId={latestResultCardId ?? null}
              latestAssistantMessageId={latestAssistantMessageId ?? null}
            />
          )}
        </div>
      </button>

      {expanded && (
        <>
          <ReasoningTracePanel stageKey={stage.key} />
          <RawToolLog toolEvents={stage.toolEvents} />
        </>
      )}
    </div>
  );
}
