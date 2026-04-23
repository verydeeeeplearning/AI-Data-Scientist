import type { ReactNode } from 'react';

type SlotState = 'default' | 'warning' | 'error' | 'active';

interface Props {
  readonly label: string;
  readonly value: string;
  readonly meta?: string;
  readonly selected: boolean;
  readonly state?: SlotState;
  readonly onClick: () => void;
  readonly ariaLabel?: string;
  readonly controlsId?: string;
  readonly children?: ReactNode;
}

const SLOT_STYLES: Record<SlotState, string> = {
  default: 'border-ds-border bg-ds-bg/70 hover:border-ds-accent/50',
  warning: 'border-amber-500/40 bg-amber-500/10 hover:border-amber-400/60',
  error: 'border-rose-500/40 bg-rose-500/10 hover:border-rose-400/60',
  active: 'border-ds-accent/60 bg-ds-accent/10 shadow-ds-sm',
};

export function MissionSlot({
  label,
  value,
  meta,
  selected,
  state = 'default',
  onClick,
  ariaLabel,
  controlsId,
  children,
}: Props) {
  const resolvedState: SlotState = selected ? 'active' : state;

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      aria-expanded={selected}
      aria-controls={controlsId}
      aria-label={ariaLabel}
      className={`flex min-h-[84px] flex-col rounded-ds-xl border px-ds-3 py-ds-3 text-left transition-colors duration-ds-normal ease-ds-standard focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg ${SLOT_STYLES[resolvedState]}`}
    >
      <span className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">{label}</span>
      <span className="mt-ds-2 line-clamp-2 text-ds-sm font-semibold leading-5 text-ds-text">{value}</span>
      {meta && <span className="mt-1 text-[11px] leading-4 text-ds-muted">{meta}</span>}
      {children}
    </button>
  );
}
