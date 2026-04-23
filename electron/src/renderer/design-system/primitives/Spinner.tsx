import type { HTMLAttributes, ReactElement } from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from './utils';

type SpinnerSize = 'sm' | 'md' | 'lg';
type SpinnerTone = 'accent' | 'muted' | 'success' | 'warning' | 'danger';

export interface SpinnerProps extends HTMLAttributes<HTMLSpanElement> {
  readonly size?: SpinnerSize;
  readonly tone?: SpinnerTone;
  readonly label?: string;
}

const SIZE_MAP: Record<SpinnerSize, number> = {
  sm: 14,
  md: 18,
  lg: 22,
};

const TONE_CLASSES: Record<SpinnerTone, string> = {
  accent: 'text-ds-accent',
  muted: 'text-ds-muted',
  success: 'text-ds-success',
  warning: 'text-ds-warning',
  danger: 'text-ds-error',
};

export function Spinner({
  size = 'md',
  tone = 'accent',
  label,
  className,
  ...rest
}: SpinnerProps): ReactElement {
  return (
    <span
      className={cn('inline-flex items-center gap-ds-2', className)}
      role={label ? 'status' : undefined}
      aria-live={label ? 'polite' : undefined}
      aria-hidden={label ? undefined : true}
      {...rest}
    >
      <Loader2 size={SIZE_MAP[size]} className={cn('animate-spin', TONE_CLASSES[tone])} aria-hidden="true" />
      {label ? <span className="text-ds-sm text-ds-muted">{label}</span> : null}
    </span>
  );
}
