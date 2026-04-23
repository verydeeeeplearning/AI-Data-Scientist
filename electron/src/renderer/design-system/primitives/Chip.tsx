import type { ButtonHTMLAttributes, ReactElement, ReactNode } from 'react';
import { cn } from './utils';

type ChipTone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger';
type ChipSize = 'sm' | 'md';

export interface ChipProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'size'> {
  readonly tone?: ChipTone;
  readonly size?: ChipSize;
  readonly selected?: boolean;
  readonly leadingIcon?: ReactNode;
  readonly trailingIcon?: ReactNode;
}

const TONE_CLASSES: Record<ChipTone, { readonly base: string; readonly selected: string }> = {
  neutral: {
    base: 'border-ds-border bg-ds-bg text-ds-muted hover:border-ds-accent/40 hover:bg-ds-surface hover:text-ds-text',
    selected: 'border-ds-accent/40 bg-ds-accent/10 text-ds-accent',
  },
  accent: {
    base: 'border-ds-accent/20 bg-ds-accent/5 text-ds-accent hover:border-ds-accent/40 hover:bg-ds-accent/10',
    selected: 'border-transparent bg-ds-accent text-ds-accent-contrast',
  },
  success: {
    base: 'border-ds-success/20 bg-ds-success/5 text-ds-success hover:bg-ds-success/10',
    selected: 'border-ds-success/30 bg-ds-success/15 text-ds-success',
  },
  warning: {
    base: 'border-ds-warning/20 bg-ds-warning/5 text-ds-warning hover:bg-ds-warning/10',
    selected: 'border-ds-warning/30 bg-ds-warning/15 text-ds-warning',
  },
  danger: {
    base: 'border-ds-error/20 bg-ds-error/5 text-ds-error hover:bg-ds-error/10',
    selected: 'border-ds-error/30 bg-ds-error/15 text-ds-error',
  },
};

const SIZE_CLASSES: Record<ChipSize, string> = {
  sm: 'min-h-9 gap-ds-1 px-ds-3 text-ds-xs',
  md: 'min-h-10 gap-ds-2 px-ds-4 text-ds-sm',
};

export function Chip({
  tone = 'neutral',
  size = 'md',
  selected = false,
  leadingIcon,
  trailingIcon,
  className,
  children,
  disabled,
  type = 'button',
  'aria-pressed': ariaPressed,
  ...rest
}: ChipProps): ReactElement {
  return (
    <button
      type={type}
      aria-pressed={ariaPressed ?? selected}
      className={cn(
        'inline-flex items-center justify-center rounded-ds-pill border font-medium shadow-ds-sm transition-all duration-ds-fast ease-ds-standard',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg',
        'disabled:cursor-not-allowed disabled:opacity-50',
        SIZE_CLASSES[size],
        TONE_CLASSES[tone].base,
        selected ? TONE_CLASSES[tone].selected : '',
        className,
      )}
      disabled={disabled}
      {...rest}
    >
      {leadingIcon}
      <span className="truncate">{children}</span>
      {trailingIcon}
    </button>
  );
}
