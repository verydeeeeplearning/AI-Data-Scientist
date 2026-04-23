import type { HTMLAttributes, ReactElement } from 'react';
import { cn } from './utils';

type CardTone = 'default' | 'elevated' | 'accent' | 'danger';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  readonly tone?: CardTone;
}

const TONE_CLASSES: Record<CardTone, string> = {
  default: 'border-ds-border bg-ds-surface/92',
  elevated: 'border-ds-border bg-ds-surface-elevated/96 shadow-ds-md',
  accent: 'border-ds-accent/30 bg-ds-accent/5',
  danger: 'border-ds-error/30 bg-ds-error/10',
};

export function Card({
  tone = 'default',
  className,
  children,
  ...rest
}: CardProps): ReactElement {
  return (
    <div
      className={cn(
        'rounded-ds-xl border p-ds-4 text-ds-text shadow-ds-sm',
        TONE_CLASSES[tone],
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

