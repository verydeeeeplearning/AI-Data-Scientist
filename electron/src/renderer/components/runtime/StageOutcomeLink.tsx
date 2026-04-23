import { ArrowUpRight } from 'lucide-react';
import {
  resolveStageJumpTarget,
  type StageJumpTarget,
} from '../../application/execution/resolveStageJumpTarget';
import type { Stage } from '../../domain/execution/stage';
import { useI18n } from '../../stores/i18nStore';

interface Props {
  stage: Stage;
  latestResultCardId?: string | null;
  latestAssistantMessageId?: string | null;
  onJump?: (target: StageJumpTarget, stage: Stage) => void;
}

function performScroll(anchorId: string | null): void {
  if (!anchorId || typeof document === 'undefined') {
    return;
  }
  const element = document.getElementById(anchorId);
  if (!element) {
    return;
  }
  element.scrollIntoView({ block: 'start', behavior: 'smooth' });
  // Restore focus visibility on the target if it can hold focus (a11y).
  if ('focus' in element && typeof (element as HTMLElement).focus === 'function') {
    try {
      (element as HTMLElement).focus({ preventScroll: true });
    } catch {
      // Some elements throw when not focusable; safe to ignore.
    }
  }
}

export function StageOutcomeLink({
  stage,
  latestResultCardId,
  latestAssistantMessageId,
  onJump,
}: Props) {
  const t = useI18n((state) => state.t);
  const target = resolveStageJumpTarget(stage, {
    latestResultCardId: latestResultCardId ?? null,
    latestAssistantMessageId: latestAssistantMessageId ?? null,
  });
  const label = t('execution.outcome.jump');
  const ariaLabel = target.available
    ? t('execution.outcome.jump_aria', { label: stage.label })
    : t('execution.outcome.jump_unavailable');

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    if (!target.available) {
      return;
    }
    if (onJump) {
      onJump(target, stage);
      return;
    }
    performScroll(target.anchorId);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={!target.available}
      aria-label={ariaLabel}
      aria-disabled={!target.available}
      data-jump-kind={target.kind}
      data-jump-anchor={target.anchorId ?? ''}
      className={[
        'mt-1 inline-flex items-center gap-1 rounded text-[11px] font-medium',
        'focus:outline-none focus-visible:ring-1 focus-visible:ring-ds-accent',
        target.available
          ? 'text-ds-accent hover:underline'
          : 'cursor-not-allowed text-ds-muted/60',
      ].join(' ')}
    >
      <ArrowUpRight size={11} aria-hidden="true" />
      {label}
    </button>
  );
}
